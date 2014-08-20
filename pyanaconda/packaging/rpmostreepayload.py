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
# Red Hat Author(s): Colin Walters <walters@redhat.com>
#

import os
import shutil

from pyanaconda import iutil
from pyanaconda.i18n import _
from pyanaconda.progress import progressQ
from gi.repository import GLib
from gi.repository import Gio

from blivet.size import Size

import logging
log = logging.getLogger("anaconda")

from pyanaconda.packaging import ArchivePayload, PayloadInstallError
import pyanaconda.errors as errors

class RPMOSTreePayload(ArchivePayload):
    """ A RPMOSTreePayload deploys a tree (possibly with layered packages) onto the target system. """
    def __init__(self, data):
        super(RPMOSTreePayload, self).__init__(data)

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

    def install(self):
        cancellable = None
        from gi.repository import OSTree
        ostreesetup = self.data.ostreesetup
        log.info("executing ostreesetup=%r", ostreesetup)

        # Initialize the filesystem - this will create the repo as well
        self._safeExecWithRedirect("ostree",
            ["admin", "--sysroot=" + iutil.getTargetPhysicalRoot(),
             "init-fs", iutil.getTargetPhysicalRoot()])

        repo_arg = "--repo=" + iutil.getTargetPhysicalRoot() + '/ostree/repo'

        # Set up the chosen remote
        remote_args = [repo_arg, "remote", "add"]
        if ((hasattr(ostreesetup, 'noGpg') and ostreesetup.noGpg) or
            (hasattr(ostreesetup, 'nogpg') and ostreesetup.nogpg)):
            remote_args.append("--set=gpg-verify=false")
        remote_args.extend([ostreesetup.remote,
                            ostreesetup.url])
        self._safeExecWithRedirect("ostree", remote_args)

        sysroot_path = Gio.File.new_for_path(iutil.getTargetPhysicalRoot())
        sysroot = OSTree.Sysroot.new(sysroot_path)
        sysroot.load(cancellable)

        repo = sysroot.get_repo(None)[1]
        repo.set_disable_fsync(True)
        progressQ.send_message(_("Starting pull of %(branchName)s from %(source)s") % \
                               {"branchName": ostreesetup.ref, "source": ostreesetup.remote})

        progress = OSTree.AsyncProgress.new()
        progress.connect('changed', self._pullProgressCb)
        repo.pull(ostreesetup.remote, [ostreesetup.ref], 0, progress, cancellable)

        progressQ.send_message(_("Preparing deployment of %s") % (ostreesetup.ref, ))

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

        # Copy specific bootloader data files from the deployment
        # checkout to the target root.  See
        # https://bugzilla.gnome.org/show_bug.cgi?id=726757 This
        # happens once, at installation time.
        # extlinux ships its modules directly in the RPM in /boot.
        # For GRUB2, Anaconda installs device.map there.  We may need
        # to add other bootloaders here though (if they can't easily
        # be fixed to *copy* data into /boot at install time, instead
        # of shipping it in the RPM).
        physboot = iutil.getTargetPhysicalRoot() + '/boot'
        sysboot = iutil.getSysroot() + '/boot'
        for fname in ['extlinux', 'grub2']:
            srcpath = os.path.join(sysboot, fname)
            if os.path.isdir(srcpath):
                log.info("Copying bootloader data: " + fname)
                shutil.copytree(srcpath, os.path.join(physboot, fname))

    def prepareMountTargets(self, storage):
        ostreesetup = self.data.ostreesetup

        varroot = iutil.getTargetPhysicalRoot() + '/ostree/deploy/' + ostreesetup.osname + '/var'

        # Set up bind mounts as if we've booted the target system, so
        # that %post script work inside the target.
        binds = [(iutil.getTargetPhysicalRoot(),
                  iutil.getSysroot() + '/sysroot'),
                 (varroot,
                  iutil.getSysroot() + '/var'),
                 (iutil.getSysroot() + '/usr', None)]

        for (src, dest) in binds:
            self._safeExecWithRedirect("mount",
                                       ["--bind", src, dest if dest else src])
            if dest is None:
                self._safeExecWithRedirect("mount",
                                           ["--bind", "-o", "ro", src, src])

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

    def recreateInitrds(self, force=False):
        # For rpmostree payloads, we're replicating an initramfs from
        # a compose server, and should never be regenerating them
        # per-machine.
        pass

    def postInstall(self):
        super(RPMOSTreePayload, self).postInstall()

        physboot = iutil.getTargetPhysicalRoot() + '/boot'

        # If we're using extlinux, rename extlinux.conf to
        # syslinux.cfg, since that's what OSTree knows about.
        # syslinux upstream supports both, but I'd say that upstream
        # using syslinux.cfg is somewhat preferred.
        physboot_extlinux = physboot + '/extlinux'
        if os.path.isdir(physboot_extlinux):
            physboot_syslinux = physboot + '/syslinux'
            physboot_loader = physboot + '/loader'
            assert os.path.isdir(physboot_loader)
            orig_extlinux_conf = physboot_extlinux + '/extlinux.conf'
            target_syslinux_cfg = physboot_loader + '/syslinux.cfg'
            log.info("Moving %s -> %s", orig_extlinux_conf, target_syslinux_cfg)
            os.rename(orig_extlinux_conf, target_syslinux_cfg)
            # A compatibility bit for OSTree
            os.mkdir(physboot_syslinux)
            os.symlink('../loader/syslinux.cfg', physboot_syslinux + '/syslinux.cfg')
            # And *also* tell syslinux that the config is really in /boot/loader
            os.symlink('loader/syslinux.cfg', physboot + '/syslinux.cfg')

        # OSTree owns the bootloader configuration, so here we give it
        # the argument list we computed from storage, architecture and
        # such.
        set_kargs_args = ["admin", "--sysroot=" + iutil.getTargetPhysicalRoot(),
                          "instutil", "set-kargs"]
        set_kargs_args.extend(self.storage.bootloader.boot_args)
        set_kargs_args.append("root=" + self.storage.rootDevice.fstabSpec)
        self._safeExecWithRedirect("ostree", set_kargs_args)
