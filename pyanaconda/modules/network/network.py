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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.configuration.network import NetworkOnBoot
from pyanaconda.dbus import DBus, SystemBus
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.base import KickstartModule
from pyanaconda.modules.common.constants.services import NETWORK, HOSTNAME
from pyanaconda.modules.network.network_interface import NetworkInterface
from pyanaconda.modules.network.kickstart import NetworkKickstartSpecification, \
    update_network_hostname_data, update_network_data_with_default_device, DEFAULT_DEVICE_SPECIFICATION, \
    update_first_network_command_activate_value
from pyanaconda.modules.network.firewall import FirewallModule
from pyanaconda.modules.network.device_configuration import DeviceConfigurations, supported_device_types, \
    supported_wired_device_types
from pyanaconda.modules.network.nm_client import get_device_name_from_network_data, \
    add_connection_from_ksdata, update_connection_from_ksdata, ensure_active_connection_for_device, \
    update_iface_setting_values, bound_hwaddr_of_device, devices_ignore_ipv6
from pyanaconda.modules.network.ifcfg import get_ifcfg_file_of_device, update_onboot_value, \
    update_slaves_onboot_value, find_ifcfg_uuid_of_device, get_dracut_arguments_from_ifcfg, \
    get_kickstart_network_data, get_ifcfg_file
from pyanaconda.modules.network.installation import NetworkInstallationTask
from pyanaconda.modules.network.utils import get_default_route_iface

