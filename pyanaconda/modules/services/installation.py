#
# Copyright (C) 2019 Red Hat, Inc.
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
import os
from configparser import ConfigParser

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import GRAPHICAL_TARGET, TEXT_ONLY_TARGET
from pyanaconda.core.path import touch
from pyanaconda.core.service import (
    disable_service,
    enable_service,
    is_service_installed,
)
from pyanaconda.core.util import get_anaconda_version_string
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.services.constants import SetupOnBootAction

log = get_module_logger(__name__)

__all__ = [
    "ConfigureDefaultDesktopTask",
    "ConfigureInitialSetupTask",
    "ConfigureServicesTask",
    "ConfigureSystemdDefaultTargetTask",
]


class ConfigureInitialSetupTask(Task):
    """Installation task for Initial Setup configuration."""

    INITIAL_SETUP_UNIT_NAME = "initial-setup.service"

    def __init__(self, sysroot, setup_on_boot):
        """Create a new Initial Setup configuration task.

        :param str sysroot: a path to the root of the target system
        :param Enum setup_on_boot: setup-on-boot mode for Initial Setup

        Modes are defined by the SetupOnBoot enum as distinct integers.

        """
        super().__init__()
        self._sysroot = sysroot
        self._setup_on_boot = setup_on_boot

    @property
    def name(self):
        return "Configure Initial Setup"

    def _enable_service(self):
        """Enable the Initial Setup service."""
        if is_service_installed(self.INITIAL_SETUP_UNIT_NAME, root=self._sysroot):
            enable_service(self.INITIAL_SETUP_UNIT_NAME, root=self._sysroot)
        else:
            log.debug("Initial Setup will not be started on first boot, because "
                      "its unit file (%s) is not installed.", self.INITIAL_SETUP_UNIT_NAME)

    def _disable_service(self):
        """Disable the Initial Setup service."""
        if is_service_installed(self.INITIAL_SETUP_UNIT_NAME, root=self._sysroot):
            disable_service(self.INITIAL_SETUP_UNIT_NAME, root=self._sysroot)

    def _enable_reconfig_mode(self):
        """Write the reconfig mode trigger file."""
        log.debug("Initial Setup reconfiguration mode will be enabled.")
        touch(os.path.join(self._sysroot, "etc/reconfigSys"))

    def run(self):
        if self._setup_on_boot == SetupOnBootAction.ENABLED:
            self._enable_service()
        elif self._setup_on_boot == SetupOnBootAction.RECONFIG:
            # reconfig implies enabled
            self._enable_service()
            self._enable_reconfig_mode()
        else:
            # the Initial Setup service is disabled by default
            self._disable_service()


class ConfigurePostInstallationToolsTask(Task):
    """Installation task for configuration of post-installation tools."""

    def __init__(self, sysroot, tools_enabled):
        """Create a new task.

        :param str sysroot: a path to the root of the target system
        :param bool tools_enabled: are the post-installation tools enabled?
        """
        super().__init__()
        self._sysroot = sysroot
        self._tools_enabled = tools_enabled

    @property
    def name(self):
        return "Configure post-installation tools"

    def run(self):
        """Run the task. """
        if conf.target.is_image:
            log.info("Not writing out user interaction config file due to image install mode.")
        elif conf.target.is_directory:
            log.info("Not writing out user interaction config file due to directory install mode.")
        else:
            parser = self._get_config()
            self._write_config(parser)

    def _get_config(self):
        """Generate the user interaction configuration."""
        parser = ConfigParser(delimiters=("=", ), comment_prefixes=("#", ))
        parser.add_section("General")
        parser["General"]["post_install_tools_disabled"] = "1" if not self._tools_enabled else "0"
        return parser

    def _write_config(self, parser):
        """Write the user interaction config file."""
        path = os.path.join(self._sysroot, "etc/sysconfig/anaconda")
        log.info("Writing out user interaction config at %s", path)

        try:
            with open(path, "wt") as f:
                f.write(
                    "# This file has been generated by the Anaconda Installer "
                    "{}\n\n".format(get_anaconda_version_string())
                )

                parser.write(f)
        except OSError:
            log.exception("Can't write user interaction config file.")


