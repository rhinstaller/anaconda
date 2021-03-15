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

import pyanaconda.errors as errors
from pyanaconda.core import util
from pyanaconda.core.constants import PAYLOAD_TYPE_RPM_OSTREE
from pyanaconda.core.i18n import _
from pyanaconda.localization import get_locale_map_from_ostree, strip_codeset_and_modifier
from pyanaconda.modules.common.constants.objects import BOOTLOADER, DEVICE_TREE
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.progress import progressQ
from pyanaconda.payload.base import Payload
from pyanaconda.payload import utils as payload_utils
from pyanaconda.payload.errors import PayloadInstallError, FlatpakInstallError
from pyanaconda.payload.flatpak import FlatpakPayload
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.glib import format_size_full, create_new_context, Variant, GError

from blivet.size import Size

import gi
gi.require_version("Gio", "2.0")
from gi.repository import Gio

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class RPMOSTreePayload(Payload):
    """ A RPMOSTreePayload deploys a tree (possibly with layered packages)
    onto the target system."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._remoteOptions = None
        self._internal_mounts = []
        self._locale_map = None

    @property
    def type(self):
        """The DBus type of the payload."""
        return PAYLOAD_TYPE_RPM_OSTREE

    @property
    def handles_bootloader_configuration(self):
        return True

    @property
    def kernel_version_list(self):
        # OSTree handles bootloader configuration
        return []

    @property
    def space_required(self):
        # We don't have this data with OSTree at the moment
        return Size("500 MB")

    @property
    def needs_network(self):
        """Test ostree repository if it requires network."""
        return not (self.data.ostreesetup.url and self.data.ostreesetup.url.startswith("file://"))

    def _get_locale_map(self):
        """Return a map of supported languages and locales."""
        if self._locale_map is None:
            self._locale_map = get_locale_map_from_ostree(
                self.data.ostreesetup.url,
                self.data.ostreesetup.ref
            )

        return self._locale_map

    def is_language_supported(self, language):
        """Is the given language supported by the payload?"""
        if not conf.payload.check_supported_locales:
            return True

        return language in self._get_locale_map()

    def is_locale_supported(self, language, locale):
        """Is the given locale supported by the payload?"""
        if not conf.payload.check_supported_locales:
            return True

        locale_map = self._get_locale_map()
        locale = strip_codeset_and_modifier(locale)
        return locale in locale_map.get(language, [])

    def _safe_exec_with_redirect(self, cmd, argv, **kwargs):
        """Like util.execWithRedirect, but treat errors as fatal"""
        rc = util.execWithRedirect(cmd, argv, **kwargs)
        if rc != 0:
            exn = PayloadInstallError("%s %s exited with code %d" % (cmd, argv, rc))
            if errors.errorHandler.cb(exn) == errors.ERROR_RAISE:
                raise exn

    def _pull_progress_cb(self, asyncProgress):
        status = asyncProgress.get_status()
        outstanding_fetches = asyncProgress.get_uint('outstanding-fetches')
        if status:
            progressQ.send_message(status)
        elif outstanding_fetches > 0:
            bytes_transferred = asyncProgress.get_uint64('bytes-transferred')
            fetched = asyncProgress.get_uint('fetched')
            requested = asyncProgress.get_uint('requested')
            formatted_bytes = format_size_full(bytes_transferred, 0)

            if requested == 0:
                percent = 0.0
            else:
                percent = (fetched * 1.0 / requested) * 100

            progressQ.send_message(_("Receiving objects: %(percent)d%% "
                                     "(%(fetched)d/%(requested)d) %(bytes)s") %
                                   {"percent": percent, "fetched": fetched,
                                    "requested": requested, "bytes": formatted_bytes}
                                   )
        else:
            progressQ.send_message(_("Writing objects"))

    def _copy_bootloader_data(self):
        # Copy bootloader data files from the deployment
        # checkout to the target root.  See
        # https://bugzilla.gnome.org/show_bug.cgi?id=726757 This
        # happens once, at installation time.
        # extlinux ships its modules directly in the RPM in /boot.
        # For GRUB2, Anaconda installs device.map there.  We may need
        # to add other bootloaders here though (if they can't easily
        # be fixed to *copy* data into /boot at install time, instead
        # of shipping it in the RPM).
        bootloader = STORAGE.get_proxy(BOOTLOADER)
        is_efi = bootloader.IsEFI()
        physboot = conf.target.physical_root + '/boot'
        ostree_boot_source = conf.target.system_root + '/usr/lib/ostree-boot'
        if not os.path.isdir(ostree_boot_source):
            ostree_boot_source = conf.target.system_root + '/boot'
        for fname in os.listdir(ostree_boot_source):
            srcpath = os.path.join(ostree_boot_source, fname)
            destpath = os.path.join(physboot, fname)

            # We're only copying directories
            if not os.path.isdir(srcpath):
                continue

            # Special handling for EFI; first, we only want to copy
            # the data if the system is actually EFI (simulating grub2-efi
            # being installed).  Second, as it's a mount point that's
            # expected to already exist (so if we used copytree, we'd
            # traceback).  If it doesn't, we're not on a UEFI system,
            # so we don't want to copy the data.
            if fname == 'efi':
                if is_efi:
                    for subname in os.listdir(srcpath):
                        sub_srcpath = os.path.join(srcpath, subname)
                        sub_destpath = os.path.join(destpath, subname)
                        self._safe_exec_with_redirect('cp',
                                                      ['-r', '-p', sub_srcpath, sub_destpath])
            else:
                log.info("Copying bootloader data: %s", fname)
                self._safe_exec_with_redirect('cp', ['-r', '-p', srcpath, destpath])

            # Unfortunate hack, see https://github.com/rhinstaller/anaconda/issues/1188
            efi_grubenv_link = physboot + '/grub2/grubenv'
            if not is_efi and os.path.islink(efi_grubenv_link):
                os.unlink(efi_grubenv_link)

    def install(self):
        # This is top installation method
        # TODO: Broke this to pieces when ostree payload is migrated to the DBus solution

        # download and install the ostree image
        self._install()

        # prepare mountpoints of the installed system
        self._prepare_mount_targets()

    def _install(self):
        mainctx = create_new_context()
        mainctx.push_thread_default()

        cancellable = None
        gi.require_version("OSTree", "1.0")
        gi.require_version("RpmOstree", "1.0")
        from gi.repository import OSTree, RpmOstree
        ostreesetup = self.data.ostreesetup
        log.info("executing ostreesetup=%r", ostreesetup)

        # Initialize the filesystem - this will create the repo as well
        self._safe_exec_with_redirect("ostree",
                                      ["admin", "--sysroot=" + conf.target.physical_root,
                                       "init-fs", conf.target.physical_root])

        # Here, we use the physical root as sysroot, because we haven't
        # yet made a deployment.
        sysroot_file = Gio.File.new_for_path(conf.target.physical_root)
        sysroot = OSTree.Sysroot.new(sysroot_file)
        sysroot.load(cancellable)
        repo = sysroot.get_repo(None)[1]
        # We don't support resuming from interrupted installs
        repo.set_disable_fsync(True)

        self._remoteOptions = {}

        if hasattr(ostreesetup, 'nogpg') and ostreesetup.nogpg:
            self._remoteOptions['gpg-verify'] = Variant('b', False)

        if not conf.payload.verify_ssl:
            self._remoteOptions['tls-permissive'] = Variant('b', True)

        repo.remote_change(None, OSTree.RepoRemoteChange.ADD_IF_NOT_EXISTS,
                           ostreesetup.remote, ostreesetup.url,
                           Variant('a{sv}', self._remoteOptions),
                           cancellable)

        # Variable substitute the ref: https://pagure.io/atomic-wg/issue/299
        ref = RpmOstree.varsubst_basearch(ostreesetup.ref)

        progressQ.send_message(_("Starting pull of %(branchName)s from %(source)s") %
                               {"branchName": ref, "source": ostreesetup.remote})

        progress = OSTree.AsyncProgress.new()
        progress.connect('changed', self._pull_progress_cb)

        pull_opts = {'refs': Variant('as', [ref])}
        # If we're doing a kickstart, we can at least use the content as a reference:
        # See <https://github.com/rhinstaller/anaconda/issues/1117>
        # The first path here is used by <https://pagure.io/fedora-lorax-templates>
        # and the second by <https://github.com/projectatomic/rpm-ostree-toolbox/>
        if OSTree.check_version(2017, 8):
            for path in ['/ostree/repo', '/install/ostree/repo']:
                if os.path.isdir(path + '/objects'):
                    pull_opts['localcache-repos'] = Variant('as', [path])
                    break

        try:
            repo.pull_with_options(ostreesetup.remote,
                                   Variant('a{sv}', pull_opts),
                                   progress, cancellable)
        except GError as e:
            exn = PayloadInstallError("Failed to pull from repository: %s" % e)
            log.error(str(exn))
            if errors.errorHandler.cb(exn) == errors.ERROR_RAISE:
                progressQ.send_quit(1)
                util.ipmi_abort(scripts=self.data.scripts)
                sys.exit(1)

        log.info("ostree pull: %s", progress.get_status() or "")
        progressQ.send_message(_("Preparing deployment of %s") % (ref, ))

        # Now that we have the data pulled, delete the remote for now.
        # This will allow a remote configuration defined in the tree
        # (if any) to override what's in the kickstart.  Otherwise,
        # we'll re-add it in post.  Ideally, ostree would support a
        # pull without adding a remote, but that would get quite
        # complex.
        repo.remote_delete(self.data.ostreesetup.remote, None)

        self._safe_exec_with_redirect("ostree",
                                      ["admin", "--sysroot=" + conf.target.physical_root,
                                       "os-init", ostreesetup.osname])

        admin_deploy_args = ["admin", "--sysroot=" + conf.target.physical_root,
                             "deploy", "--os=" + ostreesetup.osname]

        admin_deploy_args.append(ostreesetup.remote + ':' + ref)

        log.info("ostree admin deploy starting")
        progressQ.send_message(_("Deployment starting: %s") % (ref, ))
        self._safe_exec_with_redirect("ostree", admin_deploy_args)
        log.info("ostree admin deploy complete")
        progressQ.send_message(_("Deployment complete: %s") % (ref, ))

        # Reload now that we've deployed, find the path to the new deployment
        sysroot.load(None)
        deployments = sysroot.get_deployments()
        assert len(deployments) > 0
        deployment = deployments[0]
        deployment_path = sysroot.get_deployment_directory(deployment)
        util.set_system_root(deployment_path.get_path())

        try:
            self._copy_bootloader_data()
        except (OSError, RuntimeError) as e:
            exn = PayloadInstallError("Failed to copy bootloader data: %s" % e)
            log.error(str(exn))
            if errors.errorHandler.cb(exn) == errors.ERROR_RAISE:
                progressQ.send_quit(1)
                util.ipmi_abort(scripts=self.data.scripts)
                sys.exit(1)

        mainctx.pop_thread_default()

    def _setup_internal_bindmount(self, src, dest=None,
                                  src_physical=True,
                                  bind_ro=False,
                                  recurse=True):
        """Internal API for setting up bind mounts between the physical root and
           sysroot, also ensures we track them in self._internal_mounts so we can
           cleanly unmount them.

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
            src = conf.target.physical_root + src
        else:
            src = conf.target.system_root + src
        # Canonicalize dest to the full path
        dest = conf.target.system_root + dest
        if bind_ro:
            self._safe_exec_with_redirect("mount",
                                          ["--bind", src, src])
            self._safe_exec_with_redirect("mount",
                                          ["--bind", "-o", "remount,ro", src, src])
        else:
            # Recurse for non-ro binds so we pick up sub-mounts
            # like /sys/firmware/efi/efivars.
            if recurse:
                bindopt = '--rbind'
            else:
                bindopt = '--bind'
            self._safe_exec_with_redirect("mount",
                                          [bindopt, src, dest])
        self._internal_mounts.append(src if bind_ro else dest)

    def _prepare_mount_targets(self):
        """ Prepare the ostree root """
        ostreesetup = self.data.ostreesetup
        mount_points = payload_utils.get_mount_points()

        # Currently, blivet sets up mounts in the physical root.
        # We used to unmount them and remount them in the sysroot, but
        # since 664ef7b43f9102aa9332d0db5b7d13f8ece436f0 we now just set up
        # bind mounts.

        # Make /usr readonly like ostree does at runtime normally
        self._setup_internal_bindmount('/usr', bind_ro=True, src_physical=False)

        # Explicitly do API mounts; some of these may be tracked by blivet, but
        # we'll skip them below.
        api_mounts = ["/dev", "/proc", "/run", "/sys"]
        for path in api_mounts:
            self._setup_internal_bindmount(path)

        # Handle /var; if the admin didn't specify a mount for /var, we need
        # to do the default ostree one.
        # https://github.com/ostreedev/ostree/issues/855
        var_root = '/ostree/deploy/' + ostreesetup.osname + '/var'
        if mount_points.get("/var") is None:
            self._setup_internal_bindmount(var_root, dest='/var', recurse=False)
        else:
            # Otherwise, bind it
            self._setup_internal_bindmount('/var', recurse=False)

        # Now that we have /var, start filling in any directories that may be
        # required later there. We explicitly make /var/lib, since
        # systemd-tmpfiles doesn't have a --prefix-only=/var/lib. We rely on
        # 80-setfilecons.ks to set the label correctly.
        util.mkdirChain(conf.target.system_root + '/var/lib')
        # Next, run tmpfiles to make subdirectories of /var. We need this for
        # both mounts like /home (really /var/home) and %post scripts might
        # want to write to e.g. `/srv`, `/root`, `/usr/local`, etc. The
        # /var/lib/rpm symlink is also critical for having e.g. `rpm -qa` work
        # in %post. We don't iterate *all* tmpfiles because we don't have the
        # matching NSS configuration inside Anaconda, and we can't "chroot" to
        # get it because that would require mounting the API filesystems in the
        # target.
        cmd = "systemd-tmpfiles"
        for varsubdir in ('home', 'roothome', 'lib/rpm', 'opt', 'srv',
                          'usrlocal', 'mnt', 'media', 'spool', 'spool/mail'):
            argv = ["--create", "--boot", "--root=" + conf.target.system_root,
                    "--prefix=/var/" + varsubdir]

            rc = util.execWithRedirect(cmd, argv)

            # According to systemd-tmpfiles(8), the return values are:
            #  0 → success
            # 65 → so some lines had to be ignored, but no other errors
            # 73 → configuration ok, but could not be created
            #  1 → other error
            # Therefore we ignore error 65, since this is coming from
            # the payload itself and the actual execution of it was fine
            if rc not in [0, 65]:
                exn = PayloadInstallError(
                    "{} failed for /var/{}".format(cmd, varsubdir))
                if errors.errorHandler.cb(exn) == errors.ERROR_RAISE:
                    raise exn

        # Handle mounts like /boot (except avoid /boot/efi; we just need the
        # toplevel), and any admin-specified points like /home (really
        # /var/home). Note we already handled /var above. Avoid recursion since
        # sub-mounts will be in the list too.  We sort by length as a crude
        # hack to try to simulate the tree relationship; it looks like this
        # is handled in blivet in a different way.
        for mount in sorted(mount_points, key=len):
            if mount in ('/', '/var') or mount in api_mounts:
                continue
            self._setup_internal_bindmount(mount, recurse=False)

        # And finally, do a nonrecursive bind for the sysroot
        self._setup_internal_bindmount("/", dest="/sysroot", recurse=False)

    def unsetup(self):
        super().unsetup()

        for mount in reversed(self._internal_mounts):
            try:
                payload_utils.unmount(mount)
            except CalledProcessError as e:
                log.debug("unmounting %s failed: %s", mount, str(e))

    def recreate_initrds(self):
        # For rpmostree payloads, we're replicating an initramfs from
        # a compose server, and should never be regenerating them
        # per-machine.
        pass

    def post_install(self):
        super().post_install()

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
        sysroot_file = Gio.File.new_for_path(conf.target.system_root)
        sysroot = OSTree.Sysroot.new(sysroot_file)
        sysroot.load(cancellable)
        repo = sysroot.get_repo(None)[1]
        repo.remote_change(sysroot_file,
                           OSTree.RepoRemoteChange.ADD_IF_NOT_EXISTS,
                           self.data.ostreesetup.remote, self.data.ostreesetup.url,
                           Variant('a{sv}', self._remoteOptions),
                           cancellable)

        boot = conf.target.system_root + '/boot'

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
        if not conf.target.is_directory:
            # OSTree owns the bootloader configuration, so here we give it
            # the argument list we computed from storage, architecture and
            # such.
            bootloader = STORAGE.get_proxy(BOOTLOADER)
            device_tree = STORAGE.get_proxy(DEVICE_TREE)
            root_device = device_tree.GetRootDevice()

            set_kargs_args = ["admin", "instutil", "set-kargs"]
            set_kargs_args.extend(bootloader.GetArguments())
            set_kargs_args.append("root=" + device_tree.GetFstabSpec(root_device))
            self._safe_exec_with_redirect("ostree", set_kargs_args, root=conf.target.system_root)


