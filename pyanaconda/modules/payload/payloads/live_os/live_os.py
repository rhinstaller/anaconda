#
# Kickstart module for Live OS payload.
#
# Copyright (C) 2019 Red Hat, Inc.
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
from pyanaconda.dbus import DBus

from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.signal import Signal
from pyanaconda.core.constants import INSTALL_TREE

from pyanaconda.modules.common.constants.objects import LIVE_OS_HANDLER
from pyanaconda.modules.common.errors.payload import SourceSetupError, IncompatibleSourceError
from pyanaconda.modules.payload.base.constants import SourceType
from pyanaconda.modules.payload.base.handler_base import PayloadHandlerBase
from pyanaconda.modules.payload.base.initialization import PrepareSystemForInstallationTask, \
    CopyDriverDisksFilesTask, SetUpSourcesTask, TearDownSourcesTask
from pyanaconda.modules.payload.base.utils import get_dir_size
from pyanaconda.modules.payload.payloads.live_os.live_os_interface import LiveOSHandlerInterface
from pyanaconda.modules.payload.live.initialization import UpdateBLSConfigurationTask
from pyanaconda.modules.payload.live.installation import InstallFromImageTask
from pyanaconda.modules.payload.live.utils import get_kernel_version_list

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class LiveOSHandlerModule(PayloadHandlerBase):
    """The Live OS payload module."""

    def __init__(self):
        super().__init__()

        self._kernel_version_list = []
        self.kernel_version_list_changed = Signal()

    @property
    def supported_source_types(self):
        """Get list of sources supported by Live Image module."""
        return [SourceType.LIVE_OS_IMAGE]

    def set_sources(self, sources):
        """Set new sources to this handler.

        This payload is specific that it can't have more than only one source attached. It will
        instead replace the old source with the new one.

        :param source: source object
        :type source: instance of pyanaconda.modules.payload.base.source_base.PayloadSourceBase
        :raises: IncompatibleSourceError
        """
        if len(sources) > 1:
            raise IncompatibleSourceError("You can set only one source for this payload type.")

        super().set_sources(sources)

    def publish_handler(self):
        """Publish the handler."""
        DBus.publish_object(LIVE_OS_HANDLER.object_path, LiveOSHandlerInterface(self))
        return LIVE_OS_HANDLER.object_path

    def process_kickstart(self, data):
        """Process the kickstart data."""

    def setup_kickstart(self, data):
        """Setup the kickstart data."""

    @property
    def _image_source(self):
        """Get the attached source object.

        This is a shortcut for this handler because it only support one source at a time.

        :return: a source object
        """
        if self.sources:
            return list(self.sources)[0]

        return None

    def _check_source_availability(self, message):
        """Test if source is available for this payload handler."""
        if not self._image_source:
            raise SourceSetupError(message)

    @property
    def space_required(self):
        """Get space required for the source image.

        TODO: Add missing check if source is ready. Until then you shouldn't call this when
        source is not ready.

        TODO: This is not that fast as I thought (a few seconds). Caching or task?

        :return: required size in bytes
        :rtype: int
        """
        return get_dir_size("/") * 1024

    def set_up_sources_with_task(self):
        """Set up installation source."""
        self._check_source_availability("Set up source failed - source is not set!")

        return SetUpSourcesTask(self._sources)

    def tear_down_sources_with_task(self):
        """Tear down installation sources."""
        self._check_source_availability("Tear down source failed - source is not set!")

        return TearDownSourcesTask(self._sources)

    def pre_install_with_task(self):
        """Prepare intallation task."""
        self._check_source_availability("Pre install task failed - source is not available!")

        return PrepareSystemForInstallationTask(conf.target.system_root)

    def install_with_task(self):
        """Install the payload."""
        self._check_source_availability("Installation task failed - source is not available!")

        return InstallFromImageTask(
            self._image_source,
            conf.target.system_root,
            self.kernel_version_list
        )

    def post_install_with_tasks(self):
        """Perform post installation tasks.

        :returns: list of paths.
        :rtype: List
        """
        return [
            UpdateBLSConfigurationTask(
                conf.target.system_root,
                self.kernel_version_list
            ),
            CopyDriverDisksFilesTask(conf.target.system_root)
        ]

    def update_kernel_version_list(self):
        """Update list of kernel versions.

        Source have to be set-up first.
        """
        self.set_kernel_version_list(get_kernel_version_list(INSTALL_TREE))

    @property
    def kernel_version_list(self):
        """Get list of kernel versions.

        :rtype: [str]
        """
        return self._kernel_version_list

    def set_kernel_version_list(self, kernel_version_list):
        """Set list of kernel versions."""
        self._kernel_version_list = kernel_version_list
        self.kernel_version_list_changed.emit(self._kernel_version_list)
        log.debug("List of kernel versions is set to '%s'", self._kernel_version_list)
