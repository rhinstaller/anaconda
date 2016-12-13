# ostreepayload.py
# Deploy OSTree trees to target
#
# Copyright (C) 2012,2014  Red Hat, Inc.
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
import sys
from subprocess import CalledProcessError

from pyanaconda import iutil
from pyanaconda.flags import flags
from pyanaconda.i18n import _
from pyanaconda.progress import progressQ

import gi
gi.require_version("GLib", "2.0")
gi.require_version("Gio", "2.0")

from gi.repository import GLib
from gi.repository import Gio

from blivet.size import Size
from blivet.util import umount

import logging
log = logging.getLogger("anaconda")

from pyanaconda.packaging import ArchivePayload, PayloadInstallError
import pyanaconda.errors as errors

class RPMOSTreePayload(ArchivePayload):
    """ A RPMOSTreePayload deploys a tree (possibly with layered packages) onto the target system. """
    def __init__(self, data):
        super(RPMOSTreePayload, self).__init__(data)
        self._remoteOptions = None
        self._internal_mounts = []

    @property
    def handlesBootloaderConfiguration(self):
        return True

    @property
    def kernelVersionList(self):
        # OSTree handles bootloader configuration
        return []

    @property
    def spaceRequired(self):
        # We don't have this data with OSTree at the moment
        return Size("500 MB")

    def _safeExecWithRedirect(self, cmd, argv, **kwargs):
        """Like iutil.execWithRedirect, but treat errors as fatal"""
        rc = iutil.execWithRedirect(cmd, argv, **kwargs)
        if rc != 0:
            exn = PayloadInstallError("%s %s exited with code %d" % (cmd, argv, rc))
            if errors.errorHandler.cb(exn) == errors.ERROR_RAISE:
                raise exn

    def _pullProgressCb(self, asyncProgress):
        status = asyncProgress.get_status()
        outstanding_fetches = asyncProgress.get_uint('outstanding-fetches')
        if status:
            progressQ.send_message(status)
        elif outstanding_fetches > 0:
            bytes_transferred = asyncProgress.get_uint64('bytes-transferred')
            fetched = asyncProgress.get_uint('fetched')
            requested = asyncProgress.get_uint('requested')
            formatted_bytes = GLib.format_size_full(bytes_transferred, 0)

            if requested == 0:
                percent = 0.0
            else:
                percent = (fetched*1.0 / requested) * 100

            progressQ.send_message("Receiving objects: %d%% (%d/%d) %s" % (percent, fetched, requested, formatted_bytes))
        else:
            progressQ.send_message("Writing objects")

    def _copyBootloaderData(self):
        # Copy bootloader data files from the deployment
        # checkout to the target root.  See
        # https://bugzilla.gnome.org/show_bug.cgi?id=726757 This
        # happens once, at installation time.
        # extlinux ships its modules directly in the RPM in /boot.
        # For GRUB2, Anaconda installs device.map there.  We may need
        # to add other bootloaders here though (if they can't easily
        # be fixed to *copy* data into /boot at install time, instead
        # of shipping it in the RPM).
        physboot = iutil.getTargetPhysicalRoot() + '/boot'
        ostree_boot_source = iutil.getSysroot() + '/usr/lib/ostree-boot'
        if not os.path.isdir(ostree_boot_source):
            ostree_boot_source = iutil.getSysroot() + '/boot'
        for fname in os.listdir(ostree_boot_source):
            srcpath = os.path.join(ostree_boot_source, fname)
            destpath = os.path.join(physboot, fname)

            # We're only copying directories
            if not os.path.isdir(srcpath):
                continue

            # Special handling for EFI, as it's a mount point that's
            # expected to already exist (so if we used copytree, we'd
            # traceback).  If it doesn't, we're not on a UEFI system,
            # so we don't want to copy the data.
            if fname == 'efi' and os.path.isdir(destpath):
                for subname in os.listdir(srcpath):
                    sub_srcpath = os.path.join(srcpath, subname)
                    sub_destpath = os.path.join(destpath, subname)
                    self._safeExecWithRedirect('cp', ['-r', '-p', sub_srcpath, sub_destpath])
            else:
                log.info("Copying bootloader data: " + fname)
                self._safeExecWithRedirect('cp', ['-r', '-p', srcpath, destpath])

    def install(self):
        mainctx = GLib.MainContext.new()
        mainctx.push_thread_default()

        cancellable = None
        gi.require_version("OSTree", "1.0")
        from gi.repository import OSTree
        ostreesetup = self.data.ostreesetup
        log.info("executing ostreesetup=%r", ostreesetup)

        # Initialize the filesystem - this will create the repo as well
        self._safeExecWithRedirect("ostree",
            ["admin", "--sysroot=" + iutil.getTargetPhysicalRoot(),
             "init-fs", iutil.getTargetPhysicalRoot()])

        # Here, we use the physical root as sysroot, because we haven't
        # yet made a deployment.
        sysroot_file = Gio.File.new_for_path(iutil.getTargetPhysicalRoot())
        sysroot = OSTree.Sysroot.new(sysroot_file)
        sysroot.load(cancellable)
        repo = sysroot.get_repo(None)[1]
        # We don't support resuming from interrupted installs
        repo.set_disable_fsync(True)

        self._remoteOptions = {}

        if hasattr(ostreesetup, 'nogpg') and ostreesetup.nogpg:
            self._remoteOptions['gpg-verify'] = GLib.Variant('b', False)

        if flags.noverifyssl:
            self._remoteOptions['tls-permissive'] = GLib.Variant('b', True)

        repo.remote_change(None, OSTree.RepoRemoteChange.ADD_IF_NOT_EXISTS,
                           ostreesetup.remote, ostreesetup.url,
                           GLib.Variant('a{sv}', self._remoteOptions),
                           cancellable)

        progressQ.send_message(_("Starting pull of %(branchName)s from %(source)s") % \
                               {"branchName": ostreesetup.ref, "source": ostreesetup.remote})

        progress = OSTree.AsyncProgress.new()
        progress.connect('changed', self._pullProgressCb)

        try:
            repo.pull(ostreesetup.remote, [ostreesetup.ref], 0, progress, cancellable)
        except GLib.GError as e:
            exn = PayloadInstallError("Failed to pull from repository: %s" % e)
            log.error(str(exn))
            if errors.errorHandler.cb(exn) == errors.ERROR_RAISE:
                progressQ.send_quit(1)
                iutil.ipmi_abort(scripts=self.data.scripts)
                sys.exit(1)

        progressQ.send_message(_("Preparing deployment of %s") % (ostreesetup.ref, ))

        # Now that we have the data pulled, delete the remote for now.
        # This will allow a remote configuration defined in the tree
        # (if any) to override what's in the kickstart.  Otherwise,
        # we'll re-add it in post.  Ideally, ostree would support a
        # pull without adding a remote, but that would get quite
        # complex.
        repo.remote_delete(self.data.ostreesetup.remote, None)

        self._safeExecWithRedirect("ostree",
            ["admin", "--sysroot=" + iutil.getTargetPhysicalRoot(),
             "os-init", ostreesetup.osname])

        admin_deploy_args = ["admin", "--sysroot=" + iutil.getTargetPhysicalRoot(),
                             "deploy", "--os=" + ostreesetup.osname]

        admin_deploy_args.append(ostreesetup.remote + ':' + ostreesetup.ref)

        log.info("ostree admin deploy starting")
        progressQ.send_message(_("Deployment starting: %s") % (ostreesetup.ref, ))
        self._safeExecWithRedirect("ostree", admin_deploy_args)
        log.info("ostree admin deploy complete")
        progressQ.send_message(_("Deployment complete: %s") % (ostreesetup.ref, ))

        # Reload now that we've deployed, find the path to the new deployment
        sysroot.load(None)
        deployments = sysroot.get_deployments()
        assert len(deployments) > 0
        deployment = deployments[0]
        deployment_path = sysroot.get_deployment_directory(deployment)
        iutil.setSysroot(deployment_path.get_path())

        try:
            self._copyBootloaderData()
        except (OSError, RuntimeError) as e:
            exn = PayloadInstallError("Failed to copy bootloader data: %s" % e)
            log.error(str(exn))
            if errors.errorHandler.cb(exn) == errors.ERROR_RAISE:
                progressQ.send_quit(1)
                iutil.ipmi_abort(scripts=self.data.scripts)
                sys.exit(1)

        mainctx.pop_thread_default()

    def prepareMountTargets(self, storage):
        """ Prepare the ostree root """
        ostreesetup = self.data.ostreesetup

        varroot = iutil.getTargetPhysicalRoot() + '/ostree/deploy/' + ostreesetup.osname + '/var'

        # Set up bind mounts as if we've booted the target system, so
        # that %post script work inside the target.
        binds = [(varroot, iutil.getSysroot() + '/var'),
                 (iutil.getSysroot() + '/usr', None),
                 (iutil.getTargetPhysicalRoot(), iutil.getSysroot() + "/sysroot"),
                 (iutil.getTargetPhysicalRoot() + "/boot", iutil.getSysroot() + "/boot")]

        # Bind mount filesystems from /mnt/sysimage to the ostree root; perhaps
        # in the future consider `mount --move` to make the output of `findmnt`
        # not induce blindness.
        for path in ["/dev", "/proc", "/run", "/sys"]:
            binds += [(iutil.getTargetPhysicalRoot()+path, iutil.getSysroot()+path)]

        for (src, dest) in binds:
            is_ro_bind = dest is None
            if is_ro_bind:
                self._safeExecWithRedirect("mount",
                                           ["--bind", src, src])
                self._safeExecWithRedirect("mount",
                                           ["--bind", "-o", "remount,ro", src, src])
            else:
                # Recurse for non-ro binds so we pick up sub-mounts
                # like /sys/firmware/efi/efivars.
                self._safeExecWithRedirect("mount",
                                           ["--rbind", src, dest])
            self._internal_mounts.append(src if is_ro_bind else dest)

        # Now, ensure that all other potential mount point directories such as
        # (/home) are created.  We run through the full tmpfiles here in order
        # to also allow Anaconda and %post scripts to write to directories like
        # /root.  We don't iterate *all* tmpfiles because we don't have the
        # matching NSS configuration inside Anaconda, and we can't "chroot" to
        # get it because that would require mounting the API filesystems in the
        # target.
        for varsubdir in ('home', 'roothome', 'lib/rpm', 'opt', 'srv',
                          'usrlocal', 'mnt', 'media', 'spool/mail'):
            self._safeExecWithRedirect("systemd-tmpfiles",
                                       ["--create", "--boot", "--root=" + iutil.getSysroot(),
                                        "--prefix=/var/" + varsubdir])

    def unsetup(self):
        super(RPMOSTreePayload, self).unsetup()

        for mount in reversed(self._internal_mounts):
            try:
                umount(mount)
            except CalledProcessError as e:
                log.debug("unmounting %s failed: %s", mount, str(e))

    def recreateInitrds(self):
        # For rpmostree payloads, we're replicating an initramfs from
        # a compose server, and should never be regenerating them
        # per-machine.
        pass

    def postInstall(self):
        super(RPMOSTreePayload, self).postInstall()

        gi.require_version("OSTree", "1.0")
        from gi.repository import OSTree
        cancellable = None

        # Following up on the "remote delete" above, we removed the
        # remote from /ostree/repo/config.  But we want it in /etc, so
        # re-add it to /etc/ostree/remotes.d, using the sysroot path.
        #
        # However, we ignore the case where the remote already exists,
        # which occurs when the content itself provides the remote
        # config file.

        # Note here we use the deployment as sysroot, because it's
        # that version of /etc that we want.
        sysroot_file = Gio.File.new_for_path(iutil.getSysroot())
        sysroot = OSTree.Sysroot.new(sysroot_file)
        sysroot.load(cancellable)
        repo = sysroot.get_repo(None)[1]
        repo.remote_change(sysroot_file,
                           OSTree.RepoRemoteChange.ADD_IF_NOT_EXISTS,
                           self.data.ostreesetup.remote, self.data.ostreesetup.url,
                           GLib.Variant('a{sv}', self._remoteOptions),
                           cancellable)

        boot = iutil.getSysroot() + '/boot'

        # If we're using GRUB2, move its config file, also with a
        # compatibility symlink.
        boot_grub2_cfg = boot + '/grub2/grub.cfg'
        if os.path.isfile(boot_grub2_cfg):
            boot_loader = boot + '/loader'
            target_grub_cfg = boot_loader + '/grub.cfg'
            log.info("Moving %s -> %s", boot_grub2_cfg, target_grub_cfg)
            os.rename(boot_grub2_cfg, target_grub_cfg)
            os.symlink('../loader/grub.cfg', boot_grub2_cfg)

        # Skip kernel args setup for dirinstall, there is no bootloader or rootDevice setup.
        if not flags.dirInstall:
            # OSTree owns the bootloader configuration, so here we give it
            # the argument list we computed from storage, architecture and
            # such.
            set_kargs_args = ["admin", "instutil", "set-kargs"]
            set_kargs_args.extend(self.storage.bootloader.boot_args)
            set_kargs_args.append("root=" + self.storage.root_device.fstab_spec)
            self._safeExecWithRedirect("ostree", set_kargs_args, root=iutil.getSysroot())

    def writeStorageEarly(self):
        pass
