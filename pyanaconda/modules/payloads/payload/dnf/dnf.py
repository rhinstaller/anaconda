#
# Kickstart module for DNF payload.
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
from pykickstart.constants import GROUP_REQUIRED, GROUP_ALL, KS_MISSING_IGNORE, KS_BROKEN_IGNORE, \
    GROUP_DEFAULT

from pyanaconda.core.constants import RPM_LANGUAGES_NONE, MULTILIB_POLICY_ALL, \
    DNF_DEFAULT_TIMEOUT, DNF_DEFAULT_RETRIES, GROUP_PACKAGE_TYPES_ALL, \
    GROUP_PACKAGE_TYPES_REQUIRED, RPM_LANGUAGES_ALL
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.structures.payload import PackagesConfigurationData
from pyanaconda.modules.payloads.constants import PayloadType, SourceType
from pyanaconda.modules.payloads.payload.payload_base import PayloadBase
from pyanaconda.modules.payloads.payload.dnf.dnf_interface import DNFInterface
from pyanaconda.modules.payloads.source.factory import SourceFactory

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class DNFModule(PayloadBase):
    """The DNF payload module."""

    def __init__(self):
        super().__init__()
        self._packages = PackagesConfigurationData()
        self.packages_changed = Signal()

        self._packages_kickstarted = False

    def for_publication(self):
        """Get the interface used to publish this source."""
        return DNFInterface(self)

    @property
    def type(self):
        """Get type of this payload.

        :return: value of the payload.base.constants.PayloadType enum
        """
        return PayloadType.DNF

    @property
    def supported_source_types(self):
        """Get list of sources supported by DNF module."""
        return [
            SourceType.CDROM,
            SourceType.HDD,
            SourceType.HMC,
            SourceType.NFS,
            SourceType.REPO_FILES,
            SourceType.CLOSEST_MIRROR,
            SourceType.CDN,
            SourceType.URL
        ]

    @property
    def packages(self):
        """The packages configuration.

        :return: an instance of PackagesConfigurationData
        """
        return self._packages

    def set_packages(self, packages):
        """Set the packages configuration.

        :param packages: an instance of PackagesConfigurationData
        """
        self._packages = packages
        self.packages_changed.emit()
        log.debug("Packages are set to '%s'.", packages)

    @property
    def packages_kickstarted(self):
        """Are the packages set from a kickstart?

        FIXME: This is a temporary property.

        :return: True or False
        """
        return self._packages_kickstarted

    def set_packages_kickstarted(self, value):
        """Are the packages set from a kickstart?"""
        self._packages_kickstarted = value
        log.debug("Are the packages set from a kickstart? %s", value)

    def process_kickstart(self, data):
        """Process the kickstart data."""
        self._process_kickstart_sources(data)
        self._process_kickstart_packages(data)

    def _process_kickstart_sources(self, data):
        """Process the kickstart sources."""
        source_type = SourceFactory.get_rpm_type_for_kickstart(data)

        if source_type is None:
            return

        source = SourceFactory.create_source(source_type)
        source.process_kickstart(data)
        self.add_source(source)

    def _process_kickstart_packages(self, data):
        """Process the kickstart packages."""
        packages = PackagesConfigurationData()
        packages.core_group_enabled = not data.packages.nocore
        packages.default_environment_enabled = data.packages.default

        if data.packages.environment is not None:
            packages.environment = data.packages.environment

        packages.packages = data.packages.packageList
        packages.excluded_packages = data.packages.excludedList

        for group in data.packages.groupList:
            packages.groups.append(group.name)

            if group.include == GROUP_ALL:
                packages.groups_package_types[group.name] = GROUP_PACKAGE_TYPES_ALL

            if group.include == GROUP_REQUIRED:
                packages.groups_package_types[group.name] = GROUP_PACKAGE_TYPES_REQUIRED

        for group in data.packages.excludedGroupList:
            packages.excluded_groups.append(group.name)

        packages.docs_excluded = data.packages.excludeDocs
        packages.weakdeps_excluded = data.packages.excludeWeakdeps

        if data.packages.handleMissing == KS_MISSING_IGNORE:
            packages.missing_ignored = True

        if data.packages.handleBroken == KS_BROKEN_IGNORE:
            packages.broken_ignored = True

        if data.packages.instLangs == "":
            packages.languages = RPM_LANGUAGES_NONE
        elif data.packages.instLangs is not None:
            packages.languages = data.packages.instLangs

        if data.packages.multiLib:
            packages.multilib_policy = MULTILIB_POLICY_ALL

        if data.packages.timeout is not None:
            packages.timeout = data.packages.timeout

        if data.packages.retries is not None:
            packages.retries = data.packages.retries

        self.set_packages(packages)
        self.set_packages_kickstarted(data.packages.seen)

    def setup_kickstart(self, data):
        """Setup the kickstart data."""
        self._set_up_kickstart_sources(data)
        self._set_up_kickstart_packages(data)

    def _set_up_kickstart_sources(self, data):
        """Set up the kickstart sources."""
        for source in self.sources:
            source.setup_kickstart(data)

    def _set_up_kickstart_packages(self, data):
        """Set up the kickstart packages."""
        # The empty packages section won't be printed without seen set to True.
        data.packages.seen = True
        data.packages.nocore = not self.packages.core_group_enabled
        data.packages.default = self.packages.default_environment_enabled

        if self.packages.environment:
            data.packages.environment = self.packages.environment

        data.packages.packageList = self.packages.packages
        data.packages.excludedList = self.packages.excluded_packages

        for group_name in self.packages.groups:
            package_types = self.packages.groups_package_types.get(
                group_name, []
            )
            group_include = GROUP_DEFAULT

            if set(package_types) == set(GROUP_PACKAGE_TYPES_ALL):
                group_include = GROUP_ALL

            if set(package_types) == set(GROUP_PACKAGE_TYPES_REQUIRED):
                group_include = GROUP_REQUIRED

            group = data.packages.create_group(
                name=group_name,
                include=group_include
            )
            data.packages.groupList.append(group)

        for group_name in self.packages.excluded_groups:
            group = data.packages.create_group(
                name=group_name
            )
            data.packages.excludedGroupList.append(group)

        data.packages.excludeDocs = self.packages.docs_excluded
        data.packages.excludeWeakdeps = self.packages.weakdeps_excluded

        if self.packages.missing_ignored:
            data.packages.handleMissing = KS_MISSING_IGNORE

        if self.packages.broken_ignored:
            data.packages.handleBroken = KS_BROKEN_IGNORE

        if self.packages.languages == RPM_LANGUAGES_NONE:
            data.packages.instLangs = ""
        elif self.packages.languages != RPM_LANGUAGES_ALL:
            data.packages.instLangs = self.packages.languages

        if self.packages.multilib_policy == MULTILIB_POLICY_ALL:
            data.packages.multiLib = True

        if self.packages.timeout != DNF_DEFAULT_TIMEOUT:
            data.packages.timeout = self.packages.timeout

        if self.packages.retries != DNF_DEFAULT_RETRIES:
            data.packages.retries = self.packages.retries

    def get_repo_configurations(self):
        """Get RepoConfiguration structures for all sources.

        These structures will be used by DNF payload in the main process.

        FIXME: This is a temporary solution. Will be removed after DNF payload logic is moved.

        :return: RepoConfiguration structures for attached sources.
        :rtype: RepoConfigurationData instances
        """
        structures = []

        for source in self.sources:
            structures.append(source.generate_repo_configuration())

        return structures

    def pre_install_with_tasks(self):
        """Execute preparation steps.

        :return: list of tasks
        """
        # TODO: Implement this method
        pass

    def install_with_tasks(self):
        """Install the payload.

        :return: list of tasks
        """
        # TODO: Implement this method
        pass

    def post_install_with_tasks(self):
        """Execute post installation steps.

        :return: list of tasks
        """
        # TODO: Implement this method
        pass
