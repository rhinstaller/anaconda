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
#  Author(s):  Vendula Poncova <vponcova@redhat.com>
#
import configparser


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

    except (configparser.Error, IOError) as e:
        raise ConfigurationFileError(str(e), path)


def write_config(parser, path):
    """Write a configuration file.

    :param parser: an instance of ConfigParser
    :param path: a path to the file
    :raises: ConfigurationFileError
    """
    try:
        with open(path, "w") as f:
            parser.write(f)

    except (configparser.Error, IOError) as e:
        raise ConfigurationFileError(str(e), path)


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
        raise ConfigurationDataError(str(e), section_name, option_name)


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
        raise ConfigurationDataError(str(e), section_name, option_name)
