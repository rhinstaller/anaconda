#
# Kickstart module for network and hostname settings
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
import gi
from dasbus.client.observer import DBusObserver

from pyanaconda.core.async_utils import run_in_loop
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.configuration.network import NetworkOnBoot
from pyanaconda.core.constants import NETWORK_CAPABILITY_TEAM
from pyanaconda.core.dbus import DBus
from pyanaconda.core.kernel import kernel_arguments
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.base import KickstartService
from pyanaconda.modules.common.constants.services import HOSTNAME, NETWORK
from pyanaconda.modules.common.containers import TaskContainer
from pyanaconda.modules.common.structures.network import NetworkDeviceInfo
from pyanaconda.modules.common.structures.requirement import Requirement
from pyanaconda.modules.network.config_file import (
    get_config_files_content,
    is_config_file_for_system,
)
from pyanaconda.modules.network.device_configuration import (
    DeviceConfigurations,
    supported_device_types,
    supported_wired_device_types,
)
from pyanaconda.modules.network.firewall import FirewallModule
from pyanaconda.modules.network.initialization import (
    ApplyKickstartTask,
    DumpMissingConfigFilesTask,
)
from pyanaconda.modules.network.installation import (
    ConfigureActivationOnBootTask,
    HostnameConfigurationTask,
    NetworkInstallationTask,
)
from pyanaconda.modules.network.kickstart import (
    DEFAULT_DEVICE_SPECIFICATION,
    NetworkKickstartSpecification,
    update_first_network_command_activate_value,
    update_network_data_with_default_device,
    update_network_hostname_data,
)
from pyanaconda.modules.network.network_interface import NetworkInterface
from pyanaconda.modules.network.nm_client import (
    devices_ignore_ipv6,
    get_connections_dump,
    get_dracut_arguments_from_connection,
    get_kickstart_network_data,
    get_new_nm_client,
)
from pyanaconda.modules.network.utils import get_default_route_iface

gi.require_version("NM", "1.0")
from gi.repository import NM

from pyanaconda.anaconda_loggers import get_module_logger

log = get_module_logger(__name__)


