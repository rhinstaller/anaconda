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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import glob
import os
from subprocess import CalledProcessError

import blivet.util
import gi
from blivet import arch

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.glib import GError, Variant, create_new_context, format_size_full
from pyanaconda.core.i18n import _
from pyanaconda.core.path import make_directories, set_system_root
from pyanaconda.core.util import execProgram, execWithRedirect
from pyanaconda.modules.common.constants.objects import BOOTLOADER, DEVICE_TREE
from pyanaconda.modules.common.constants.services import LOCALIZATION, STORAGE
from pyanaconda.modules.common.errors.installation import (
    BootloaderInstallationError,
    PayloadInstallationError,
)
from pyanaconda.modules.common.structures.storage import DeviceData
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.payloads.payload.rpm_ostree.util import have_bootupd

gi.require_version("OSTree", "1.0")
gi.require_version("Gio", "2.0")
gi.require_version("RpmOstree", "1.0")
from gi.repository import Gio, OSTree, RpmOstree

log = get_module_logger(__name__)


def safe_exec_program(cmd, argv, successful_return_codes=(0,), **kwargs):
    """Like util.execProgram, but treat errors as fatal.

    :raise: PayloadInstallationError if the call fails for any reason
    """
    rc, output = execProgram(cmd, argv, **kwargs)

    if rc not in successful_return_codes:
        raise PayloadInstallationError(
            "The command '{}' exited with the code {}:\n{}".format(" ".join([cmd] + argv), rc,
            output)
        )


def _get_ref(data):
    """Get ref or name based on source.

    OSTree container don't have ref because it's specified by the container. In that case let's
    return just url for reporting.

    :param data: OSTree source structure
    :return str: ref or name based on source
    """
    # Variable substitute the ref: https://pagure.io/atomic-wg/issue/299
    if data.is_container():
        # we don't have ref with container; there are not multiple references in one container
        return data.url
    else:
        return RpmOstree.varsubst_basearch(data.ref)


def _get_stateroot(data):
    """Get stateroot.

    The OSTree renamed old osname to stateroot for containers.

    :param data: OSTree source structure
    :return str: stateroot or osname value based on source
    """
    if data.is_container():
        # osname was renamed to stateroot so let's use the new name
        if data.stateroot:
            return data.stateroot
        else:
            # The stateroot doesn't have to be defined
            # https://github.com/ostreedev/ostree-rs-ext/pull/462/files
            # However, it's working just for a subset of calls now.
            # TODO: Remove this when all ostree commands undestarstands this
            return "default"
    else:
        return data.osname


def _get_verification_enabled(data):
    """Find out if source has enabled verification.

    OSTree sources has different names for enabled verification. This helper function
    will make the access consistent.

    :param data: OSTree source structure
    :return bool: True if verification is enabled
    """
    if data.is_container():
        return data.signature_verification_enabled
    else:
        return data.gpg_verification_enabled


