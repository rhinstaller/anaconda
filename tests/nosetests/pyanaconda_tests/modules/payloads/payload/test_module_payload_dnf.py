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
from unittest.mock import patch, PropertyMock

from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.core.constants import SOURCE_TYPE_CDROM, SOURCE_TYPE_HDD, SOURCE_TYPE_HMC, \
    SOURCE_TYPE_NFS, SOURCE_TYPE_REPO_FILES, SOURCE_TYPE_URL, URL_TYPE_BASEURL, \
    SOURCE_TYPE_CLOSEST_MIRROR, SOURCE_TYPE_CDN, GROUP_PACKAGE_TYPES_REQUIRED, \
    GROUP_PACKAGE_TYPES_ALL, MULTILIB_POLICY_ALL
from pyanaconda.core.kickstart.specification import KickstartSpecificationHandler
from pyanaconda.modules.common.constants.interfaces import PAYLOAD_DNF
from pyanaconda.modules.common.structures.payload import RepoConfigurationData, \
    PackagesConfigurationData
from pyanaconda.modules.payloads.constants import PayloadType, SourceType
from pyanaconda.modules.payloads.kickstart import PayloadKickstartSpecification
from pyanaconda.modules.payloads.payload.dnf.dnf import DNFModule
from pyanaconda.modules.payloads.payload.dnf.dnf_interface import DNFInterface
from pyanaconda.modules.payloads.payloads import PayloadsService
from pyanaconda.modules.payloads.payloads_interface import PayloadsInterface

from tests.nosetests.pyanaconda_tests import patch_dbus_publish_object, check_dbus_property
from tests.nosetests.pyanaconda_tests.modules.payloads.payload.module_payload_shared import \
    PayloadSharedTest, PayloadKickstartSharedTest