class NetworkService(KickstartService):
    """The Network service."""

    def __init__(self):
        super().__init__()

        self._firewall_module = FirewallModule()

        self.hostname_changed = Signal()
        self._hostname = ""

        self.current_hostname_changed = Signal()
        self._hostname_service_proxy = self._get_hostname_proxy()

        self._capabilities = []
        self.capabilities_changed = Signal()

        self.connected_changed = Signal()
        # TODO fallback solution - use Gio/GNetworkMonitor ?
        self.nm_client = get_new_nm_client()
        if self.nm_client:
            self.nm_client.connect("notify::%s" % NM.CLIENT_STATE, self._nm_state_changed)
            initial_state = self.nm_client.get_state()
            self.set_connected(self._nm_state_connected(initial_state))
            self.nm_client.connect("notify::%s" % NM.CLIENT_CAPABILITIES,
                                   self._nm_capabilities_changed)
            nm_capabilities = self.nm_client.get_capabilities()
            self.set_capabilities(self._get_capabilities_from_nm(nm_capabilities))

        self._original_network_data = []
        self._device_configurations = None
        self._use_device_configurations = False
        self.configurations_changed = Signal()

        self._default_device_specification = DEFAULT_DEVICE_SPECIFICATION
        self._bootif = None
        self._ifname_option_values = []
        self._disable_ipv6 = False
        self._apply_boot_options(kernel_arguments)

    def publish(self):
        """Publish the module."""
        TaskContainer.set_namespace(NETWORK.namespace)
        self._firewall_module.publish()

        DBus.publish_object(NETWORK.object_path, NetworkInterface(self))
        DBus.register_service(NETWORK.service_name)

    def run(self):
        """Run the loop."""
        run_in_loop(self._connect_to_hostname_service_once_available)
        super().run()

    @property
    def kickstart_specification(self):
        """Return the kickstart specification."""
        return NetworkKickstartSpecification

    @property
    def default_device_specification(self):
        """Get the default specification for missing kickstart --device option."""
        return self._default_device_specification

    @default_device_specification.setter
    def default_device_specification(self, specification):
        """Set the default specification for missing kickstart --device option.

        :param specification: device specification accepted by network --device option
        :type specification: str
        """
        self._default_device_specification = specification
        log.debug("default kickstart device specification set to %s", specification)

    def process_kickstart(self, data):
        """Process the kickstart data."""
        # Handle default value for --device
        spec = self.default_device_specification
        if update_network_data_with_default_device(data.network.network, spec):
            log.debug("used '%s' for missing network --device options", spec)
        if update_first_network_command_activate_value(data.network.network):
            log.debug("updated activate value of the first network command (None -> True)")

        self._original_network_data = data.network.network
        if data.network.hostname:
            self.set_hostname(data.network.hostname)
        self._firewall_module.process_kickstart(data)

    def setup_kickstart(self, data):
        """Set up the kickstart data."""
        if self._device_configurations and self._use_device_configurations:
            log.debug("using device configurations to generate kickstart")
            device_data = self.generate_kickstart_network_data(data.NetworkData)
        else:
            log.debug("using original kickstart data to generate kickstart")
            device_data = self._original_network_data

        data.network.network = device_data

        if self.hostname:
            hostname_data = data.NetworkData(hostname=self.hostname, bootProto="")
            update_network_hostname_data(data.network.network, hostname_data)

        # firewall
        self._firewall_module.setup_kickstart(data)

    def _is_device_activated(self, iface):
        device = self.nm_client.get_device_by_iface(iface)
        return device and device.get_state() == NM.DeviceState.ACTIVATED

    def generate_kickstart_network_data(self, network_data_class):
        rv = []
        for cfg in self._device_configurations.get_all():
            network_data = None
            if cfg.device_type != NM.DeviceType.WIFI and cfg.connection_uuid:
                uuid = cfg.connection_uuid
                con = self.nm_client.get_connection_by_uuid(uuid)
                filename = con.get_filename() or ""
                if not is_config_file_for_system(filename):
                    log.debug("Config file for %s not found, not generating ks command.", uuid)
                    continue
                connection = self.nm_client.get_connection_by_uuid(uuid)
                if connection:
                    network_data = get_kickstart_network_data(connection,
                                                              self.nm_client,
                                                              network_data_class)
                else:
                    log.debug("Connection %s for kickstart data generating not found", uuid)
            if not network_data:
                log.debug("Device configuration %s does not generate any kickstart data", cfg)
                continue
            if cfg.device_name:
                if self._is_device_activated(cfg.device_name):
                    network_data.activate = True
                else:
                    # First network command defaults to --activate so we must
                    # use --no-activate explicitly to prevent the default
                    # (Default value is None)
                    if not rv:
                        network_data.activate = False
            rv.append(network_data)
        return rv

    @property
    def hostname(self):
        """Return the hostname."""
        return self._hostname

    def set_hostname(self, hostname):
        """Set the hostname."""
        self._hostname = hostname
        self.hostname_changed.emit()
        log.debug("Hostname is set to %s", hostname)

    @staticmethod
    def _get_hostname_proxy():
        """Get a proxy of the hostname service.

        It won't activate the hostnamed service if it is deactivated.
        See `man systemd-hostnamed.service`.
        """
        if not conf.system.provides_system_bus:
            log.debug("Not using hostnamed service: system does not "
                      "provide system bus according to configuration.")
            return None

        return HOSTNAME.get_proxy()

    def _connect_to_hostname_service_once_available(self):
        """Connect to the hostname service once available.

        It won't activate the hostnamed service if it is deactivated.
        See `man systemd-hostnamed.service`.
        """
        log.debug("Watching the hostnamed service.")

        observer = DBusObserver(
            HOSTNAME.message_bus,
            HOSTNAME.service_name
        )
        observer.service_available.connect(
            self._connect_to_hostname_service
        )
        observer.connect_once_available()

    def _connect_to_hostname_service(self, observer):
        """Connect to the hostname service.

        It will activate the hostnamed service if it is deactivated.
        See `man systemd-hostnamed.service`.
        """
        log.debug("Connecting to the hostnamed service.")

        if self._hostname_service_proxy:
            self._hostname_service_proxy.PropertiesChanged.connect(
                self._hostname_service_properties_changed
            )

        observer.disconnect()

    def _hostname_service_properties_changed(self, interface, changed, invalid):
        if interface == HOSTNAME.interface_name and "Hostname" in changed:
            hostname = changed["Hostname"].unpack()
            self.current_hostname_changed.emit(hostname)
            log.debug("Current hostname changed to %s", hostname)

    def get_current_hostname(self):
        """Return current hostname of the system.

        It will activate the hostnamed service if it is deactivated.
        See `man systemd-hostnamed.service`.
        """
        if self._hostname_service_proxy:
            return self._hostname_service_proxy.Hostname

        log.debug("Current hostname cannot be get.")
        return ""

    def set_current_hostname(self, hostname):
        """Set current system hostname.

        It will activate the hostnamed service if it is deactivated.
        See `man systemd-hostnamed.service`.
        """
        if not self._hostname_service_proxy:
            log.debug("Current hostname cannot be set.")
            return

        self._hostname_service_proxy.SetStaticHostname(hostname, False)
        log.debug("Current static hostname is set to %s", hostname)

    @property
    def nm_available(self):
        return self.nm_client is not None

    @property
    def connected(self):
        """Is the system connected to the network?"""
        if self.nm_available:
            return self._connected
        else:
            log.debug("Connectivity state can't be determined, assuming connected.")
            return True

    def set_connected(self, connected):
        """Set network connectivity status."""
        self._connected = connected
        self.connected_changed.emit()
        self.module_properties_changed.emit()
        log.debug("Connected to network: %s", connected)

    def is_connecting(self):
        """Is NM in connecting state?"""
        if self.nm_available:
            return self.nm_client.get_state() == NM.State.CONNECTING
        else:
            log.debug("Connectivity state can't be determined, assuming not connecting.")
            return False

    @property
    def capabilities(self):
        """Capabilities of the network backend."""
        if not self.nm_available:
            log.debug("Capabilities can't be determined.")
            return []

        return self._capabilities

    def set_capabilities(self, capabilities):
        """Set network capabilities."""
        self._capabilities = capabilities
        self.capabilities_changed.emit()
        self.module_properties_changed.emit()
        log.debug("Capabilities: %s", capabilities)

    @staticmethod
    def _get_capabilities_from_nm(nm_capabilities):
        capabilities = []
        if NM.Capability.TEAM in nm_capabilities:
            capabilities.append(NETWORK_CAPABILITY_TEAM)

        return capabilities

    def _nm_capabilities_changed(self, *args):
        nm_capabilities = self.nm_client.get_capabilities()
        log.debug("NeworkManager capabilities changed to %s", nm_capabilities)
        self.set_capabilities(self._get_capabilities_from_nm(nm_capabilities))

    @staticmethod
    def _nm_state_connected(state):
        return state in (NM.State.CONNECTED_LOCAL,
                         NM.State.CONNECTED_SITE,
                         NM.State.CONNECTED_GLOBAL)

    def _nm_state_changed(self, *args):
        state = self.nm_client.get_state()
        log.debug("NeworkManager state changed to %s", state)
        self.set_connected(self._nm_state_connected(state))

    @property
    def disable_ipv6(self):
        """Disable IPv6 on target system."""
        return self._disable_ipv6

    @disable_ipv6.setter
    def disable_ipv6(self, disable_ipv6):
        """Set disable IPv6 on target system.

        :param disable_ipv6: should ipv6 be disabled on target system
        :type disable_ipv6: bool
        """
        self._disable_ipv6 = disable_ipv6
        log.debug("disable IPv6 is set to %s", disable_ipv6)

    def collect_requirements(self):
        """Return installation requirements for this module.

        :return: a list of requirements
        """
        # first collect requirements from the Firewall sub-module
        requirements = self._firewall_module.collect_requirements()

        # team device configuration support
        if self.get_team_devices():
            requirements.append(Requirement.for_package(
                "teamd",
                reason="Necessary for network team device configuration."
            ))
        # infiniband device configuration support
        if self.get_infiniband_devices():
            requirements.append(Requirement.for_package(
                "rdma-core",
                reason="Necessary for network infiniband device configuration."
            ))
        # prefixdevname
        if self._is_using_persistent_device_names(kernel_arguments):
            requirements.append(Requirement.for_package(
                "prefixdevname",
                reason="Necessary for persistent network device naming feature."
            ))
        # biosdevname
        if self._is_using_biosdevname(kernel_arguments):
            requirements.append(Requirement.for_package(
                "biosdevname",
                reason="Necessary for biosdevname network device naming feature."
            ))

        # encrypted dns
        if self._is_using_dnsconfd(kernel_arguments):
            requirements.append(Requirement.for_package(
                "dnsconfd",
                reason="Necessary for encrypted DNS configurtion."
            ))
            requirements.append(Requirement.for_package(
                "dnsconfd-dracut",
                reason="Necessary for encrypted DNS configuration in initramfs."
            ))

        return requirements

    def configure_activation_on_boot_with_task(self, onboot_ifaces):
        """Configure automatic activation of devices on system boot.

        1) Specified devices are set to be activated automatically.
        2) Policy set in anaconda configuration (default_on_boot) is applied.

        :param onboot_ifaces: list of network interfaces which should have ONBOOT=yes
        """
        onboot_ifaces_by_policy = []
        if self.nm_available and self._should_apply_onboot_policy() and \
                not self._has_any_onboot_yes_device(self._device_configurations):
            onboot_ifaces_by_policy = self._get_onboot_ifaces_by_policy(
                conf.network.default_on_boot
            )

        log.debug("Configure ONBOOT: set to yes for %s (reqested) %s (policy)",
                  onboot_ifaces, onboot_ifaces_by_policy)

        all_onboot_ifaces = list(set(onboot_ifaces + onboot_ifaces_by_policy))

        task = ConfigureActivationOnBootTask(
            all_onboot_ifaces
        )
        task.succeeded_signal.connect(lambda: self.log_task_result(task))
        return task

    def install_network_with_task(self, overwrite):
        """Install network with an installation task.

        :param overwrite: overwrite existing configuration
        :return: a DBus path of an installation task
        """
        disable_ipv6 = False
        network_ifaces = []
        if self.nm_available:
            disable_ipv6 = self.disable_ipv6 and devices_ignore_ipv6(self.nm_client,
                                                                     supported_wired_device_types)
            network_ifaces = [device.get_iface() for device in self.nm_client.get_devices()]

        task = NetworkInstallationTask(
            conf.target.system_root,
            disable_ipv6,
            overwrite,
            network_ifaces,
            self.ifname_option_values,
            self._is_using_persistent_device_names(kernel_arguments)
        )

        task.succeeded_signal.connect(
            lambda: self.log_task_result(task, root_path=conf.target.system_root)
        )
        return task

    def configure_hostname_with_task(self, overwrite):
        """Configure hostname with an installation task.

        :param overwrite: overwrite existing configuration
        :return: a DBus path of an installation task
        """
        return HostnameConfigurationTask(
            conf.target.system_root,
            self.hostname,
            overwrite
        )

    def _should_apply_onboot_policy(self):
        """Should policy for ONBOOT of devices be applied?."""
        # Not if any network device was configured via kickstart.
        if self._original_network_data:
            return False
        # Not if there is no configuration to apply the policy to
        if not self._device_configurations or not self._device_configurations.get_all():
            return False
        return True

    def _has_any_onboot_yes_device(self, device_configurations):
        """Does any device have ONBOOT value set to 'yes'?"""
        uuids = [dev_cfg.connection_uuid for dev_cfg in device_configurations.get_all()
                 if dev_cfg.connection_uuid]
        for uuid in uuids:
            con = self.nm_client.get_connection_by_uuid(uuid)
            if con:
                if (con.get_flags() & NM.SettingsConnectionFlags.UNSAVED):
                    log.debug("ONBOOT policy: not considering UNSAVED connection %s",
                              con.get_uuid())
                    continue
                if con.get_setting_connection().get_autoconnect():
                    log.debug("ONBOOT policy: %s has 'autoconnect' == True", con.get_uuid())
                    return True
        return False

    def _get_onboot_ifaces_by_policy(self, policy):
        """Get network interfaces that shoud have ONBOOT set to 'yes' by policy."""
        ifaces = []
        if policy is NetworkOnBoot.FIRST_WIRED_WITH_LINK:
            # choose first device having link
            log.info("Onboot policy: choosing the first device having link.")
            for device in self.nm_client.get_devices():
                if device.get_device_type() not in supported_device_types:
                    continue
                if device.get_device_type() == NM.DeviceType.WIFI:
                    continue
                if device.get_carrier():
                    ifaces.append(device.get_iface())
                    break

        elif policy is NetworkOnBoot.DEFAULT_ROUTE_DEVICE:
            # choose the device used during installation
            # (ie for majority of cases the one having the default route)
            log.info("Onboot policy: choosing the default route device.")
            iface = get_default_route_iface() or get_default_route_iface(family="inet6")
            if iface:
                device = self.nm_client.get_device_by_iface(iface)
                if device.get_device_type() != NM.DeviceType.WIFI:
                    ifaces.append(iface)

        return ifaces

    def create_device_configurations(self):
        """Create and populate the state of network devices configuration."""
        if not self.nm_available:
            log.debug("Device configurations can't be created, no NetworkManager available.")
            return
        self._device_configurations = DeviceConfigurations(self.nm_client)
        self._device_configurations.configurations_changed.connect(
            self.device_configurations_changed_cb
        )
        self._device_configurations.reload()
        self._device_configurations.connect()
        log.debug("Device configurations created: %s", self._device_configurations)

    def get_device_configurations(self):
        if not self._device_configurations:
            return []
        return self._device_configurations.get_all()

    def device_configurations_changed_cb(self, changes):
        log.debug("Device configurations changed: %s", changes)
        self.configurations_changed.emit(changes)

    def get_supported_devices(self):
        """Get information about existing supported devices on the system.

        :return: list of objects describing found supported devices
        :rtype: list(NetworkDeviceInfo)
        """
        # TODO guard on system (provides_system_bus)
        supported_devices = []
        if not self.nm_available:
            log.debug("Supported devices can't be determined.")
            return supported_devices

        for device in self.nm_client.get_devices():
            if device.get_device_type() not in supported_device_types:
                continue
            dev_info = NetworkDeviceInfo()
            dev_info.set_from_nm_device(device)
            if not all((dev_info.device_name, dev_info.device_type, dev_info.hw_address)):
                log.warning("Missing value when setting NetworkDeviceInfo from NM device: %s",
                            dev_info)
            supported_devices.append(dev_info)

        return supported_devices

    def get_activated_interfaces(self):
        """Get activated network interfaces.

        Device is considered as activated if it has an active network (NM)
        connection.

        :return: list of names of devices having active network connection
        :rtype: list(str)
        """
        # TODO guard on system (provides_system_bus)
        activated_ifaces = []
        if not self.nm_available:
            log.debug("Activated interfaces can't be determined.")
            return activated_ifaces

        for ac in self.nm_client.get_active_connections():
            if ac.get_state() != NM.ActiveConnectionState.ACTIVATED:
                continue
            for device in ac.get_devices():
                activated_ifaces.append(device.get_ip_iface() or device.get_iface())

        return activated_ifaces

    def get_team_devices(self):
        """Get existing team network devices.

        :return: basic information about existing team devices
        :rtype: list(NetworkDeviceInfo)
        """
        return [dev for dev in self.get_supported_devices()
                if dev.device_type == NM.DeviceType.TEAM]

    def get_infiniband_devices(self):
        """Get existing infiniband network devices.

        :return: basic information about existing infiniband devices
        :rtype: list(NetworkDeviceInfo)
        """
        return [dev for dev in self.get_supported_devices()
                if dev.device_type == NM.DeviceType.INFINIBAND]
    @property
    def bootif(self):
        """Get the value of kickstart --device bootif option."""
        return self._bootif

    @bootif.setter
    def bootif(self, specification):
        """Set the value of kickstart --device bootif option.

        :param specification: mac address specified by kickstart --device bootif option
        :type specification: str
        """
        self._bootif = specification
        log.debug("bootif device specification is set to %s", specification)

    @property
    def ifname_option_values(self):
        """Get values of ifname boot option."""
        return self._ifname_option_values

    @ifname_option_values.setter
    def ifname_option_values(self, values):
        """Set values of ifname boot option.

        :param values: list of ifname boot option values
        :type values: list(str)
        """
        self._ifname_option_values = values
        log.debug("ifname boot option values are set to %s", values)

    def apply_kickstart_with_task(self):
        """Apply kickstart configuration which has not already been applied.

        * Activate configurations created in initramfs if --activate is True.
        * Create configurations for %pre kickstart commands and activate eventually.

        :returns: a task applying the kickstart
        """
        supported_devices = [dev_info.device_name for dev_info in self.get_supported_devices()]
        task = ApplyKickstartTask(self._original_network_data,
                                  supported_devices,
                                  self.capabilities,
                                  self.bootif,
                                  self.ifname_option_values)
        task.succeeded_signal.connect(lambda: self.log_task_result(task, check_result=True))
        return task

    def dump_missing_config_files_with_task(self):
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

        :returns: a task dumping the files
        """
        data = self.get_kickstart_handler()
        default_network_data = data.NetworkData(onboot=False, ipv6="auto")
        task = DumpMissingConfigFilesTask(default_network_data,
                                          self.ifname_option_values)
        task.succeeded_signal.connect(lambda: self.log_task_result(task, check_result=True))
        return task

    def network_device_configuration_changed(self):
        if not self._device_configurations:
            log.error("Got request to use DeviceConfigurations that has not been created yet")
        self._use_device_configurations = True

    def get_dracut_arguments(self, iface, target_ip, hostname, ibft):
        """Get dracut arguments for the iface and iSCSI target.

        The dracut arguments would activate the iface in initramfs so that the
        iSCSI target can be attached (for example to mount root filesystem).

        :param iface: network interface used to connect to the target
        :param target_ip: IP of the iSCSI target
        :param hostname: static hostname to be configured
        :param ibft: the device should be configured from iBFT
        """
        log.debug("Getting dracut arguments for iface %s target %s (ibft==%s)",
                  iface, target_ip, ibft)
        dracut_args = []

        if not self.nm_available:
            log.debug("Get dracut arguments: can't be obtained, no NetworkManager available.")
            return dracut_args

        if iface and iface not in (device.get_iface() for device in self.nm_client.get_devices()):
            log.error("Get dracut arguments for %s: device not found", iface)
            return dracut_args

        if ibft:
            dracut_args.append('rd.iscsi.ibft')
        else:
            target_connections = []
            if self._device_configurations:
                for cfg in self._device_configurations.get_for_device(iface):
                    uuid = cfg.connection_uuid
                    if uuid:
                        connection = self.nm_client.get_connection_by_uuid(uuid)
                        if connection:
                            target_connections.append(connection)
            else:
                # DeviceConfigurations are not used on LiveCD,
                # use iface's active connection
                device = self.nm_client.get_device_by_iface(iface)
                if device:
                    active_connection = device.get_active_connection()
                    if active_connection:
                        target_connections = [active_connection.get_connection()]

            if target_connections:
                if len(target_connections) > 1:
                    log.debug("Get dracut arguments: "
                              "multiple connections found for target %s: %s, taking the first one",
                              [con.get_uuid() for con in target_connections], target_ip)
                connection = target_connections[0]
            else:
                log.error("Get dracut arguments: can't find connection for target %s", target_ip)
                return dracut_args

            dracut_args = list(get_dracut_arguments_from_connection(
                self.nm_client,
                connection,
                iface,
                target_ip,
                hostname
            ))
        return dracut_args

    def _apply_boot_options(self, kernel_args):
        """Apply boot options to the module.

        :param kernel_args: structure holding installer boot options
        :type kernel_args: KernelArguments
        """
        log.debug("Applying boot options %s", kernel_args)
        if 'ksdevice' in kernel_args:
            self.default_device_specification = kernel_args.get('ksdevice')
        if 'BOOTIF' in kernel_args:
            self.bootif = kernel_args.get('BOOTIF')[3:].replace("-", ":").upper()
        if 'ifname' in kernel_args:
            self.ifname_option_values = kernel_args.get("ifname").split()
        if 'noipv6' in kernel_args:
            self.disable_ipv6 = True

    def log_task_result(self, task, check_result=False, root_path=""):
        if not check_result:
            self.log_configuration_state(task.name, root_path)
        else:
            result = task.get_result()
            log.debug("%s result: %s", task.name, result)
            if result:
                self.log_configuration_state(task.name, root_path)

    def log_configuration_state(self, msg_header, root_path=""):
        """Log the current network configuration state.

        Logs NM config files and NM connections
        """
        log.debug("Dumping configuration state - %s", msg_header)
        for line in get_config_files_content(root_path=root_path).splitlines():
            log.debug(line)
        if self.nm_available:
            for line in get_connections_dump(self.nm_client).splitlines():
                log.debug(line)

    def _is_using_persistent_device_names(self, kernel_args):
        return 'net.ifnames.prefix' in kernel_args

    def _is_using_biosdevname(self, kernel_args):
        return kernel_args.get('biosdevname') == "1"

    def _is_using_dnsconfd(self, kernel_args):
        return kernel_args.get('rd.net.dns-backend') == "dnsconfd"
