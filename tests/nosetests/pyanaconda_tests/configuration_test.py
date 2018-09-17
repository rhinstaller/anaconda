#
# Copyright (C) 2018  Red Hat, Inc.
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
# Red Hat Author(s): Vendula Poncova <vponcova@redhat.com>
#
import os
import tempfile
import unittest
from textwrap import dedent

from pyanaconda.core.configuration.anaconda import AnacondaConfiguration
from pyanaconda.core.configuration.base import create_parser, read_config, write_config, \
    get_option, set_option, ConfigurationError, ConfigurationDataError, ConfigurationFileError


class ConfigurationTestCase(unittest.TestCase):
    """Test the configuration support."""

    @property
    def _content(self):
        return dedent("""

        [Main]
        string = Hello
        integer = 1
        boolean = False

        """)

    def _read_content(self, parser):

        with tempfile.NamedTemporaryFile("w") as f:
            # Prepare the config file.
            f.write(self._content)
            f.flush()

            # Read the config file.
            read_config(parser, f.name)

        return parser

    def read_test(self):
        parser = create_parser()
        self._read_content(parser)

    def invalid_read_test(self):
        parser = create_parser()

        with self.assertRaises(ConfigurationFileError) as cm:
            read_config(parser, "nonexistent/path/to/file")

        self.assertEqual(cm.exception._filename, "nonexistent/path/to/file")

    def write_test(self):
        parser = create_parser()
        self._read_content(parser)

        with tempfile.NamedTemporaryFile("r+") as f:
            # Write the config file.
            write_config(parser, f.name)
            f.flush()

            # Check the config file.
            self.assertEqual(f.read().strip(), self._content.strip())

    def invalid_write_test(self):
        parser = create_parser()

        with self.assertRaises(ConfigurationFileError) as cm:
            write_config(parser, "nonexistent/path/to/file")

        self.assertEqual(cm.exception._filename, "nonexistent/path/to/file")

    def get_test(self):
        parser = create_parser()
        self._read_content(parser)

        self.assertEqual(get_option(parser, "Main", "string"), "Hello")
        self.assertEqual(get_option(parser, "Main", "integer"), "1")
        self.assertEqual(get_option(parser, "Main", "boolean"), "False")

        self.assertEqual(get_option(parser, "Main", "string", str), "Hello")
        self.assertEqual(get_option(parser, "Main", "integer", int), 1)
        self.assertEqual(get_option(parser, "Main", "boolean", bool), False)

    def invalid_get_test(self):
        parser = create_parser()
        self._read_content(parser)

        # Invalid value.
        with self.assertRaises(ConfigurationDataError) as cm:
            get_option(parser, "Main", "string", bool)

        self.assertEqual(cm.exception._section, "Main")
        self.assertEqual(cm.exception._option, "string")

        # Invalid option.
        with self.assertRaises(ConfigurationDataError) as cm:
            get_option(parser, "Main", "unknown")

        self.assertEqual(cm.exception._section, "Main")
        self.assertEqual(cm.exception._option, "unknown")

        # Invalid section.
        with self.assertRaises(ConfigurationDataError) as cm:
            get_option(parser, "Unknown", "unknown")

        self.assertEqual(cm.exception._section, "Unknown")
        self.assertEqual(cm.exception._option, "unknown")

    def set_test(self):
        parser = create_parser()
        self._read_content(parser)

        set_option(parser, "Main", "string", "Hi")
        set_option(parser, "Main", "integer", 2)
        set_option(parser, "Main", "boolean", True)

        self.assertEqual(get_option(parser, "Main", "string"), "Hi")
        self.assertEqual(get_option(parser, "Main", "integer"), "2")
        self.assertEqual(get_option(parser, "Main", "boolean"), "True")

        self.assertEqual(get_option(parser, "Main", "string", str), "Hi")
        self.assertEqual(get_option(parser, "Main", "integer", int), 2)
        self.assertEqual(get_option(parser, "Main", "boolean", bool), True)

    def invalid_set_test(self):
        parser = create_parser()
        self._read_content(parser)

        # Invalid option.
        with self.assertRaises(ConfigurationDataError) as cm:
            set_option(parser, "Main", "unknown", "value")

        self.assertEqual(cm.exception._section, "Main")
        self.assertEqual(cm.exception._option, "unknown")

        # Invalid section.
        with self.assertRaises(ConfigurationDataError) as cm:
            set_option(parser, "Unknown", "unknown", "value")

        self.assertEqual(cm.exception._section, "Unknown")
        self.assertEqual(cm.exception._option, "unknown")


class AnacondaConfigurationTestCase(unittest.TestCase):
    """Test the Anaconda configuration."""

    def default_configuration_test(self):
        # Make sure that we are able to import conf.
        from pyanaconda.core.configuration.anaconda import conf
        self.assertEqual(conf.anaconda.debug, False)

    def source_test(self):
        conf = AnacondaConfiguration()
        sources = conf.get_sources()
        self.assertEqual(sources, [])

    def default_source_test(self):
        conf = AnacondaConfiguration.from_defaults()
        sources = conf.get_sources()
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0], os.environ.get("ANACONDA_CONFIG_TMP"))

    def default_validation_test(self):
        conf = AnacondaConfiguration.from_defaults()
        conf.validate()

        # Set invalid value.
        parser = conf.get_parser()
        parser["Anaconda"]["debug"] = "string"
        with self.assertRaises(ConfigurationError):
            conf.validate()

        # Remove a required option.
        parser.remove_option("Anaconda", "debug")
        with self.assertRaises(ConfigurationError):
            conf.validate()

        # Remove a required section.
        parser.remove_section("Anaconda")
        with self.assertRaises(ConfigurationError):
            conf.validate()

    def read_test(self):
        conf = AnacondaConfiguration()

        with tempfile.NamedTemporaryFile("w") as f:
            conf.read(f.name)
            self.assertEqual(len(conf.get_sources()), 1)
            self.assertEqual(conf.get_sources()[0], f.name)

    def default_read_test(self):
        AnacondaConfiguration.from_defaults()

    def write_test(self):
        conf = AnacondaConfiguration()

        with tempfile.NamedTemporaryFile("r+") as f:
            conf.write(f.name)
            f.flush()
            self.assertFalse(f.read(), "The file should be empty.")

    def default_write_test(self):
        conf = AnacondaConfiguration.from_defaults()

        with tempfile.NamedTemporaryFile("r+") as f:
            conf.write(f.name)
            f.flush()
            self.assertTrue(f.read(), "The file shouldn't be empty.")
