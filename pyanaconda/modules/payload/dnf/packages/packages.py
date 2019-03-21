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
from pyanaconda.core.signal import Signal
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
        self.core_group_enabled_changed = Signal()
        self._default_environment = False

        self._environment = None
        self.environment_changed = Signal()
        self._groups = []
        self.groups_changed = Signal()
        self._packages = []
        self.packages_changed = Signal()

        self._excluded_packages = []
        self.excluded_packages_changed = Signal()
        self._excluded_groups = []
        self.excluded_groups_changed = Signal()

        self._docs_excluded = False
        self.docs_excluded_changed = Signal()
        self._weakdeps_excluded = False
        self.weakdeps_excluded_changed = Signal()
        self._missing_ignored = False
        self.missing_ignored_changed = Signal()
        self._languages = None
        self.languages_changed = Signal()
        self._multilib_policy = None
        self.multilib_policy_changed = Signal()
        self._timeout = None
        self.timeout_changed = Signal()
        self._retries = None
        self.retries_changed = Signal()

    def publish(self):
        """Publish the module."""
        DBus.publish_object(DNF_PACKAGES.object_path, PackagesHandlerInterface(self))

    def process_kickstart(self, data):
        """Process the kickstart data."""
        packages = data.packages

        self.set_core_group_enabled(not packages.nocore)
        self.set_default_environment(packages.default)

        self.set_environment(packages.environment)
        self.set_groups(packages.groupList)
        self.set_packages(packages.packageList)

        self.set_excluded_packages(packages.excludedList)
        self.set_excluded_groups(packages.excludedGroupList)

        self.set_docs_excluded(packages.excludeDocs)
        self.set_weakdeps_excluded(packages.excludeWeakdeps)

        if packages.handleMissing == KS_MISSING_IGNORE:
            self.set_missing_ignored(True)
        else:
            self.set_missing_ignored(False)

        self.set_languages(packages.instLangs)
        self.set_multilib_policy(packages.multiLib)
        self.set_timeout(packages.timeout)
        self.set_retries(packages.retries)

    def setup_kickstart(self, data):
        """Setup the kickstart data."""
        packages = data.packages

        packages.nocore = not self.core_group_enabled
        packages.default = self.default_environment

        packages.environment = self.environment
        packages.groupList = self.groups
        packages.packageList = self.packages

        packages.excludedList = self.excluded_packages
        packages.excludedGroupList = self.excluded_groups

        packages.excludeDocs = self.docs_excluded
        packages.excludeWeakdeps = self.weakdeps_excluded
        packages.handleMissing = KS_MISSING_IGNORE if self.missing_ignored else KS_MISSING_PROMPT
        packages.instLangs = self.languages
        packages.multiLib = self.multilib_policy
        packages.timeout = self.timeout
        packages.retries = self.retries

        # The empty packages section won't be printed without seen set to True
        packages.seen = True

    @property
    def core_group_enabled(self):
        """Should the core group be installed?

        :rtype: Bool
        """
        return self._core_group_enabled

    def set_core_group_enabled(self, core_group_enabled):
        """Set if the core group should be installed.

        :param core_group_enabled: True if the core group should be installed
        :type core_group_enabled: Bool
        """
        self._core_group_enabled = core_group_enabled
        self.core_group_enabled_changed.emit()
        log.debug("Core group enabled is set to %s.", core_group_enabled)

    @property
    def default_environment(self):
        """Default environment should be marked for installation?

        :rtype: Bool
        """
        return self._default_environment

    def set_default_environment(self, default_environment):
        """Mark the default environment for installation.

        :param default_environment: True if the default package set should be installed
        :type default_environment: True
        """
        self._default_environment = default_environment
        log.debug("Default package set is set to %s.", default_environment)

    @property
    def environment(self):
        """Get chosen packages environment.

        :rtype: str
        """
        return self._environment

    def set_environment(self, environment):
        """Set packages environment.

        :param environment: environment id
        :type environment: str
        """
        self._environment = environment
        self.environment_changed.emit()
        log.debug("Environment is set to %s.", environment)

    @property
    def groups(self):
        """Get list of package groups marked for installation.

        :rtype: [str]
        """
        return self._groups

    def set_groups(self, groups):
        """Set package groups marked for installation.

        :param groups: list of package groups
        :type groups: [str]
        """
        self._groups = groups
        self.groups_changed.emit()
        log.debug("Groups is set to %s.", groups)

    @property
    def packages(self):
        """Get list of packages marked for installation.

        :rtype: [str]
        """
        return self._packages

    def set_packages(self, packages):
        """Set list of packages marked for installation.

        :param packages: list of packages
        :type packages: [str]
        """
        self._packages = packages
        self.packages_changed.emit()
        log.debug("Packages is set to %s.", packages)

    @property
    def excluded_groups(self):
        """Get list of excluded groups from the installation.

        :rtype: [str]
        """
        return self._excluded_groups

    def set_excluded_groups(self, excluded_groups):
        """Set list of excluded groups to the installation.

        :param excluded_groups: list of excluded group
        :type excluded_groups: [str]
        """
        self._excluded_groups = excluded_groups
        self.excluded_groups_changed.emit()
        log.debug("Excluded groups is set to %s.", excluded_groups)

    @property
    def excluded_packages(self):
        """Get list of excluded packages from the installation.

        :rtype: [str]
        """
        return self._excluded_packages

    def set_excluded_packages(self, excluded_packages):
        """Set list of excluded packages from the installation.

        :param excluded_packages: list of excluded packages
        :type excluded_packages: [str]
        """
        self._excluded_packages = excluded_packages
        self.excluded_packages_changed.emit()
        log.debug("Excluded packages is set to %s.", excluded_packages)

    @property
    def docs_excluded(self):
        """Should the documentation be excluded during the installation.

        :rtype: bool
        """
        return self._docs_excluded

    def set_docs_excluded(self, docs_excluded):
        """Set if the documentation should be installed with the packages.

        :param docs_excluded: True if packages documentation should be installed
        :type docs_excluded: bool
        """
        self._docs_excluded = docs_excluded
        self.docs_excluded_changed.emit()
        log.debug("Exclude docs is set to %s.", docs_excluded)

    @property
    def weakdeps_excluded(self):
        """Should the packages weak dependencies be excluded from the installation.

        :rtype: bool
        """
        return self._weakdeps_excluded

    def set_weakdeps_excluded(self, weakdeps_excluded):
        """Set if the weak dependencies should be excluded during the installation.

        :param weakdeps_excluded: True if the weak dependencies should be excluded
        :type weakdeps_excluded: bool
        """
        self._weakdeps_excluded = weakdeps_excluded
        self.weakdeps_excluded_changed.emit()
        log.debug("Exclude weakdeps is set to %s.", weakdeps_excluded)

    @property
    def missing_ignored(self):
        """Ignore packages that are missing from the repositories.

        :rtype: bool
        """
        return self._missing_ignored

    def set_missing_ignored(self, missing_ignored):
        """Set if the packages missing during the installation should be ignored.

        :param missing_ignored: True if missing packages should be ignored.
        :type missing_ignored: bool
        """
        self._missing_ignored = missing_ignored
        self.missing_ignored_changed.emit()
        log.debug("Ignore missing is set to %s.", missing_ignored)

    @property
    def languages(self):
        """Languages marked for installation.

        In case multiple languages are specified they are split by ',' in the string returned.

        :rtype: str
        """
        return self._languages

    def set_languages(self, languages):
        """Languages marked for installation.

        :param languages: list of languages split by ','
        :type languages: str
        """
        self._languages = languages
        self.languages_changed.emit()
        log.debug("Install languages is set to %s.", languages)

    @property
    def multilib_policy(self):
        """Enable 'all' multilib policy as opposed to the default of “best”.

        :rtype: bool
        """
        return self._multilib_policy

    def set_multilib_policy(self, multilib_policy):
        """Set the multilib 'all' policy.

        :param multilib_policy: True if we want to set 'all' multilib policy.
        :type multilib_policy: bool
        """
        self._multilib_policy = multilib_policy
        self.multilib_policy_changed.emit()
        log.debug("Multilib policy is set to %s.", multilib_policy)

    @property
    def timeout(self):
        """Timeout how long to try before failing during the package installation.

        :rtype: int
        """
        return self._timeout

    def set_timeout(self, timeout):
        """Set timeout how long to try before failing during the package installation.

        :param timeout: number of seconds to wait
        :type timeout: int
        """
        self._timeout = timeout
        self.timeout_changed.emit()
        log.debug("Timeout is set to %s.", timeout)

    @property
    def retries(self):
        """How many times to try before failing during the package installation.

        :rtype: int
        """
        return self._retries

    def set_retries(self, retries):
        """Set how many times to try before failing during the package installation.

        :param retries: number of how many times to try
        :type retries: int
        """
        self._retries = retries
        self.retries_changed.emit()
        log.debug("Retries is set to %s.", retries)