import gi
gi.require_version("NM", "1.0")
from gi.repository import NM

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class NetworkModule(KickstartModule):
    """The Network module."""

    def __init__(self):
        super().__init__()

        self._firewall_module = FirewallModule()

        self.hostname_changed = Signal()
        self._hostname = "localhost.localdomain"

        self.disable_ipv6_changed = Signal()
        self._disable_ipv6 = False

        self.current_hostname_changed = Signal()
        self._hostname_service_proxy = None

        if conf.system.provides_system_bus:
            self._hostname_service_proxy = HOSTNAME.get_proxy()
            self._hostname_service_proxy.PropertiesChanged.connect(self._hostname_service_properties_changed)

        self.connected_changed = Signal()
        self.nm_client = None
        # TODO fallback solution - use Gio/GNetworkMonitor ?
        if SystemBus.check_connection():
            nm_client = NM.Client.new(None)
            if nm_client.get_nm_running():
                self.nm_client = nm_client
                self.nm_client.connect("notify::%s" % NM.CLIENT_STATE, self._nm_state_changed)
                initial_state = self.nm_client.get_state()
                self.set_connected(self._nm_state_connected(initial_state))
            else:
                log.debug("NetworkManager is not running.")

        self._original_network_data = []
        self._onboot_yes_ifaces = []
        self._device_configurations = None
        self._use_device_configurations = False
        self.configurations_changed = Signal()

        self._default_device_specification = DEFAULT_DEVICE_SPECIFICATION
        self._bootif = None
        self._ifname_option_values = []

    def publish(self):
        """Publish the module."""
        self._firewall_module.publish()

        DBus.publish_object(NETWORK.object_path, NetworkInterface(self))
        DBus.register_service(NETWORK.service_name)

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

        :param specifiacation: device specification accepted by network --device option
        :type specification: str
        """
        self._default_device_specification = specification
        log.debug("default kickstart device specification set to %s", specification)

    def process_kickstart(self, data):
        """Process the kickstart data."""
        log.debug("Processing kickstart data...")

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

    def generate_kickstart(self):
        """Return the kickstart string."""
        data = self.get_kickstart_handler()

        if self._device_configurations and self._use_device_configurations:
            log.debug("using device configurations to generate kickstart")
            device_data = self.generate_kickstart_network_data(data.NetworkData)
        else:
            log.debug("using original kickstart data to generate kickstart")
            device_data = self._original_network_data

        data.network.network = device_data

        self._update_network_data_with_onboot(data.network.network, self._onboot_yes_ifaces)

        hostname_data = data.NetworkData(hostname=self.hostname, bootProto="")
        update_network_hostname_data(data.network.network, hostname_data)

        # firewall
        self._firewall_module.setup_kickstart(data)

        return str(data)

    def _is_device_activated(self, iface):
        device = self.nm_client.get_device_by_iface(iface)
        return device and device.get_state() == NM.DeviceState.ACTIVATED

    def generate_kickstart_network_data(self, network_data_class):
        rv = []
        for cfg in self._device_configurations.get_all():
            network_data = None
            if cfg.device_type != NM.DeviceType.WIFI and cfg.connection_uuid:
                ifcfg = get_ifcfg_file([("UUID", cfg.connection_uuid)])
                if not ifcfg:
                    log.debug("Ifcfg file for %s not found.")
                    continue
                network_data = get_kickstart_network_data(ifcfg,
                                                          self.nm_client,
                                                          network_data_class)
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

    def _hostname_service_properties_changed(self, interface, changed, invalid):
        if interface == HOSTNAME.interface_name and "Hostname" in changed:
            hostname = changed["Hostname"]
            self.current_hostname_changed.emit(hostname)
            log.debug("Current hostname changed to %s", hostname)

    def get_current_hostname(self):
        """Return current hostname of the system."""
        if self._hostname_service_proxy:
            return self._hostname_service_proxy.Hostname

        log.debug("Current hostname cannot be get.")
        return ""

    def set_current_hostname(self, hostname):
        """Set current system hostname."""
        if not self._hostname_service_proxy:
            log.debug("Current hostname cannot be set.")
            return

        self._hostname_service_proxy.SetHostname(hostname, False)
        log.debug("Current hostname is set to %s", hostname)

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

    @staticmethod
    def _nm_state_connected(state):
        return state in (NM.State.CONNECTED_LOCAL, NM.State.CONNECTED_SITE, NM.State.CONNECTED_GLOBAL)

    def _nm_state_changed(self, *args):
        state = self.nm_client.get_state()
        log.debug("NeworkManager state changed to %s", state)
        self.set_connected(self._nm_state_connected(state))

    @property
    def disable_ipv6(self):
        """Disable IPv6 on target system."""
        return self._disable_ipv6

    def set_disable_ipv6(self, disable_ipv6):
        """Set disable IPv6 on target system."""
        self._disable_ipv6 = disable_ipv6
        self.disable_ipv6_changed.emit()
        log.debug("Disable IPv6 is set to %s", disable_ipv6)

    def install_network_with_task(self, sysroot, onboot_ifaces, overwrite):
        """Install network with an installation task.

        :param sysroot: a path to the root of the installed system
        :param onboot_ifaces: list of network interfaces which should have ONBOOT=yes
        :param overwrite: overwrite existing configuration
        :return: a DBus path of an installation task
        """
        disable_ipv6 = self.disable_ipv6 and devices_ignore_ipv6(self.nm_client, supported_wired_device_types)
        network_ifaces = [device.get_iface() for device in self.nm_client.get_devices()]

        onboot_ifaces_by_policy = []
        if self._should_apply_onboot_policy():
            onboot_ifaces_by_policy = self._get_onboot_ifaces_by_policy(conf.network.default_on_boot)
        all_onboot_ifaces = list(set(onboot_ifaces + onboot_ifaces_by_policy))
        self._onboot_yes_ifaces = all_onboot_ifaces
        onboot_yes_uuids = [find_ifcfg_uuid_of_device(self.nm_client, iface) or "" for iface in all_onboot_ifaces]
        log.debug("ONBOOT will be set to yes for %s (fcoe) %s (policy)",
                  onboot_ifaces, onboot_ifaces_by_policy)

        task = NetworkInstallationTask(sysroot, self.hostname, disable_ipv6, overwrite,
                                       onboot_yes_uuids, network_ifaces)
        path = self.publish_task(NETWORK.namespace, task)
        return path

    def _should_apply_onboot_policy(self):
        # Not if network is configured by kickstart
        if self._original_network_data:
            return False
        # Not if network is configured in UI
        if self._use_device_configurations:
            return False
        if self._device_configurations:
            data = self.get_kickstart_handler()
            device_data = self.generate_kickstart_network_data(data.NetworkData)
            return device_data and not any(dd.onboot for dd in device_data if dd.device)

    def _get_onboot_ifaces_by_policy(self, policy):
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

    def _update_network_data_with_onboot(self, network_data, ifaces):
        if not ifaces:
            return
        for nd in network_data:
            supported_devices = self.get_supported_devices()
            device_name = get_device_name_from_network_data(self.nm_client,
                                                            nd, supported_devices, self._bootif)
            if device_name in ifaces:
                log.debug("Updating network data onboot value: %s -> %s", nd.onboot, True)
                nd.onboot = True

    def create_device_configurations(self):
        """Create and populate the state of network devices configuration."""
        self._device_configurations = DeviceConfigurations(self.nm_client)
        self._device_configurations.configurations_changed.connect(self.device_configurations_changed_cb)
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

    def consolidate_initramfs_connections(self):
        """Ensure devices configured in initramfs have no more than one NM connection.

        In case of multiple connections for device having ifcfg configuration from
        boot options, the connection should correspond to the ifcfg file.
        NetworkManager can be generating additional in-memory connection in case it
        fails to match device configuration to the ifcfg (#1433891).  By
        reactivating the device with ifcfg connection the generated in-memory
        connection will be deleted by NM.

        Don't enforce on slave devices for which having multiple connections can be
        valid (slave connection, regular device connection).
        """
        consolidated_devices = []

        for device in self.nm_client.get_devices():
            cons = device.get_available_connections()
            number_of_connections = len(cons)
            iface = device.get_iface()

            if number_of_connections < 2:
                continue

            # Ignore devices which are slaves
            if any(con.get_setting_connection().get_master() for con in cons):
                log.debug("consolidate %d initramfs connections for %s: it is OK, device is a slave",
                          number_of_connections, iface)
                continue

            ifcfg_file = get_ifcfg_file_of_device(self.nm_client, iface)
            if not ifcfg_file:
                log.error("consolidate %d initramfs connections for %s: no ifcfg file",
                          number_of_connections, iface)
                continue
            else:
                # Handle only ifcfgs created from boot options in initramfs
                # (Kickstart based ifcfgs are handled when applying kickstart)
                if ifcfg_file.is_from_kickstart:
                    continue

            log.debug("consolidate %d initramfs connections for %s: ensure active ifcfg connection",
                      number_of_connections, iface)

            ensure_active_connection_for_device(self.nm_client, ifcfg_file.uuid, iface, only_replace=True)

            consolidated_devices.append(iface)

        return consolidated_devices

    def get_supported_devices(self):
        """Get names of existing supported devices on the system."""
        return [device.get_iface() for device in self.nm_client.get_devices()
                if device.get_device_type() in supported_device_types]

    @property
    def bootif(self):
        """Get the value of kickstart --bootif option."""
        return self._bootif

    @bootif.setter
    def bootif(self, specification):
        """Set the value of kickstart --bootif option.

        :param specifiacation: mac address specified in kickstart --bootif option
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

    def apply_kickstart(self):
        """Apply kickstart configuration which has not already been applied.

        * Activate configurations created in initramfs if --activate is True.
        * Create configurations for %pre kickstart commands and activate eventually.

        :returns: list of devices to which kickstart configuration was applied
        """
        applied_devices = []

        if not self._original_network_data:
            log.debug("No kickstart data to apply.")
            return []

        for network_data in self._original_network_data:
            # Wireless is not supported
            if network_data.essid:
                log.info("Wireless devices configuration is not supported.")
                continue

            supported_devices = self.get_supported_devices()
            device_name = get_device_name_from_network_data(self.nm_client,
                                                            network_data,
                                                            supported_devices,
                                                            self._bootif)
            if not device_name:
                log.warning("apply kickstart: --device %s not found", network_data.device)
                continue

            ifcfg_file = get_ifcfg_file_of_device(self.nm_client, device_name)
            if ifcfg_file and ifcfg_file.is_from_kickstart:
                if network_data.activate:
                    if ensure_active_connection_for_device(self.nm_client, ifcfg_file.uuid, device_name):
                        applied_devices.append(device_name)
                continue

            # If there is no kickstart ifcfg from initramfs the command was added
            # in %pre section after switch root, so apply it now
            applied_devices.append(device_name)
            if ifcfg_file:
                # if the device was already configured in initramfs update the settings
                con_uuid = ifcfg_file.uuid
                log.debug("pre kickstart - updating settings %s of device %s",
                          con_uuid, device_name)
                connection = self.nm_client.get_connection_by_uuid(con_uuid)
                update_connection_from_ksdata(self.nm_client, connection, network_data, device_name=device_name)
                if network_data.activate:
                    device = self.nm_client.get_device_by_iface(device_name)
                    self.nm_client.activate_connection_async(connection, device, None, None)
                    log.debug("pre kickstart - activating connection %s with device %s",
                              con_uuid, device_name)
            else:
                log.debug("pre kickstart - adding connection for %s", device_name)
                add_connection_from_ksdata(self.nm_client, network_data, device_name,
                                           activate=network_data.activate)

        return applied_devices

    def set_real_onboot_values_from_kickstart(self):
        """Update ifcfg ONBOOT values according to kickstart configuration.

        So it reflects the --onboot option.

        This is needed because:
        1) For ifcfg files created in initramfs we use ONBOOT for --activate
        2) For kickstart applied in stage 2 we can't set the autoconnect
           setting of connection because the device would be activated immediately.

        :return: list of devices for which ONBOOT was updated
        :rtype: list(str)
        """
        updated_devices = []

        if not self._original_network_data:
            log.debug("No kickstart data to set onboot from.")
            return []

        for network_data in self._original_network_data:
            supported_devices = self.get_supported_devices()
            device_name = get_device_name_from_network_data(self.nm_client,
                                                            network_data,
                                                            supported_devices,
                                                            self._bootif)
            if not device_name:
                log.warning("set ONBOOT: --device %s does not exist", network_data.device)

            devices_to_update = [device_name]
            master = device_name
            # When defining both bond/team and vlan in one command we need more care
            # network --onboot yes --device bond0 --bootproto static --bondslaves ens9,ens10
            # --bondopts mode=active-backup,miimon=100,primary=ens9,fail_over_mac=2
            # --ip 192.168.111.1 --netmask 255.255.255.0 --gateway 192.168.111.222 --noipv6
            # --vlanid 222 --no-activate
            if network_data.vlanid and (network_data.bondslaves or network_data.teamslaves):
                master = network_data.device
                devices_to_update.append(master)

            for devname in devices_to_update:
                if network_data.onboot:
                    # We need to handle "no" -> "yes" change by changing ifcfg file instead of the NM connection
                    # so the device does not get autoactivated (BZ #1261864)
                    uuid = find_ifcfg_uuid_of_device(self.nm_client, devname) or ""
                    if not update_onboot_value(uuid, network_data.onboot, root_path=""):
                        continue
                else:
                    n_cons = update_iface_setting_values(self.nm_client, devname,
                        [("connection", NM.SETTING_CONNECTION_AUTOCONNECT, network_data.onboot)])
                    if n_cons != 1:
                        log.debug("set ONBOOT: %d connections found for %s", n_cons, devname)
                        if n_cons > 1:
                            # In case of multiple connections for a device, update ifcfg directly
                            uuid = find_ifcfg_uuid_of_device(self.nm_client, devname) or ""
                            if not update_onboot_value(uuid, network_data.onboot, root_path=""):
                                continue

                updated_devices.append(devname)

            # Handle slaves if there are any
            if network_data.bondslaves or network_data.teamslaves or network_data.bridgeslaves:
                # Master can be identified by devname or uuid, try to find master uuid
                uuid = None
                device = self.nm_client.get_device_by_iface(master)
                if device:
                    cons = device.get_available_connections()
                    n_cons = len(cons)
                    if n_cons == 1:
                        uuid = cons[0].get_uuid()
                    else:
                        log.debug("set ONBOOT: %d connections found for %s", n_cons, master)
                updated_slaves = update_slaves_onboot_value(self.nm_client, master, network_data.onboot, uuid=uuid)
                updated_devices.extend(updated_slaves)

        return updated_devices

    def dump_missing_ifcfg_files(self):
        """Dump missing default ifcfg file for wired devices.

        Make sure each supported wired device has ifcfg file.

        For default auto connections created by NM upon start (which happens in
        case of missing ifcfg file, eg the file was not created in initramfs)
        rename the in-memory connection using device name and dump it into
        ifcfg file.

        If default auto connections are turned off by NM configuration (based
        on policy, eg on RHEL or server), the connection will be created by Anaconda
        and dumped into ifcfg file.

        The connection id (and consequently ifcfg file name) is set to device
        name.
        """
        new_ifcfgs = []

        for device in self.nm_client.get_devices():
            if device.get_device_type() not in supported_wired_device_types:
                continue

            iface = device.get_iface()
            if get_ifcfg_file_of_device(self.nm_client, iface):
                continue

            cons = device.get_available_connections()
            n_cons = len(cons)
            device_is_slave = any(con.get_setting_connection().get_master() for con in cons)

            if n_cons == 0:
                data = self.get_kickstart_handler()
                default_data = data.NetworkData(onboot=False, ipv6="auto")
                log.debug("dump missing ifcfgs: creating default connection for %s", iface)
                add_connection_from_ksdata(self.nm_client, default_data, iface)
            elif n_cons == 1:
                if device_is_slave:
                    log.debug("dump missing ifcfgs: not creating default connection for slave device %s",
                              iface)
                    continue
                con = cons[0]
                log.debug("dump missing ifcfgs: dumping default autoconnection %s for %s",
                          con.get_uuid(), iface)
                s_con = con.get_setting_connection()
                s_con.set_property(NM.SETTING_CONNECTION_ID, iface)
                s_con.set_property(NM.SETTING_CONNECTION_INTERFACE_NAME, iface)
                if not bound_hwaddr_of_device(self.nm_client, iface, self.ifname_option_values):
                    s_wired = con.get_setting_wired()
                    s_wired.set_property(NM.SETTING_WIRED_MAC_ADDRESS, None)
                else:
                    log.debug("dump missing ifcfgs: iface %s bound to mac address by ifname boot option")
                con.commit_changes(True, None)
            elif n_cons > 1:
                if not device_is_slave:
                    log.warning("dump missing ifcfgs: %d non-slave connections found for device %s",
                                n_cons, iface)
                continue

            new_ifcfgs.append(iface)

        return new_ifcfgs

    def network_device_configuration_changed(self):
        if not self._device_configurations:
            log.error("Got request to use DeviceConfigurations that has not been created yet")
        self._use_device_configurations = True

    def get_dracut_arguments(self, iface, target_ip, hostname):
        """Get dracut arguments for the iface and iSCSI target.

        The dracut arguments would activate the iface in initramfs so that the
        iSCSI target can be attached (for example to mount root filesystem).

        :param iface: network interface used to connect to the target
        :param target_ip: IP of the iSCSI target
        :param hostname: static hostname to be configured
        """
        dracut_args = []

        if iface not in (device.get_iface() for device in self.nm_client.get_devices()):
            log.error("get dracut argumetns for %s: device not found", iface)
            return dracut_args

        return get_dracut_arguments_from_ifcfg(self.nm_client, iface, target_ip, hostname)