class PrepareOSTreeMountTargetsTask(Task):
    """Task to prepare OSTree mount targets."""

    def __init__(self, sysroot, physroot, data):
        """Create a new task.

        :param str sysroot: a path to the system root
        :param str physroot: a path to the physical root
        :param data: an RPM OSTree configuration
        """
        super().__init__()
        self._data = data
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
        # Resolve symlinks as bind mounting over symlinks does not
        # seem to work on btrfs:
        # https://bugzilla.redhat.com/show_bug.cgi?id=2262892
        dest = os.path.realpath(dest)

        if bind_ro:
            safe_exec_program("mount", ["--bind", src, src])
            safe_exec_program("mount", ["--bind", "-o", "remount,ro", src, src])
        else:
            # Create missing directories for user defined mount points
            if not os.path.exists(dest):
                make_directories(dest)

            # Recurse for non-ro binds so we pick up sub-mounts
            # like /sys/firmware/efi/efivars.
            if recurse:
                bindopt = '--rbind'
            else:
                bindopt = '--bind'
            safe_exec_program("mount", [bindopt, src, dest])

        self._internal_mounts.append(src if bind_ro else dest)

    def _handle_var_mount_point(self, existing_mount_points):
        """Handle /var mount point

        If the admin didn't specify a mount for /var, we need to do the default ostree one.
        Otherwise, bind it.
        https://github.com/ostreedev/ostree/issues/855

        :param [] existing_mount_points: a list of existing mount points
        """
        # osname was used for ostreesetup but ostreecontainer renamed it to stateroot
        stateroot = _get_stateroot(self._data)

        var_root = '/ostree/deploy/' + stateroot + '/var'
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
        `/usr/local`, etc. We don't iterate *all* tmpfiles because we don't have the matching NSS
        configuration inside Anaconda, and we can't "chroot" to get it because that would require
        mounting the API filesystems in the target.
        """
        make_directories(self._sysroot + '/var/lib')
        self._create_tmpfiles('/var/home')
        self._create_tmpfiles('/var/roothome')
        self._create_tmpfiles('/var/opt')
        self._create_tmpfiles('/var/srv')
        self._create_tmpfiles('/var/usrlocal')
        self._create_tmpfiles('/var/mnt')
        self._create_tmpfiles('/var/media')
        self._create_tmpfiles('/var/spool')
        self._create_tmpfiles('/var/spool/mail')

    def _create_tmpfiles(self, path):
        """Run systemd-tmpfiles --create for the given path."""

        # According to systemd-tmpfiles(8), the return values are:
        #  0 → success
        # 65 → so some lines had to be ignored, but no other errors
        # 73 → configuration ok, but could not be created
        #  1 → other error
        # Therefore we ignore error 65, since this is coming from
        # the payload itself and the actual execution of it was fine

        safe_exec_program(
            "systemd-tmpfiles", [
                "--create",
                "--boot",
                "--root=" + self._sysroot,
                "--prefix=" + path
            ],
            successful_return_codes=(0, 65)
        )

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

    def _handle_boot_if_not_mount_point(self, mount_points):
        """Make sure that /boot is bind mounted into the sysroot

        """
        if "/boot" not in self._internal_mounts:
            # Should ths be ro?  I feel like the bind mount should be rw but
            # /usr is being mounted ro for ostree installs (in run()).
            self._setup_internal_bindmount('/boot', recurse=False)

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
        self._handle_boot_if_not_mount_point(mount_points)

        # And finally, do a nonrecursive bind for the sysroot
        self._setup_internal_bindmount("/", dest="/sysroot", recurse=False)

        return self._internal_mounts


class TearDownOSTreeMountTargetsTask(Task):
    """Task to tear down OSTree mount targets."""

    def __init__(self, mount_points):
        super().__init__()
        self._internal_mounts = mount_points

    @property
    def name(self):
        return "Tear down OSTree mount targets"

    def run(self):
        """Run the installation task."""
        for mount_point in reversed(self._internal_mounts):
            try:
                blivet.util.umount(mount_point)
            except (OSError, CalledProcessError) as e:
                log.debug("Unmounting %s has failed: %s", mount_point, str(e))


class CopyBootloaderDataTask(Task):
    """Task to copy OSTree bootloader data."""

    def __init__(self, sysroot, physroot):
        """Create a new task.

        :param str sysroot: a path to the system root
        :param str physroot: a path to the physical root
        """
        super().__init__()
        self._sysroot = sysroot
        self._physroot = physroot

    @property
    def name(self):
        return "Copy OSTree bootloader data"

    def run(self):
        """Run the installation task.

        :raise PayloadInstallationError: if the installation fails
        """
        try:
            self._run()
        except (OSError, RuntimeError) as e:
            raise PayloadInstallationError("Failed to copy bootloader data: {}".format(e)) from e

    def _run(self):
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
            if fname != "efi" or (is_efi and os.path.isdir(os.path.join(physboot, fname))):
                log.info("Copying bootloader data: %s", fname)
                safe_exec_program('cp', ['-r', '-p', srcpath, physboot])

            # Unfortunate hack, see https://github.com/rhinstaller/anaconda/issues/1188
            efi_grubenv_link = physboot + '/grub2/grubenv'
            if not is_efi and os.path.islink(efi_grubenv_link):
                os.unlink(efi_grubenv_link)


class InitOSTreeFsAndRepoTask(Task):
    """Task to initialize OSTree filesystem and repository."""

    def __init__(self, physroot):
        """Create a new task.

        :param str physroot: a path to the physical root
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
        safe_exec_program(
            "ostree",
            ["admin",
             "--sysroot=" + self._physroot,
             "init-fs", self._physroot]
        )


