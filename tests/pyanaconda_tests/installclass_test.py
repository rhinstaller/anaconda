#
# Vendula Poncova <vponcova@redhat.com>
#
# Copyright 2017 Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use, modify,
# copy, or redistribute it subject to the terms and conditions of the GNU
# General Public License v.2.  This program is distributed in the hope that it
# will be useful, but WITHOUT ANY WARRANTY expressed or implied, including the
# implied warranties of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.  Any Red Hat
# trademarks that are incorporated in the source code or documentation are not
# subject to the GNU General Public License and may only be used or replicated
# with the express permission of Red Hat, Inc.
#

import unittest
from mock import patch
from pyanaconda.installclass import BaseInstallClass, InstallClassFactory
from pyanaconda import kickstart
from pykickstart.errors import KickstartParseError


class FactoryTest(unittest.TestCase):

    factory_class = None
    base_class = None
    collect = None

    def _get_fake_factory(self):
        """Return the fake factory."""
        factory = InstallClassFactory()
        factory._paths = ["/fake/path"]
        return factory

    def _patch_collect(self, collected):
        return patch("pyanaconda.installclass.collect", lambda *x: collected)

    def path_test(self):
        """Test paths to install classes."""
        # Test the fake factory,
        factory = self._get_fake_factory()
        self.assertEqual(factory.paths, ["/fake/path"])

        # Test the real factory.
        factory = InstallClassFactory()
        # There should be always at least one path.
        self.assertTrue(any(filter(lambda p: p.endswith("/pyanaconda/installclasses"), factory.paths)))

    def simple_test(self):
        """Test the basic factory methods."""

        class NotInstallClass(object):
            name = "Not Install Class"
            hidden = False
            sortPriority = 1

        class InstallClass(BaseInstallClass):
            name = "Install Class"
            hidden = True
            sortPriority = 2

        class ChildInstallClass(InstallClass):
            name = "Child Install Class"
            hidden = False
            sortPriority = 3

        factory = self._get_fake_factory()

        # Test if class is an install class.
        self.assertEqual(factory._is_install_class(BaseInstallClass), False)
        self.assertEqual(factory._is_install_class(NotInstallClass), False)
        self.assertEqual(factory._is_install_class(InstallClass), True)
        self.assertEqual(factory._is_install_class(ChildInstallClass), True)

        # Test if class is visible.
        self.assertEqual(factory._is_visible_class(InstallClass), False)
        self.assertEqual(factory._is_visible_class(ChildInstallClass), True)

        # Test a description.
        self.assertEqual(factory._get_class_description(InstallClass), "Install Class (InstallClass)")

        # Test a key.
        self.assertEqual(factory._get_install_class_key(InstallClass), (2, "Install Class"))
        self.assertEqual(factory._get_install_class_key(ChildInstallClass), (3, "Child Install Class"))

    def collect_test(self):
        """Test the collecting of the install classes."""

        class InstallClassA(BaseInstallClass):
            name = "Install Class A"
            hidden = True
            sortPriority = 1

        class InstallClassB(BaseInstallClass):
            name = "Install Class B"
            hidden = False
            sortPriority = 2

        class InstallClassC(BaseInstallClass):
            name = "Install Class C"
            hidden = False
            sortPriority = 3

        # Test with no available classes.
        with self._patch_collect([]):
            factory = self._get_fake_factory()
            self.assertEqual(factory.classes, [])
            self.assertEqual(factory.visible_classes, [])

            with self.assertRaises(RuntimeError):
                factory.get_best_install_class()

            with self.assertRaises(RuntimeError):
                factory.get_install_class_by_name("Install Class A")

        # Test with one hidden class.
        with self._patch_collect([InstallClassA]):
            factory = self._get_fake_factory()
            self.assertEqual(factory.classes, [InstallClassA])
            self.assertEqual(factory.visible_classes, [])

            with self.assertRaises(RuntimeError):
                factory.get_best_install_class()

            self.assertTrue(isinstance(factory.get_install_class_by_name("Install Class A"), InstallClassA))

            with self.assertRaises(RuntimeError):
                factory.get_install_class_by_name("Install Class B")

        with self._patch_collect([InstallClassA, InstallClassB, InstallClassC]):
            factory = self._get_fake_factory()
            self.assertEqual(factory.classes, [InstallClassC, InstallClassB, InstallClassA])
            self.assertEqual(factory.visible_classes, [InstallClassC, InstallClassB])

            self.assertTrue(isinstance(factory.get_best_install_class(), InstallClassC))
            self.assertTrue(isinstance(factory.get_install_class_by_name("Install Class A"), InstallClassA))
            self.assertTrue(isinstance(factory.get_install_class_by_name("Install Class B"), InstallClassB))
            self.assertTrue(isinstance(factory.get_install_class_by_name("Install Class C"), InstallClassC))

            with self.assertRaises(RuntimeError):
                factory.get_install_class_by_name("Install Class D")

    def sort_test(self):
        """Test that the install classes are sorted as expected."""

        class InstallClassA1(BaseInstallClass):
            name = "Install Class A"
            hidden = False
            sortPriority = 1

        class InstallClassA2(BaseInstallClass):
            name = "Install Class A"
            hidden = False
            sortPriority = 2

        class InstallClassB1(BaseInstallClass):
            name = "Install Class B 1"
            hidden = False
            sortPriority = 3

        class InstallClassB2(BaseInstallClass):
            name = "Install Class B 2"
            hidden = False
            sortPriority = 3

        with self._patch_collect([InstallClassA1, InstallClassA2, InstallClassB1, InstallClassB2]):
            factory = self._get_fake_factory()
            self.assertEqual(factory.classes, [InstallClassB2, InstallClassB1, InstallClassA2, InstallClassA1])

            self.assertTrue(isinstance(factory.get_best_install_class(), InstallClassB2))
            self.assertTrue(isinstance(factory.get_install_class_by_name("Install Class A"), InstallClassA2))
            self.assertTrue(isinstance(factory.get_install_class_by_name("Install Class B 1"), InstallClassB1))
            self.assertTrue(isinstance(factory.get_install_class_by_name("Install Class B 2"), InstallClassB2))

