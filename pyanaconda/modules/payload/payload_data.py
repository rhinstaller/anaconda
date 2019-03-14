#
# Class for storing payload data.
#
# Copyright (C) 2018 Red Hat, Inc.
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


class PayloadData(object):
    """Data object to store %packages section data."""

    def __init__(self):
        self.add_base = True
        self.no_core = False
        self.default = False

        self.environment = None
        self.group_list = []
        self.package_list = []

        self.exluded_list = []
        self.exluded_group_list = []

        self.exclude_docs = False
        self.exlude_weakdeps = False
        self.handle_missing = None
        self.inst_langs = None
        self.multi_lib = None
        self.timeout = None
        self.retries = None
        self.seen = False

    def load_packages_data(self, packages):
        """Load data from the Packages pykickstart object into this object.

        :param packages: pykickstart object we want to load into this object
        :type packages: :class:`pykickstart.parser.Packages` section handler object instance
        """
        self.add_base = packages.addBase
        self.no_core = packages.nocore
        self.default = packages.default

        self.environment = packages.environment
        self.group_list = packages.groupList
        self.package_list = packages.packageList

        self.exluded_list = packages.excludedList
        self.exluded_group_list = packages.excludedGroupList

        self.exclude_docs = packages.excludeDocs
        self.exlude_weakdeps = packages.excludeWeakdeps
        self.handle_missing = packages.handleMissing
        self.inst_langs = packages.instLangs
        self.multi_lib = packages.multiLib
        self.timeout = packages.timeout
        self.retries = packages.retries
        self.seen = packages.seen

    def fill_packages_data(self, packages):
        """Save data in this object to the pykickstart object.

        :param packages: pykickstart object we want to fill by data from this object
        :type packages: :class:`pykickstart.parser.Packages` section handler object instance
        """
        packages.addBase = self.add_base
        packages.nocore = self.no_core
        packages.default = self.default

        packages.environment = self.environment
        packages.groupList = self.group_list
        packages.packageList = self.package_list

        packages.excludedList = self.exluded_list
        packages.excludedGroupList = self.exluded_group_list

        packages.excludeDocs = self.exclude_docs
        packages.excludeWeakdeps = self.exlude_weakdeps
        packages.handleMissing = self.handle_missing
        packages.instLangs = self.inst_langs
        packages.multiLib = self.multi_lib
        packages.timeout = self.timeout
        packages.retries = self.retries
        packages.seen = self.seen
