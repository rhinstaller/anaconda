#
# Copyright (C) 2019  Red Hat, Inc.
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
# Red Hat Author(s): Jiri Konecny <jkonecny@redhat.com>
#
import unittest

from mock import Mock
from textwrap import dedent

from pyanaconda.modules.common.constants.objects import DNF_PACKAGES
from pyanaconda.modules.payload.payload_interface import PayloadInterface
from pyanaconda.modules.payload.payload import PayloadModule
from pyanaconda.modules.payload.dnf.packages.packages_interface import PackagesHandlerInterface
from tests.nosetests.pyanaconda_tests import check_kickstart_interface


class PayloadInterfaceTestCase(unittest.TestCase):

    def setUp(self):
        """Set up the payload module."""
        # Set up the security module.
        self.payload_module = PayloadModule()
        self.payload_interface = PayloadInterface(self.payload_module)

        self.package_module = self.payload_module._payload_handler._packages_handler
        self.package_interface = PackagesHandlerInterface(self.package_module)

        self.callback = Mock()
        self.package_interface.PropertiesChanged.connect(self.callback)

    def _test_kickstart(self, ks_in, ks_out):
        check_kickstart_interface(self, self.payload_interface, ks_in, ks_out)

    def kickstart_properties_test(self):
        """Test kickstart properties."""
        self.assertEqual(self.payload_interface.KickstartCommands, [])
        self.assertEqual(self.payload_interface.KickstartSections, ["packages"])
        self.assertEqual(self.payload_interface.KickstartAddons, [])

    def packages_section_empty_kickstart_test(self):
        """Test the empty packages section."""
        ks_in = """
        %packages
        %end
        """
        ks_out = """
        %packages

        %end
        """
        self._test_kickstart(ks_in, ks_out)

    def packages_section_kickstart_test(self):
        """Test the packages section."""
        ks_in = """
        %packages
        package
        @group
        @module:10
        @module2:1.5/server
        @^environment
        %end
        """
        ks_out = """
        %packages
        @^environment
        @group
        @module2:1.5/server
        @module:10
        package

        %end
        """
        self._test_kickstart(ks_in, ks_out)

    def packages_section_complex_kickstart_test(self):
        """Test the packages section with duplicates."""
        ks_in = """
        %packages
        @^environment1
        package1
        @group1
        package2

        # Only this environment will stay (last specified wins)
        @^environment2
        @group2

        # duplicates
        package2
        @group2

        # modules
        @module:4
        @module:3.5/server

        %end
        """
        # The last specified environment wins, you can't specify two environments
        # Same package or group specified twice will be deduplicated
        ks_out = """
        %packages
        @^environment2
        @group1
        @group2
        @module:3.5/server
        @module:4
        package1
        package2

        %end
        """
        self._test_kickstart(ks_in, ks_out)

    def packages_section_with_attribute_kickstart_test(self):
        """Test the packages section with attribute."""
        ks_in = """
        %packages --nocore
        %end
        """
        ks_out = """
        %packages --nocore

        %end
        """
        self._test_kickstart(ks_in, ks_out)

    def packages_section_multiple_attributes_kickstart_test(self):
        """Test the packages section with multiple attributes."""
        ks_in = """
        %packages --nocore --multilib --instLangs en_US.UTF-8

        %end
        """
        ks_out = """
        %packages --nocore --instLangs=en_US.UTF-8 --multilib

        %end
        """
        self._test_kickstart(ks_in, ks_out)

    def packages_section_excludes_kickstart_test(self):
        """Test the packages section with excludes."""
        ks_in = """
        %packages
        -vim
        %end
        """
        ks_out = """
        %packages
        -vim

        %end
        """
        self._test_kickstart(ks_in, ks_out)

    def packages_section_complex_exclude_kickstart_test(self):
        """Test the packages section with complex exclude example."""
        ks_in = """
        %packages --nocore --ignoremissing
        @^environment1
        @group1
        package1
        -package2
        -@group2
        @group3
        package3
        %end
        """
        ks_out = """
        %packages --nocore --ignoremissing
        @^environment1
        @group1
        @group3
        package1
        package3
        -@group2
        -package2

        %end
        """
        self._test_kickstart(ks_in, ks_out)

    def core_group_enabled_properties_test(self):
        self.package_interface.SetCoreGroupEnabled(True)
        self.assertEqual(self.package_interface.CoreGroupEnabled, True)
        self.callback.assert_called_once_with(
            DNF_PACKAGES.interface_name, {"CoreGroupEnabled": True}, [])

    def environment_properties_test(self):
        self.package_interface.SetEnvironment("TestEnv")
        self.assertEqual(self.package_interface.Environment, "TestEnv")
        self.callback.assert_called_once_with(
            DNF_PACKAGES.interface_name, {"Environment": "TestEnv"}, [])

    def groups_properties_test(self):
        self.package_interface.SetGroups(["group1", "group2"])
        self.assertEqual(self.package_interface.Groups, ["group1", "group2"])
        self.callback.assert_called_once_with(
            DNF_PACKAGES.interface_name, {"Groups": ["group1", "group2"]}, [])

    def groups_properties_from_kickstart_test(self):
        ks_in = """
        %packages
        @^environment
        @module:14
        @group1
        -@group1
        -@group2
        @group3
        @group4
        @module2:3/client
        %end
        """
        self.payload_interface.ReadKickstart(ks_in)
        self.assertEqual(self.package_interface.Groups, ["module:14",
                                                         "group3", "group4",
                                                         "module2:3/client"])

    def groups_properties_to_kickstart_test(self):
        ks_out = """
        %packages
        @group1
        @group2
        @module1:2.4/server
        @module2:33

        %end
        """
        self.package_interface.SetGroups(["group2", "group1",
                                          "module1:2.4/server", "module2:33"])
        self.assertEqual(self.payload_interface.GenerateKickstart().strip(),
                         dedent(ks_out).strip())

    def packages_properties_test(self):
        self.package_interface.SetPackages(["package1", "package2"])
        self.assertEqual(self.package_interface.Packages, ["package1", "package2"])
        self.callback.assert_called_once_with(
            DNF_PACKAGES.interface_name, {"Packages": ["package1", "package2"]}, [])

    def excluded_groups_properties_test(self):
        self.package_interface.SetExcludedGroups(["group1", "group2"])
        self.assertEqual(self.package_interface.ExcludedGroups, ["group1", "group2"])
        self.callback.assert_called_once_with(
            DNF_PACKAGES.interface_name, {"ExcludedGroups": ["group1", "group2"]}, [])

    def excluded_groups_properties_from_kickstart_test(self):
        ks_in = """
        %packages
        @^environment1
        @group1
        -@group2
        @group3
        -@group3
        %end
        """
        self.payload_interface.ReadKickstart(ks_in)
        self.assertEqual(self.package_interface.ExcludedGroups, ["group2", "group3"])

    def excluded_groups_properties_to_kickstart_test(self):
        ks_out = """
        %packages
        -@group1
        -@group2

        %end
        """
        self.package_interface.SetExcludedGroups(["group2", "group1"])
        self.assertEqual(self.payload_interface.GenerateKickstart().strip(),
                         dedent(ks_out).strip())

    def excluded_packages_properties_test(self):
        self.package_interface.SetExcludedPackages(["package1", "package2"])
        self.assertEqual(self.package_interface.ExcludedPackages, ["package1", "package2"])
        self.callback.assert_called_once_with(
            DNF_PACKAGES.interface_name, {"ExcludedPackages": ["package1", "package2"]}, [])

    def docs_excluded_properties_test(self):
        self.package_interface.SetDocsExcluded(True)
        self.assertEqual(self.package_interface.DocsExcluded, True)
        self.callback.assert_called_once_with(
            DNF_PACKAGES.interface_name, {"DocsExcluded": True}, [])

    def weakdeps_excluded_properties_test(self):
        self.package_interface.SetWeakdepsExcluded(True)
        self.assertEqual(self.package_interface.WeakdepsExcluded, True)
        self.callback.assert_called_once_with(
            DNF_PACKAGES.interface_name, {"WeakdepsExcluded": True}, [])

    def missing_ignored_properties_test(self):
        self.package_interface.SetMissingIgnored(True)
        self.assertEqual(self.package_interface.MissingIgnored, True)
        self.callback.assert_called_once_with(
            DNF_PACKAGES.interface_name, {"MissingIgnored": True}, [])

    def languages_properties_test(self):
        self.package_interface.SetLanguages(["TestLang1", "Esperanto"])
        self.assertEqual(self.package_interface.Languages, ["TestLang1", "Esperanto"])
        self.callback.assert_called_once_with(
            DNF_PACKAGES.interface_name, {"Languages": ["TestLang1", "Esperanto"]}, [])

    def multilib_policy_properties_test(self):
        self.package_interface.SetMultilibPolicy('all')
        self.assertEqual(self.package_interface.MultilibPolicy, 'all')
        self.callback.assert_called_once_with(
            DNF_PACKAGES.interface_name, {"MultilibPolicy": 'all'}, [])

    def timeout_properties_test(self):
        self.package_interface.SetTimeout(60)
        self.assertEqual(self.package_interface.Timeout, 60)
        self.callback.assert_called_once_with(
            DNF_PACKAGES.interface_name, {"Timeout": 60}, [])

    def retries_properties_test(self):
        self.package_interface.SetRetries(30)
        self.assertEqual(self.package_interface.Retries, 30)
        self.callback.assert_called_once_with(
            DNF_PACKAGES.interface_name, {"Retries": 30}, [])
