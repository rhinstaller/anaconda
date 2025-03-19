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
import tarfile

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.payload import ProxyString, ProxyStringError
from pyanaconda.modules.payloads.base.utils import sort_kernel_version_list

log = get_module_logger(__name__)


def get_kernel_version_list_from_tar(tarfile_path):
    with tarfile.open(tarfile_path) as archive:
        names = archive.getnames()

    # Strip out vmlinuz- from the names
    kernel_version_list = [
        n.split("/")[-1][8:] for n in names
        if "boot/vmlinuz-" in n and "-rescue-" not in n
    ]

    sort_kernel_version_list(kernel_version_list)
    return kernel_version_list


def get_local_image_path_from_url(url):
    image_path = ""
    if url.startswith("file://"):
        image_path = url[7:]
    return image_path


def get_proxies_from_option(proxy_option):
    proxies = {}
    if proxy_option:
        try:
            proxy = ProxyString(proxy_option)
            proxies = {"http": proxy.url,
                       "https": proxy.url}
        except ProxyStringError as e:
            log.info("Failed to parse proxy \"%s\": %s", proxy_option, e)
    return proxies