class DNFKSTestCase(unittest.TestCase):

    def setUp(self):
        self.maxDiff = None
        self.module = PayloadsService()
        self.interface = PayloadsInterface(self.module)

        self.shared_ks_tests = PayloadKickstartSharedTest(self,
                                                          self.module,
                                                          self.interface)

    def _check_properties(self, expected_source_type):
        payload = self.shared_ks_tests.get_payload()
        self.assertIsInstance(payload, DNFModule)

        # verify sources set
        if expected_source_type is None:
            self.assertFalse(payload.sources)
        else:
            sources = payload.sources
            self.assertEqual(1, len(sources))
            self.assertEqual(sources[0].type.value, expected_source_type)

    def cdrom_kickstart_test(self):
        ks_in = """
        cdrom
        """
        ks_out = """
        # Use CDROM installation media
        cdrom

        %packages

        %end
        """
        self.shared_ks_tests.check_kickstart(ks_in, ks_out)
        self._check_properties(SOURCE_TYPE_CDROM)

    def hmc_kickstart_test(self):
        ks_in = """
        hmc
        """
        ks_out = """
        # Use installation media via SE/HMC
        hmc

        %packages

        %end
        """
        self.shared_ks_tests.check_kickstart(ks_in, ks_out)
        self._check_properties(SOURCE_TYPE_HMC)

    def harddrive_kickstart_test(self):
        ks_in = """
        harddrive --partition=nsa-device --dir=top-secret
        """
        ks_out = """
        # Use hard drive installation media
        harddrive --dir=top-secret --partition=nsa-device

        %packages

        %end
        """
        self.shared_ks_tests.check_kickstart(ks_in, ks_out)
        self._check_properties(SOURCE_TYPE_HDD)

    def harddrive_kickstart_failed_test(self):
        ks_in = """
        harddrive --partition=nsa-device
        """
        self.shared_ks_tests.check_kickstart(ks_in, ks_valid=False, expected_publish_calls=0)
        self.assertEqual(self.interface.ActivePayload, "")

    def nfs_kickstart_test(self):
        ks_in = """
        nfs --server=gotham.city --dir=/secret/underground/base --opts=nomount
        """
        ks_out = """
        # Use NFS installation media
        nfs --server=gotham.city --dir=/secret/underground/base --opts="nomount"

        %packages

        %end
        """
        self.shared_ks_tests.check_kickstart(ks_in, ks_out)
        self._check_properties(SOURCE_TYPE_NFS)

    def url_kickstart_test(self):
        ks_in = """
        url --proxy=https://ClarkKent:suuuperrr@earth:1 --noverifyssl --url http://super/powers --sslcacert wardrobe.cert --sslclientcert private-wardrobe.cert --sslclientkey super-key.key
        """
        ks_out = """
        # Use network installation
        url --url="http://super/powers" --proxy="https://ClarkKent:suuuperrr@earth:1" --noverifyssl --sslcacert="wardrobe.cert" --sslclientcert="private-wardrobe.cert" --sslclientkey="super-key.key"

        %packages

        %end
        """
        self.shared_ks_tests.check_kickstart(ks_in, ks_out)
        self._check_properties(SOURCE_TYPE_URL)

    def url_mirrorlist_kickstart_test(self):
        ks_in = """
        url --mirrorlist http://cool/mirror
        """
        ks_out = """
        # Use network installation
        url --mirrorlist="http://cool/mirror"

        %packages

        %end
        """
        self.shared_ks_tests.check_kickstart(ks_in, ks_out)
        self._check_properties(SOURCE_TYPE_URL)

    def url_metalink_kickstart_test(self):
        ks_in = """
        url --metalink http://itsjustametanotrealstuff --proxy="https://ClarkKent:suuuperrr@earth:1" --sslcacert="wardrobe.cert"
        """
        ks_out = """
        # Use network installation
        url --metalink="http://itsjustametanotrealstuff" --proxy="https://ClarkKent:suuuperrr@earth:1" --sslcacert="wardrobe.cert"

        %packages

        %end
        """
        self.shared_ks_tests.check_kickstart(ks_in, ks_out)
        self._check_properties(SOURCE_TYPE_URL)

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
        self.shared_ks_tests.check_kickstart(
            ks_in, ks_out
        )

    def packages_attributes_ignore_test(self):
        """Test the packages section with attributes for ignoring."""
        ks_in = """
        %packages --ignoremissing --ignorebroken
        %end
        """
        ks_out = """
        %packages --ignoremissing --ignorebroken

        %end
        """
        self.shared_ks_tests.check_kickstart(
            ks_in, ks_out
        )

    def packages_attributes_exclude_test(self):
        """Test the packages section with attributes for exclusion."""
        ks_in = """
        %packages --excludedocs --nocore --inst-langs= --exclude-weakdeps
        %end
        """
        ks_out = """
        %packages --excludedocs --nocore --inst-langs= --exclude-weakdeps

        %end
        """
        self.shared_ks_tests.check_kickstart(
            ks_in, ks_out
        )

    def packages_attributes_other_kickstart_test(self):
        """Test the packages section with other attributes."""
        ks_in = """
        %packages --default --inst-langs en,es --multilib --timeout 10 --retries 5

        %end
        """
        ks_out = """
        %packages --default --inst-langs=en,es --multilib --timeout=10 --retries=5

        %end
        """
        self.shared_ks_tests.check_kickstart(
            ks_in, ks_out
        )

    def packages_section_include_kickstart_test(self):
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
        self.shared_ks_tests.check_kickstart(
            ks_in, ks_out
        )

    def packages_section_complex_include_kickstart_test(self):
        """Test the packages section with duplicates."""
        ks_in = """
        %packages
        @^environment1
        package1
        @group1 --nodefaults
        package2

        # Only this environment will stay (last specified wins)
        @^environment2
        @group2
        @group3 --optional

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
        @group1 --nodefaults
        @group2
        @group3 --optional
        @module:3.5/server
        @module:4
        package1
        package2

        %end
        """
        self.shared_ks_tests.check_kickstart(
            ks_in, ks_out
        )

    def packages_section_exclude_kickstart_test(self):
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
        self.shared_ks_tests.check_kickstart(
            ks_in, ks_out
        )

    def packages_section_complex_exclude_kickstart_test(self):
        """Test the packages section with complex exclude example."""
        ks_in = """
        %packages
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
        %packages
        @^environment1
        @group1
        @group3
        package1
        package3
        -@group2
        -package2

        %end
        """
        self.shared_ks_tests.check_kickstart(
            ks_in, ks_out
        )


