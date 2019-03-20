#
# Kickstart module for packaging section.
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
from pyanaconda.modules.common.base import KickstartBaseModule
from pyanaconda.modules.common.constants.objects import DNF_PACKAGES
from pyanaconda.modules.payload.dnf.packages.packages_interface import PackagesHandlerInterface
from pykickstart.constants import KS_MISSING_IGNORE, KS_MISSING_PROMPT

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class PackagesHandlerModule(KickstartBaseModule):
    """The DNF sub-module for packages section."""

    def __init__(self):
        super().__init__()

        self._core_group_enabled = True
        self._default_environment = False

        self._environment = None
        self._groups = []
        self._packages = []

        self._excluded_packages = []
        self._excluded_groups = []

        self._docs_excluded = False
        self._weakdeps_excluded = False
        self._missing_ignored = False
        self._languages = None
        self._multilib_policy = None
        self._timeout = None
        self._retries = None

    def publish(self):
        """Publish the module."""
        DBus.publish_object(DNF_PACKAGES.object_path, PackagesHandlerInterface(self))

    def process_kickstart(self, data):
        """Process the kickstart data."""
        packages = data.packages

        self._core_group_enabled = not packages.nocore
        self._default_environment = packages.default

        self._environment = packages.environment
        self._groups = packages.groupList
        self._packages = packages.packageList

        self._excluded_packages = packages.excludedList
        self._excluded_groups = packages.excludedGroupList

        self._docs_excluded = packages.excludeDocs
        self._weakdeps_excluded = packages.excludeWeakdeps

        if packages.handleMissing == KS_MISSING_IGNORE:
            self._missing_ignored = True
        else:
            self._missing_ignored = False

        self._languages = packages.instLangs
        self._multilib_policy = packages.multiLib
        self._timeout = packages.timeout
        self._retries = packages.retries

    def setup_kickstart(self, data):
        """Setup the kickstart data."""
        packages = data.packages

        packages.nocore = not self._core_group_enabled
        packages.default = self._default_environment

        packages.environment = self._environment
        packages.groupList = self._groups
        packages.packageList = self._packages

        packages.excludedList = self._excluded_packages
        packages.excludedGroupList = self._excluded_groups

        packages.excludeDocs = self._docs_excluded
        packages.excludeWeakdeps = self._weakdeps_excluded
        packages.handleMissing = KS_MISSING_IGNORE if self._missing_ignored else KS_MISSING_PROMPT
        packages.instLangs = self._languages
        packages.multiLib = self._multilib_policy
        packages.timeout = self._timeout
        packages.retries = self._retries

        # The empty packages section won't be printed without seen set to True
        packages.seen = True