class ChangeOSTreeRemoteTask(Task):
    """Task to change OSTree remote."""

    def __init__(self, data, physroot=None, sysroot=None):
        """Create a new task.

        Specify the physical root to use it as sysroot, or the system
        root to use it as sysroot. If you specify both roots, we will
        use the system root.

        :param str physroot: a path to the physical root or None
        :param str sysroot: a path to the system root or None
        """
        super().__init__()
        self._data = data
        self._physroot = physroot
        self._sysroot = sysroot

    @property
    def name(self):
        return "Change OSTree remote"

    def run(self):
        """Run the task.

        At the beginning of the installation, we use the physical root
        as sysroot, because we haven't yet made a deployment.

        At the end of the installation, we use the system root as sysroot.
        Following up on the "remote delete" earlier, we removed the remote
        from /ostree/repo/config. But we want it in /etc, so re-add it to
        /etc/ostree/remotes.d, using the sysroot path. However, we ignore
        the case where the remote already exists, which occurs when the
        content itself provides the remote config file. Note here we use
        the deployment as sysroot, because it's that version of /etc that
        we want.
        """
        sysroot_file = Gio.File.new_for_path(
            self._sysroot or self._physroot
        )

        # Create a new object for the sysroot.
        sysroot = OSTree.Sysroot.new(sysroot_file)
        sysroot.load(cancellable=None)

        # Retrieve the OSTree repository in the sysroot.
        repo = sysroot.get_repo(None)[1]

        # We don't support resuming from interrupted installs.
        repo.set_disable_fsync(True)

        # Remote is set or it should be named as stateroot is
        remote = self._data.remote or _get_stateroot(self._data)

        # Add a remote if it doesn't exist.
        repo.remote_change(
            sysroot_file if self._sysroot else None,
            OSTree.RepoRemoteChange.ADD_IF_NOT_EXISTS,
            remote,
            self._data.url,
            self._get_remote_options(),
            cancellable=None
        )

    def _get_remote_options(self):
        """Get the remote options."""
        remote_options = {}

        if not _get_verification_enabled(self._data):
            remote_options['gpg-verify'] = Variant('b', False)

        if not conf.payload.verify_ssl:
            remote_options['tls-permissive'] = Variant('b', True)

        return Variant('a{sv}', remote_options)


class ConfigureBootloader(Task):
    """Task to configure bootloader after OSTree setup."""

    def __init__(self, sysroot):
        """Create a new task.

        :param str sysroot: a path to the system root
        """
        super().__init__()
        self._sysroot = sysroot

    @property
    def name(self):
        return "Configure OSTree bootloader"

    def run(self):
        if have_bootupd(self._sysroot):
            self._install_bootupd()
        else:
            self._move_grub_config()
        self._set_kargs()

    def _install_bootupd(self):
        bootloader = STORAGE.get_proxy(BOOTLOADER)
        device_tree = STORAGE.get_proxy(DEVICE_TREE)
        dev_data = DeviceData.from_structure(device_tree.GetDeviceData(bootloader.Drive))

        bootupdctl_args = [
                "--auto",
                "--write-uuid",
        ]

        # do not insert UEFI entry if leavebootorder was requested
        if not bootloader.KeepBootOrder:
            log.debug("Adding --update-firmware to bootupdctl call")
            bootupdctl_args.append("--update-firmware")

        rc = execWithRedirect(
            "bootupctl",
            [
                "backend",
                "install",
                *bootupdctl_args,
                "--device",
                dev_data.path,
                "/",
            ],
            root=self._sysroot
        )

        if rc:
            raise BootloaderInstallationError(
                "failed to write boot loader configuration")

    def _move_grub_config(self):
        """If using GRUB2, move its config file, also with a compatibility symlink."""
        boot_grub2_cfg = self._sysroot + '/boot/grub2/grub.cfg'
        target_grub_cfg = self._sysroot + '/boot/loader/grub.cfg'

        if os.path.isfile(boot_grub2_cfg):
            log.info("Moving %s -> %s", boot_grub2_cfg, target_grub_cfg)
            os.rename(boot_grub2_cfg, target_grub_cfg)
            os.symlink('../loader/grub.cfg', boot_grub2_cfg)

    def _set_kargs(self):
        """Set kernel arguments via OSTree-specific utils.

        OSTree owns the bootloader configuration, so here we give it an argument list computed
        from storage, architecture and such.
        """

        # Skip kernel args setup for dirinstall, there is no bootloader or rootDevice setup.
        if conf.target.is_directory:
            return

        bootloader = STORAGE.get_proxy(BOOTLOADER)
        device_tree = STORAGE.get_proxy(DEVICE_TREE)
        localization = LOCALIZATION.get_proxy()

        root_id = device_tree.GetRootDevice()
        root_data = DeviceData.from_structure(
            device_tree.GetDeviceData(root_id)
        )

        set_kargs_args = ["admin", "instutil", "set-kargs", "--merge"]
        set_kargs_args.extend(bootloader.GetArguments())
        set_kargs_args.append("root=" + device_tree.GetFstabSpec(root_id))
        set_kargs_args.append("vconsole.keymap=" + localization.VirtualConsoleKeymap)

        if root_data.type == "btrfs subvolume":
            set_kargs_args.append("rootflags=subvol=" + root_data.name)

        set_kargs_args.append("rw")

        safe_exec_program("ostree", set_kargs_args, root=self._sysroot)

        if arch.is_s390():
            # Deployment was done. Enable ostree's zipl support; this is how things are currently done in e.g.
            # https://github.com/coreos/coreos-assembler/blob/7d6fa376fc9f73625487adbb9386785bb09f1bb2/src/osbuild-manifests/coreos.osbuild.s390x.mpp.yaml#L261
            safe_exec_program(
                "ostree",
                ["config",
                 "--repo=" + self._sysroot + "/ostree/repo",
                 "set", "sysroot.bootloader", "zipl"]
            )

            for bls_path in sorted(glob.glob(self._sysroot + "/boot/loader/entries/*.conf")):
                log.info("found %s", bls_path)
                with open(bls_path, "r") as bls:
                    for line in bls.readlines():
                        if line.startswith("options "):
                            cmdline = line.split()[1]
                        if line.startswith("linux"):
                            kernel = self._sysroot + "/boot" + line.split()[1]
                        if line.startswith("initrd"):
                            initrd = self._sysroot + "/boot" + line.split()[1]
                break

            # pylint: disable=possibly-used-before-assignment
            safe_exec_program(
                "zipl",
                ["-V",
                 "-i",
                 kernel,
                 "-r",
                 initrd,
                 "-P",
                 f"\"{cmdline}\"",
                 "-t",
                 self._sysroot + "/boot"])


