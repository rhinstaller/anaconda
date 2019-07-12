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
import glob
import functools
import os
from pyanaconda.payload.utils import version_cmp
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.util import ProxyString, ProxyStringError, execWithRedirect
from pyanaconda.core.constants import TAR_SUFFIX

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


def get_kernel_version_list(root_path):
    files = glob.glob(root_path + "/boot/vmlinuz-*")
    files.extend(glob.glob(root_path + "/boot/efi/EFI/{}/vmlinuz-*".format(conf.bootloader.efi_dir)))

    kernel_version_list = sorted((f.split("/")[-1][8:] for f in files
                                  if os.path.isfile(f) and "-rescue-" not in f),
                                 key=functools.cmp_to_key(version_cmp))
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


def url_target_is_tarfile(url):
    """Does the url point to a tarfile?"""
    return any(url.endswith(suffix) for suffix in TAR_SUFFIX)


def create_rescue_image(root, kernel_version_list):
    """Create the rescue initrd images for each kernel."""
    # Always make sure the new system has a new machine-id, it won't boot without it
    # (and nor will some of the subsequent commands like grub2-mkconfig and kernel-install)
    log.info("Generating machine ID")
    if os.path.exists(root + "/etc/machine-id"):
        os.unlink(root + "/etc/machine-id")
    execWithRedirect("systemd-machine-id-setup", [], root=root)

    if os.path.exists(root + "/usr/sbin/new-kernel-pkg"):
        use_nkp = True
    else:
        log.warning("new-kernel-pkg does not exist - grubby wasn't installed?")
        use_nkp = False

    for kernel in kernel_version_list:
        log.info("Generating rescue image for %s", kernel)
        if use_nkp:
            execWithRedirect("new-kernel-pkg", ["--rpmposttrans", kernel], root=root)
        else:
            files = glob.glob(root + "/etc/kernel/postinst.d/*")
            srlen = len(root)
            files = sorted([f[srlen:] for f in files if os.access(f, os.X_OK)])
            for file in files:
                execWithRedirect(file, [kernel, "/boot/vmlinuz-%s" % kernel], root=root)