class ConfigureServicesTask(Task):
    """Installation task for service configuration.

    We enable and disable services as specified.
    """

    def __init__(self, sysroot, disabled_services, enabled_services):
        """Create a new service configuration task.

        :param str sysroot: a path to the root of the target system
        :param disabled_services: services that should be disabled
        :param enabled_services: services that should be enabled

        NOTE: We always first disable all services that should be disabled
              and only then enable all services that should be enabled.
        """
        super().__init__()
        self._sysroot = sysroot
        self._disabled_services = disabled_services
        self._enabled_services = enabled_services

    @property
    def name(self):
        return "Configure services"

    def run(self):
        for service_name in self._disabled_services:
            log.debug("Disabling service: %s.", service_name)
            disable_service(service_name, root=self._sysroot)

        for service_name in self._enabled_services:
            log.debug("Enabling service: %s.", service_name)
            enable_service(service_name, root=self._sysroot)


class ConfigureSystemdDefaultTargetTask(Task):
    """Installation task for configuring systemd default target.

    Set the correct systemd default target for the target system.

    We support setting either the text only "multi-user"
    target or the graphical target called "graphical".
    """

    def __init__(self, sysroot, default_target):
        """Create a new systemd target configuration task.

        :param str sysroot: a path to the root of the target system
        :param default_target: systemd default target to be set
        """
        super().__init__()
        self._sysroot = sysroot
        self._default_target = default_target

    @property
    def name(self):
        return "Configure systemd default target"

    def _check_login_manager_package_is_installed(self):
        """Check if a package which provides service(graphical-login) is installed.

        If such package has been installed & no default target has been explicitely set
        (via kickstart or DBus) then graphical.target should be the systemd
        default target.
        """
        log.debug("Checking if a package with provides == service(graphical-login) is installed.")
        try:
            import rpm
        except ImportError:
            log.info("failed to import rpm -- not adjusting default runlevel")
        else:
            ts = rpm.TransactionSet(conf.target.system_root)

            if ts.dbMatch("provides", 'service(graphical-login)').count():
                log.debug("A package with provides == service(graphical-login) is installed, "
                          "using graphical.target.")
                self._default_target = GRAPHICAL_TARGET

    def run(self):
        # Skip if /etc/systemd/system doesn't exist.
        if not os.path.isdir(os.path.join(self._sysroot, 'etc/systemd/system')):
            log.warning("There is no /etc/systemd/system directory, cannot update default.target!")
            return

        # If no target has been explicitly set we to switch the default target to graphical.target
        # ig a graphical login manager has been installed.
        if not self._default_target:
            self._check_login_manager_package_is_installed()

        # If at this point in time we still don't have a target set,
        # we default to the multi-user.target.
        if not self._default_target:
            self._default_target = TEXT_ONLY_TARGET

        log.debug("Setting systemd default target to: %s", self._default_target)
        default_target_path = os.path.join(self._sysroot, 'etc/systemd/system/default.target')
        # unlink any links already in place
        if os.path.islink(default_target_path):
            os.unlink(default_target_path)
        # symlink the selected target
        selected_target_path = os.path.join('/usr/lib/systemd/system', self._default_target)
        log.debug("Linking %s as systemd default target.", selected_target_path)
        os.symlink(selected_target_path, default_target_path)


class ConfigureDefaultDesktopTask(Task):
    """Installation task for configuring the default desktop."""

    def __init__(self, sysroot, default_desktop):
        """Create a new default desktop configuration task.

        :param str sysroot: a path to the root of the target system
        :param str default_desktop: default desktop to be set
        """
        super().__init__()
        self._sysroot = sysroot
        self._default_desktop = default_desktop

    @property
    def name(self):
        return "Configure default desktop"

    def run(self):
        if self._default_desktop:
            with open(os.path.join(self._sysroot, "etc/sysconfig/desktop"), "wt") as f:
                f.write("DESKTOP=%s\n" % self._default_desktop)
