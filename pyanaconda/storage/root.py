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
import os
import shlex

from blivet import util as blivet_util
from blivet.storage_log import log_exception_info

from pyanaconda.core import util
from pyanaconda.core.i18n import _
from pyanaconda.storage.fsset import BlkidTab, CryptTab

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

__all__ = ["mount_existing_system", "find_existing_installations", "Root"]


def mount_existing_system(fsset, root_device, read_only=None):
    """Mount filesystems specified in root_device's /etc/fstab file."""
    root_path = util.getSysroot()
    read_only = "ro" if read_only else ""

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

    fsset.parse_fstab()
    fsset.mount_filesystems(root_path=root_path, read_only=read_only, skip_root=True)


def find_existing_installations(devicetree, teardown_all=True):
    """Find existing GNU/Linux installations on devices from the device tree.

    :param devicetree: a device tree to find existing installations in
    :param bool teardown_all: whether to tear down all devices in the end
    :return: roots of all found installations
    """
    try:
        roots = _find_existing_installations(devicetree)
        return roots
    except Exception:  # pylint: disable=broad-except
        log_exception_info(log.info, "failure detecting existing installations")
    finally:
        if teardown_all:
            devicetree.teardown_all()

    return []


def _find_existing_installations(devicetree):
    """Find existing GNU/Linux installations on devices from the device tree.

    :param devicetree: a device tree to find existing installations in
    :return: roots of all found installations
    """
    if not os.path.exists(util.getTargetPhysicalRoot()):
        blivet_util.makedirs(util.getTargetPhysicalRoot())

    sysroot = util.getSysroot()
    roots = []
    direct_devices = (dev for dev in devicetree.devices if dev.direct)
    for device in direct_devices:
        if not device.format.linux_native or not device.format.mountable or \
           not device.controllable:
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

        try:
            (architecture, product, version) = get_release_string()
        except ValueError:
            name = _("Linux on %s") % device.name
        else:
            # I'd like to make this finer grained, but it'd be very difficult
            # to translate.
            if not product or not version or not architecture:
                name = _("Unknown Linux")
            elif "linux" in product.lower():
                name = _("%(product)s %(version)s for %(arch)s") % \
                    {"product": product, "version": version, "arch": architecture}
            else:
                name = _("%(product)s Linux %(version)s for %(arch)s") % \
                    {"product": product, "version": version, "arch": architecture}

        (mounts, swaps) = _parse_fstab(devicetree, chroot=sysroot)
        blivet_util.umount(mountpoint=sysroot)
        if not mounts and not swaps:
            # empty /etc/fstab. weird, but I've seen it happen.
            continue
        roots.append(Root(mounts=mounts, swaps=swaps, name=name))

    return roots


def get_release_string():
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
    sysroot = util.getSysroot()

    try:
        rel_arch = blivet_util.capture_output(["arch"], root=sysroot).strip()
    except OSError:
        rel_arch = None

    filename = "%s/etc/redhat-release" % sysroot
    if os.access(filename, os.R_OK):
        (rel_name, rel_ver) = _release_from_redhat_release(filename)
    else:
        filename = "%s/etc/os-release" % sysroot
        if os.access(filename, os.R_OK):
            (rel_name, rel_ver) = _release_from_os_release(filename)

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
        except (IOError, AttributeError):
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

    return rel_name, rel_ver


def _parse_fstab(devicetree, chroot=None):
    """Parse /etc/fstab.

    :param devicetree: a device tree
    :param chroot: a path to the target OS installation
    :return: a tuple of a mount dict and swap list
    """
    if not chroot or not os.path.isdir(chroot):
        chroot = util.getSysroot()

    mounts = {}
    swaps = []
    path = "%s/etc/fstab" % chroot
    if not os.access(path, os.R_OK):
        # XXX should we raise an exception instead?
        log.info("cannot open %s for read", path)
        return mounts, swaps

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

    with open(path) as f:
        log.debug("parsing %s", path)
        for line in f.readlines():

            (line, _pound, _comment) = line.partition("#")
            fields = line.split(None, 4)

            if len(fields) < 5:
                continue

            (devspec, mountpoint, fstype, options, _rest) = fields

            # find device in the tree
            device = devicetree.resolve_device(devspec,
                                               crypt_tab=crypt_tab,
                                               blkid_tab=blkid_tab,
                                               options=options)

            if device is None:
                continue

            if fstype != "swap":
                mounts[mountpoint] = device
            else:
                swaps.append(device)

    return mounts, swaps


class Root(object):
    """A root represents an existing OS installation."""

    def __init__(self, mounts=None, swaps=None, name=None):
        """
            :keyword mounts: mountpoint dict
            :type mounts: dict (mountpoint keys and :class:`blivet.devices.StorageDevice` values)
            :keyword swaps: swap device list
            :type swaps: list of :class:`blivet.devices.StorageDevice`
            :keyword name: name for this installed OS
            :type name: str
        """
        # mountpoint key, StorageDevice value
        if not mounts:
            self.mounts = {}
        else:
            self.mounts = mounts

        # StorageDevice
        if not swaps:
            self.swaps = []
        else:
            self.swaps = swaps

        self.name = name    # eg: "Fedora Linux 16 for x86_64", "Linux on sda2"

        if not self.name and "/" in self.mounts:
            self.name = self.mounts["/"].format.uuid

    @property
    def device(self):
        return self.mounts.get("/")
