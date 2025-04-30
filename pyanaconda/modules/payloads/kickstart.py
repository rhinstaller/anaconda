#
# Kickstart handler for packaging.
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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pykickstart.constants import (
    GROUP_ALL,
    GROUP_DEFAULT,
    GROUP_REQUIRED,
    KS_BROKEN_IGNORE,
    KS_MISSING_IGNORE,
)
from pykickstart.parser import Group, Packages
from pykickstart.sections import PackageSection

from pyanaconda.core.constants import (
    DNF_DEFAULT_REPO_COST,
    DNF_DEFAULT_RETRIES,
    DNF_DEFAULT_TIMEOUT,
    GROUP_PACKAGE_TYPES_ALL,
    GROUP_PACKAGE_TYPES_REQUIRED,
    MULTILIB_POLICY_ALL,
    REPO_ORIGIN_SYSTEM,
    REPO_ORIGIN_USER,
    RPM_LANGUAGES_ALL,
    RPM_LANGUAGES_NONE,
    URL_TYPE_BASEURL,
    URL_TYPE_METALINK,
    URL_TYPE_MIRRORLIST,
)
from pyanaconda.core.kickstart import KickstartSpecification
from pyanaconda.core.kickstart import commands as COMMANDS
from pyanaconda.modules.common.structures.packages import (
    PackagesConfigurationData,
    PackagesSelectionData,
)
from pyanaconda.modules.common.structures.payload import RepoConfigurationData


def convert_ks_repo_to_repo_data(ks_data):
    """Convert the kickstart command into a repo configuration.

    :param RepoData ks_data: a kickstart data
    :return RepoConfigurationData: a repo configuration
    """
    repo_data = RepoConfigurationData()
    repo_data.name = ks_data.name

    if ks_data.baseurl:
        repo_data.url = ks_data.baseurl
        repo_data.type = URL_TYPE_BASEURL
    elif ks_data.mirrorlist:
        repo_data.url = ks_data.mirrorlist
        repo_data.type = URL_TYPE_MIRRORLIST
    elif ks_data.metalink:
        repo_data.url = ks_data.metalink
        repo_data.type = URL_TYPE_METALINK

    if not repo_data.url:
        repo_data.origin = REPO_ORIGIN_SYSTEM
    else:
        repo_data.origin = REPO_ORIGIN_USER

    repo_data.proxy = ks_data.proxy or ""
    repo_data.cost = ks_data.cost or DNF_DEFAULT_REPO_COST
    repo_data.included_packages = ks_data.includepkgs
    repo_data.excluded_packages = ks_data.excludepkgs
    repo_data.installation_enabled = ks_data.install

    repo_data.ssl_verification_enabled = not ks_data.noverifyssl
    repo_data.ssl_configuration.ca_cert_path = ks_data.sslcacert or ""
    repo_data.ssl_configuration.client_cert_path = ks_data.sslclientcert or ""
    repo_data.ssl_configuration.client_key_path = ks_data.sslclientkey or ""

    return repo_data


def convert_repo_data_to_ks_repo(repo_data):
    """Convert the repo configuration into a kickstart command.

    :param RepoConfigurationData repo_data: a repo configuration
    :return RepoData: a kickstart data
    """
    ks_data = COMMANDS.RepoData()
    ks_data.name = repo_data.name

    if repo_data.type == URL_TYPE_BASEURL:
        ks_data.baseurl = repo_data.url
    elif repo_data.type == URL_TYPE_MIRRORLIST:
        ks_data.mirrorlist = repo_data.url
    elif repo_data.type == URL_TYPE_METALINK:
        ks_data.metalink = repo_data.url

    ks_data.proxy = repo_data.proxy
    ks_data.noverifyssl = not repo_data.ssl_verification_enabled
    ks_data.sslcacert = repo_data.ssl_configuration.ca_cert_path
    ks_data.sslclientcert = repo_data.ssl_configuration.client_cert_path
    ks_data.sslclientkey = repo_data.ssl_configuration.client_key_path

    if repo_data.cost != DNF_DEFAULT_REPO_COST:
        ks_data.cost = repo_data.cost

    ks_data.includepkgs = repo_data.included_packages
    ks_data.excludepkgs = repo_data.excluded_packages
    ks_data.install = repo_data.installation_enabled

    return ks_data


def convert_ks_data_to_packages_configuration(ks_data):
    """Convert the kickstart data into a packages configuration.

    :param KickstartHandler ks_data: a kickstart data
    :return PackagesSelectionData: a packages selection data
    """
    configuration = PackagesConfigurationData()
    configuration.docs_excluded = ks_data.packages.excludeDocs
    configuration.weakdeps_excluded = ks_data.packages.excludeWeakdeps

    if ks_data.packages.handleMissing == KS_MISSING_IGNORE:
        configuration.missing_ignored = True

    if ks_data.packages.handleBroken == KS_BROKEN_IGNORE:
        configuration.broken_ignored = True

    if ks_data.packages.instLangs == "":
        configuration.languages = RPM_LANGUAGES_NONE
    elif ks_data.packages.instLangs is not None:
        configuration.languages = ks_data.packages.instLangs

    if ks_data.packages.multiLib:
        configuration.multilib_policy = MULTILIB_POLICY_ALL

    if ks_data.packages.timeout is not None:
        configuration.timeout = ks_data.packages.timeout

    if ks_data.packages.retries is not None:
        configuration.retries = ks_data.packages.retries

    return configuration


