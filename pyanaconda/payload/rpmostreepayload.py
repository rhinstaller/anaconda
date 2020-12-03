# ostreepayload.py
# Deploy OSTree trees to target
#
# Copyright (C) 2012,2014,2021  Red Hat, Inc.
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
from subprocess import CalledProcessError

from pyanaconda.core import util
from pyanaconda.core.constants import PAYLOAD_TYPE_RPM_OSTREE, SOURCE_TYPE_RPM_OSTREE
from pyanaconda.core.i18n import _
from pyanaconda.modules.common.structures.rpm_ostree import RPMOSTreeConfigurationData
from pyanaconda.modules.payloads.payload.rpm_ostree.installation import safe_exec_with_redirect
from pyanaconda.progress import progressQ
from pyanaconda.payload.base import Payload
from pyanaconda.payload import utils as payload_utils
from pyanaconda.payload.errors import PayloadInstallError, FlatpakInstallError
from pyanaconda.payload.flatpak import FlatpakPayload
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.glib import format_size_full, create_new_context, Variant, GError
from pyanaconda.ui.lib.payload import get_payload, get_source, set_up_sources, tear_down_sources

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
        self._payload_proxy = get_payload(self.type)
        self._remoteOptions = None
        self._internal_mounts = []

    @property
    def type(self):
        """The DBus type of the payload."""
        return PAYLOAD_TYPE_RPM_OSTREE

    def get_source_proxy(self):
        """Get the DBus proxy of the RPM source."""
        return get_source(self.proxy, SOURCE_TYPE_RPM_OSTREE)

    @property
    def source_type(self):
        """The DBus type of the source."""
        source_proxy = self.get_source_proxy()
        return source_proxy.Type

    def _get_source_configuration(self):
        """Get the configuration of the RPM OSTree source.

        :return: an instance of RPMOSTreeConfigurationData
        """
        source_proxy = self.get_source_proxy()

        return RPMOSTreeConfigurationData.from_structure(
            source_proxy.Configuration
        )

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
        return self.proxy.IsNetworkRequired()

    def setup(self):
        """Do any payload-specific setup."""
        super().setup()
        set_up_sources(self.proxy)

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

    def install(self):
        # This is top installation method
        # TODO: Broke this to pieces when ostree payload is migrated to the DBus solution
        data = self._get_source_configuration()

        # download and install the ostree image
        self._install(data)

        # prepare mountpoints of the installed system
        self._prepare_mount_targets(data)

    def _install(self, data):
        mainctx = create_new_context()
        mainctx.push_thread_default()

        cancellable = None
        gi.require_version("OSTree", "1.0")
        gi.require_version("RpmOstree", "1.0")
        from gi.repository import OSTree, RpmOstree
        log.info("executing ostreesetup=%r", data)

        from pyanaconda.modules.payloads.payload.rpm_ostree.installation import \
            InitOSTreeFsAndRepoTask
        task = InitOSTreeFsAndRepoTask(conf.target.physical_root)
        task.run()

        # Here, we use the physical root as sysroot, because we haven't
        # yet made a deployment.
        from pyanaconda.modules.payloads.payload.rpm_ostree.installation import \
            ChangeOSTreeRemoteTask
        task = ChangeOSTreeRemoteTask(
            data,
            use_root=False,
            root=conf.target.physical_root
        )
        task.run()

        # Variable substitute the ref: https://pagure.io/atomic-wg/issue/299
        ref = RpmOstree.varsubst_basearch(data.ref)

        progressQ.send_message(_("Starting pull of %(branchName)s from %(source)s") %
                               {"branchName": ref, "source": data.remote})

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

        sysroot_file = Gio.File.new_for_path(conf.target.physical_root)
        sysroot = OSTree.Sysroot.new(sysroot_file)
        sysroot.load(cancellable)
        repo = sysroot.get_repo(None)[1]
        # We don't support resuming from interrupted installs
        repo.set_disable_fsync(True)

        try:
            repo.pull_with_options(data.remote,
                                   Variant('a{sv}', pull_opts),
                                   progress, cancellable)
        except GError as e:
            raise PayloadInstallError("Failed to pull from repository: %s" % e) from e

        log.info("ostree pull: %s", progress.get_status() or "")
        progressQ.send_message(_("Preparing deployment of %s") % (ref, ))

        # Now that we have the data pulled, delete the remote for now.
        # This will allow a remote configuration defined in the tree
        # (if any) to override what's in the kickstart.  Otherwise,
        # we'll re-add it in post.  Ideally, ostree would support a
        # pull without adding a remote, but that would get quite
        # complex.
        repo.remote_delete(data.remote, None)

        safe_exec_with_redirect("ostree",
                                ["admin", "--sysroot=" + conf.target.physical_root,
                                 "os-init", data.osname])

        admin_deploy_args = ["admin", "--sysroot=" + conf.target.physical_root, "deploy",
                             "--os=" + data.osname, data.remote + ':' + ref]

        log.info("ostree admin deploy starting")
        progressQ.send_message(_("Deployment starting: %s") % (ref, ))
        safe_exec_with_redirect("ostree", admin_deploy_args)
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
            from pyanaconda.modules.payloads.payload.rpm_ostree.installation import \
                CopyBootloaderDataTask
            task = CopyBootloaderDataTask(
                sysroot=conf.target.system_root,
                physroot=conf.target.physical_root
            )
            task.run()
        except (OSError, RuntimeError) as e:
            raise PayloadInstallError("Failed to copy bootloader data: %s" % e) from e

        mainctx.pop_thread_default()

    def _prepare_mount_targets(self, data):
        """ Prepare the ostree root """
        from pyanaconda.modules.payloads.payload.rpm_ostree.installation import \
            PrepareOSTreeMountTargetsTask
        task = PrepareOSTreeMountTargetsTask(
            sysroot=conf.target.system_root,
            physroot=conf.target.physical_root,
            source_config=data
        )
        bindmounts = task.run()
        self._internal_mounts.extend(bindmounts)

    def unsetup(self):
        """Invalidate a previously setup payload."""
        super().unsetup()

        for mount in reversed(self._internal_mounts):
            try:
                payload_utils.unmount(mount)
            except CalledProcessError as e:
                log.debug("unmounting %s failed: %s", mount, str(e))

        tear_down_sources(self.proxy)

    def post_install(self):
        super().post_install()
        data = self._get_source_configuration()

        # Following up on the "remote delete" earlier, we removed the remote from
        # /ostree/repo/config.  But we want it in /etc, so re-add it to /etc/ostree/remotes.d,
        # using the sysroot path.
        #
        # However, we ignore the case where the remote already exists, which occurs when the
        # content itself provides the remote config file.
        #
        # Note here we use the deployment as sysroot, because it's that version of /etc that we
        # want.

        from pyanaconda.modules.payloads.payload.rpm_ostree.installation import \
            ChangeOSTreeRemoteTask
        task = ChangeOSTreeRemoteTask(
            data,
            use_root=True,
            root=conf.target.system_root
        )
        task.run()

        # Handle bootloader configuration
        from pyanaconda.modules.payloads.payload.rpm_ostree.installation import \
            ConfigureBootloader
        task = ConfigureBootloader(
            sysroot=conf.target.system_root,
            is_dirinstall=conf.target.is_directory
        )
        task.run()


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
            raise PayloadInstallError("Failed to install flatpaks: %s" % e) from e

        progressQ.send_message(_("Post-installation flatpak tasks"))

        self._flatpak_payload.add_remote("fedora", "oci+https://registry.fedoraproject.org")
        self._flatpak_payload.replace_installed_refs_remote("fedora")
        self._flatpak_payload.remove_remote(FlatpakPayload.LOCAL_REMOTE_NAME)

        progressQ.send_message(_("Flatpak installation has finished"))
