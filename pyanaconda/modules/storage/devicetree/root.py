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
import copy
import os
import shlex

from blivet import util as blivet_util
from blivet.errors import StorageError
from blivet.fstab import FSTabManager
from blivet.storage_log import log_exception_info

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.i18n import _
from pyanaconda.core.path import set_system_root
from pyanaconda.modules.storage.devicetree.fsset import BlkidTab, CryptTab

log = get_module_logger(__name__)

__all__ = ["Root", "find_existing_installations", "mount_existing_system"]


def mount_existing_system(storage, root_device, read_only=None):
    """Mount filesystems specified in root_device's /etc/fstab file."""
    root_path = conf.target.physical_root
    read_only = "ro" if read_only else ""

    # Mount the root device.
    if root_device.protected and os.path.ismount("/mnt/install/isodir"):
        blivet_util.mount("/mnt/install/isodir",
                          root_path,
                          fstype=root_device.format.type,
                          options="bind")
    else:
        root_device.setup()
        root_device.format.mount(chroot=root_path,
                                 mountpoint="/",
                                 options="%s,%s" % (root_device.format.options, read_only))

    # Set up the sysroot.
    set_system_root(root_path)

    # Mount the filesystems.
    storage.fsset.parse_fstab(chroot=root_path)
    storage.fsset.mount_filesystems(root_path=root_path, read_only=read_only, skip_root=True)

    # Turn on swap.
    if not conf.target.is_image or not read_only:
        try:
            storage.fsset.turn_on_swap(root_path=root_path)
        except StorageError as e:
            log.error("Error enabling swap: %s", str(e))

    # Generate mtab.
    if not read_only:
        storage.make_mtab(chroot=root_path)


def find_existing_installations(devicetree):
    """Find existing GNU/Linux installations on devices from the device tree.

    :param devicetree: a device tree to find existing installations in
    :return: roots of all found installations
    """
    try:
        roots = _find_existing_installations(devicetree)
        return roots
    except Exception:  # pylint: disable=broad-except
        log_exception_info(log.info, "failure detecting existing installations")
    finally:
        devicetree.teardown_all()

    return []


def _find_existing_installations(devicetree):
    """Find existing GNU/Linux installations on devices from the device tree.

    :param devicetree: a device tree to find existing installations in
    :return: roots of all found installations
    """
    if not os.path.exists(conf.target.physical_root):
        blivet_util.makedirs(conf.target.physical_root)

    sysroot = conf.target.physical_root
    roots = []
    direct_devices = (dev for dev in devicetree.devices if dev.direct)
    for device in direct_devices:
        if not device.format.linux_native or not device.format.mountable or \
           not device.controllable or not device.format.exists:
            continue

        try:
            device.setup()
        except Exception:  # pylint: disable=broad-except
            log_exception_info(log.warning, "setup of %s failed", [device.name])
            continue

        options = device.format.options + ",ro"
        try:
            device.format.mount(options=options, mountpoint=sysroot)
        except Exception:  # pylint: disable=broad-except
            log_exception_info(log.warning, "mount of %s as %s failed", [device.name, device.format.type])
            blivet_util.umount(mountpoint=sysroot)
            continue

        if not os.access(sysroot + "/etc/fstab", os.R_OK):
            blivet_util.umount(mountpoint=sysroot)
            device.teardown()
            continue

        architecture, product, version = get_release_string(chroot=sysroot)
        (mounts, devices, mountopts) = _parse_fstab(devicetree, chroot=sysroot)
        blivet_util.umount(mountpoint=sysroot)

        if not mounts and not devices:
            # empty /etc/fstab. weird, but I've seen it happen.
            continue

        roots.append(Root(
            product=product,
            version=version,
            arch=architecture,
            devices=devices,
            mounts=mounts,
            mountopts=mountopts,
        ))

    return roots


def get_release_string(chroot):
    """Identify the installation of a Linux distribution.

    Attempt to identify the installation of a Linux distribution by checking
    a previously mounted filesystem for several files.  The filesystem must
    be mounted under the target physical root.

    :returns: The machine's arch, distribution name, and distribution version
    or None for any parts that cannot be determined
    :rtype: (string, string, string)
    """
    rel_name = None
    rel_ver = None
    sysroot = chroot

    try:
        rel_arch = blivet_util.capture_output(["arch"], root=sysroot).strip()
    except OSError:
        rel_arch = None

    try:
        filename = "%s/etc/redhat-release" % sysroot
        if os.access(filename, os.R_OK):
            (rel_name, rel_ver) = _release_from_redhat_release(filename)
        else:
            filename = "%s/etc/os-release" % sysroot
            if os.access(filename, os.R_OK):
                (rel_name, rel_ver) = _release_from_os_release(filename)
    except ValueError:
        pass

    return rel_arch, rel_name, rel_ver


def _release_from_redhat_release(fn):
    """Identify the installation of a Linux distribution via /etc/redhat-release.

    Attempt to identify the installation of a Linux distribution via
    /etc/redhat-release.  This file must already have been verified to exist
    and be readable.

    :param fn: an open filehandle on /etc/redhat-release
    :type fn: filehandle
    :returns: The distribution's name and version, or None for either or both
    if they cannot be determined
    :rtype: (string, string)
    """
    rel_name = None
    rel_ver = None

    with open(fn) as f:
        try:
            relstr = f.readline().strip()
        except (OSError, AttributeError):
            relstr = ""

    # get the release name and version
    # assumes that form is something
    # like "Red Hat Linux release 6.2 (Zoot)"
    (product, sep, version) = relstr.partition(" release ")
    if sep:
        rel_name = product
        rel_ver = version.split()[0]

    return rel_name, rel_ver


