#
# Copyright (C) 2021 Red Hat, Inc.
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

from pyanaconda.payload.errors import PayloadInstallError

from pyanaconda.core.util import execWithRedirect, mkdirChain
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.common.constants.objects import DEVICE_TREE, BOOTLOADER
from pyanaconda.modules.common.constants.services import STORAGE

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


def safe_exec_with_redirect(cmd, argv, **kwargs):
    """Like util.execWithRedirect, but treat errors as fatal.

    :raise: PayloadInstallError if the call fails for any reason
    """
    rc = execWithRedirect(cmd, argv, **kwargs)
    if rc != 0:
        raise PayloadInstallError("{} {} exited with code {}".format(cmd, argv, rc))


class PrepareOSTreeMountTargetsTask(Task):
    """Task to prepare OSTree mount targets."""

    def __init__(self, sysroot, physroot, source_config):
        super().__init__()
        self._source_config = source_config
        self._sysroot = sysroot
        self._physroot = physroot
        self._internal_mounts = []

    @property
    def name(self):
        return "Prepare OSTree mount targets"

    def _setup_internal_bindmount(self, src, dest=None,
                                  src_physical=True,
                                  bind_ro=False,
                                  recurse=True):
        """Internal API for setting up bind mounts between the physical root and sysroot

        Also ensures we track them in self._internal_mounts so we can cleanly unmount them.

        Currently, blivet sets up mounts in the physical root. We used to unmount them and remount
        them in the sysroot, but since 664ef7b43f9102aa9332d0db5b7d13f8ece436f0 we now just set up
        bind mounts.

        :param src: Source path, will be prefixed with physical or sysroot
        :param dest: Destination, will be prefixed with sysroot (defaults to same as src)
        :param src_physical: Prefix src with physical root
        :param bind_ro: Make mount read-only
        :param recurse: Use --rbind to recurse, otherwise plain --bind
        """
        # Default to the same basename
        if dest is None:
            dest = src

        # Almost all of our mounts go from physical to sysroot
        if src_physical:
            src = self._physroot + src
        else:
            src = self._sysroot + src

        # Canonicalize dest to the full path
        dest = self._sysroot + dest

        if bind_ro:
            safe_exec_with_redirect("mount", ["--bind", src, src])
            safe_exec_with_redirect("mount", ["--bind", "-o", "remount,ro", src, src])
        else:
            # Recurse for non-ro binds so we pick up sub-mounts
            # like /sys/firmware/efi/efivars.
            if recurse:
                bindopt = '--rbind'
            else:
                bindopt = '--bind'
            safe_exec_with_redirect("mount", [bindopt, src, dest])

        self._internal_mounts.append(src if bind_ro else dest)

    def _handle_var_mount_point(self, existing_mount_points):
        """Handle /var mount point

        If the admin didn't specify a mount for /var, we need to do the default ostree one.
        Otherwise, bind it.
        https://github.com/ostreedev/ostree/issues/855

        :param [] existing_mount_points: a list of existing mount points
        """
        var_root = '/ostree/deploy/' + self._source_config.osname + '/var'
        if existing_mount_points.get("/var") is None:
            self._setup_internal_bindmount(var_root, dest='/var', recurse=False)
        else:
            self._setup_internal_bindmount('/var', recurse=False)

    def _fill_var_subdirectories(self):
        """Add subdirectories to /var

        Once we have /var, start filling in any directories that may be required later there.
        We explicitly make /var/lib, since systemd-tmpfiles doesn't have a --prefix-only=/var/lib.
        We rely on 80-setfilecons.ks to set the label correctly.

        Next, run tmpfiles to make subdirectories of /var. We need this for both mounts like
        /home (really /var/home) and %post scripts might want to write to e.g. `/srv`, `/root`,
        `/usr/local`, etc. The /var/lib/rpm symlink is also critical for having e.g. `rpm -qa`
        work in %post. We don't iterate *all* tmpfiles because we don't have the matching NSS
        configuration inside Anaconda, and we can't "chroot" to get it because that would require
        mounting the API filesystems in the target.
        """
        mkdirChain(self._sysroot + '/var/lib')

        for varsubdir in ('home', 'roothome', 'lib/rpm', 'opt', 'srv',
                          'usrlocal', 'mnt', 'media', 'spool', 'spool/mail'):
            safe_exec_with_redirect("systemd-tmpfiles",
                                    ["--create", "--boot", "--root=" + self._sysroot,
                                     "--prefix=/var/" + varsubdir])

    def _handle_api_mount_points(self):
        """Handle API mount points

        Explicitly do API (sysfs, tmpfs,...) mounts; some of these may be tracked by blivet, but
        we'll skip them later.
        """
        for path in ("/dev", "/proc", "/run", "/sys"):
            self._setup_internal_bindmount(path)

    def _handle_other_mount_points(self, existing_mount_points):
        """Handle other mount points

        Handle mounts like /boot (except avoid /boot/efi; we just need the  toplevel), and any
        admin-specified points like /home (really /var/home). Note we already handled /var
        earlier. Avoid recursion since sub-mounts will be in the list too.  We sort by length as
        a crude hack to try to simulate the tree relationship; it looks like this is handled in
        blivet in a different way.

        :param [] existing_mount_points: a list of existing mount points
        """
        for mount in sorted(existing_mount_points, key=len):
            if mount in ('/', '/var', "/dev", "/proc", "/run", "/sys"):
                continue
            self._setup_internal_bindmount(mount, recurse=False)

    def run(self):
        """Run the task.

        :return: list of bindmounts created for internal use
        :rtype: list of str
        """
        device_tree = STORAGE.get_proxy(DEVICE_TREE)
        mount_points = device_tree.GetMountPoints()

        # Make /usr readonly like ostree does at runtime normally
        self._setup_internal_bindmount('/usr', bind_ro=True, src_physical=False)

        self._handle_api_mount_points()

        self._handle_var_mount_point(mount_points)
        self._fill_var_subdirectories()

        self._handle_other_mount_points(mount_points)

        # And finally, do a nonrecursive bind for the sysroot
        self._setup_internal_bindmount("/", dest="/sysroot", recurse=False)

        return self._internal_mounts