class DeployOSTreeTask(Task):
    """Task to deploy OSTree."""

    def __init__(self, data, physroot):
        """Create a new task.

        :param data: an RPM OSTree configuration
        :param str physroot: a path to the physical root
        """
        super().__init__()
        self._data = data
        self._physroot = physroot

    @property
    def name(self):
        return "Deploy OSTree"

    def run(self):
        ref = _get_ref(self._data)
        stateroot = _get_stateroot(self._data)

        self.report_progress(_("Deployment starting: {}").format(ref))

        if arch.is_s390():
            # Disable ostree's builtin zipl support; this is how things are currently done in e.g.
            # https://github.com/coreos/coreos-assembler/blob/7d6fa376fc9f73625487adbb9386785bb09f1bb2/src/osbuild-manifests/coreos.osbuild.s390x.mpp.yaml#L168
            safe_exec_program(
                "ostree",
                ["config",
                 "--repo=" + self._physroot + "/ostree/repo",
                 "set", "sysroot.bootloader", "none"]
            )

        safe_exec_program(
            "ostree",
            ["admin",
             "--sysroot=" + self._physroot,
             "os-init",
             stateroot]
        )

        if self._data.is_container():
            log.info("ostree image deploy starting")

            args = ["container", "image", "deploy",
                    "--sysroot=" + self._physroot,
                    "--image=" + ref]

            if self._data.transport:
                args.append("--transport=" + self._data.transport)
            if self._data.stateroot:
                args.append("--stateroot=" + self._data.stateroot)
            if not self._data.signature_verification_enabled:
                args.append("--no-signature-verification")

            safe_exec_program(
                "ostree",
                args
            )
        else:
            log.info("ostree admin deploy starting")
            safe_exec_program(
                "ostree",
                ["admin",
                 "--sysroot=" + self._physroot,
                 "deploy",
                 "--os=" + stateroot,
                 self._data.remote + ':' + ref]
            )

        log.info("ostree config set sysroot.readonly true")

        safe_exec_program(
            "ostree",
            ["config",
             "--repo=" + self._physroot + "/ostree/repo",
             "set",
             "sysroot.readonly",
             "true"]
        )

        log.info("ostree admin deploy complete")
        self.report_progress(_("Deployment complete: {}").format(ref))


