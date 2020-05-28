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

from tests.nosetests.pyanaconda_tests import patch_dbus_publish_object
from tests.nosetests.pyanaconda_tests.module_payload_shared import PayloadSharedTest, \
    PayloadKickstartSharedTest

from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.core.constants import SOURCE_TYPE_CDROM, SOURCE_TYPE_HDD, SOURCE_TYPE_HMC, \
    SOURCE_TYPE_NFS, SOURCE_TYPE_REPO_FILES, SOURCE_TYPE_URL, URL_TYPE_BASEURL, \
    SOURCE_TYPE_CLOSEST_MIRROR, SOURCE_TYPE_CDN
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.payloads.constants import PayloadType, SourceType
from pyanaconda.modules.payloads.payload.dnf.dnf import DNFModule
from pyanaconda.modules.payloads.payload.dnf.dnf_interface import DNFInterface
from pyanaconda.modules.payloads.payloads import PayloadsService
from pyanaconda.modules.payloads.payloads_interface import PayloadsInterface


class DNFKSTestCase(unittest.TestCase):

    def setUp(self):
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
        """
        self.shared_ks_tests.check_kickstart(ks_in, ks_out)
        self._check_properties(SOURCE_TYPE_HDD)

    def harddrive_kickstart_failed_test(self):
        ks_in = """
        harddrive --partition=nsa-device
        """
        self.shared_ks_tests.check_kickstart(ks_in, ks_valid=False, expected_publish_calls=0)
        self.assertEqual(self.interface.ActivePayload, "")

    def harddrive_biospart_kickstart_failed_test(self):
        # The biospart parameter is not implemented since 2012 and it won't
        # really work. Make it obvious for user.
        ks_in = """
        harddrive --biospart=007 --dir=cool/store
        """
        # One publisher call because the biospart support is decided in the harddrive source
        self.shared_ks_tests.check_kickstart(ks_in, ks_valid=False, expected_publish_calls=1)
        self.assertEqual(self.interface.ActivePayload, "")

    def nfs_kickstart_test(self):
        ks_in = """
        nfs --server=gotham.city --dir=/secret/underground/base --opts=nomount
        """
        ks_out = """
        # Use NFS installation media
        nfs --server=gotham.city --dir=/secret/underground/base --opts="nomount"
        """
        self.shared_ks_tests.check_kickstart(ks_in, ks_out)
        self._check_properties(SOURCE_TYPE_NFS)

    def url_kickstart_test(self):
        self.maxDiff = None
        ks_in = """
        url --proxy=https://ClarkKent:suuuperrr@earth:1 --noverifyssl --url http://super/powers --sslcacert wardrobe.cert --sslclientcert private-wardrobe.cert --sslclientkey super-key.key
        """
        ks_out = """
        # Use network installation
        url --url="http://super/powers" --proxy="https://ClarkKent:suuuperrr@earth:1" --noverifyssl --sslcacert="wardrobe.cert" --sslclientcert="private-wardrobe.cert" --sslclientkey="super-key.key"
        """
        self.shared_ks_tests.check_kickstart(ks_in, ks_out)
        self._check_properties(SOURCE_TYPE_URL)

    def url_mirrorlist_kickstart_test(self):
        self.maxDiff = None
        ks_in = """
        url --mirrorlist http://cool/mirror
        """
        ks_out = """
        # Use network installation
        url --mirrorlist="http://cool/mirror"
        """
        self.shared_ks_tests.check_kickstart(ks_in, ks_out)
        self._check_properties(SOURCE_TYPE_URL)

    def url_metalink_kickstart_test(self):
        self.maxDiff = None
        ks_in = """
        url --metalink http://itsjustametanotrealstuff --proxy="https://ClarkKent:suuuperrr@earth:1" --sslcacert="wardrobe.cert"
        """
        ks_out = """
        # Use network installation
        url --metalink="http://itsjustametanotrealstuff" --proxy="https://ClarkKent:suuuperrr@earth:1" --sslcacert="wardrobe.cert"
        """
        self.shared_ks_tests.check_kickstart(ks_in, ks_out)
        self._check_properties(SOURCE_TYPE_URL)


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
