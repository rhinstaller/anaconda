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
#  Author(s):  Vendula Poncova <vponcova@redhat.com>
#
import os

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.base import (
    ConfigurationError,
    create_parser,
    get_option,
    read_config,
)

log = get_module_logger(__name__)


__all__ = ["ProfileLoader"]


class ProfileData:
    """A class that represents a profile."""

    def __init__(self):
        """Create the profile data."""
        self.config_path = ""
        self.profile_id = ""
        self.base_profile = ""
        self.os_id = ""
        self.variant_id = ""

    def load_from_file(self, config_path):
        """Load information about a profile from the given configuration file.

        :param config_path: a path to a configuration file
        :raises: ConfigurationError if a profile cannot be loaded
        """
        # Set up the parser.
        parser = create_parser()
        self._create_profile_section(parser)
        self._create_profile_detection_section(parser)

        # Read the profile sections.
        self.config_path = config_path
        read_config(parser, config_path)

        self._read_profile_section(parser)
        self._read_profile_detection_section(parser)

        if not self.profile_id:
            raise ConfigurationError("The profile id is not specified!")

    def _create_profile_section(self, parser):
        """Create the [Profile] section.

        :param parser: a configuration parser
        """
        section_name = "Profile"
        parser.add_section(section_name)
        parser.set(section_name, "profile_id", "")
        parser.set(section_name, "base_profile", "")

    def _read_profile_section(self, parser):
        """Read the [Profile] section.

        :param parser: a configuration parser
        """
        section_name = "Profile"
        self.profile_id = get_option(parser, section_name, "profile_id")
        self.base_profile = get_option(parser, section_name, "base_profile")

    def _create_profile_detection_section(self, parser):
        """Create the [Profile Detection] section.

        :param parser: a configuration parser
        """
        section_name = "Profile Detection"
        parser.add_section(section_name)
        parser.set(section_name, "os_id", "")
        parser.set(section_name, "variant_id", "")

    def _read_profile_detection_section(self, parser):
        """Read the [Profile Detection] section.

        :param parser: a configuration parser
        """
        section_name = "Profile Detection"
        self.os_id = get_option(parser, section_name, "os_id")
        self.variant_id = get_option(parser, section_name, "variant_id")


class ProfileLoader:
    """A class for loading information about profiles from configuration files."""

    def __init__(self):
        """Create a new loader."""
        self._profiles = {}

    def load_profiles(self, config_dir):
        """Load information about profiles from the given configuration directory.

        Invalid configuration files will be skipped.

        :param config_dir: a path to a directory
        """
        log.info("Loading information about profiles from %s.", config_dir)

        for file_name in sorted(os.listdir(config_dir)):
            if not file_name.endswith(".conf"):
                continue

            config_path = os.path.join(config_dir, file_name)

            try:
                self.load_profile(config_path)
            except ConfigurationError as e:
                log.error("Skipping an invalid configuration at %s: %s", config_path, e)

    def load_profile(self, config_path):
        """Load information about a profile from the given configuration file.

        :param config_path: a path to a configuration file
        :raises: ConfigurationError if a profile cannot be loaded
        """
        data = ProfileData()

        # Load the profile.
        data.load_from_file(config_path)
        profile_id = data.profile_id

        if profile_id in self._profiles:
            raise ConfigurationError("The '{}' profile was already loaded.".format(profile_id))

        # Add the profile.
        log.info("Found the '%s' profile at %s.", profile_id, config_path)
        self._profiles[profile_id] = data

    def check_profile(self, profile_id):
        """Check if the specified profile is supported.

        :param profile_id: an id of the profile
        :return: True if the profile is supported, otherwise False
        """
        if profile_id not in self._profiles:
            log.warning("No support for the '%s' profile.", profile_id)
            return False

        try:
            self._get_profile_bases(profile_id)
        except ConfigurationError as e:
            log.warning("Invalid support for the '%s' profile: %s", profile_id, e)
            return False

        return True

    def detect_profile(self, os_id, variant_id=None):
        """Find a profile that matches the specified values.

        :param str os_id: an id of the operating system or None
        :param str variant_id: an id of a specific variant of the operating system or None
        :return: a product id or None
        """
        log.debug("Detecting a profile for ID=%s, VARIANT_ID=%s.", os_id, variant_id)

        # Collect keys and profiles for the detection.
        profiles = {}

        for profile_id, data in self._profiles.items():
            key = (data.os_id, data.variant_id)

            # The profile is not detectable.
            if not any(key):
                continue

            profiles[key] = profile_id

        # Find a profile with the best match.
        profile_id = profiles.get((os_id, variant_id)) or profiles.get((os_id, ""))

        if profile_id:
            log.info("The '%s' profile is detected.", profile_id)

        return profile_id

    def collect_configurations(self, profile_id):
        """Collect configuration files of the given profile.

        The configuration files should be processed in the given order.

        :param profile_id: an id of the profile
        :return: a list of paths to configuration files
        """
        return self._get_profile_configs(profile_id)

    def _get_profile_config(self, profile_id):
        """Get the configuration path of the profile.

        :param profile_id: an id of the profile
        :return: a path to a configuration file
        """
        return self._profiles.get(profile_id).config_path

    def _get_profile_configs(self, profile_id):
        """Get a list of configuration paths of the profile.

        The configuration files should be processed in the given order.

        :param profile_id: an id of the profile
        :return: a list of paths to a configuration files
        """
        profile_ids = reversed(self._get_profile_bases(profile_id))
        return [self._get_profile_config(i) for i in profile_ids]

    def _get_profile_base(self, profile_id):
        """Get the base of the profile.

        :param profile_id: an id of the profile
        :return: an id of the base profile
        """
        return self._profiles.get(profile_id).base_profile

    def _get_profile_bases(self, profile_id):
        """Return a list of bases of the given profile.

        The profiles are ordered by the "is based on" relation.

        If the profile A is based on the profile B and the profile B
        is based on the profile C, then the related profiles of the
        profile A are: A, B, C

        :param profile_id: an id of the profile
        :return: a list of ids of the base profiles
        :raises: ConfigurationError if the dependencies cannot be resolved
        """
        current_id = profile_id
        visited = set()
        profiles = []

        while current_id:
            if current_id not in self._profiles:
                raise ConfigurationError(
                    "Dependencies of the '{}' profile cannot be resolved "
                    "due to an unknown '{}' profile.".format(profile_id, current_id)
                )

            if current_id in visited:
                raise ConfigurationError(
                    "Dependencies of the '{}' profile cannot be resolved "
                    "due to a conflict with '{}'.".format(profile_id, current_id)
                )

            visited.add(current_id)
            profiles.append(current_id)
            current_id = self._get_profile_base(current_id)

        return profiles