class CopyBootloaderDataTask(Task):
    """Task to copy OSTree bootloader data."""

    def __init__(self, sysroot, physroot):
        super().__init__()
        self._sysroot = sysroot
        self._physroot = physroot

    @property
    def name(self):
        return "Copy OSTree bootloader data"

    def run(self):
        """Copy bootloader data files from the deployment checkout to the target root.

        See https://bugzilla.gnome.org/show_bug.cgi?id=726757 This happens once, at installation
        time. extlinux ships its modules directly in the RPM in /boot. For GRUB2, Anaconda installs
        device.map there.  We may need to add other bootloaders here though (if they can't easily
        be fixed to *copy* data into /boot at install time, instead of shipping it in the RPM).
        """
        bootloader = STORAGE.get_proxy(BOOTLOADER)
        is_efi = bootloader.IsEFI()

        physboot = self._physroot + '/boot'
        ostree_boot_source = self._sysroot + '/usr/lib/ostree-boot'

        if not os.path.isdir(ostree_boot_source):
            ostree_boot_source = self._sysroot + '/boot'

        for fname in os.listdir(ostree_boot_source):
            srcpath = os.path.join(ostree_boot_source, fname)

            # We're only copying directories
            if not os.path.isdir(srcpath):
                continue

            # Special handling for EFI; first, we only want to copy the data if the system is
            # actually EFI (simulating grub2-efi being installed).  Second, as it's a mount point
            # that's expected to already exist (so if we used copytree, we'd traceback). If it
            # doesn't, we're not on a UEFI system, so we don't want to copy the data.
            if not fname == 'efi' or is_efi and os.path.isdir(os.path.join(physboot, fname)):
                log.info("Copying bootloader data: %s", fname)
                safe_exec_with_redirect('cp', ['-r', '-p', srcpath, physboot])

            # Unfortunate hack, see https://github.com/rhinstaller/anaconda/issues/1188
            efi_grubenv_link = physboot + '/grub2/grubenv'
            if not is_efi and os.path.islink(efi_grubenv_link):
                os.unlink(efi_grubenv_link)


class InitOSTreeFsAndRepoTask(Task):
    """Task to initialize OSTree filesystem and repository."""

    def __init__(self, physroot):
        """Create a new task.

        :param str sysroot: path to the physical root
        """
        super().__init__()
        self._physroot = physroot

    @property
    def name(self):
        return "Initialize OSTree file system and repository"

    def run(self):
        """Initialize the filesystem.

        This will create the repository as well.
        """
        safe_exec_with_redirect(
            "ostree",
            ["admin",
             "--sysroot=" + self._physroot,
             "init-fs", self._physroot]
        )
