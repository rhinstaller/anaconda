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

from subprocess import CalledProcessError

from pyanaconda.core.constants import PAYLOAD_TYPE_RPM_OSTREE, SOURCE_TYPE_RPM_OSTREE, SOURCE_TYPE_RPM_OSTREE_CONTAINER
from pyanaconda.modules.common.structures.rpm_ostree import RPMOSTreeContainerConfigurationData
from pyanaconda.progress import progressQ
from pyanaconda.payload.base import Payload
from pyanaconda.payload import utils as payload_utils
from pyanaconda.payload.errors import PayloadInstallError
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.ui.lib.payload import get_payload, get_source, set_up_sources, tear_down_sources

from blivet.size import Size

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

        :return: an instance of RPMOSTreeContainerConfigurationData
        """
        source_proxy = self.get_source_proxy()

        if self.source_type == SOURCE_TYPE_RPM_OSTREE_CONTAINER:
            return RPMOSTreeContainerConfigurationData.from_structure(
                source_proxy.Configuration
            )
        else:
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

    def _progress_cb(self, step, message):
        """Callback for task progress reporting."""
        progressQ.send_message(message)

    def install(self):
        # This is top installation method
        # TODO: Broke this to pieces when ostree payload is migrated to the DBus solution
        data = self._get_source_configuration()

        # download and install the ostree image
        self._install(data)

        # prepare mountpoints of the installed system
        self._prepare_mount_targets(data)

    def _install(self, data):
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
            sysroot=conf.target.system_root,
            physroot=conf.target.physical_root
        )
        task.run()

        if not data.is_container():
            from pyanaconda.modules.payloads.payload.rpm_ostree.installation import \
                PullRemoteAndDeleteTask
            task = PullRemoteAndDeleteTask(data)
            task.progress_changed_signal.connect(self._progress_cb)
            task.run()

        from pyanaconda.modules.payloads.payload.rpm_ostree.installation import DeployOSTreeTask
        task = DeployOSTreeTask(data, conf.target.physical_root)
        task.progress_changed_signal.connect(self._progress_cb)
        task.run()

        # Reload now that we've deployed, find the path to the new deployment
        from pyanaconda.modules.payloads.payload.rpm_ostree.installation import SetSystemRootTask
        task = SetSystemRootTask(conf.target.physical_root)
        task.run()

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

        # find Flatpak installation size and cache it
        from pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_initialization import \
            GetFlatpaksSizeTask
        task = GetFlatpaksSizeTask(conf.target.system_root)
        self._flatpak_required_size = task.run()

    @property
    def space_required(self):
        return super().space_required + self._flatpak_required_size

    def install(self):
        # install ostree payload first
        super().install()

        # then flatpaks
        self._flatpak_install()

    def _progress_cb(self, step, message):
        """Callback for task progress reporting."""
        progressQ.send_message(message)

    def _flatpak_install(self):
        from pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_installation import \
            InstallFlatpaksTask
        task = InstallFlatpaksTask(conf.target.system_root)
        task.progress_changed_signal.connect(self._progress_cb)
        task.run()
