#
# DBus interface for the network module.
#
# Copyright (C) 2018 Red Hat, Inc.
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

from dasbus.server.interface import dbus_class, dbus_interface, dbus_signal
from dasbus.server.property import emits_properties_changed
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.modules.common.base import KickstartModuleInterface
from pyanaconda.modules.common.constants.services import NETWORK
from pyanaconda.modules.common.containers import TaskContainer
from pyanaconda.modules.common.structures.network import (
    NetworkDeviceConfiguration,
    NetworkDeviceInfo,
)
from pyanaconda.modules.common.task import TaskInterface


@dbus_class
class NetworkInitializationTaskInterface(TaskInterface):
    """The interface for a network configuration initialization task

    Such a task returns a list of names of the devices the task has affected.
    """

    @staticmethod
    def convert_result(value):
        return get_variant(List[Str], value)


@dbus_interface(NETWORK.interface_name)
class NetworkInterface(KickstartModuleInterface):
    """DBus interface for Network module."""

    def connect_signals(self):
        super().connect_signals()
        self.watch_property("Hostname", self.implementation.hostname_changed)
        self.implementation.current_hostname_changed.connect(self.CurrentHostnameChanged)
        self.watch_property("Connected", self.implementation.connected_changed)
        self.implementation.configurations_changed.connect(self._device_configurations_changed)
        self.watch_property("Capabilities", self.implementation.capabilities_changed)

    @property
    def Hostname(self) -> Str:
        """Hostname the system will use."""
        return self.implementation.hostname

    @Hostname.setter
    @emits_properties_changed
    def Hostname(self, hostname: Str):
        """Set the hostname.

        Sets the hostname of installed system.

        param hostname: a string with a hostname
        """
        self.implementation.set_hostname(hostname)

    @dbus_signal
    def CurrentHostnameChanged(self, hostname: Str):
        """Signal current hostname change."""
        pass

    def GetCurrentHostname(self) -> Str:
        """Current system hostname."""
        return self.implementation.get_current_hostname()

    def SetCurrentHostname(self, hostname: Str):
        """Set current system hostname.

        Sets the hostname of installer environment.

        param: hostname: a string with a hostname
        """
        self.implementation.set_current_hostname(hostname)

    @property
    def Connected(self) -> Bool:
        """Is the system connected to the network?

        The system is considered to be connected if being in one of the states
        NM_STATE_CONNECTED_LOCAL, NM_STATE_CONNECTED_SITE or NM_STATE_CONNECTED_GLOBAL.
        """
        return self.implementation.connected

    def IsConnecting(self) -> Bool:
        """Is NewtorkManager in connecting state?

        The connecting state can indicate that dhcp configuration is
        in progress.

        The state corresponds to NM_STATE_CONNECTING.

        Internal API used for networking initialization and synchronization.
        To be removed after reworking the synchronization.
        """
        return self.implementation.is_connecting()

    @property
    def Capabilities(self) -> List[Int]:
        """The network backend capabilities

        Supported capabilities:
        team capability = 1
        """
        return self.implementation.capabilities

    def GetSupportedDevices(self) -> List[Structure]:
        """Get info about existing network devices supported by the module.

        :return: list of objects describing supported devices found on the system
        """
        dev_infos = self.implementation.get_supported_devices()
        return NetworkDeviceInfo.to_structure_list(dev_infos)

    def GetActivatedInterfaces(self) -> List[Str]:
        """Get activated network interfaces.

        Device is considered as activated if it has an active network (NM)
        connection.

        :return: list of names of devices having active network connection
        """
        return self.implementation.get_activated_interfaces()

    def InstallNetworkWithTask(self, overwrite: Bool) -> ObjPath:
        """Install network with an installation task.

        FIXME: does overwrite still apply?
        :param overwrite: overwrite existing configuration
        :return: a DBus path of an installation task
        """
        return TaskContainer.to_object_path(
            self.implementation.install_network_with_task(overwrite)
        )

    def ConfigureHostnameWithTask(self, overwrite: Bool) -> ObjPath:
        """Configure hostname with an installation task.

        FIXME: does overwrite still apply?
        :param overwrite: overwrite existing configuration
        :return: a DBus path of an installation task
        """
        return TaskContainer.to_object_path(
            self.implementation.configure_hostname_with_task(overwrite)
        )

    def ConfigureActivationOnBootWithTask(self, onboot_ifaces: List[Str]) -> ObjPath:
        """Configure automatic activation of devices on system boot.

        1) Specified devices are set to be activated automatically.
        2) Policy set in anaconda configuration (default_on_boot) is applied.

        :param onboot_ifaces: list of network interfaces which should have ONBOOT=yes
        """
        return TaskContainer.to_object_path(
            self.implementation.configure_activation_on_boot_with_task(onboot_ifaces)
        )

    def CreateDeviceConfigurations(self):
        """Create and populate the state of network devices configuration."""
        self.implementation.create_device_configurations()

    def GetDeviceConfigurations(self) -> List[Structure]:
        """Get the state of network devices configuration.

        Contains only configuration of devices supported by Anaconda.

        Returns list of NetworkDeviceConfiguration objects holding
        configuration of a network device.

        For a physical device there is only single NetworkDeviceConfiguration
        object bound to the device name (the mandatory persistent element of
        the object).  The uuid corresponds to the configuration of the device
        for installed system.

        For a virtual device there can be multiple NetworkDeviceConfiguration
        objects, bound to uuid of the device configuration (the mandatory
        persistent element of the object).  The device name is set in the
        object only if there exists respective active device with the
        configuration given by uuid applied.

        Configurations correspond to NetworkManager persistent connections by
        their uuid.
        """
        dev_cfgs = self.implementation.get_device_configurations()
        return NetworkDeviceConfiguration.to_structure_list(dev_cfgs)

    def _device_configurations_changed(self, changes):
        self.DeviceConfigurationChanged([
            (
                NetworkDeviceConfiguration.to_structure(old),
                NetworkDeviceConfiguration.to_structure(new)
            )
            for old, new in changes
        ])

    @dbus_signal
    def DeviceConfigurationChanged(self, changes: List[Tuple[Structure, Structure]]):
        """Signal change of network devices configurations."""
        pass

    def ApplyKickstartWithTask(self) -> ObjPath:
        """Apply kickstart configuration which has not already been applied.

        * activate configurations created in initramfs if --activate is True
        * create configurations for %pre kickstart commands and activate eventually

        :returns: DBus path of the task applying the kickstart
        """
        return TaskContainer.to_object_path(
            self.implementation.apply_kickstart_with_task()
        )

    def DumpMissingConfigFilesWithTask(self) -> ObjPath:
        """Dump missing default config file for wired devices.

        Make sure each supported wired device has config file.

        For default auto connections created by NM upon start (which happens in
        case of missing config file, eg the file was not created in initramfs)
        rename the in-memory connection using device name and dump it into
        config file.

        If default auto connections are turned off by NM configuration (based
        on policy, eg on RHEL or server), the connection will be created by Anaconda
        and dumped into config file.

        The connection id (and consequently config file name) is set to device
        name.

        :returns: DBus path of the task dumping the files
        """
        return TaskContainer.to_object_path(
            self.implementation.dump_missing_config_files_with_task()
        )

    def NetworkDeviceConfigurationChanged(self):
        """Inform module that network device configuration might have changed.

        Therefore kickstart for device configurations should be generated
        from persistent configuration instead of using original kickstart data.
        """
        return self.implementation.network_device_configuration_changed()

    def GetDracutArguments(
        self,
        iface: Str,
        target_ip: Str,
        hostname: Str,
        ibft: Bool
    ) -> List[Str]:
        """Get dracut arguments for the iface and iSCSI target.

        The dracut arguments would activate the iface in initramfs so that the
        iSCSI target can be attached (for example to mount root filesystem).

        :param iface: network interface used to connect to the target
        :param target_ip: IP of the iSCSI target
        :param hostname: static hostname to be configured
        :param ibft: the device should be configured from iBFT
        """
        return self.implementation.get_dracut_arguments(iface, target_ip, hostname, ibft)

    def LogConfigurationState(self, msg_header: Str):
        """Logs the state of network configuration.

        :param msg_header: header of the log messages
        """
        return self.implementation.log_configuration_state(msg_header)
