#
# Copyright (C) 2020 Red Hat, Inc.
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
import os
from collections import namedtuple

from requests import RequestException

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.constants import NETWORK_CONNECTION_TIMEOUT
from pyanaconda.core.util import requests_session
from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.common.structures.live_image import LiveImageConfigurationData
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.payloads.payload.live_image.utils import (
    get_local_image_path_from_url,
    get_proxies_from_option,
)

log = get_module_logger(__name__)

# The result of the setup task.
SetupImageResult = namedtuple("SetupImageResult", ["required_space"])


class SetUpLocalImageSourceTask(Task):
    """Task to set up a local live image."""

    def __init__(self, configuration: LiveImageConfigurationData):
        """Create a new task.

        :param configuration: a configuration of a local image
        :type configuration: an instance of LiveImageConfigurationData
        """
        super().__init__()
        self._url = configuration.url

    @property
    def name(self):
        return "Set up a local live image"

    def run(self):
        """Run installation source image check.

        :return: a tuple with the required space
        :rtype: an instance of SetupImageResult
        :raise: SourceSetupError on failure
        """
        path = get_local_image_path_from_url(self._url)

        if not os.path.exists(path):
            raise SourceSetupError("File {} does not exist.".format(path))

        size = self._get_required_space(path)
        return SetupImageResult(required_space=size)

    def _get_required_space(self, path):
        """Calculate the required space of the image."""
        size = os.stat(path).st_blocks * 512 * 3

        if size <= 0:
            # It means that we don't know the size.
            log.debug("Unknown required space.")
            return None

        log.debug("Required space: %s", size)
        return size


class SetUpRemoteImageSourceTask(Task):
    """Task to set up a remote live image."""

    def __init__(self, configuration: LiveImageConfigurationData):
        """Create a new task.

        :param configuration: a configuration of a remote image
        :type configuration: an instance of LiveImageConfigurationData
        """
        super().__init__()
        self._url = configuration.url
        self._proxy = configuration.proxy
        self._ssl_verify = configuration.ssl_verification_enabled

    @property
    def name(self):
        return "Set up a remote live image"

    def run(self):
        """Run installation source image check.

        :return: a tuple with the required space
        :rtype: an instance of SetupImageResult
        :raise: SourceSetupError on failure
        """
        with requests_session() as session:
            try:
                # Send a HEAD request to the image URL.
                response = self._send_request(session)

                # Calculate the required space for the image.
                size = self._get_required_space(response)

            except RequestException as e:
                msg = "Error while handling a request: {}".format(e)
                raise SourceSetupError(msg) from e

        return SetupImageResult(required_space=size)

    def _send_request(self, session):
        """Send a HEAD request to the image URL."""
        # Send a request.
        proxies = get_proxies_from_option(
            self._proxy
        )
        response = session.head(
            url=self._url,
            proxies=proxies,
            verify=self._ssl_verify,
            timeout=NETWORK_CONNECTION_TIMEOUT
        )

        # Check the response.
        if response.status_code != 200:
            msg = "The request has failed: {}".format(
                response.status_code
            )
            raise SourceSetupError(msg)

        return response

    def _get_required_space(self, response):
        """Calculate the required space of the image."""
        size = 0

        # Make a guess as to minimum size needed:
        # enough space for image and image * 3
        if response.headers.get('content-length'):
            size = int(response.headers.get('content-length')) * 4

        if size <= 0:
            # It means that we don't know the size.
            log.debug("Unknown required space.")
            return None

        log.debug("Required space: %s", size)
        return size