class PullRemoteAndDeleteTask(Task):
    """Task to pull an OSTree remote and delete it."""

    def __init__(self, data):
        """Create a new task.

        :param data: an RPM OSTree configuration
        """
        super().__init__()
        self._data = data

    @property
    def name(self):
        return "Pull OSTree Remote"

    def run(self):
        """Pull a remote and delete it.

        All pulls in our code follow the pattern pull + delete.

        :raise: PayloadInstallationError if the pull fails
        """
        # pull requires this for some reason
        mainctx = create_new_context()
        mainctx.push_thread_default()

        cancellable = None

        # Variable substitute the ref: https://pagure.io/atomic-wg/issue/299
        ref = RpmOstree.varsubst_basearch(self._data.ref)

        self.report_progress(
            _("Starting pull of {branch_name} from {source}").format(
                branch_name=ref, source=self._data.remote
            )
        )

        progress = OSTree.AsyncProgress.new()
        progress.connect('changed', self._pull_progress_cb)

        # We use the UNTRUSTED flag as a way to help verification for potentially
        # corrupted ISOs - this way ostree will validate the checksum of objects as
        # it writes data.
        pull_opts = {'refs': Variant('as', [ref]), 'flags': Variant('i', OSTree.RepoPullFlags.UNTRUSTED)}
        # If we're doing a kickstart, we can at least use the content as a reference:
        # See <https://github.com/rhinstaller/anaconda/issues/1117>
        # The first path here is used by <https://pagure.io/fedora-lorax-templates>
        # and the second by <https://github.com/projectatomic/rpm-ostree-toolbox/>
        # FIXME extend tests to cover this part of code
        if OSTree.check_version(2017, 8):
            for path in ['/ostree/repo', '/install/ostree/repo']:
                if os.path.isdir(path + '/objects'):
                    pull_opts['localcache-repos'] = Variant('as', [path])
                    break

        sysroot_file = Gio.File.new_for_path(conf.target.physical_root)
        sysroot = OSTree.Sysroot.new(sysroot_file)
        sysroot.load(cancellable)
        repo = sysroot.get_repo(None)[1]
        # We don't support resuming from interrupted installs
        repo.set_disable_fsync(True)

        try:
            repo.pull_with_options(self._data.remote,
                                   Variant('a{sv}', pull_opts),
                                   progress, cancellable)
        except GError as e:
            raise PayloadInstallationError("Failed to pull from repository: %s" % e) from e

        log.info("ostree pull: %s", progress.get_status() or "")
        self.report_progress(_("Preparing deployment of {}").format(ref))

        # Now that we have the data pulled, delete the remote for now. This will allow a remote
        # configuration defined in the tree (if any) to override what's in the kickstart.
        # Otherwise, we'll re-add it in post.  Ideally, ostree would support a pull without adding
        # a remote, but that would get quite complex.
        repo.remote_delete(self._data.remote, None)

        mainctx.pop_thread_default()

    def _pull_progress_cb(self, async_progress):
        status = async_progress.get_status()
        outstanding_fetches = async_progress.get_uint('outstanding-fetches')

        if status:
            self.report_progress(status)
        elif outstanding_fetches > 0:
            bytes_transferred = async_progress.get_uint64('bytes-transferred')
            fetched = async_progress.get_uint('fetched')
            requested = async_progress.get_uint('requested')
            formatted_bytes = format_size_full(bytes_transferred, 0)

            if requested == 0:
                percent = 0.0
            else:
                percent = (fetched * 1.0 / requested) * 100

            self.report_progress(
                _("Receiving objects: {percent}% ({fetched}/{requested}) {bytes}").format(
                    percent=int(percent), fetched=fetched, requested=requested,
                    bytes=formatted_bytes
                )
            )
        else:
            self.report_progress(_("Writing objects"))


class SetSystemRootTask(Task):
    """The installation task for setting up the system root."""

    def __init__(self, physroot):
        """Create a new task.

        :param str physroot: a path to the physical root
        """
        super().__init__()
        self._physroot = physroot

    @property
    def name(self):
        return "Set OSTree system root"

    def run(self):
        """Reload and find the path to the new deployment."""
        sysroot_file = Gio.File.new_for_path(self._physroot)
        sysroot = OSTree.Sysroot.new(sysroot_file)
        sysroot.load(None)

        deployments = sysroot.get_deployments()
        assert len(deployments) > 0

        deployment = deployments[0]
        deployment_path = sysroot.get_deployment_directory(deployment)
        set_system_root(deployment_path.get_path())
