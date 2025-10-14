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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import os
import shutil
import time

from blivet import blockdev
from blivet.devices import (
    DirectoryDevice,
    FileDevice,
    MDRaidArrayDevice,
    NetworkStorageDevice,
    NoDevice,
    OpticalDevice,
)
from blivet.errors import (
    StorageError,
    SwapSpaceError,
    UnrecognizedFSTabEntryError,
)
from blivet.formats import get_format
from blivet.fstab import FSTabManager
from blivet.storage_log import log_exception_info

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.modules.storage.platform import EFI, platform

log = get_module_logger(__name__)

__all__ = ["BlkidTab", "CryptTab", "FSSet"]


def copy_to_system(source):
    """ Copy the source file the target OS installation. """
    if not os.access(source, os.R_OK):
        log.info("copy_to_system: source '%s' does not exist.", source)
        return False

    target = conf.target.system_root + source
    target_dir = os.path.dirname(target)
    log.debug("copy_to_system: '%s' -> '%s'.", source, target)
    if not os.path.isdir(target_dir):
        os.makedirs(target_dir)
    shutil.copy(source, target)
    return True


def get_containing_device(path, devicetree):
    """ Return the device that a path resides on. """
    if not os.path.exists(path):
        return None

    st = os.stat(path)
    major = os.major(st.st_dev)
    minor = os.minor(st.st_dev)
    link = "/sys/dev/block/%s:%s" % (major, minor)
    if not os.path.exists(link):
        return None

    try:
        device_name = os.path.basename(os.readlink(link))
    except Exception:  # pylint: disable=broad-except
        log_exception_info(fmt_str="failed to find device name for path %s", fmt_args=[path])
        return None

    if device_name.startswith("dm-"):
        # have I told you lately that I love you, device-mapper?
        device_name = blockdev.dm.name_from_node(device_name)

    # XXX we get device name from sysfs so usage of get_device_by_name here is correct
    return devicetree.get_device_by_name(device_name)


def get_system_filesystems(devicetree):
    """Get system filesystems.

    :param devicetree: a model of the storage
    :return: a list of new devices
    """
    devices = [
        DirectoryDevice(
            "/dev",
            exists=True,
            fmt=get_format(
                "bind",
                device="/dev",
                mountpoint="/dev",
                exists=True
            ),
        ),
        NoDevice(
            fmt=get_format(
                "tmpfs",
                device="tmpfs",
                mountpoint="/dev/shm"
            )
        ),
        NoDevice(
            fmt=get_format(
                "devpts",
                device="devpts",
                mountpoint="/dev/pts"
            )
        ),
        NoDevice(
            fmt=get_format(
                "sysfs",
                device="sysfs",
                mountpoint="/sys"
            )
        ),
        NoDevice(
            fmt=get_format(
                "proc",
                device="proc",
                mountpoint="/proc"
            )
        ),
        NoDevice(
            fmt=get_format(
                "selinuxfs",
                device="selinuxfs",
                mountpoint="/sys/fs/selinux"
            )
        ),
        NoDevice(
            fmt=get_format(
                "usbfs",
                device="usbfs",
                mountpoint="/proc/bus/usb"
            )
        ),
        DirectoryDevice(
            "/run",
            exists=True,
            fmt=get_format(
                "bind",
                device="/run",
                mountpoint="/run",
                exists=True
            )
        )
    ]

    if isinstance(platform, EFI):
        device = NoDevice(
            fmt=get_format(
                "efivarfs",
                device="efivarfs",
                mountpoint="/sys/firmware/efi/efivars"
            )
        )
        devices.append(device)

    if "/tmp" not in devicetree.mountpoints:
        device = NoDevice(
            fmt=get_format(
                "tmpfs",
                device="tmpfs",
                mountpoint="/tmp"
            )
        )
        devices.append(device)

    return devices


class BlkidTab:
    """ Dictionary-like interface to blkid.tab with device path keys """

    def __init__(self, chroot=""):
        self.chroot = chroot
        self.devices = {}

    def parse(self):
        path = "%s/etc/blkid/blkid.tab" % self.chroot
        if not os.access(path, os.R_OK):
            return

        log.debug("parsing %s", path)
        with open(path) as f:
            for line in f.readlines():
                # this is pretty ugly, but an XML parser is more work than
                # is justifiable for this purpose
                if not line.startswith("<device "):
                    continue

                line = line[len("<device "):-len("</device>\n")]

                (data, _sep, device) = line.partition(">")
                if not device:
                    continue

                self.devices[device] = {}
                for pair in data.split():
                    try:
                        (key, value) = pair.split("=")
                    except ValueError:
                        continue

                    self.devices[device][key] = value[1:-1]  # strip off quotes

    def __getitem__(self, key):
        return self.devices[key]

    def get(self, key, default=None):
        return self.devices.get(key, default)


