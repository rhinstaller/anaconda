#
# Copyright (C) 2019  Red Hat, Inc.
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
from blivet.devices import MultipathDevice, iScsiDiskDevice, NVDIMMNamespaceDevice
from blivet.iscsi import iscsi

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.constants import CLEAR_PARTITIONS_NONE
from pyanaconda.modules.common.constants.objects import AUTO_PARTITIONING, \
    DISK_INITIALIZATION, MANUAL_PARTITIONING, NVDIMM
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.storage.partitioning.base import PartitioningModule
from pyanaconda.modules.storage.disk_initialization.initialization import DiskInitializationModule

log = get_module_logger(__name__)

__all__ = ["update_storage_ksdata", "reset_custom_storage_data"]


def update_storage_ksdata(storage, ksdata):
    """Update kickstart data to reflect the current storage configuration.

    FIXME: This is a temporary workaround for UI.

    :param storage: an instance of the storage
    :param ksdata: an instance of kickstart data
    """
    if not ksdata or not storage.mountpoints:
        return

    _update_clearpart(storage)
    _update_custom_storage(storage, ksdata)
    _update_iscsi_data(storage, ksdata)
    _update_nvdimm_data(storage)


def _update_clearpart(storage):
    """Update data for clearpart.

    :param storage: an instance of the storage
    """
    disk_init_proxy = STORAGE.get_proxy(DISK_INITIALIZATION)

    if disk_init_proxy.InitializationMode == CLEAR_PARTITIONS_NONE:
        # FIXME: This is an ugly temporary workaround for UI.
        mode, drives, devices = DiskInitializationModule._find_cleared_devices(storage)

        disk_init_proxy.SetInitializationMode(mode.value)
        disk_init_proxy.SetDrivesToClear(drives)
        disk_init_proxy.SetDevicesToClear(devices)


def _update_custom_storage(storage, ksdata):
    """Update kickstart data for custom storage.

    :param storage: an instance of the storage
    :param ksdata: an instance of kickstart data
    """
    auto_part_proxy = STORAGE.get_proxy(AUTO_PARTITIONING)
    manual_part_proxy = STORAGE.get_proxy(MANUAL_PARTITIONING)

    # Clear out whatever was there before.
    reset_custom_storage_data(ksdata)

    # Check if the custom partitioning was used.
    if auto_part_proxy.Enabled or manual_part_proxy.Enabled:
        log.debug("Custom partitioning is disabled.")
        return

    # FIXME: This is an ugly temporary workaround for UI.
    PartitioningModule._setup_kickstart_from_storage(ksdata, storage)


def reset_custom_storage_data(ksdata):
    """Reset the custom storage data.

    :param ksdata: an instance of kickstart data
    """
    for command in ["partition", "raid", "volgroup", "logvol", "btrfs"]:
        ksdata.resetCommand(command)


def _update_iscsi_data(storage, ksdata):
    """Update kickstart data for iSCSI.

    FIXME: Move the logic to the iSCSI DBus module.

    :param storage: an instance of the storage
    :param ksdata: an instance of kickstart data
    """
    # Find all iSCSI devices.
    iscsi_devices = []

    for d in storage.disks:
        # Get parents of a multipath devices.
        if isinstance(d, MultipathDevice):
            for parent_dev in d.parents:
                if (isinstance(parent_dev, iScsiDiskDevice)
                        and not parent_dev.ibft
                        and not parent_dev.offload):
                    iscsi_devices.append(parent_dev)
        # Add no-ibft iScsiDiskDevice. IBFT disks are added automatically
        # so there is no need to have them in the kickstart.
        elif isinstance(d, iScsiDiskDevice) and not d.ibft and not d.offload:
            iscsi_devices.append(d)

    if not iscsi_devices:
        return

    # Set the initiator name.
    ksdata.iscsiname.iscsiname = iscsi.initiator

    # Generate the iSCSI data.
    ksdata.iscsi.iscsi = []

    for device in iscsi_devices:
        iscsi_data = ksdata.IscsiData()

        _setup_iscsi_data_from_node(iscsi_data, device.node)

        for saved_iscsi in ksdata.iscsi.iscsi:
            if (iscsi_data.ipaddr == saved_iscsi.ipaddr and
                    iscsi_data.target == saved_iscsi.target and
                    iscsi_data.port == saved_iscsi.port):
                break
        else:
            ksdata.iscsi.iscsi.append(iscsi_data)


def _setup_iscsi_data_from_node(iscsi_data, dev_node):
    """Set up iSCSI data from a device node.

    FIXME: Move the logic to the iSCSI DBus module.

    :param iscsi_data: an instance of iSCSI data
    :param dev_node: a device node
    """
    iscsi_data.ipaddr = dev_node.address
    iscsi_data.target = dev_node.name
    iscsi_data.port = dev_node.port

    if iscsi.ifaces:
        iscsi_data.iface = iscsi.ifaces[dev_node.iface]

    if dev_node.username and dev_node.password:
        iscsi_data.user = dev_node.username
        iscsi_data.password = dev_node.password

    if dev_node.r_username and dev_node.r_password:
        iscsi_data.user_in = dev_node.r_username
        iscsi_data.password_in = dev_node.r_password

    return iscsi_data


def _update_nvdimm_data(storage):
    """Update kickstart data for NVDIMM.

    FIXME: Move the logic to the iSCSI DBus module.

    :param storage: an instance of the storage
    """
    nvdimm_proxy = STORAGE.get_proxy(NVDIMM)
    nvdimm_proxy.SetNamespacesToUse([
        d.devname for d in storage.disks
        if isinstance(d, NVDIMMNamespaceDevice)
    ])