class Installclass_AttribsTestCase(unittest.TestCase):

    def verify_attribs_test(self):
        """Just check that common attributes are defined at the top"""
        class InstallClassExample(BaseInstallClass):
            pass

        testclass = InstallClassExample()

        self.assertTrue(hasattr(testclass, 'sortPriority'))
        self.assertTrue(hasattr(testclass, 'hidden'))
        self.assertTrue(hasattr(testclass, 'name'))
        self.assertTrue(hasattr(testclass, 'bootloaderTimeoutDefault'))
        self.assertTrue(hasattr(testclass, 'bootloaderExtraArgs'))
        self.assertTrue(hasattr(testclass, 'ignoredPackages'))
        self.assertTrue(hasattr(testclass, 'installUpdates'))
        self.assertTrue(hasattr(testclass, '_l10n_domain'))
        self.assertTrue(hasattr(testclass, 'efi_dir'))
        self.assertTrue(hasattr(testclass, 'defaultFS'))
        self.assertTrue(hasattr(testclass, 'help_folder'))
        self.assertTrue(hasattr(testclass, 'help_main_page'))
        self.assertTrue(hasattr(testclass, 'help_main_page_plain_text'))
        self.assertTrue(hasattr(testclass, 'help_placeholder'))
        self.assertTrue(hasattr(testclass, 'help_placeholder_with_links'))
        self.assertTrue(hasattr(testclass, 'help_placeholder_plain_text'))
        self.assertTrue(hasattr(testclass, 'stylesheet'))
        self.assertTrue(hasattr(testclass, 'defaultPackageEnvironment'))
        self.assertTrue(hasattr(testclass, 'setup_on_boot'))
        self.assertTrue(hasattr(testclass, 'use_geolocation_with_kickstart'))


class F27_Installclass_TestCase(unittest.TestCase):

    def apply_section(self, content):
        return "\n%anaconda\n" + content + "%end\n"

    def parse(self, s):
        handler = kickstart.AnacondaKSHandler()
        parser = kickstart.AnacondaKSParser(handler)
        parser.readKickstartFromString(self.apply_section(s + "\n"))
        return handler

    def assert_parse(self, s, expected):
        self.assertEqual(str(self.parse(s).anaconda), self.apply_section(expected))

    def assert_parse_error(self, s, error):
        with self.assertRaises(error):
            self.parse(s)

    def parse_test(self):
        """Test parsing of the installclass command."""
        # pass
        self.assert_parse("installclass --name='An Install Class'",
                          "installclass --name=\"An Install Class\"\n")

        self.assert_parse("installclass --name=\"An Install Class\"",
                          "installclass --name=\"An Install Class\"\n")

        # fail
        self.assert_parse_error("installclass", KickstartParseError)
        self.assert_parse_error("installclass --name", KickstartParseError)
        self.assert_parse_error("installclass --xyz", KickstartParseError)
        self.assert_parse_error("installclass --name=\"An Install Class\" --xyz", KickstartParseError)

    def command_test(self):
        """Test the installclass command."""
        handler = self.parse("installclass --name='An Install Class'")
        self.assertTrue(handler.anaconda.installclass.seen)  # pylint: disable=no-member
        self.assertEqual(handler.anaconda.installclass.name, "An Install Class")  # pylint: disable=no-member
