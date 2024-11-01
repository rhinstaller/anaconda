#
# Utility functions shared for the whole payload module.
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
from functools import partial

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import NETWORK_CONNECTION_TIMEOUT, USER_AGENT
from pyanaconda.core.payload import ProxyString, ProxyStringError, rpm_version_key
from pyanaconda.modules.common.structures.payload import RepoConfigurationData

log = get_module_logger(__name__)


def sort_kernel_version_list(kernel_version_list):
    """Sort the given kernel version list."""
    kernel_version_list.sort(key=rpm_version_key)


def get_downloader_for_repo_configuration(session, data: RepoConfigurationData):
    """Get a configured session.get method.

    :return: a partial function
    """
    # Prepare the SSL configuration.
    ssl_enabled = conf.payload.verify_ssl and data.ssl_verification_enabled

    # ssl_verify can be:
    #   - the path to a cert file
    #   - True, to use the system's certificates
    #   - False, to not verify
    ssl_verify = data.ssl_configuration.ca_cert_path or ssl_enabled

    # ssl_cert can be:
    #   - a tuple of paths to a client cert file and a client key file
    #   - None
    ssl_client_cert = data.ssl_configuration.client_cert_path or None
    ssl_client_key = data.ssl_configuration.client_key_path or None
    ssl_cert = (ssl_client_cert, ssl_client_key) if ssl_client_cert else None

    # Prepare the proxy configuration.
    proxy_url = data.proxy or None
    proxies = {}

    if proxy_url:
        try:
            proxy = ProxyString(proxy_url)
            proxies = {
                "http": proxy.url,
                "https": proxy.url,
                "ftp": proxy.url
            }
        except ProxyStringError as e:
            log.debug("Failed to parse the proxy '%s': %s", proxy_url, e)

    # Prepare headers.
    headers = {"user-agent": USER_AGENT}

    # Return a partial function.
    return partial(
        session.get,
        headers=headers,
        proxies=proxies,
        verify=ssl_verify,
        cert=ssl_cert,
        timeout=NETWORK_CONNECTION_TIMEOUT
    )
