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

from blivet.size import Size

from pyanaconda.core.configuration.anaconda import AnacondaConfiguration
from pyanaconda.core.configuration.base import create_parser, read_config, write_config, \
    get_option, set_option, ConfigurationError, ConfigurationDataError, ConfigurationFileError, \
    Configuration
from pyanaconda.core.configuration.storage import StorageSection
from pyanaconda.modules.common.constants import services


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
        self.assertTrue(str(cm.exception).startswith(
            "The following error has occurred while handling the configuration file"
        ))

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

        self.assertTrue(str(cm.exception).startswith(
            "The following error has occurred while handling the option"
        ))

    def configuration_test(self):
        config = Configuration()

        with tempfile.TemporaryDirectory() as directory:

            for filename in ["d.conf", "a.conf", "c", "b.conf"]:
                with open(os.path.join(directory, filename), mode="w") as f:
                    f.write("")

            config.read_from_directory(directory)

            self.assertEqual(
                [os.path.relpath(path, directory) for path in config.get_sources()],
                ["a.conf", "b.conf", "d.conf"]
            )


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

    def set_from_files_test(self):
        conf = AnacondaConfiguration.from_defaults()
        paths = []

        with tempfile.TemporaryDirectory() as d:
            # Add nonexistent file.
            nonexistent = os.path.join(d, "nonexistent")
            paths.append(nonexistent)

            # Add empty directory.
            empty_dir = os.path.join(d, "empty")
            os.mkdir(empty_dir)
            paths.append(empty_dir)

            # Add existing file.
            existing = os.path.join(d, "a.conf")
            paths.append(existing)

            with open(existing, mode="w") as f:
                f.write("")

            # Add non-empty directory.
            conf_dir = os.path.join(d, "conf.d")
            os.mkdir(conf_dir)
            paths.append(conf_dir)

            for name in ["b.conf", "c.conf", "d"]:
                with open(os.path.join(conf_dir, name), mode="w") as f:
                    f.write("")

            # Check the paths.
            self.assertEqual(
                [os.path.relpath(path, d) for path in paths],
                ["nonexistent", "empty", "a.conf", "conf.d"]
            )

            conf._sources = []
            conf.set_from_files(paths)

            # Check the loaded files.
            self.assertEqual(
                [os.path.relpath(path, d) for path in conf.get_sources()],
                ["a.conf", "conf.d/b.conf", "conf.d/c.conf"]
            )

    def kickstart_modules_test(self):
        conf = AnacondaConfiguration.from_defaults()

        self.assertEqual(
            set(conf.anaconda.kickstart_modules),
            set(service.service_name for service in (
                services.TIMEZONE,
                services.NETWORK,
                services.LOCALIZATION,
                services.SECURITY,
                services.USERS,
                services.PAYLOADS,
                services.STORAGE,
                services.SERVICES
            ))
        )

    def bootloader_test(self):
        conf = AnacondaConfiguration.from_defaults()
        self.assertIn("selinux", conf.bootloader.preserved_arguments)

    def default_partitioning_test(self):
        conf = AnacondaConfiguration.from_defaults()
        self.assertEqual(conf.storage.default_partitioning, [
            {
                'name': '/',
                'min': Size("1024 MiB"),
                'max': Size("70 GiB"),
            }, {
                'name': '/home',
                'min': Size("500 MiB"),
                'free': Size("50 GiB"),
            }, {
                'name': 'swap',
            }
        ])

    def convert_partitioning_test(self):
        convert_line = StorageSection._convert_partitioning_line

        self.assertEqual(convert_line("/ (min 1 GiB, max 2 GiB, free 20 GiB)"), {
            "name": "/",
            "min": Size("1 GiB"),
            "max": Size("2 GiB"),
            "free": Size("20 GiB")
        })

        self.assertEqual(convert_line("/home (size 1 GiB)"), {
            "name": "/home",
            "size": Size("1 GiB")
        })

        self.assertEqual(convert_line("swap"), {
            "name": "swap"
        })

        with self.assertRaises(ValueError):
            convert_line("")

        with self.assertRaises(ValueError):
            convert_line("(size 1 GiB)")

        with self.assertRaises(ValueError):
            convert_line("/home (size)")

        with self.assertRaises(ValueError):
            convert_line("/home (invalid 1 GiB)")

        with self.assertRaises(ValueError):
            convert_line("/home  (size 1 GiB, min 2 GiB)")

        with self.assertRaises(ValueError):
            convert_line("/home  (max 2 GiB)")
