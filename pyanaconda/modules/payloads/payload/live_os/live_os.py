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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.signal import Signal
from pyanaconda.core.constants import INSTALL_TREE

from pyanaconda.modules.common.errors.payload import SourceSetupError, IncompatibleSourceError
from pyanaconda.modules.payloads.constants import SourceType, PayloadType
from pyanaconda.modules.payloads.payload.payload_base import PayloadBase
from pyanaconda.modules.payloads.base.initialization import PrepareSystemForInstallationTask, \
    CopyDriverDisksFilesTask, SetUpSourcesTask, TearDownSourcesTask
from pyanaconda.modules.payloads.base.installation import InstallFromImageTask
from pyanaconda.modules.payloads.payload.live_os.utils import get_kernel_version_list
from pyanaconda.modules.payloads.payload.live_os.live_os_interface import LiveOSInterface

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class LiveOSModule(PayloadBase):
    """The Live OS payload module."""

    def __init__(self):
        super().__init__()

        self._kernel_version_list = []
        self.kernel_version_list_changed = Signal()

    def for_publication(self):
        """Get the interface used to publish this source."""
        return LiveOSInterface(self)

    @property
    def type(self):
        """Get type of this payload.

        :return: value of the payload.base.constants.PayloadType enum
        """
        return PayloadType.LIVE_OS

    @property
    def supported_source_types(self):
        """Get list of sources supported by Live Image module."""
        return [SourceType.LIVE_OS_IMAGE]

    def set_sources(self, sources):
        """Set new sources to this payload.

        This payload is specific that it can't have more than only one source attached. It will
        instead replace the old source with the new one.

        :param sources: source objects
        :type sources:
            list of pyanaconda.modules.payloads.source.source_base.PayloadSourceBase instances
        :raises: IncompatibleSourceError
        """
        if len(sources) > 1:
            raise IncompatibleSourceError("You can set only one source for this payload type.")

        super().set_sources(sources)

    def process_kickstart(self, data):
        """Process the kickstart data."""

    def setup_kickstart(self, data):
        """Setup the kickstart data."""

    @property
    def _image_source(self):
        """Get the attached source object.

        This is a shortcut for this payload because it only support one source at a time.

        :return: a source object
        """
        if self.sources:
            return list(self.sources)[0]

        return None

    def _check_source_availability(self, message):
        """Test if source is available for this payload."""
        if not self._image_source:
            raise SourceSetupError(message)

    # @staticmethod
    # def _get_required_space():
    #     # TODO: This is not that fast as I thought (a few seconds). Caching or solved in task?
    #     size = get_dir_size("/") * 1024
    #
    #     # we don't know the size -- this should not happen
    #     if size == 0:
    #         log.debug("Space required is not known. This should not happen!")
    #         return None
    #     else:
    #         return size

    def set_up_sources_with_task(self):
        """Set up installation sources."""
        self._check_source_availability("Set up source failed - source is not set!")

        task = SetUpSourcesTask(self._sources)
        # task.succeeded_signal.connect(lambda: self.set_required_space(
        # self._get_required_space()))

        return task

    def tear_down_sources_with_task(self):
        """Tear down installation sources."""
        self._check_source_availability("Tear down source failed - source is not set!")

        task = TearDownSourcesTask(self._sources)
        # task.stopped_signal.connect(lambda: self.set_required_space(0))

        return task

    def pre_install_with_tasks(self):
        """Execute preparation steps."""
        self._check_source_availability("Pre install task failed - source is not available!")

        return [PrepareSystemForInstallationTask(conf.target.system_root)]

    def install_with_tasks(self):
        """Install the payload."""
        self._check_source_availability("Installation task failed - source is not available!")

        return [InstallFromImageTask(
            self._image_source,
            conf.target.system_root
        )]

    def post_install_with_tasks(self):
        """Execute post installation steps.

        :returns: list of paths.
        :rtype: List
        """
        return [
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
