#
# The abstraction of the DNF base
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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import shutil
import dnf

from blivet.size import Size

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.payload import ProxyString, ProxyStringError
from pyanaconda.core.util import get_os_release_value
from pyanaconda.modules.payloads.constants import DNF_REPO_DIRS
from pyanaconda.modules.payloads.payload.dnf.utils import get_product_release_version
from pykickstart.constants import KS_BROKEN_IGNORE

log = get_module_logger(__name__)

DNF_CACHE_DIR = '/tmp/dnf.cache'
DNF_PLUGINCONF_DIR = '/tmp/dnf.pluginconf'

# Bonus to required free space which depends on block size and
# rpm database size estimation. Every file could be aligned to
# fragment size so 4KiB * number_of_files should be a worst case
# scenario. 2KiB for RPM DB was acquired by testing.
#
#   4KiB = max default fragment size
#   2KiB = RPM DB could be taken for a header file
#   6KiB = 4KiB + 2KiB
#
DNF_EXTRA_SIZE_PER_FILE = Size("6 KiB")


class DNFManager(object):
    """The abstraction of the DNF base."""

    def __init__(self):
        self.__base = None

    @property
    def _base(self):
        """The DNF base."""
        if self.__base is None:
            self.__base = self._create_base()

        return self.__base

    @staticmethod
    def _create_base():
        """Create a new DNF base."""
        base = dnf.Base()
        base.conf.cachedir = DNF_CACHE_DIR
        base.conf.pluginconfpath = DNF_PLUGINCONF_DIR
        base.conf.logdir = '/tmp/'
        base.conf.debug_solver = conf.anaconda.debug
        base.conf.releasever = get_product_release_version()
        base.conf.installroot = conf.target.system_root
        base.conf.prepend_installroot('persistdir')

        # Set the platform id based on the /os/release present
        # in the installation environment.
        platform_id = get_os_release_value("PLATFORM_ID")

        if platform_id is not None:
            base.conf.module_platform_id = platform_id

        # Start with an empty comps so we can go ahead and use
        # the environment and group properties. Unset reposdir
        # to ensure dnf has nothing it can check automatically.
        base.conf.reposdir = []
        base.read_comps(arch_filter=True)
        base.conf.reposdir = DNF_REPO_DIRS

        log.debug("The DNF base has been created.")
        return base

    def reset_base(self):
        """Reset the DNF base."""
        self.__base = None
        log.debug("The DNF base has been reset.")

    def configure_base(self, data):
        """Configure the DNF base.

        FIXME: Don't use kickstart data.

        :param data: a kickstart data
        """
        base = self._base

        if data.packages.multiLib:
            base.conf.multilib_policy = "all"

        if data.packages.timeout is not None:
            base.conf.timeout = data.packages.timeout

        if data.packages.retries is not None:
            base.conf.retries = data.packages.retries

        if data.packages.handleBroken == KS_BROKEN_IGNORE:
            log.warning(
                "\n***********************************************\n"
                "User has requested to skip broken packages. Using"
                "this option may result in an UNUSABLE system!"
                "\n***********************************************\n"
            )
            base.conf.strict = False

        # Two reasons to turn this off:
        # 1. Minimal installs don't want all the extras this brings in.
        # 2. Installs aren't reproducible due to weak deps. failing silently.
        if data.packages.excludeWeakdeps:
            base.conf.install_weak_deps = False

    def configure_proxy(self, url):
        """Configure the proxy of the DNF base.

        :param url: a proxy URL or None
        """
        base = self._base

        # Reset the proxy configuration.
        base.conf.proxy = ""
        base.conf.proxy_username = ""
        base.conf.proxy_password = ""

        # No URL is provided.
        if not url:
            return

        # Parse the given URL.
        try:
            proxy = ProxyString(url)
        except ProxyStringError as e:
            log.error("Failed to parse the proxy '%s': %s", url, e)
            return

        # Set the proxy configuration.
        log.info("Using '%s' as a proxy.", url)
        base.conf.proxy = proxy.noauth_url
        base.conf.proxy_username = proxy.username or ""
        base.conf.proxy_password = proxy.password or ""

    def dump_configuration(self):
        """Log the state of the DNF configuration."""
        log.debug("DNF configuration:\n%s", self._base.conf.dump())

    def get_installation_size(self):
        """Calculate the installation size.

        :return: a space required by packages
        :rtype: an instance of Size
        """
        packages_size = Size(0)
        files_number = 0

        if self._base.transaction is None:
            return Size("3000 MiB")

        for tsi in self._base.transaction:
            # Space taken by all files installed by the packages.
            packages_size += tsi.pkg.installsize
            # Number of files installed on the system.
            files_number += len(tsi.pkg.files)

        log.debug("Space required for packages: %s", packages_size)

        # Calculate the files size depending on number of files.
        files_size = Size(files_number * DNF_EXTRA_SIZE_PER_FILE)
        log.debug("Space required for installed files: %s", files_size)

        # Get the total size. Add another 10% as safeguard.
        total_space = Size((packages_size + files_size) * 1.1)
        log.debug("Total required size: %s", total_space)

        return total_space

    def get_download_size(self):
        """Calculate the download size.

        :return: a space required for packages
        :rtype: an instance of Size
        """
        if self._base.transaction is None:
            return Size(0)

        download_size = Size(0)

        # Calculate the download size.
        for tsi in self._base.transaction:
            download_size += tsi.pkg.downloadsize

        # Get the total size. Reserve extra space.
        total_space = download_size + Size("150 MiB")
        log.debug("Total download size: %s", total_space)

        return total_space

    def clear_cache(self):
        """Clear the DNF cache."""
        shutil.rmtree(DNF_CACHE_DIR, ignore_errors=True)
        shutil.rmtree(DNF_PLUGINCONF_DIR, ignore_errors=True)
        self._base.reset(sack=True, repos=True)
        log.debug("The DNF cache has been cleared.")
