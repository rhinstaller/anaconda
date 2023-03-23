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
from unittest.mock import patch, PropertyMock, Mock

from dasbus.structure import compare_data
from dasbus.typing import *  # pylint: disable=wildcard-import
from pykickstart.version import isRHEL as is_rhel

from pyanaconda.core.constants import SOURCE_TYPE_CDROM, SOURCE_TYPE_HDD, SOURCE_TYPE_HMC, \
    SOURCE_TYPE_NFS, SOURCE_TYPE_REPO_FILES, SOURCE_TYPE_URL, URL_TYPE_BASEURL, \
    SOURCE_TYPE_CLOSEST_MIRROR, SOURCE_TYPE_CDN, GROUP_PACKAGE_TYPES_REQUIRED, \
    GROUP_PACKAGE_TYPES_ALL, MULTILIB_POLICY_ALL, PAYLOAD_TYPE_DNF, REPO_ORIGIN_SYSTEM, \
    REPO_ORIGIN_USER, URL_TYPE_MIRRORLIST, URL_TYPE_METALINK, SOURCE_TYPE_REPO_PATH
from pyanaconda.core.kickstart.specification import KickstartSpecificationHandler
from pyanaconda.core.kickstart.version import VERSION
from pyanaconda.modules.common.constants.interfaces import PAYLOAD_DNF
from pyanaconda.modules.common.errors.payload import UnknownCompsGroupError, \
    UnknownCompsEnvironmentError
from pyanaconda.modules.common.structures.comps import CompsEnvironmentData, CompsGroupData
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.common.structures.packages import PackagesConfigurationData, \
    PackagesSelectionData
from pyanaconda.modules.common.task.task_interface import ValidationTaskInterface
from pyanaconda.modules.payloads.constants import SourceType
from pyanaconda.modules.payloads.kickstart import PayloadKickstartSpecification
from pyanaconda.modules.payloads.payload.dnf.dnf import DNFModule
from pyanaconda.modules.payloads.payload.dnf.dnf_interface import DNFInterface
from pyanaconda.modules.payloads.payload.dnf.dnf_manager import DNFManager
from pyanaconda.modules.payloads.payload.dnf.validation import CheckPackagesSelectionTask, \
    VerifyRepomdHashesTask
from pyanaconda.modules.payloads.payloads import PayloadsService
from pyanaconda.modules.payloads.payloads_interface import PayloadsInterface
from pyanaconda.modules.payloads.source.cdrom.cdrom import CdromSourceModule
from pyanaconda.modules.payloads.source.closest_mirror.closest_mirror import \
    ClosestMirrorSourceModule

from tests.unit_tests.pyanaconda_tests import patch_dbus_publish_object, check_dbus_property, \
    check_task_creation
from tests.unit_tests.pyanaconda_tests.modules.payloads.payload.module_payload_shared import \
    PayloadSharedTest, PayloadKickstartSharedTest