class CryptTab:
    """ Dictionary-like interface to crypttab entries with map name keys """

    def __init__(self, devicetree, blkid_tab=None, chroot=""):
        self.devicetree = devicetree
        self.blkid_tab = blkid_tab
        self.chroot = chroot
        self.mappings = {}

    def parse(self, chroot=""):
        """ Parse /etc/crypttab from an existing installation. """
        if not chroot or not os.path.isdir(chroot):
            chroot = ""

        path = "%s/etc/crypttab" % chroot
        if not os.access(path, os.R_OK):
            return

        log.debug("parsing %s", path)
        with open(path) as f:
            if not self.blkid_tab:
                try:
                    self.blkid_tab = BlkidTab(chroot=chroot)
                    self.blkid_tab.parse()
                except Exception:  # pylint: disable=broad-except
                    log_exception_info(fmt_str="failed to parse blkid.tab")
                    self.blkid_tab = None

            for line in f.readlines():
                (line, _pound, _comment) = line.partition("#")
                fields = line.split()
                if not 2 <= len(fields) <= 4:
                    continue
                elif len(fields) == 2:
                    fields.extend(['none', ''])
                elif len(fields) == 3:
                    fields.append('')

                (name, devspec, keyfile, options) = fields

                # resolve devspec to a device in the tree
                device = self.devicetree.resolve_device(devspec,
                                                        blkid_tab=self.blkid_tab)
                if device:
                    self.mappings[name] = {"device": device,
                                           "keyfile": keyfile,
                                           "options": options}

    def populate(self):
        """ Populate the instance based on the device tree's contents. """
        for device in self.devicetree.devices:
            # XXX should we put them all in there or just the ones that
            #     are part of a device containing swap or a filesystem?
            #
            #       Put them all in here -- we can filter from FSSet
            if device.format.type != "luks":
                continue

            key_file = device.format.key_file
            if not key_file:
                key_file = "none"

            options = device.format.options or ""

            self.mappings[device.format.map_name] = {"device": device,
                                                     "keyfile": key_file,
                                                     "options": options}

    def crypttab(self):
        """ Write out /etc/crypttab """
        crypttab = ""
        for name in self.mappings:
            entry = self[name]
            crypttab += "%s UUID=%s %s %s\n" % (name,
                                                entry['device'].format.uuid,
                                                entry['keyfile'],
                                                entry['options'])
        return crypttab

    def __getitem__(self, key):
        return self.mappings[key]

    def get(self, key, default=None):
        return self.mappings.get(key, default)