class DNFInterfaceTestCase(unittest.TestCase):

    def setUp(self):
        self.module = DNFModule()
        self.interface = DNFInterface(self.module)

        self.shared_tests = PayloadSharedTest(self,
                                              payload=self.module,
                                              payload_intf=self.interface)

    def type_test(self):
        self.shared_tests.check_type(PayloadType.DNF)

    def supported_sources_test(self):
        """Test DNF supported sources API."""
        self.assertEqual(
            [SOURCE_TYPE_CDROM,
             SOURCE_TYPE_HDD,
             SOURCE_TYPE_HMC,
             SOURCE_TYPE_NFS,
             SOURCE_TYPE_REPO_FILES,
             SOURCE_TYPE_CLOSEST_MIRROR,
             SOURCE_TYPE_CDN,
             SOURCE_TYPE_URL],
            self.interface.SupportedSourceTypes)

    def _check_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            self,
            PAYLOAD_DNF,
            self.interface,
            *args, **kwargs
        )

    def packages_kickstarted_property_test(self):
        """Test the PackagesKickstarted property."""
        self.assertEqual(self.interface.PackagesKickstarted, False)

        data = KickstartSpecificationHandler(
            PayloadKickstartSpecification
        )

        self.module.process_kickstart(data)
        self.assertEqual(self.interface.PackagesKickstarted, False)

        data.packages.seen = True
        self.module.process_kickstart(data)
        self.assertEqual(self.interface.PackagesKickstarted, True)

    def packages_property_test(self):
        """Test the Packages property."""
        data = {
            "core-group-enabled": get_variant(Bool, False),
            "default-environment-enabled": get_variant(Bool, False),
            "environment": get_variant(Str, "environment"),
            "groups": get_variant(List[Str], [
                "g1", "g2"
            ]),
            "groups-package-types": get_variant(Dict[Str, List[Str]], {
                "g1": GROUP_PACKAGE_TYPES_ALL,
                "g2": GROUP_PACKAGE_TYPES_REQUIRED
            }),
            "excluded-groups": get_variant(List[Str], [
                "g3", "g4"
            ]),
            "packages": get_variant(List[Str], [
                "p1", "p2"
            ]),
            "excluded-packages": get_variant(List[Str], [
                "p3", "p4"
            ]),
            "docs-excluded": get_variant(Bool, True),
            "weakdeps-excluded": get_variant(Bool, True),
            "missing-ignored": get_variant(Bool, True),
            "broken-ignored": get_variant(Bool, True),
            "languages": get_variant(Str, "en,es"),
            "multilib-policy": get_variant(Str, MULTILIB_POLICY_ALL),
            "timeout": get_variant(Int, 10),
            "retries": get_variant(Int, 5),
        }

        self._check_dbus_property(
            "Packages",
            data
        )

        data = PackagesConfigurationData.to_structure(
            PackagesConfigurationData()
        )

        self._check_dbus_property(
            "Packages",
            data
        )

    @staticmethod
    def _generate_expected_repo_configuration_dict(mount_path):
        return {
            "name": get_variant(Str, ""),
            "url": get_variant(Str, mount_path),
            "type": get_variant(Str, URL_TYPE_BASEURL),
            "ssl-verification-enabled": get_variant(Bool, True),
            "ssl-configuration": get_variant(Structure, {
                "ca-cert-path": get_variant(Str, ""),
                "client-cert-path": get_variant(Str, ""),
                "client-key-path": get_variant(Str, "")
            }),
            "proxy": get_variant(Str, ""),
            "cost": get_variant(Int, 1000),
            "excluded-packages": get_variant(List[Str], []),
            "included-packages": get_variant(List[Str], [])
        }

    @patch("pyanaconda.modules.payloads.source.cdrom.cdrom.CdromSourceModule.mount_point",
           new_callable=PropertyMock)
    @patch_dbus_publish_object
    def cdrom_get_repo_configurations_test(self, publisher, mount_point):
        """Test DNF GetRepoConfigurations for CDROM source."""
        mount_point.return_value = "/install_source/cdrom"
        source = self.shared_tests.prepare_source(SourceType.CDROM)

        self.shared_tests.set_sources([source])

        expected = [self._generate_expected_repo_configuration_dict("file:///install_source/cdrom")]

        self.assertEqual(self.interface.GetRepoConfigurations(), expected)

    @patch("pyanaconda.modules.payloads.source.hmc.hmc.HMCSourceModule.mount_point",
           new_callable=PropertyMock)
    @patch_dbus_publish_object
    def hmc_get_repo_configurations_test(self, publisher, mount_point):
        """Test DNF GetRepoConfigurations for CDROM source."""
        mount_point.return_value = "/install_source/hmc"
        source = self.shared_tests.prepare_source(SourceType.HMC)

        self.shared_tests.set_sources([source])

        expected = [self._generate_expected_repo_configuration_dict("file:///install_source/hmc")]

        self.assertEqual(self.interface.GetRepoConfigurations(), expected)

    @patch("pyanaconda.modules.payloads.source.nfs.nfs.NFSSourceModule.install_tree_path",
           new_callable=PropertyMock)
    @patch_dbus_publish_object
    def nfs_get_repo_configurations_test(self, publisher, install_tree_path_mock):
        """Test DNF GetRepoConfigurations for NFS source."""
        install_tree_path_mock.return_value = "/install_source/nfs"
        source = self.shared_tests.prepare_source(SourceType.NFS)

        self.shared_tests.set_sources([source])

        expected = [self._generate_expected_repo_configuration_dict("file:///install_source/nfs")]

        self.assertEqual(self.interface.GetRepoConfigurations(), expected)

    @patch("pyanaconda.modules.payloads.source.harddrive.harddrive.HardDriveSourceModule.install_tree_path",
           new_callable=PropertyMock)
    @patch_dbus_publish_object
    def harddrive_get_repo_configurations_test(self, publisher, install_tree_path_mock):
        """Test DNF GetRepoConfigurations for HARDDRIVE source."""
        install_tree_path_mock.return_value = "/install_source/harddrive"
        source = self.shared_tests.prepare_source(SourceType.HDD)

        self.shared_tests.set_sources([source])

        expected = [self._generate_expected_repo_configuration_dict("file:///install_source/harddrive")]

        self.assertEqual(self.interface.GetRepoConfigurations(), expected)

    @patch_dbus_publish_object
    def url_get_repo_configurations_test(self, publisher):
        """Test DNF GetRepoConfigurations for URL source."""
        source = self.shared_tests.prepare_source(SourceType.URL)

        data = RepoConfigurationData()
        data.name = "Bernard Black"
        data.url = "http://library.uk"
        data.ssl_verification_enabled = False
        data.proxy = "http://MannyBianco/"

        source.set_repo_configuration(data)

        self.shared_tests.set_sources([source])

        expected = [{
            "name": get_variant(Str, "Bernard Black"),
            "url": get_variant(Str, "http://library.uk"),
            "type": get_variant(Str, URL_TYPE_BASEURL),
            "ssl-verification-enabled": get_variant(Bool, False),
            "ssl-configuration": get_variant(Structure, {
                "ca-cert-path": get_variant(Str, ""),
                "client-cert-path": get_variant(Str, ""),
                "client-key-path": get_variant(Str, "")
            }),
            "proxy": get_variant(Str, "http://MannyBianco/"),
            "cost": get_variant(Int, 1000),
            "excluded-packages": get_variant(List[Str], []),
            "included-packages": get_variant(List[Str], [])
        }]

        self.assertEqual(self.interface.GetRepoConfigurations(), expected)
