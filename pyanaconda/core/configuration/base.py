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
import configparser
import os
from abc import ABC


class ConfigurationError(Exception):
    """A general configuration error."""


class ConfigurationFileError(ConfigurationError):
    """An error in the configuration file."""

    def __init__(self, msg, filename):
        super().__init__(msg)
        self._filename = filename

    def __str__(self):
        return "The following error has occurred while handling the configuration file '{}': " \
               "{}".format(self._filename, super().__str__())


class ConfigurationDataError(ConfigurationError):
    """An error in the configuration data."""

    def __init__(self, msg, section, option):
        super().__init__(msg)
        self._section = section
        self._option = option

    def __str__(self):
        return "The following error has occurred while handling the option '{}' in the section " \
               "'{}': {}".format(self._option, self._section, super().__str__())


def create_parser():
    """Create a new config parser.

    :return: an instance of ConfigParser
    """
    return configparser.ConfigParser()


def read_config(parser, path):
    """Read a configuration file.

    :param parser: an instance of ConfigParser
    :param path: a path to the file
    :raises: ConfigurationFileError
    """
    try:
        with open(path, "r") as f:
            parser.read_file(f, path)

    except (configparser.Error, OSError) as e:
        raise ConfigurationFileError(str(e), path) from e


def write_config(parser, path):
    """Write a configuration file.

    :param parser: an instance of ConfigParser
    :param path: a path to the file
    :raises: ConfigurationFileError
    """
    try:
        with open(path, "w") as f:
            parser.write(f)

    except (configparser.Error, OSError) as e:
        raise ConfigurationFileError(str(e), path) from e


def get_option(parser, section_name, option_name, converter=None):
    """Get a converted value of the option.

    The converter should accept a string and return a converted value.
    For example: int

    :param parser: an instance of ConfigParser
    :param section_name: a section name
    :param option_name: an option name
    :param converter: a function or None
    :return: a converted value
    :raises: ConfigurationAccessError
    """
    try:
        # Return a string.
        if converter is None:
            return parser.get(section_name, option_name)

        # Return a boolean.
        if converter is bool:
            return parser.getboolean(section_name, option_name)

        # Return a converted value.
        return converter(parser.get(section_name, option_name))

    except (configparser.Error, ValueError) as e:
        raise ConfigurationDataError(str(e), section_name, option_name) from e


def set_option(parser, section_name, option_name, value):
    """Set the option.

    :param parser: an instance of ConfigParser
    :param section_name: a section name
    :param option_name: an option name
    :param value: an option value
    :raises: ConfigurationAccessError
    """
    try:
        # Make sure that the section and option exists.
        parser.get(section_name, option_name)

        # Set the option to the string representation of the value.
        parser[section_name][option_name] = str(value)

    except (configparser.Error, ValueError) as e:
        raise ConfigurationDataError(str(e), section_name, option_name) from e


class Section(ABC):
    """A base class for representation of a configuration section."""

    def __init__(self, section_name, parser):
        self._section_name = section_name
        self._parser = parser

    def _has_option(self, option_name):
        """Is the specified option defined?.

        :param option_name: an option name
        :return: True or False
        """
        return self._parser.has_option(self._section_name, option_name)

    def _get_option(self, option_name, converter=None):
        """Get a converted value of the option.

        :param option_name: an option name
        :param converter: a function or None
        :return: a converted value
        """
        return get_option(self._parser, self._section_name, option_name, converter)

    def _set_option(self, option_name, value):
        """Set the option.

        :param option_name: an option name
        :param value: an option value
        """
        set_option(self._parser, self._section_name, option_name, value)


class Configuration:
    """A base class for representation of a configuration handler."""

    def __init__(self):
        """Initialize the configuration."""
        self._sources = []
        self._parser = create_parser()

    def get_parser(self):
        """Get the configuration parser.

        :return: instance of the ConfigParser
        """
        return self._parser

    def get_sources(self):
        """Get the configuration sources.

        :return: a list of file names
        """
        return self._sources

    def read(self, path):
        """Read a configuration file.

        :param path: a path to the file
        """
        read_config(self._parser, path)
        self._sources.append(path)

    def read_from_directory(self, path):
        """Read all configuration files in a directory

        Find and read all *.conf files sorted by their name.

        :return: a path to the directory
        """
        for filename in sorted(os.listdir(path)):
            if not filename.endswith(".conf"):
                continue

            self.read(os.path.join(path, filename))

    def write(self, path):
        """Write a configuration file.

        :param path: a path to the file
        """
        write_config(self._parser, path)

    def validate(self):
        """Validate the configuration."""
        self._validate_members(self)

    def _validate_members(self, obj):
        """Validate members of the object.

        The main goal of this method is to check if all sections
        are accessible and all options readable and convertible.

        The implementation actually tries to access all public
        members of the given object and its sections.
        """
        for member_name in dir(obj):

            # Skip private members.
            if member_name.startswith("_"):
                continue

            # Try to get the value of the member.
            value = getattr(obj, member_name)

            # Validate the sections of the configuration object.
            if isinstance(obj, Configuration) and isinstance(value, Section):
                self._validate_members(value)