def _release_from_os_release(fn):
    """Identify the installation of a Linux distribution via /etc/os-release.

    Attempt to identify the installation of a Linux distribution via
    /etc/os-release.  This file must already have been verified to exist
    and be readable.

    :param fn: an open filehandle on /etc/os-release
    :type fn: filehandle
    :returns: The distribution's name and version, or None for either or both
    if they cannot be determined
    :rtype: (string, string)
    """
    rel_name = None
    rel_ver = None

    with open(fn, "r") as f:
        parser = shlex.shlex(f)

        while True:
            key = parser.get_token()
            if key == parser.eof:
                break
            elif key == "NAME":
                # Throw away the "=".
                parser.get_token()
                rel_name = parser.get_token().strip("'\"")
            elif key == "VERSION_ID":
                # Throw away the "=".
                parser.get_token()
                rel_ver = parser.get_token().strip("'\"")
            elif key  == "VERSION_CODENAME" and not rel_ver:
                # Throw away the "=".
                parser.get_token()
                rel_ver = parser.get_token().strip("'\"")

    return rel_name, rel_ver


def _parse_fstab(devicetree, chroot):
    """Parse /etc/fstab.

    :param devicetree: a device tree
    :param chroot: a path to the target OS installation
    :return: a tuple of a mount dict, device list, mount options
    """

    mounts = {}
    devices = []
    mountopts = {}

    fstab_path = "%s/etc/fstab" % chroot
    if not os.access(fstab_path, os.R_OK):
        log.info("cannot open %s for read", fstab_path)
        return mounts, devices, mountopts

    blkid_tab = BlkidTab(chroot=chroot)
    try:
        blkid_tab.parse()
        log.debug("blkid.tab devs: %s", list(blkid_tab.devices.keys()))
    except Exception:  # pylint: disable=broad-except
        log_exception_info(log.info, "error parsing blkid.tab")
        blkid_tab = None

    crypt_tab = CryptTab(devicetree, blkid_tab=blkid_tab, chroot=chroot)
    try:
        crypt_tab.parse(chroot=chroot)
        log.debug("crypttab maps: %s", list(crypt_tab.mappings.keys()))
    except Exception:  # pylint: disable=broad-except
        log_exception_info(log.info, "error parsing crypttab")
        crypt_tab = None

    fstab = FSTabManager(src_file=fstab_path)
    fstab.read()

    for entry in fstab:

        device = fstab.find_device(devicetree, entry=entry)
        if device is None:
            continue

        # If a btrfs volume is found but a subvolume is expected, ignore the volume.
        if device.type == "btrfs volume" and "subvol=" in entry.mntopts:
            log.debug("subvolume from %s for %s not found", entry.mntopts, entry.spec)
            continue

        if entry.vfstype != "swap":
            mounts[entry.file] = device
            mountopts[entry.file] = entry.get_raw_mntopts()

        devices.append(device)

    return mounts, devices, mountopts


class Root:
    """A root represents an existing OS installation."""

    def __init__(self, name=None, product=None, version=None, arch=None, devices=None,
                 mounts=None, mountopts=None):
        """Create a new OS representation.

        :param name: a name of the OS or None
        :param product: a distribution name or None
        :param version: a distribution version or None
        :param arch: a machine's architecture or None
        :param devices: a list of all devices
        :param mounts: a dictionary of mount points and devices
        :param mountopts: a dictionary of mount points and its mount options
        """
        self._name = name
        self._product = product
        self._version = version
        self._arch = arch
        self._devices = devices or []
        self._mounts = mounts or {}
        self._mountopts = mountopts or {}

    @property
    def name(self):
        """The name of the OS."""
        # Use the specified name.
        if self._name:
            return self._name

        # Or generate a translated name.
        if not self._product or not self._version or not self._arch:
            return _("Unknown Linux")

        if "linux" in self._product.lower():
            template = _("{product} {version} for {arch}")
        else:
            template = _("{product} Linux {version} for {arch}")

        return template.format(
            product=self._product,
            version=self._version,
            arch=self._arch
        )

    @property
    def devices(self):
        """Devices used by the OS.

        For example:

        * bootloader devices
        * mount point sources
        * swap devices

        :return: a list of all devices
        """
        return self._devices

    @property
    def mounts(self):
        """Mount points defined by the OS.

        :return: a dictionary of mount points and devices
        """
        return self._mounts

    @property
    def mountopts(self):
        """Mount point options of mount points defined by the OS.

        :return: a dictionary of mount points and their mount options
        """
        return self._mountopts

    def copy(self, storage):
        """Create a copy with devices of the given storage model.

        :param InstallerStorage storage: a storage model
        :return Root: a copy of this root object
        """
        new_root = copy.deepcopy(self)

        def _get_device(d):
            return storage.devicetree.get_device_by_id(d.id, hidden=True)

        def _get_mount(i):
            m, d = i[0], _get_device(i[1])
            return (m, d) if m and d else None

        def _get_mount_opt(i):
            m, d = i[0], _get_device(i[1])
            return (m, self._mountopts[m]) if m and d and m in self._mountopts else None

        new_root._devices = list(filter(None, map(_get_device, new_root._devices)))
        new_root._mounts = dict(filter(None, map(_get_mount, new_root._mounts.items())))
        new_root._mountopts = dict(filter(None, map(_get_mount_opt,
                                                    new_root._mounts.items())))
        return new_root
