#
# Copyright (C) 2018  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Vendula Poncova <vponcova@redhat.com>
#
import os
import tempfile
import unittest
from textwrap import dedent

from unittest.mock import patch

from tests.unit_tests.pyanaconda_tests import patch_dbus_publish_object, check_kickstart_interface, \
    PropertiesChangedCallback

from pyanaconda.core.constants import SETUP_ON_BOOT_DISABLED, \
    SETUP_ON_BOOT_RECONFIG, SETUP_ON_BOOT_ENABLED, SETUP_ON_BOOT_DEFAULT, \
    TEXT_ONLY_TARGET, GRAPHICAL_TARGET
from pyanaconda.modules.common.constants.services import SERVICES
from pyanaconda.modules.services.installation import ConfigurePostInstallationToolsTask
from pyanaconda.modules.common.task import TaskInterface
from pyanaconda.modules.services.services import ServicesService
from pyanaconda.modules.services.services_interface import ServicesInterface
from pyanaconda.modules.services.constants import SetupOnBootAction
from pyanaconda.modules.services.installation import ConfigureInitialSetupTask, \
    ConfigureServicesTask, ConfigureSystemdDefaultTargetTask, ConfigureDefaultDesktopTask


class ServicesInterfaceTestCase(unittest.TestCase):
    """Test DBus interface for the services module."""

    def setUp(self):
        """Set up the services module."""
        # Set up the services module.
        self.services_module = ServicesService()
        self.services_interface = ServicesInterface(self.services_module)

        # Connect to the properties changed signal.
        self.callback = PropertiesChangedCallback()
        self.services_interface.PropertiesChanged.connect(self.callback)

    def test_kickstart_properties(self):
        """Test kickstart properties."""
        assert self.services_interface.KickstartCommands == ["firstboot", "services", "skipx", "xconfig"]
        assert self.services_interface.KickstartSections == []
        assert self.services_interface.KickstartAddons == []
        self.callback.assert_not_called()

    def test_enabled_services_property(self):
        """Test the enabled services property."""
        self.services_interface.SetEnabledServices(["a", "b", "c"])
        assert self.services_interface.EnabledServices == ["a", "b", "c"]
        self.callback.assert_called_once_with(
            SERVICES.interface_name, {'EnabledServices': ["a", "b", "c"]}, []
        )

    def test_disabled_services_property(self):
        """Test the disabled services property."""
        self.services_interface.SetDisabledServices(["a", "b", "c"])
        assert self.services_interface.DisabledServices == ["a", "b", "c"]
        self.callback.assert_called_once_with(
            SERVICES.interface_name, {'DisabledServices': ["a", "b", "c"]}, []
        )

    def test_default_target_property_default_graphical(self):
        """Test the default target property - default value."""
        self.callback.assert_not_called()
        assert self.services_interface.DefaultTarget == ""

    def test_default_target_property_graphical(self):
        """Test the default target property - set graphical target."""
        self.services_interface.SetDefaultTarget(GRAPHICAL_TARGET)
        assert self.services_interface.DefaultTarget == GRAPHICAL_TARGET
        self.callback.assert_called_once_with(
            SERVICES.interface_name, {'DefaultTarget': GRAPHICAL_TARGET}, []
        )

    def test_default_target_property_text(self):
        """Test the default target property - set text target."""
        self.services_interface.SetDefaultTarget(TEXT_ONLY_TARGET)
        assert self.services_interface.DefaultTarget == TEXT_ONLY_TARGET
        self.callback.assert_called_once_with(
            SERVICES.interface_name, {'DefaultTarget': TEXT_ONLY_TARGET}, []
        )

    def test_default_desktop_property(self):
        """Test the default desktop property."""
        self.services_interface.SetDefaultDesktop("KDE")
        assert self.services_interface.DefaultDesktop == "KDE"
        self.callback.assert_called_once_with(
            SERVICES.interface_name, {'DefaultDesktop': "KDE"}, []
        )

    def test_setup_on_boot_property(self):
        """Test the setup on boot property."""
        self.services_interface.SetSetupOnBoot(SETUP_ON_BOOT_DISABLED)
        assert self.services_interface.SetupOnBoot == SETUP_ON_BOOT_DISABLED
        self.callback.assert_called_once_with(
            SERVICES.interface_name, {'SetupOnBoot': SETUP_ON_BOOT_DISABLED}, []
        )

    def test_post_install_tools_disabled(self):
        """Test the post-install-tools-enabled property."""
        # should not be marked as disabled by default
        assert self.services_interface.PostInstallToolsEnabled is True
        # mark as disabled
        self.services_interface.SetPostInstallToolsEnabled(False)
        assert self.services_interface.PostInstallToolsEnabled is False
        self.callback.assert_called_once_with(
            SERVICES.interface_name, {'PostInstallToolsEnabled': False}, []
        )
        # mark as not disabled again
        self.services_interface.SetPostInstallToolsEnabled(True)
        assert self.services_interface.PostInstallToolsEnabled is True
        self.callback.assert_called_with(
            SERVICES.interface_name, {'PostInstallToolsEnabled': True}, []
        )

    def _test_kickstart(self, ks_in, ks_out):
        check_kickstart_interface(self.services_interface, ks_in, ks_out)

    def test_no_kickstart(self):
        """Test with no kickstart."""
        ks_in = None
        ks_out = ""
        self._test_kickstart(ks_in, ks_out)
        assert self.services_interface.SetupOnBoot == SETUP_ON_BOOT_DEFAULT
        assert self.services_interface.PostInstallToolsEnabled is True

    def test_kickstart_empty(self):
        """Test with empty string."""
        ks_in = ""
        ks_out = ""
        self._test_kickstart(ks_in, ks_out)
        assert self.services_interface.SetupOnBoot == SETUP_ON_BOOT_DEFAULT
        assert self.services_interface.PostInstallToolsEnabled is True

    def test_services_kickstart(self):
        """Test the services command."""
        ks_in = """
        services --disabled=a,b,c --enabled=d,e,f
        """
        ks_out = """
        # System services
        services --disabled="a,b,c" --enabled="d,e,f"
        """
        self._test_kickstart(ks_in, ks_out)

    def test_skipx_kickstart(self):
        """Test the skipx command."""
        ks_in = """
        skipx
        """
        ks_out = """
        # Do not configure the X Window System
        skipx
        """
        self._test_kickstart(ks_in, ks_out)

    def test_xconfig_kickstart(self):
        """Test the xconfig command."""
        ks_in = """
        xconfig --defaultdesktop GNOME --startxonboot
        """
        ks_out = """
        # X Window System configuration information
        xconfig  --defaultdesktop=GNOME --startxonboot
        """
        self._test_kickstart(ks_in, ks_out)

    def test_firstboot_disabled_kickstart(self):
        """Test the firstboot command - disabled."""
        ks_in = """
        firstboot --disable
        """
        ks_out = """
        firstboot --disable
        """
        self._test_kickstart(ks_in, ks_out)
        assert self.services_interface.SetupOnBoot == SETUP_ON_BOOT_DISABLED
        assert self.services_interface.PostInstallToolsEnabled is False

    def test_firstboot_enabled_kickstart(self):
        """Test the firstboot command - enabled."""
        ks_in = """
        firstboot --enable
        """
        ks_out = """
        # Run the Setup Agent on first boot
        firstboot --enable
        """
        self._test_kickstart(ks_in, ks_out)
        assert self.services_interface.SetupOnBoot == SETUP_ON_BOOT_ENABLED
        assert self.services_interface.PostInstallToolsEnabled is True

    def test_firstboot_reconfig_kickstart(self):
        """Test the firstboot command - reconfig."""
        ks_in = """
        firstboot --reconfig
        """
        ks_out = """
        # Run the Setup Agent on first boot
        firstboot --reconfig
        """
        self._test_kickstart(ks_in, ks_out)
        assert self.services_interface.SetupOnBoot == SETUP_ON_BOOT_RECONFIG
        assert self.services_interface.PostInstallToolsEnabled is True