class FSSet:
    """A class to represent a set of filesystems."""

    def __init__(self, devicetree):
        self.devicetree = devicetree
        self.crypt_tab = None
        self.blkid_tab = None
        self._fstab_swaps = set()
        self._system_filesystems = []

        # unrecognized or ignored entries in fstab (blivet.fstab.FSTabEntry)
        self.preserve_entries = []

    @property
    def system_filesystems(self):
        if not self._system_filesystems:
            self._system_filesystems = get_system_filesystems(
                self.devicetree
            )

        return self._system_filesystems

    @property
    def devices(self):
        return sorted(self.devicetree.devices, key=lambda d: d.path)

    @property
    def mountpoints(self):
        return self.devicetree.mountpoints

    def parse_fstab(self, chroot=None):
        """ Process fstab. Devices in there but not in devicetree are added into it.
            Unrecognized fstab entries are stored so they can be preserved
        """

        if not chroot or not os.path.isdir(chroot):
            chroot = conf.target.system_root

        fstab_path = "%s/etc/fstab" % chroot
        if not os.access(fstab_path, os.R_OK):
            log.info("cannot open %s for read", fstab_path)
            return

        blkid_tab = BlkidTab(chroot=chroot)
        try:
            blkid_tab.parse()
            log.debug("blkid.tab devs: %s", list(blkid_tab.devices.keys()))
        except Exception:  # pylint: disable=broad-except
            log_exception_info(log.info, "error parsing blkid.tab")
            blkid_tab = None

        crypt_tab = CryptTab(self.devicetree, blkid_tab=blkid_tab, chroot=chroot)
        try:
            crypt_tab.parse(chroot=chroot)
            log.debug("crypttab maps: %s", list(crypt_tab.mappings.keys()))
        except Exception:  # pylint: disable=broad-except
            log_exception_info(log.info, "error parsing crypttab")
            crypt_tab = None

        self.blkid_tab = blkid_tab
        self.crypt_tab = crypt_tab

        fstab = FSTabManager(src_file=fstab_path)
        fstab.read()

        for entry in fstab:
            try:
                device = fstab.get_device(self.devicetree, entry=entry)
            except UnrecognizedFSTabEntryError:
                self.preserve_entries.append(entry)
                continue

            if device not in self.devicetree.devices:
                try:
                    self.devicetree._add_device(device)
                except ValueError:
                    self.preserve_entries.append(entry)


    def turn_on_swap(self, root_path=""):
        """Activate the system's swap space."""
        for device in self.swap_devices:
            if isinstance(device, FileDevice):
                # set up FileDevices' parents now that they are accessible
                target_dir = "%s/%s" % (root_path, device.path)
                parent = get_containing_device(target_dir, self.devicetree)
                if not parent:
                    log.error("cannot determine which device contains "
                              "directory %s", device.path)
                    device.parents = []
                    self.devicetree._remove_device(device)
                    continue
                else:
                    device.parents = [parent]

            while True:
                if device.status and device.format.status:
                    break
                try:
                    device.setup()
                    device.format.setup()
                except (SwapSpaceError, blockdev.SwapActivateError,
                        StorageError, blockdev.BlockDevError) as e:
                    log.error("Failed to activate swap on '%s': %s", device.name, str(e))
                    break
                else:
                    break

    def collect_filesystems(self):
        """Collect the system's filesystems.

        :return: a list of devices
        """
        devices = \
            list(self.mountpoints.values()) + \
            self.swap_devices + \
            self.system_filesystems

        devices.sort(key=lambda d: getattr(d.format, "mountpoint", ""))
        return devices

    def mount_filesystems(self, root_path="", read_only=None, skip_root=False):
        """Mount the system's filesystems.

        :param str root_path: the root directory for this filesystem
        :param read_only: read only option str for this filesystem
        :type read_only: str or None
        :param bool skip_root: whether to skip mounting the root filesystem
        """
        devices = self.collect_filesystems()

        for device in devices:
            if not device.format.mountable or not device.format.mountpoint:
                continue

            if skip_root and device.format.mountpoint == "/":
                continue

            options = device.format.options
            if "noauto" in options.split(","):
                continue

            if device.format.type == "bind" and device.name not in ["/dev", "/run"]:
                # set up the DirectoryDevice's parents now that they are
                # accessible
                #
                # -- bind formats' device and mountpoint are always both
                #    under the chroot. no exceptions. none, damn it.
                target_dir = "%s/%s" % (root_path, device.path)
                parent = get_containing_device(target_dir, self.devicetree)
                if not parent:
                    log.error("cannot determine which device contains "
                              "directory %s", device.path)
                    device.parents = []
                    self.devicetree._remove_device(device)
                    continue
                else:
                    device.parents = [parent]

            if read_only:
                options = "%s,%s" % (options, read_only)

            # Create /tmp with the right permissions (rhbz#1937626).
            # It needs to be created right before we mount anything.
            # Call chmod to enforce the mode.
            if device.format.mountpoint == "/tmp":
                path = os.path.join(root_path, "tmp")

                if not os.path.exists(path):
                    os.makedirs(path)
                    os.chmod(path, 0o1777)

            device.setup()
            device.format.setup(
                options=options,
                chroot=root_path
            )

    def umount_filesystems(self, swapoff=True):
        """Unmount filesystems.

        Exclude swap if swapoff is False.
        """
        devices = self.collect_filesystems()
        devices.reverse()

        for device in devices:
            if (not device.format.mountable) or \
               (device.format.type == "swap" and not swapoff):
                continue

            # Unmount the devices
            device.format.teardown()

    @property
    def swap_devices(self):
        swaps = []
        for device in self.devices:
            if device.format.type == "swap" and device in self._fstab_swaps:
                swaps.append(device)
        return swaps

    @property
    def root_device(self):
        for path in ["/", conf.target.physical_root]:
            for device in self.devices:
                try:
                    mountpoint = device.format.mountpoint
                except AttributeError:
                    mountpoint = None

                if mountpoint == path:
                    return device

    def write(self):
        """Write out all config files based on the set of filesystems."""
        sysroot = conf.target.system_root
        # /etc/fstab
        fstab = self.fstab()
        fstab.write(dest_file=os.path.normpath("%s/etc/fstab" % sysroot))

        # /etc/crypttab
        crypttab_path = os.path.normpath("%s/etc/crypttab" % sysroot)
        crypttab = self.crypttab()
        origmask = os.umask(0o077)
        open(crypttab_path, "w").write(crypttab)
        os.umask(origmask)

        # /etc/mdadm.conf
        mdadm_path = os.path.normpath("%s/etc/mdadm.conf" % sysroot)
        mdadm_conf = self.mdadm_conf()
        if mdadm_conf:
            open(mdadm_path, "w").write(mdadm_conf)

        # /etc/multipath.conf
        if any(d for d in self.devices if d.type == "dm-multipath"):
            copy_to_system("/etc/multipath.conf")
            copy_to_system("/etc/multipath/wwids")
            copy_to_system("/etc/multipath/bindings")
        else:
            log.info("not writing out mpath configuration")

    def crypttab(self):
        # if we are upgrading, do we want to update crypttab?
        # gut reaction says no, but plymouth needs the names to be very
        # specific for passphrase prompting
        if not self.crypt_tab:
            self.crypt_tab = CryptTab(self.devicetree)
            self.crypt_tab.populate()

        devices = list(self.mountpoints.values()) + self.swap_devices

        # prune crypttab -- only mappings required by one or more entries
        for name in list(self.crypt_tab.mappings.keys()):
            keep = False
            map_info = self.crypt_tab[name]
            crypto_dev = map_info['device']
            for device in devices:
                if device == crypto_dev or device.depends_on(crypto_dev):
                    keep = True
                    break

            if not keep:
                del self.crypt_tab.mappings[name]

        return self.crypt_tab.crypttab()

    def mdadm_conf(self):
        """Return the contents of mdadm.conf."""
        arrays = [d for d in self.devices if isinstance(d, MDRaidArrayDevice)]
        # Sort it, this not only looks nicer, but this will also put
        # containers (which get md0, md1, etc.) before their members
        # (which get md127, md126, etc.). and lame as it is mdadm will not
        # assemble the whole stack in one go unless listed in the proper order
        # in mdadm.conf
        arrays.sort(key=lambda d: d.path)
        if not arrays:
            return ""

        content = "# mdadm.conf written out by anaconda\n"
        content += "MAILADDR root\n"
        content += "AUTO +imsm +1.x -all\n"
        devices = list(self.mountpoints.values()) + self.swap_devices
        for array in arrays:
            for device in devices:
                if device == array or device.depends_on(array):
                    content += array.mdadm_conf_entry
                    break

        return content

    def fstab(self):
        """ Create a FSTabManager object, fill it with current devices
            and return it as a result to be written
        """
        intro_comment = """
#
# /etc/fstab
# Created by anaconda on %s
#
# Accessible filesystems, by reference, are maintained under '/dev/disk/'.
# See man pages fstab(5), findfs(8), mount(8) and/or blkid(8) for more info.
#
# After editing this file, run 'systemctl daemon-reload' to update systemd
# units generated from this file.
#
""" % time.asctime()

        devices = sorted(self.mountpoints.values(),
                         key=lambda d: d.format.mountpoint)

        devices += self.swap_devices

        netdevs = [d for d in self.devices if isinstance(d, NetworkStorageDevice)]

        rootdev = devices[0]
        root_on_netdev = any(rootdev.depends_on(netdev) for netdev in netdevs)

        fstab = FSTabManager(src_file=None, dest_file=None)

        fstab._table.intro_comment = intro_comment

        for device in devices:
            # why the hell do we put swap in the fstab, anyway?
            if not device.format.mountable and device.format.type != "swap":
                continue

            # Don't write out lines for optical devices, either.
            if isinstance(device, OpticalDevice):
                continue

            try:
                new_entry = fstab.entry_from_device(device)
            except ValueError:
                fstype = getattr(device.format, "mount_type", device.format.type)
                log.warning("%s filesystem on %s has no mount point",
                            fstype,
                            device.path)  # legacy warning message # TODO change to e.msg?
                continue

            for netdev in netdevs:
                if device.depends_on(netdev):
                    if root_on_netdev and new_entry.file == "/var":
                        new_entry.mntopts_add("x-initrd.mount")
                    break

            if device.encrypted:
                new_entry.mntopts_add("x-systemd.device-timeout=0")

            new_entry.comment = device.fstab_comment
            fstab.add_entry(entry=new_entry)

        # now, write out any entries we were unable to process because of
        # unrecognized filesystems or unresolvable device specifications
        for preserved_entry in self.preserve_entries:
            fstab.add_entry(entry=preserved_entry)

        return fstab

    def add_fstab_swap(self, device):
        """Add swap device to the list of swaps that should appear in the fstab.

        :param device: swap device that should be added to the list
        :type device: StorageDevice instance holding a swap format
        """
        self._fstab_swaps.add(device)

    def set_fstab_swaps(self, devices):
        """Set swap devices that should appear in the fstab.

        :param devices: iterable providing devices that should appear in the fstab
        :type devices: iterable providing StorageDevice instances holding a swap format
        """
        self._fstab_swaps = set(devices)
