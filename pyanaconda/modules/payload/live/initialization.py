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
import os
import stat

from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.common.structures.storage import DeviceData
from pyanaconda.modules.common.constants.objects import DEVICE_TREE
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.payload.utils import mount, unmount
from pyanaconda.core.constants import TAR_SUFFIX
from pyanaconda.core.util import ProxyString, ProxyStringError

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class SetupInstallationSourceTask(Task):
    """Task to setup installation source."""

    def __init__(self, live_partition, target_mount):
        super().__init__()
        self._live_partition = live_partition
        self._target_mount = target_mount

    @property
    def name(self):
        return "Setup Installation Source"

    def run(self):
        """Run live installation source setup."""
        # Mount the live device and copy from it instead of the overlay at /
        device_tree = STORAGE.get_proxy(DEVICE_TREE)
        device_name = device_tree.ResolveDevice(self._live_partition)
        if not device_name:
            raise SourceSetupError("Failed to find liveOS image!")

        device_data = DeviceData.from_structure(device_tree.GetDeviceData(device_name))

        if not stat.S_ISBLK(os.stat(device_data.path)[stat.ST_MODE]):
            raise SourceSetupError("{} is not a valid block device".format(
                self._live_partition))
        rc = mount(device_data.path, self._target_mount, fstype="auto", options="ro")
        if rc != 0:
            raise SourceSetupError("Failed to mount the install tree")

        # FIXME: Update kernel version outside of this task
        #
        # Grab the kernel version list now so it's available after umount
        # self._update_kernel_version_list()

        # FIXME: This should be done by the module
        # source = os.statvfs(self._target_mount)
        # self.source_size = source.f_frsize * (source.f_blocks - source.f_bfree)


class TeardownInstallationSourceTask(Task):
    """Task to teardown installation source."""

    def __init__(self, target_mount):
        super().__init__()
        self._target_mount = target_mount

    @property
    def name(self):
        return "Teardown Installation Source"

    def run(self):
        """Run live installation source unsetup."""
        unmount(self._target_mount)


class CheckInstallationSourceImageTask(Task):
    """Task to check installation source image and get its size."""

    def __init__(self, url, proxy, session):
        """Create a new task.

        :param url: installation source image url
        :type url: str
        :param proxy: proxy to be used to fetch the image
        :type proxy: str
        :param session: Requests session for image download
        :type session:
        """
        super().__init__()
        self._url = url
        self._proxy = proxy
        self._session = session

    @property
    def name(self):
        return "Check installation source image"

    def _check_local_image(self, file_path):
        """Check that the file exists and return required space."""
        if not os.path.exists(file_path):
            raise SourceSetupError("File {} does not exist".format(file_path))
        size = os.stat(file_path)[stat.ST_SIZE] * 3
        return size

    def _check_remote_image(self, url, proxy):
        """Check that the url is available and return required space."""
        # FIXME: move to a function
        # FIXME: validate earlier when setting?
        size = 0
        proxies = {}
        if self._proxy:
            try:
                proxy = ProxyString(self._proxy)
                proxies = {"http": proxy.url,
                           "https": proxy.url}
            except ProxyStringError as e:
                log.info("Failed to parse proxy \"%s\": %s", self._proxy, e)

        try:
            response = self._session.get(url, proxies=proxies, verify=True)

            # At this point we know we can get the image and what its size is
            # Make a guess as to minimum size needed:
            # Enough space for image and image * 3
            if response.headers.get('content-length'):
                size = int(response.headers.get('content-length')) * 4
        except IOError as e:
            raise SourceSetupError("Error opening liveimg: {}".format(e))
        else:
            if response.status_code != 200:
                raise SourceSetupError("http request returned: {}".format(response.status_code))

        return size

    def run(self):
        """Run installation source image check.

        :returns: space required for the image in bytes
        :rtype: int
        """
        size = 0
        if self._url.startswith("file://"):
            file_path = self._url[7:]
            size = self._check_file_image(file_path)
        else:
            size = self._check_url_image(self._url, self._proxy)
        return size

# FIXME:
# Create SourceImageType enum? ... when we have more than 2
# Export it by the Handler? ... NO
def url_target_is_tarfile(url):
    """Does the url point to a tarfile?"""
    return any(url.endswith(suffix) for suffix in TAR_SUFFIX)