class ServicesTasksTestCase(unittest.TestCase):
    """Test the services tasks."""

    def setUp(self):
        """Set up the services module."""
        # Set up the services module.
        self.services_module = ServicesService()
        self.services_interface = ServicesInterface(self.services_module)

        # Connect to the properties changed signal.
        self.callback = PropertiesChangedCallback()
        self.services_interface.PropertiesChanged.connect(self.callback)

    @patch('pyanaconda.modules.services.installation.get_anaconda_version_string')
    def test_enable_post_install_tools(self, version_getter):
        version_getter.return_value = "1.0"

        content = dedent("""
        # This file has been generated by the Anaconda Installer 1.0

        [General]
        post_install_tools_disabled = 0
        """)

        with tempfile.TemporaryDirectory() as sysroot:
            os.makedirs(os.path.join(sysroot, "etc/sysconfig"))

            ConfigurePostInstallationToolsTask(
                sysroot=sysroot,
                tools_enabled=True
            ).run()

            with open(os.path.join(sysroot, "etc/sysconfig/anaconda")) as f:
                assert f.read().strip() == content.strip()

    @patch('pyanaconda.modules.services.installation.get_anaconda_version_string')
    def test_disable_post_install_tools(self, version_getter):
        version_getter.return_value = "1.0"

        content = dedent("""
        # This file has been generated by the Anaconda Installer 1.0

        [General]
        post_install_tools_disabled = 1
        """)

        print(content)

        with tempfile.TemporaryDirectory() as sysroot:
            os.makedirs(os.path.join(sysroot, "etc/sysconfig"))

            ConfigurePostInstallationToolsTask(
                sysroot=sysroot,
                tools_enabled=False
            ).run()

            with open(os.path.join(sysroot, "etc/sysconfig/anaconda")) as f:
                assert f.read().strip() == content.strip()

    @patch('pyanaconda.modules.services.installation.conf')
    def test_skip_post_install_tools(self, conf):
        with tempfile.TemporaryDirectory() as sysroot:
            os.makedirs(os.path.join(sysroot, "etc/sysconfig"))

            task = ConfigurePostInstallationToolsTask(
                sysroot=sysroot,
                tools_enabled=True
            )

            conf.target.is_directory = False
            conf.target.is_image = True
            task.run()

            assert not os.path.isfile(os.path.join(sysroot, "etc/sysconfig/anaconda"))

            conf.target.is_directory = True
            conf.target.is_image = False
            task.run()

            assert not os.path.isfile(os.path.join(sysroot, "etc/sysconfig/anaconda"))


    @patch_dbus_publish_object
    def test_install_with_tasks_default(self, publisher):
        """Test default install tasks behavior."""
        tasks = self.services_interface.InstallWithTasks()
        is_task_path = tasks[0]
        post_install_tools_task = tasks[1]
        services_task_path = tasks[2]
        target_task_path = tasks[3]
        desktop_task_path = tasks[4]

        publisher.assert_called()

        # Initial Setup configuration
        object_path = publisher.call_args_list[0][0][0]
        obj = publisher.call_args_list[0][0][1]

        assert is_task_path == object_path
        assert isinstance(obj, TaskInterface)
        assert isinstance(obj.implementation, ConfigureInitialSetupTask)
        assert obj.implementation._setup_on_boot == SetupOnBootAction.DEFAULT

        # post install tools configuration
        object_path = publisher.call_args_list[1][0][0]
        obj = publisher.call_args_list[1][0][1]

        assert post_install_tools_task == object_path
        assert isinstance(obj, TaskInterface)
        assert isinstance(obj.implementation, ConfigurePostInstallationToolsTask)
        assert obj.implementation._tools_enabled is True

        # Services configuration
        object_path = publisher.call_args_list[2][0][0]
        obj = publisher.call_args_list[2][0][1]

        assert services_task_path == object_path
        assert isinstance(obj, TaskInterface)
        assert isinstance(obj.implementation, ConfigureServicesTask)
        assert obj.implementation._enabled_services == []
        assert obj.implementation._disabled_services == []

        # Default systemd target configuration
        object_path = publisher.call_args_list[3][0][0]
        obj = publisher.call_args_list[3][0][1]

        assert target_task_path == object_path
        assert isinstance(obj, TaskInterface)
        assert isinstance(obj.implementation, ConfigureSystemdDefaultTargetTask)
        assert obj.implementation._default_target == ""

        # Default desktop configuration
        object_path = publisher.call_args_list[4][0][0]
        obj = publisher.call_args_list[4][0][1]

        assert desktop_task_path == object_path
        assert isinstance(obj, TaskInterface)
        assert isinstance(obj.implementation, ConfigureDefaultDesktopTask)
        assert obj.implementation._default_desktop == ""

    @patch_dbus_publish_object
    def test_initial_setup_config_task_enable(self, publisher):
        """Test the Initial Setup conifg task - enable."""
        self.services_interface.SetSetupOnBoot(SETUP_ON_BOOT_ENABLED)
        tasks = self.services_interface.InstallWithTasks()
        is_task_path = tasks[0]

        publisher.assert_called()

        # Initial Setup configuration
        object_path = publisher.call_args_list[0][0][0]
        obj = publisher.call_args_list[0][0][1]

        assert is_task_path == object_path
        assert isinstance(obj, TaskInterface)
        assert isinstance(obj.implementation, ConfigureInitialSetupTask)
        assert obj.implementation._setup_on_boot == SetupOnBootAction.ENABLED

    @patch_dbus_publish_object
    def test_initial_setup_config_task_disable(self, publisher):
        """Test the Initial Setup config task - disable."""
        self.services_interface.SetSetupOnBoot(SETUP_ON_BOOT_DISABLED)
        tasks = self.services_interface.InstallWithTasks()
        is_task_path = tasks[0]

        publisher.assert_called()

        # Initial Setup configuration
        object_path = publisher.call_args_list[0][0][0]
        obj = publisher.call_args_list[0][0][1]

        assert is_task_path == object_path
        assert isinstance(obj, TaskInterface)
        assert isinstance(obj.implementation, ConfigureInitialSetupTask)
        assert obj.implementation._setup_on_boot == SetupOnBootAction.DISABLED

    @patch_dbus_publish_object
    def test_initial_setup_config_task_reconfig(self, publisher):
        """Test the Initial Setup config task - reconfig."""
        self.services_interface.SetSetupOnBoot(SETUP_ON_BOOT_RECONFIG)
        tasks = self.services_interface.InstallWithTasks()
        is_task_path = tasks[0]

        publisher.assert_called()

        # Initial Setup configuration
        object_path = publisher.call_args_list[0][0][0]
        obj = publisher.call_args_list[0][0][1]

        assert is_task_path == object_path
        assert isinstance(obj, TaskInterface)
        assert isinstance(obj.implementation, ConfigureInitialSetupTask)
        assert obj.implementation._setup_on_boot == SetupOnBootAction.RECONFIG

    @patch_dbus_publish_object
    def test_configure_services_task(self, publisher):
        """Test the services configuration task."""
        self.services_interface.SetEnabledServices(["a", "b", "c"])
        self.services_interface.SetDisabledServices(["c", "e", "f"])
        tasks = self.services_interface.InstallWithTasks()
        services_task_path = tasks[2]

        publisher.assert_called()

        # Services configuration
        object_path = publisher.call_args_list[2][0][0]
        obj = publisher.call_args_list[2][0][1]

        assert services_task_path == object_path
        assert isinstance(obj, TaskInterface)
        assert isinstance(obj.implementation, ConfigureServicesTask)
        assert obj.implementation._enabled_services == ["a", "b", "c"]
        assert obj.implementation._disabled_services == ["c", "e", "f"]

    @patch_dbus_publish_object
    def test_configure_systemd_target_task_text(self, publisher):
        """Test the systemd default traget configuration task - text."""
        self.services_interface.SetDefaultTarget(TEXT_ONLY_TARGET)
        tasks = self.services_interface.InstallWithTasks()
        target_task_path = tasks[3]

        publisher.assert_called()

        # Default systemd target configuration
        object_path = publisher.call_args_list[3][0][0]
        obj = publisher.call_args_list[3][0][1]

        assert target_task_path == object_path
        assert isinstance(obj, TaskInterface)
        assert isinstance(obj.implementation, ConfigureSystemdDefaultTargetTask)
        assert obj.implementation._default_target == TEXT_ONLY_TARGET

    @patch_dbus_publish_object
    def test_configure_systemd_target_task_graphical(self, publisher):
        """Test the systemd default traget configuration task - graphical."""
        self.services_interface.SetDefaultTarget(GRAPHICAL_TARGET)
        tasks = self.services_interface.InstallWithTasks()
        target_task_path = tasks[3]

        publisher.assert_called()

        # Default systemd target configuration
        object_path = publisher.call_args_list[3][0][0]
        obj = publisher.call_args_list[3][0][1]

        assert target_task_path == object_path
        assert isinstance(obj, TaskInterface)
        assert isinstance(obj.implementation, ConfigureSystemdDefaultTargetTask)
        assert obj.implementation._default_target == GRAPHICAL_TARGET

    @patch_dbus_publish_object
    def test_configure_default_desktop_task(self, publisher):
        """Test the default desktop configuration task."""
        self.services_interface.SetDefaultDesktop("GNOME")
        tasks = self.services_interface.InstallWithTasks()
        desktop_task_path = tasks[4]

        publisher.assert_called()

        # Default desktop configuration
        object_path = publisher.call_args_list[4][0][0]
        obj = publisher.call_args_list[4][0][1]

        assert desktop_task_path == object_path
        assert isinstance(obj, TaskInterface)
        assert isinstance(obj.implementation, ConfigureDefaultDesktopTask)
        assert obj.implementation._default_desktop == "GNOME"