def convert_packages_configuration_to_ksdata(configuration, ks_data):
    """Convert the packages configuration into a kickstart data.

    :param PackagesConfigurationData configuration: a packages configuration data
    :param KickstartHandler ks_data: a kickstart data to modify
    """
    ks_data.packages.excludeDocs = configuration.docs_excluded
    ks_data.packages.excludeWeakdeps = configuration.weakdeps_excluded

    if configuration.missing_ignored:
        ks_data.packages.handleMissing = KS_MISSING_IGNORE

    if configuration.broken_ignored:
        ks_data.packages.handleBroken = KS_BROKEN_IGNORE

    if configuration.languages == RPM_LANGUAGES_NONE:
        ks_data.packages.instLangs = ""
    elif configuration.languages != RPM_LANGUAGES_ALL:
        ks_data.packages.instLangs = configuration.languages

    if configuration.multilib_policy == MULTILIB_POLICY_ALL:
        ks_data.packages.multiLib = True

    if configuration.timeout != DNF_DEFAULT_TIMEOUT:
        ks_data.packages.timeout = configuration.timeout

    if configuration.retries != DNF_DEFAULT_RETRIES:
        ks_data.packages.retries = configuration.retries


def convert_ks_data_to_packages_selection(ks_data):
    """Convert the kickstart data into a packages selection.

    :param KickstartHandler ks_data: a kickstart data
    :return PackagesSelectionData: a packages selection data
    """
    selection = PackagesSelectionData()
    selection.core_group_enabled = not ks_data.packages.nocore
    selection.default_environment_enabled = ks_data.packages.default

    if ks_data.packages.environment is not None:
        selection.environment = ks_data.packages.environment

    selection.packages = ks_data.packages.packageList
    selection.excluded_packages = ks_data.packages.excludedList

    for group in ks_data.packages.groupList:
        selection.groups.append(group.name)

        if group.include == GROUP_ALL:
            selection.groups_package_types[group.name] = GROUP_PACKAGE_TYPES_ALL

        if group.include == GROUP_REQUIRED:
            selection.groups_package_types[group.name] = GROUP_PACKAGE_TYPES_REQUIRED

    for group in ks_data.packages.excludedGroupList:
        selection.excluded_groups.append(group.name)

    return selection


def convert_packages_selection_to_ksdata(selection, ks_data):
    """Convert the packages selection into a kickstart data.

    :param PackagesSelectionData selection: a packages selection data
    :param KickstartHandler ks_data: a kickstart data to modify
    """
    # The empty packages section won't be printed without seen set to True.
    ks_data.packages.seen = True
    ks_data.packages.nocore = not selection.core_group_enabled
    ks_data.packages.default = selection.default_environment_enabled

    if selection.environment:
        ks_data.packages.environment = selection.environment

    ks_data.packages.packageList = selection.packages
    ks_data.packages.excludedList = selection.excluded_packages

    for group_name in selection.groups:
        package_types = selection.groups_package_types.get(
            group_name, []
        )
        group_include = GROUP_DEFAULT

        if set(package_types) == set(GROUP_PACKAGE_TYPES_ALL):
            group_include = GROUP_ALL

        if set(package_types) == set(GROUP_PACKAGE_TYPES_REQUIRED):
            group_include = GROUP_REQUIRED

        ks_group = create_ks_group(
            name=group_name,
            include=group_include
        )
        ks_data.packages.groupList.append(ks_group)

    for group_name in selection.excluded_groups:
        ks_group = create_ks_group(
            name=group_name
        )
        ks_data.packages.excludedGroupList.append(ks_group)


def create_ks_group(name, include=GROUP_DEFAULT):
    """Create a new instance of a kickstart group.

    :param name: a name of the group
    :param include: a level of inclusion
    :return: a kickstart group object
    """
    return Group(name=name, include=include)


class PayloadKickstartSpecification(KickstartSpecification):
    """The kickstart specification of the Payloads module."""

    commands = {
        "cdrom": COMMANDS.Cdrom,
        "harddrive": COMMANDS.HardDrive,
        "hmc": COMMANDS.Hmc,
        "liveimg": COMMANDS.Liveimg,
        "module": COMMANDS.Module,
        "nfs": COMMANDS.NFS,
        "ostreecontainer": COMMANDS.OSTreeContainer,
        "ostreesetup": COMMANDS.OSTreeSetup,
        "bootc": COMMANDS.Bootc,
        "repo": COMMANDS.Repo,
        "url": COMMANDS.Url
    }

    commands_data = {
        "ModuleData": COMMANDS.ModuleData,
        "RepoData": COMMANDS.RepoData,

    }

    sections = {
        "packages": PackageSection
    }

    sections_data = {
        "packages": Packages
    }
