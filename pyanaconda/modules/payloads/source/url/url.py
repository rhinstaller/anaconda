#
# Kickstart module for URL payload source.
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
import copy

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.constants import (
    URL_TYPE_BASEURL,
    URL_TYPE_METALINK,
    URL_TYPE_MIRRORLIST,
    URL_TYPES,
)
from pyanaconda.core.payload import ProxyString, ProxyStringError
from pyanaconda.modules.common.errors.general import InvalidValueError
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.payloads.constants import SourceState, SourceType
from pyanaconda.modules.payloads.source.source_base import (
    PayloadSourceBase,
    RepositorySourceMixin,
    RPMSourceMixin,
)
from pyanaconda.modules.payloads.source.source_base_interface import (
    RepositorySourceInterface,
)
from pyanaconda.modules.payloads.source.utils import has_network_protocol

log = get_module_logger(__name__)


class URLSourceModule(PayloadSourceBase, RepositorySourceMixin, RPMSourceMixin):
    """The URL source payload module."""

    def for_publication(self):
        """Get the interface used to publish this source."""
        return RepositorySourceInterface(self)

    @property
    def type(self):
        """Get type of this source."""
        return SourceType.URL

    @property
    def description(self):
        """Get description of this source."""
        return self.configuration.url

    @property
    def supported_protocols(self):
        """A list of supported URL protocols."""
        return ["http:", "https:", "ftp:", "file:"]

    @property
    def network_required(self):
        """Does the source require a network?

        :return: True or False
        """
        return has_network_protocol(self.configuration.url)

    @property
    def required_space(self):
        """The space required for the installation.

        :return: required size in bytes
        :rtype: int
        """
        return 0

    def set_configuration(self, configuration):
        """Set the source and repository configuration."""
        super().set_configuration(configuration)
        self._set_repository(copy.deepcopy(configuration))

    def process_kickstart(self, data):
        """Process the kickstart data."""
        repo_data = RepoConfigurationData()

        if data.url.url:
            repo_data.url = data.url.url
            repo_data.type = URL_TYPE_BASEURL
        elif data.url.mirrorlist:
            repo_data.url = data.url.mirrorlist
            repo_data.type = URL_TYPE_MIRRORLIST
        elif data.url.metalink:
            repo_data.url = data.url.metalink
            repo_data.type = URL_TYPE_METALINK

        repo_data.proxy = data.url.proxy
        repo_data.ssl_verification_enabled = not data.url.noverifyssl
        repo_data.ssl_configuration.ca_cert_path = data.url.sslcacert or ""
        repo_data.ssl_configuration.client_cert_path = data.url.sslclientcert or ""
        repo_data.ssl_configuration.client_key_path = data.url.sslclientkey or ""

        self.set_configuration(repo_data)

    def setup_kickstart(self, data):
        """Setup the kickstart data."""
        repo_data = self.configuration

        if repo_data.type == URL_TYPE_BASEURL:
            data.url.url = repo_data.url
        elif repo_data.type == URL_TYPE_MIRRORLIST:
            data.url.mirrorlist = repo_data.url
        elif repo_data.type == URL_TYPE_METALINK:
            data.url.metalink = repo_data.url

        data.url.proxy = repo_data.proxy
        data.url.noverifyssl = not repo_data.ssl_verification_enabled
        data.url.sslcacert = repo_data.ssl_configuration.ca_cert_path
        data.url.sslclientcert = repo_data.ssl_configuration.client_cert_path
        data.url.sslclientkey = repo_data.ssl_configuration.client_key_path

        data.url.seen = True

    def _validate_configuration(self, configuration):
        """Validate the specified source configuration."""
        is_protocol_supported = any(
            configuration.url.startswith(p)
            for p in self.supported_protocols
        )

        if not is_protocol_supported:
            raise InvalidValueError(
                "Invalid protocol of an URL source: '{}'"
                "".format(configuration.url)
            )

        if configuration.type not in URL_TYPES:
            raise InvalidValueError(
                "Invalid URL type of an URL source: '{}'"
                "".format(configuration.type)
            )

        if configuration.proxy:
            try:
                ProxyString(configuration.proxy)
            except ProxyStringError:
                raise InvalidValueError(
                    "Invalid proxy of an URL source: '{}'"
                    "".format(configuration.proxy)
                ) from None

    def get_state(self):
        """Get state of this source."""
        return SourceState.NOT_APPLICABLE

    def set_up_with_tasks(self):
        """Set up the installation source.

        :return: list of tasks required for the source setup
        :rtype: [Task]
        """
        return []

    def tear_down_with_tasks(self):
        """Tear down the installation source.

        :return: list of tasks required for the source clean-up
        :rtype: [Task]
        """
        return []

    def generate_repo_configuration(self):
        """Generate RepoConfigurationData structure."""
        return self.repository

    def __repr__(self):
        """Generate a string representation."""
        return "Source(type='URL', url='{}')".format(self.configuration.url)