class DNFKSTestCase(unittest.TestCase):

    def setUp(self):
        self.maxDiff = None
        self.module = PayloadsService()
        self.interface = PayloadsInterface(self.module)

        self.shared_ks_tests = PayloadKickstartSharedTest(self.module,
                                                          self.interface)

    def _check_properties(self, expected_source_type):
        payload = self.shared_ks_tests.get_payload()
        assert isinstance(payload, DNFModule)

        # verify sources set
        if expected_source_type is None:
            assert not payload.sources
        else:
            sources = payload.sources
            assert 1 == len(sources)
            assert sources[0].type.value == expected_source_type

    def _test_kickstart(self, ks_in, ks_out, *args, **kwargs):
        self.shared_ks_tests.check_kickstart(ks_in, ks_out, *args, **kwargs)

    def test_cdrom_kickstart(self):
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

    def test_hmc_kickstart(self):
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

    def test_harddrive_kickstart(self):
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

    def test_harddrive_kickstart_failed(self):
        ks_in = """
        harddrive --partition=nsa-device
        """
        self.shared_ks_tests.check_kickstart(ks_in, ks_valid=False, expected_publish_calls=0)
        assert self.interface.ActivePayload == ""

    def test_nfs_kickstart(self):
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

    def test_url_kickstart(self):
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

    def test_url_mirrorlist_kickstart(self):
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

    def test_url_metalink_kickstart(self):
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

    def test_repo_updates(self):
        """Test the repo command with enabled updates."""
        ks_in = """
        repo --name updates
        """
        ks_out = """
        repo --name="updates" 

        %packages

        %end
        """
        self._test_kickstart(ks_in, ks_out)

        payload = self.shared_ks_tests.get_payload()
        data = payload.repositories[0]

        assert data.origin == REPO_ORIGIN_SYSTEM
        assert data.type == URL_TYPE_BASEURL
        assert data.url == ""

    def test_repo_baseurl(self):
        """Test the repo command with a baseurl."""
        ks_in = """
        repo --name test --baseurl http://url
        """
        ks_out = """
        repo --name="test" --baseurl=http://url

        %packages

        %end
        """
        self._test_kickstart(ks_in, ks_out)

        payload = self.shared_ks_tests.get_payload()
        data = payload.repositories[0]

        assert data.origin == REPO_ORIGIN_USER
        assert data.type == URL_TYPE_BASEURL
        assert data.url == "http://url"

    def test_repo_mirrorlist(self):
        """Test the repo command with a mirrorlist."""
        ks_in = """
        repo --name test --mirrorlist http://mirror
        """
        ks_out = """
        repo --name="test" --mirrorlist=http://mirror

        %packages

        %end
        """
        self._test_kickstart(ks_in, ks_out)

        payload = self.shared_ks_tests.get_payload()
        data = payload.repositories[0]

        assert data.origin == REPO_ORIGIN_USER
        assert data.type == URL_TYPE_MIRRORLIST
        assert data.url == "http://mirror"

    def test_repo_metalink(self):
        """Test the repo command with a metalink."""
        ks_in = """
        repo --name test --metalink http://metalink
        """
        ks_out = """
        repo --name="test"  --metalink=http://metalink

        %packages

        %end
        """
        self._test_kickstart(ks_in, ks_out)

        payload = self.shared_ks_tests.get_payload()
        data = payload.repositories[0]

        assert data.origin == REPO_ORIGIN_USER
        assert data.type == URL_TYPE_METALINK
        assert data.url == "http://metalink"

    def test_repo_nfs(self):
        """Test the repo command with a NFS url."""
        ks_in = """
        repo --name test --baseurl nfs://server:path
        """
        ks_out = """
        repo --name="test" --baseurl=nfs://server:path

        %packages

        %end
        """
        self._test_kickstart(ks_in, ks_out)

        payload = self.shared_ks_tests.get_payload()
        data = payload.repositories[0]

        assert data.origin == REPO_ORIGIN_USER
        assert data.type == URL_TYPE_BASEURL
        assert data.url == "nfs://server:path"

    def test_repo_proxy(self):
        """Test the repo command with a proxy configuration."""
        ks_in = """
        repo --name test --baseurl http://url  --proxy http://user:pass@example.com:3128
        """
        ks_out = """
        repo --name="test" --baseurl=http://url --proxy="http://user:pass@example.com:3128"

        %packages

        %end
        """
        self._test_kickstart(ks_in, ks_out)

    def test_repo_cost(self):
        """Test the repo command with a repo cost."""
        ks_in = """
        repo --name test --baseurl http://url  --cost 123
        """
        ks_out = """
        repo --name="test" --baseurl=http://url --cost=123

        %packages

        %end
        """
        self._test_kickstart(ks_in, ks_out)

    def test_repo_packages(self):
        """Test the repo command with includepkgs and excludepkgs."""
        ks_in = """
        repo --name test --baseurl http://url --includepkgs p1,p2 --excludepkgs p3,p4
        """
        ks_out = """
        repo --name="test" --baseurl=http://url --includepkgs="p1,p2" --excludepkgs="p3,p4"

        %packages

        %end
        """
        self._test_kickstart(ks_in, ks_out)

        payload = self.shared_ks_tests.get_payload()
        data = payload.repositories[0]

        assert data.included_packages == ["p1", "p2"]
        assert data.excluded_packages == ["p3", "p4"]

    def test_repo_no_ssl_verification(self):
        """Test the repo command with disabled ssl verification."""
        ks_in = """
        repo --name test --baseurl http://url --noverifyssl
        """
        ks_out = """
        repo --name="test" --baseurl=http://url --noverifyssl

        %packages

        %end
        """
        self._test_kickstart(ks_in, ks_out)

        payload = self.shared_ks_tests.get_payload()
        data = payload.repositories[0]

        assert data.ssl_verification_enabled is False

    def test_repo_ssl_configuration(self):
        """Test the repo command with enabled ssl verification."""
        ks_in = """
        repo --name test --baseurl http://url --sslcacert x.cert --sslclientcert private-x.cert --sslclientkey x.key
        """
        ks_out = """
        repo --name="test" --baseurl=http://url --sslcacert="x.cert" --sslclientcert="private-x.cert" --sslclientkey="x.key"

        %packages

        %end
        """
        self._test_kickstart(ks_in, ks_out)

        payload = self.shared_ks_tests.get_payload()
        data = payload.repositories[0]

        assert data.ssl_verification_enabled is True

    def test_repo_install(self):
        """Test the repo command with enabled installation."""
        ks_in = """
        repo --name test --baseurl http://url --install
        """
        ks_out = """
        repo --name="test" --baseurl=http://url --install

        %packages

        %end
        """
        self._test_kickstart(ks_in, ks_out)

    def test_repo_multiple(self):
        """Test multiple repo commands."""
        ks_in = """
        repo --name r1 --baseurl http://url/1
        repo --name r2 --baseurl http://url/2
        repo --name r3 --baseurl http://url/3
        """
        ks_out = """
        repo --name="r1" --baseurl=http://url/1
        repo --name="r2" --baseurl=http://url/2
        repo --name="r3" --baseurl=http://url/3

        %packages

        %end
        """
        self._test_kickstart(ks_in, ks_out)
        payload = self.shared_ks_tests.get_payload()
        assert len(payload.repositories) == 3

    def test_repo_disabled(self):
        """Test the repo command with disabled repositories."""
        ks_in = """
        repo --name r1 --baseurl http://url/1
        repo --name r2 --baseurl http://url/2
        repo --name r3 --baseurl http://url/3
        """
        ks_out = """
        repo --name="r1" --baseurl=http://url/1
        repo --name="r3" --baseurl=http://url/3

        %packages

        %end
        """
        self._test_kickstart(ks_in, None)
        payload = self.shared_ks_tests.get_payload()
        payload.repositories[1].enabled = False
        self._test_kickstart(None, ks_out, expected_publish_calls=0)

    def test_module_kickstart(self):
        ks_in = """
        module --name=nodejs
        module --name=django --stream=1.6
        module --name=postgresql --disable
        module --name=mysql --stream=8.0 --disable
        """
        ks_out = """
        module --name=nodejs
        module --name=django --stream=1.6
        module --name=postgresql --disable
        module --name=mysql --stream=8.0 --disable

        %packages

        %end
        """
        self.shared_ks_tests.check_kickstart(ks_in, ks_out)

    def test_packages_section_empty_kickstart(self):
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

    def test_packages_attributes_ignore_missing(self):
        """Test the packages section with ignored missing packages."""
        ks_in = """
        %packages --ignoremissing
        %end
        """
        ks_out = """
        %packages --ignoremissing

        %end
        """
        self.shared_ks_tests.check_kickstart(
            ks_in, ks_out
        )

    def test_packages_attributes_ignore_broken(self):
        """Test the packages section with ignored broken packages."""
        ks_in = """
        %packages --ignorebroken
        %end
        """
        ks_out = """
        %packages --ignorebroken

        %end
        """
        self.shared_ks_tests.check_kickstart(
            ks_in, ks_out, ks_valid=not is_rhel(VERSION)
        )

    def test_packages_attributes_exclude(self):
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

    def test_packages_attributes_other_kickstart(self):
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

    def test_packages_section_include_kickstart(self):
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

    def test_packages_section_complex_include_kickstart(self):
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

    def test_packages_section_exclude_kickstart(self):
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

    def test_packages_section_complex_exclude_kickstart(self):
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
    """Test the DBus interface of the DNF module."""

    def setUp(self):
        self.module = DNFModule()
        self.interface = DNFInterface(self.module)
        self.shared_tests = PayloadSharedTest(payload=self.module,
                                              payload_intf=self.interface)

    def test_type(self):
        """Test the Type property."""
        assert self.interface.Type == PAYLOAD_TYPE_DNF

    def test_default_source_type(self):
        """Test the DefaultSourceType property."""
        assert self.interface.DefaultSourceType == SOURCE_TYPE_CLOSEST_MIRROR

    def test_supported_sources(self):
        """Test DNF supported sources API."""
        assert self.interface.SupportedSourceTypes == [
            SOURCE_TYPE_CDROM,
            SOURCE_TYPE_HDD,
            SOURCE_TYPE_HMC,
            SOURCE_TYPE_NFS,
            SOURCE_TYPE_REPO_FILES,
            SOURCE_TYPE_REPO_PATH,
            SOURCE_TYPE_CLOSEST_MIRROR,
            SOURCE_TYPE_CDN,
            SOURCE_TYPE_URL
        ]

    def _check_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            PAYLOAD_DNF,
            self.interface,
            *args, **kwargs
        )

    def test_repositories_property(self):
        """Test the Repositories property."""
        data = [
            self._generate_repository_structure("https://r1"),
            self._generate_repository_structure("http://r2"),
            self._generate_repository_structure("ftp://r3"),
        ]

        self._check_dbus_property(
            "Repositories",
            data
        )

    def test_repositories_data(self):
        """Test the RepoConfigurationData structure."""
        r1 = RepoConfigurationData()
        r1.name = "r1"
        r1.url = "https://r1"

        r2 = RepoConfigurationData()
        r2.name = "r2"
        r2.url = "http://r2"

        r3 = RepoConfigurationData()
        r3.name = "r3"
        r3.url = "ftp://r3"

        data = RepoConfigurationData.to_structure_list([
            r1, r2, r3
        ])

        self._check_dbus_property(
            "Repositories",
            data
        )

    def test_packages_kickstarted_property(self):
        """Test the PackagesKickstarted property."""
        assert self.interface.PackagesKickstarted is False

        data = KickstartSpecificationHandler(
            PayloadKickstartSpecification
        )

        self.module.process_kickstart(data)
        assert self.interface.PackagesKickstarted is False

        data.packages.seen = True
        self.module.process_kickstart(data)
        assert self.interface.PackagesKickstarted is True

    def test_packages_selection_property(self):
        """Test the PackagesSelection property."""
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
            "modules": get_variant(List[Str], [
                "m1", "m2:latest", "m3:1.01"
            ]),
            "disabled-modules": get_variant(List[Str], [
                "m4", "m5:master", "m6:10"
            ]),
        }

        self._check_dbus_property(
            "PackagesSelection",
            data
        )

    def test_packages_selection_data(self):
        """Test the PackagesSelectionData structure."""
        data = PackagesSelectionData.to_structure(
            PackagesSelectionData()
        )

        self._check_dbus_property(
            "PackagesSelection",
            data
        )

    def test_packages_configuration_property(self):
        """Test the PackagesConfiguration property."""
        data = {
            "docs-excluded": get_variant(Bool, True),
            "weakdeps-excluded": get_variant(Bool, True),
            "missing-ignored": get_variant(Bool, True),
            "broken-ignored": get_variant(Bool, True),
            "languages": get_variant(Str, "en:es"),
            "multilib-policy": get_variant(Str, MULTILIB_POLICY_ALL),
            "timeout": get_variant(Int, 10),
            "retries": get_variant(Int, 5),
        }

        self._check_dbus_property(
            "PackagesConfiguration",
            data
        )

    def test_packages_configuration_data(self):
        """Test the PackagesConfigurationData structure."""
        data = PackagesConfigurationData.to_structure(
            PackagesConfigurationData()
        )

        self._check_dbus_property(
            "PackagesConfiguration",
            data
        )

    def test_get_repositories(self):
        """Test the GetAvailableRepositories method."""
        assert self.interface.GetAvailableRepositories() == []

        dnf_manager = Mock(spec=DNFManager)
        dnf_manager.repositories = ["r1", "r2", "r3"]
        self.module._dnf_manager = dnf_manager

        assert self.interface.GetAvailableRepositories() == ["r1", "r2", "r3"]

    def test_get_enabled_repositories(self):
        """Test the GetEnabledRepositories method."""
        assert self.interface.GetEnabledRepositories() == []

        dnf_manager = Mock(spec=DNFManager)
        dnf_manager.enabled_repositories = ["r1", "r3"]
        self.module._dnf_manager = dnf_manager

        assert self.interface.GetEnabledRepositories() == ["r1", "r3"]

    @patch_dbus_publish_object
    def test_verify_repomd_hashes_with_task(self, publisher):
        """Test the VerifyRepomdHashesWithTask method."""
        task_path = self.interface.VerifyRepomdHashesWithTask()
        task_proxy = check_task_creation(task_path, publisher, VerifyRepomdHashesTask)
        assert isinstance(task_proxy, ValidationTaskInterface)

    def test_get_default_environment(self):
        """Test the GetDefaultEnvironment method."""
        assert self.interface.GetDefaultEnvironment() == ""

    def test_get_environments(self):
        """Test the GetEnvironments method."""
        assert self.interface.GetEnvironments() == []

        dnf_manager = Mock(spec=DNFManager)
        dnf_manager.environments = ["e1", "e2", "e3"]
        self.module._dnf_manager = dnf_manager

        assert self.interface.GetEnvironments() == ["e1", "e2", "e3"]

    def test_resolve_environment(self):
        """Test the ResolveEnvironment method."""
        assert self.interface.ResolveEnvironment("e1") == ""

        dnf_manager = Mock(spec=DNFManager)
        dnf_manager.resolve_environment.return_value = "e1"
        self.module._dnf_manager = dnf_manager

        assert self.interface.ResolveEnvironment("e1") == "e1"

    def test_get_environment_data(self):
        """Test the GetEnvironmentData method."""
        with self.assertRaises(UnknownCompsEnvironmentError):
            self.interface.GetEnvironmentData("e1")

        data = CompsEnvironmentData()
        data.id = "e1"
        data.name = "The 'e1' environment"
        data.description = "This is the 'e1' environment."

        dnf_manager = Mock(spec=DNFManager)
        dnf_manager.get_environment_data.return_value = data
        self.module._dnf_manager = dnf_manager

        assert self.interface.GetEnvironmentData("e1") == {
            'id': get_variant(Str, 'e1'),
            'name': get_variant(Str, "The 'e1' environment"),
            'description': get_variant(Str, "This is the 'e1' environment."),
            'default-groups': get_variant(List[Str], []),
            'optional-groups': get_variant(List[Str], []),
            'visible-groups': get_variant(List[Str], []),
        }

    def test_resolve_group(self):
        """Test the ResolveGroup method."""
        assert self.interface.ResolveGroup("g1") == ""

        dnf_manager = Mock(spec=DNFManager)
        dnf_manager.resolve_group.return_value = "g1"
        self.module._dnf_manager = dnf_manager

        assert self.interface.ResolveGroup("g1") == "g1"

    def test_get_group_data(self):
        """Test the GetGroupData method."""
        with self.assertRaises(UnknownCompsGroupError):
            self.interface.GetGroupData("g1")

        data = CompsGroupData()
        data.id = "g1"
        data.name = "The 'g1' group"
        data.description = "This is the 'g1' group."

        dnf_manager = Mock(spec=DNFManager)
        dnf_manager.get_group_data.return_value = data
        self.module._dnf_manager = dnf_manager

        assert self.interface.GetGroupData("g1") == {
            'id': get_variant(Str, 'g1'),
            'name': get_variant(Str, "The 'g1' group"),
            'description': get_variant(Str, "This is the 'g1' group.")
        }

    @patch_dbus_publish_object
    def test_validate_packages_selection_with_task(self, publisher):
        """Test the ValidatePackagesSelectionWithTask method."""
        data = PackagesSelectionData()
        data.packages = ["p1", "p2", "p3"]

        task_path = self.interface.ValidatePackagesSelectionWithTask(
            PackagesSelectionData.to_structure(data)
        )
        task_proxy = check_task_creation(
            task_path, publisher, CheckPackagesSelectionTask
        )
        task = task_proxy.implementation

        assert compare_data(data, task._selection)

    @staticmethod
    def _generate_repository_structure(url=""):
        """Generate a RepoConfigurationData structure with the specified URL."""
        return {
            "name": get_variant(Str, ""),
            "origin": get_variant(Str, "USER"),
            "enabled": get_variant(Bool, True),
            "url": get_variant(Str, url),
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
            "included-packages": get_variant(List[Str], []),
            "installation-enabled": get_variant(Bool, False),
        }

    @patch("pyanaconda.modules.payloads.source.cdrom.cdrom.CdromSourceModule.mount_point",
           new_callable=PropertyMock)
    @patch_dbus_publish_object
    def test_cdrom_get_repo_configurations(self, publisher, mount_point):
        """Test DNF GetRepoConfigurations for CDROM source."""
        mount_point.return_value = "/install_source/cdrom"
        source = self.shared_tests.prepare_source(SourceType.CDROM)

        self.shared_tests.set_sources([source])

        expected = [self._generate_repository_structure("file:///install_source/cdrom")]

        assert self.interface.GetRepoConfigurations() == expected

    @patch_dbus_publish_object
    def test_repo_path_get_repo_configurations(self, publisher):
        """Test DNF GetRepoConfigurations for the repo path source."""
        source = self.shared_tests.prepare_source(SourceType.REPO_PATH)
        source.set_path("/install_source/path")

        self.shared_tests.set_sources([source])

        expected = [self._generate_repository_structure("file:///install_source/path")]
        assert self.interface.GetRepoConfigurations() == expected

    @patch("pyanaconda.modules.payloads.source.hmc.hmc.HMCSourceModule.mount_point",
           new_callable=PropertyMock)
    @patch_dbus_publish_object
    def test_hmc_get_repo_configurations(self, publisher, mount_point):
        """Test DNF GetRepoConfigurations for CDROM source."""
        mount_point.return_value = "/install_source/hmc"
        source = self.shared_tests.prepare_source(SourceType.HMC)

        self.shared_tests.set_sources([source])

        expected = [self._generate_repository_structure("file:///install_source/hmc")]

        assert self.interface.GetRepoConfigurations() == expected

    @patch_dbus_publish_object
    def test_nfs_get_repo_configurations(self, publisher):
        """Test DNF GetRepoConfigurations for NFS source."""
        configuration = RepoConfigurationData()
        configuration.url = "file:///install_source/nfs"

        source = self.shared_tests.prepare_source(SourceType.NFS)
        source._set_repository(configuration)
        self.shared_tests.set_sources([source])

        expected = [self._generate_repository_structure("file:///install_source/nfs")]
        assert self.interface.GetRepoConfigurations() == expected

    @patch("pyanaconda.modules.payloads.source.harddrive.harddrive.HardDriveSourceModule.install_tree_path",
           new_callable=PropertyMock)
    @patch_dbus_publish_object
    def test_harddrive_get_repo_configurations(self, publisher, install_tree_path_mock):
        """Test DNF GetRepoConfigurations for HARDDRIVE source."""
        install_tree_path_mock.return_value = "/install_source/harddrive"
        source = self.shared_tests.prepare_source(SourceType.HDD)

        self.shared_tests.set_sources([source])

        expected = [self._generate_repository_structure("file:///install_source/harddrive")]

        assert self.interface.GetRepoConfigurations() == expected

    @patch_dbus_publish_object
    def test_url_get_repo_configurations(self, publisher):
        """Test DNF GetRepoConfigurations for URL source."""
        source = self.shared_tests.prepare_source(SourceType.URL)

        data = RepoConfigurationData()
        data.name = "Bernard Black"
        data.url = "http://library.uk"
        data.ssl_verification_enabled = False
        data.proxy = "http://MannyBianco/"

        source.set_configuration(data)
        self.shared_tests.set_sources([source])

        expected = self._generate_repository_structure()
        expected.update({
            "name": get_variant(Str, "Bernard Black"),
            "url": get_variant(Str, "http://library.uk"),
            "proxy": get_variant(Str, "http://MannyBianco/"),
            "ssl-verification-enabled": get_variant(Bool, False),
        })

        assert self.interface.GetRepoConfigurations() == [expected]


class DNFModuleTestCase(unittest.TestCase):
    """Test the DNF module."""

    def setUp(self):
        """Set up the test."""
        self.module = DNFModule()

    def test_is_network_required(self):
        """Test the is_network_required function."""
        assert self.module.is_network_required() is False

        source = ClosestMirrorSourceModule()
        self.module.set_sources([source])
        assert self.module.is_network_required() is True

        source = CdromSourceModule()
        self.module.set_sources([source])
        assert self.module.is_network_required() is False

        r1 = RepoConfigurationData()
        r1.url = "http://r1"
        self.module.set_repositories([r1])
        assert self.module.is_network_required() is True

        r2 = RepoConfigurationData()
        r2.url = "file://r2"
        self.module.set_repositories([r2])
        assert self.module.is_network_required() is False

        r1.enabled = True
        self.module.set_repositories([r1, r2])
        assert self.module.is_network_required() is True

        r1.enabled = False
        self.module.set_repositories([r1, r2])
        assert self.module.is_network_required() is False
