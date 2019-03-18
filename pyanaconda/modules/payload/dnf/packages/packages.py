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

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class PackagesHandlerModule(KickstartBaseModule):
    """The DNF sub-module for packages section."""

    def __init__(self):
        super().__init__()

        self._add_base = True
        self._no_core = False
        self._default = False

        self._environment = None
        self._group_list = []
        self._package_list = []

        self._excluded_list = []
        self._excluded_group_list = []

        self._exclude_docs = False
        self._exclude_weakdeps = False
        self._handle_missing = None
        self._inst_langs = None
        self._multi_lib = None
        self._timeout = None
        self._retries = None

    def publish(self):
        """Publish the module."""
        DBus.publish_object(DNF_PACKAGES.object_path, PackagesHandlerInterface(self))

    def process_kickstart(self, data):
        """Process the kickstart data."""
        packages = data.packages

        self._add_base = packages.addBase
        self._no_core = packages.nocore
        self._default = packages.default

        self._environment = packages.environment
        self._group_list = packages.groupList
        self._package_list = packages.packageList

        self._excluded_list = packages.excludedList
        self._excluded_group_list = packages.excludedGroupList

        self._exclude_docs = packages.excludeDocs
        self._exclude_weakdeps = packages.excludeWeakdeps
        self._handle_missing = packages.handleMissing
        self._inst_langs = packages.instLangs
        self._multi_lib = packages.multiLib
        self._timeout = packages.timeout
        self._retries = packages.retries

    def setup_kickstart(self, data):
        """Setup the kickstart data."""
        packages = data.packages

        packages.addBase = self._add_base
        packages.nocore = self._no_core
        packages.default = self._default

        packages.environment = self._environment
        packages.groupList = self._group_list
        packages.packageList = self._package_list

        packages.excludedList = self._excluded_list
        packages.excludedGroupList = self._excluded_group_list

        packages.excludeDocs = self._exclude_docs
        packages.excludeWeakdeps = self._exclude_weakdeps
        packages.handleMissing = self._handle_missing
        packages.instLangs = self._inst_langs
        packages.multiLib = self._multi_lib
        packages.timeout = self._timeout
        packages.retries = self._retries

        # The empty packages section won't be printed without seen set to True
        packages.seen = True