class RPMOSTreePayloadWithFlatpaks(RPMOSTreePayload):

    def __init__(self, *args, **kwargs):
        """Variant of rpmostree payload with flatpak support.

        This variant will be used if flatpaks are available for system.
        """
        super().__init__(*args, **kwargs)

        self._flatpak_payload = FlatpakPayload(conf.target.system_root)
        # Initialize temporal repo to enable reading of the remote
        self._flatpak_payload.initialize_with_path("/var/tmp/anaconda-flatpak-temp")

    @property
    def space_required(self):
        return super().space_required + Size(self._flatpak_payload.get_required_size())

    def install(self):
        # install ostree payload first
        super().install()

        # then flatpaks
        self._flatpak_install()

    def _flatpak_install(self):
        # Install flatpak from the local source on SilverBlue
        progressQ.send_message(_("Starting Flatpak installation"))
        # Cleanup temporal repo created in the __init__
        self._flatpak_payload.cleanup()

        # Initialize new repo on the installed system
        self._flatpak_payload.initialize_with_system_path()

        try:
            self._flatpak_payload.install_all()
        except FlatpakInstallError as e:
            exn = PayloadInstallError("Failed to install flatpaks: %s" % e)
            log.error(str(exn))
            if errors.errorHandler.cb(exn) == errors.ERROR_RAISE:
                progressQ.send_quit(1)
                util.ipmi_abort(scripts=self.data.scripts)
                sys.exit(1)

        progressQ.send_message(_("Post-installation flatpak tasks"))

        self._flatpak_payload.add_remote("fedora", "oci+https://registry.fedoraproject.org")
        self._flatpak_payload.replace_installed_refs_remote("fedora")
        self._flatpak_payload.remove_remote(FlatpakPayload.LOCAL_REMOTE_NAME)

        progressQ.send_message(_("Flatpak installation has finished"))
