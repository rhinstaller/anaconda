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

from pyanaconda.core.constants import NETWORK_CONNECTION_TIMEOUT
from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.payload.live.utils import get_local_image_path_from_url, \
    get_proxies_from_option

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


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
        size = 0
        # FIXME: validate earlier when setting?
        proxies = get_proxies_from_option(self._proxy)
        try:
            response = self._session.get(url, proxies=proxies, verify=True,
                                         timeout=NETWORK_CONNECTION_TIMEOUT)

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
        local_image_path = get_local_image_path_from_url(self._url)
        if local_image_path:
            size = self._check_local_image(local_image_path)
        else:
            size = self._check_remote_image(self._url, self._proxy)
        log.debug("Required space: %s", size)
        return size
