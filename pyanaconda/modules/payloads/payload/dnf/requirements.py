#
# The support for package and group requirements
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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import os

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import (
    MULTILIB_POLICY_BEST,
    REQUIREMENT_TYPE_GROUP,
    REQUIREMENT_TYPE_PACKAGE,
)
from pyanaconda.core.hw import detect_virtualized_platform
from pyanaconda.localization import find_best_locale_match, is_valid_langcode
from pyanaconda.modules.common.constants.services import BOSS, LOCALIZATION
from pyanaconda.modules.common.structures.requirement import Requirement
from pyanaconda.modules.common.util import is_module_available

log = get_module_logger(__name__)


def collect_remote_requirements():
    """Collect requirements of the DBus modules.

    :return: a list of requirements
    """
    boss = BOSS.get_proxy()
    return Requirement.from_structure_list(
        boss.CollectRequirements()
    )


def collect_language_requirements(dnf_manager):
    """Collect requirements for supported languages.

    :param dnf_manager: a DNF manager
    :return: a list of requirements
    """
    requirements = []

    if not is_module_available(LOCALIZATION):
        return requirements

    localization_proxy = LOCALIZATION.get_proxy()
    locales = [localization_proxy.Language] + localization_proxy.LanguageSupport

    # Find all available langpacks.
    packages = dnf_manager.match_available_packages("langpacks-*")

    # Get all valid langcodes.
    codes = [p.split('-', 1)[1] for p in packages]
    codes = list(filter(is_valid_langcode, codes))

    # Find the best langpacks to install.
    for locale in locales:
        best_locale = find_best_locale_match(locale, codes)

        if not best_locale:
            log.warning("Selected locale '%s' does not match "
                        "any available langpacks.", locale)
            continue

        requirements.append(Requirement.for_package(
            package_name="langpacks-" + best_locale,
            reason="Required to support the locale '{}'.".format(locale)
        ))

    return requirements


def collect_dnf_requirements(dnf_manager, packages_configuration):
    """Collect the requirements for the current dnf.

    :param dnf_manager: a DNF manager
    :param package_configuration: packages selection
    :return: a list of requirements
    """
    requirements = []

    # Detect if dnf plugin is required
    if dnf_manager.is_package_available("dnf5"):
        plugins_name = "dnf5-plugins"
    else:
        plugins_name = "dnf-plugins-core"

    if packages_configuration.multilib_policy != MULTILIB_POLICY_BEST:
        requirements.append(
            Requirement.for_package(plugins_name, reason="Needed to enable multilib support.")
        )

    return requirements


def collect_platform_requirements(dnf_manager):
    """Collect the requirements for the current platform.

    :param dnf_manager: a DNF manager
    :return: a list of requirements
    """
    # Detect the current platform.
    platform = detect_virtualized_platform()

    if not platform:
        return []

    # Add a platform specific group.
    group = "platform-" + platform.lower()

    if group not in dnf_manager.groups:
        log.warning("Platform group %s not available.", group)
        return []

    return [Requirement.for_group(
        group_name=group,
        reason="Required for the {} platform.".format(platform)
    )]


def collect_driver_disk_requirements(path="/run/install/dd_packages"):
    """Collect the requirements from the driver updates disk.

    :param path: a path to the file with a package list
    :return: a list of requirements
    """
    requirements = []

    if not os.path.exists(path):
        return []

    with open(path, "r") as f:
        for line in f:
            package = line.strip()
            requirements.append(Requirement.for_package(
                package_name=package,
                reason="Required by the driver updates disk."
            ))

    return requirements


def apply_requirements(requirements, include_list, exclude_list):
    """Apply the provided requirements.

    :param requirements: a list of requirements
    :param include_list: a list of specs to include in the transaction
    :param exclude_list: a list of specs to exclude from the transaction
    """
    log.debug("Applying requirements: %s", requirements)

    for r in requirements:
        # Generate a spec for the requirement.
        if r.type == REQUIREMENT_TYPE_PACKAGE:
            spec = r.name
        elif r.type == REQUIREMENT_TYPE_GROUP:
            spec = "@{}".format(r.name)
        else:
            log.warning("Unsupported type '%s' of the requirement.", r.type)
            continue

        # Check if the requirement can be applied.
        if spec in conf.payload.ignored_packages:
            log.debug("Requirement '%s' is ignored by the configuration.", spec)
            continue

        if spec in exclude_list:
            log.debug("Requirement '%s' is ignored because it's excluded.", spec)
            continue

        # Apply the requirement.
        include_list.append(spec)
        log.debug("Requirement '%s' is applied. Reason: %s", spec, r.reason)
