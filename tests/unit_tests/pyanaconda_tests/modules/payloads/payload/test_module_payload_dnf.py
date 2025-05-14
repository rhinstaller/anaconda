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
from unittest.mock import Mock, PropertyMock, patch

import pytest
from blivet.size import Size
from dasbus.structure import compare_data
from dasbus.typing import *  # pylint: disable=wildcard-import
from pykickstart.version import isRHEL as is_rhel

from pyanaconda.core.constants import (
    GROUP_PACKAGE_TYPES_ALL,
    GROUP_PACKAGE_TYPES_REQUIRED,
    MULTILIB_POLICY_ALL,
    PAYLOAD_TYPE_DNF,
    REPO_ORIGIN_SYSTEM,
    REPO_ORIGIN_USER,
    SOURCE_TYPE_CDN,
    SOURCE_TYPE_CDROM,
    SOURCE_TYPE_CLOSEST_MIRROR,
    SOURCE_TYPE_HDD,
    SOURCE_TYPE_HMC,
    SOURCE_TYPE_NFS,
    SOURCE_TYPE_REPO_FILES,
    SOURCE_TYPE_REPO_PATH,
    SOURCE_TYPE_URL,
    URL_TYPE_BASEURL,
    URL_TYPE_METALINK,
    URL_TYPE_MIRRORLIST,
)
from pyanaconda.core.kickstart.specification import KickstartSpecificationHandler
from pyanaconda.core.kickstart.version import VERSION
from pyanaconda.modules.common.constants.interfaces import PAYLOAD_DNF
from pyanaconda.modules.common.constants.objects import DISK_SELECTION
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.common.errors.general import UnavailableValueError
from pyanaconda.modules.common.errors.payload import (
    IncompatibleSourceError,
    SourceSetupError,
    UnknownCompsEnvironmentError,
    UnknownCompsGroupError,
)
from pyanaconda.modules.common.structures.comps import (
    CompsEnvironmentData,
    CompsGroupData,
)
from pyanaconda.modules.common.structures.packages import (
    PackagesConfigurationData,
    PackagesSelectionData,
)
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.common.task.task_interface import ValidationTaskInterface
from pyanaconda.modules.payloads.constants import SourceState, SourceType
from pyanaconda.modules.payloads.kickstart import PayloadKickstartSpecification
from pyanaconda.modules.payloads.payload.dnf.dnf import DNFModule
from pyanaconda.modules.payloads.payload.dnf.dnf_interface import DNFInterface
from pyanaconda.modules.payloads.payload.dnf.dnf_manager import DNFManager
from pyanaconda.modules.payloads.payload.dnf.initialization import (
    SetUpDNFSourcesResult,
    SetUpDNFSourcesTask,
    TearDownDNFSourcesTask,
)
from pyanaconda.modules.payloads.payload.dnf.installation import (
    CleanUpDownloadLocationTask,
    DownloadPackagesTask,
    ImportRPMKeysTask,
    InstallPackagesTask,
    PrepareDownloadLocationTask,
    ResolvePackagesTask,
    SetRPMMacrosTask,
    UpdateDNFConfigurationTask,
    WriteRepositoriesTask,
)
from pyanaconda.modules.payloads.payload.dnf.tear_down import ResetDNFManagerTask
from pyanaconda.modules.payloads.payload.dnf.validation import (
    CheckPackagesSelectionTask,
    VerifyRepomdHashesTask,
)
from pyanaconda.modules.payloads.payloads import PayloadsService
from pyanaconda.modules.payloads.payloads_interface import PayloadsInterface
from pyanaconda.modules.payloads.source.cdrom.cdrom import CdromSourceModule
from pyanaconda.modules.payloads.source.closest_mirror.closest_mirror import (
    ClosestMirrorSourceModule,
)
from pyanaconda.modules.payloads.source.factory import SourceFactory
from pyanaconda.modules.payloads.source.harddrive.harddrive import HardDriveSourceModule
from tests.unit_tests.pyanaconda_tests import (
    check_dbus_property,
    check_instances,
    check_task_creation,
    patch_dbus_get_proxy,
    patch_dbus_get_proxy_with_cache,
    patch_dbus_publish_object,
)
from tests.unit_tests.pyanaconda_tests.modules.payloads.payload.module_payload_shared import (
    PayloadKickstartSharedTest,
    PayloadSharedTest,
)


class DNFKickstartTestCase(unittest.TestCase):
    """Test the DNF kickstart commands."""

    def setUp(self):
        self.maxDiff = None
        self.module = PayloadsService()
        self.interface = PayloadsInterface(self.module)
        self.shared_ks_tests = PayloadKickstartSharedTest(
            payload_service=self.module,
            payload_service_intf=self.interface
        )

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
        self._test_kickstart(ks_in, ks_out)
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
        self._test_kickstart(ks_in, ks_out)
        self._check_properties(SOURCE_TYPE_HMC)

    @patch_dbus_get_proxy_with_cache
    def test_harddrive_kickstart(self, proxy_getter):
        ks_in = """
        harddrive --partition=nsa-device --dir=top-secret
        """
        ks_out = """
        # Use hard drive installation media
        harddrive --dir=top-secret --partition=nsa-device

        %packages

        %end
        """
        proxy = STORAGE.get_proxy(DISK_SELECTION)
        proxy.ProtectedDevices = []

        self._test_kickstart(ks_in, ks_out)
        self._check_properties(SOURCE_TYPE_HDD)

        assert proxy.ProtectedDevices == ["nsa-device"]

    def test_harddrive_kickstart_failed(self):
        ks_in = """
        harddrive --partition=nsa-device
        """
        self._test_kickstart(ks_in, None, ks_valid=False, expected_publish_calls=0)
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
        self._test_kickstart(ks_in, ks_out)
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
        self._test_kickstart(ks_in, ks_out)
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
        self._test_kickstart(ks_in, ks_out)
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
        self._test_kickstart(ks_in, ks_out)
        self._check_properties(SOURCE_TYPE_URL)

    def test_repo_updates(self):
        """Test the repo command with enabled updates."""
        ks_in = """
        repo --name updates
        """
        # ruff: noqa: W291
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
        """Test the repo command with an NFS url."""
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
        self._test_kickstart(ks_in, ks_out)

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
        self._test_kickstart(ks_in, ks_out)

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
        self._test_kickstart(ks_in, ks_out)

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
        self._test_kickstart(
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
        self._test_kickstart(ks_in, ks_out)

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
        self._test_kickstart(ks_in, ks_out)

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
        self._test_kickstart(ks_in, ks_out)

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
        self._test_kickstart(ks_in, ks_out)

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
        self._test_kickstart(ks_in, ks_out)

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
        self._test_kickstart(ks_in, ks_out)


class DNFInterfaceTestCase(unittest.TestCase):
    """Test the DBus interface of the DNF module."""

    def setUp(self):
        self.module = DNFModule()
        self.interface = DNFInterface(self.module)
        self.shared_tests = PayloadSharedTest(
            payload=self.module,
            payload_intf=self.interface
        )

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

    @patch.object(DNFModule, "supported_source_types", [SourceType.URL])
    @patch_dbus_publish_object
    def test_set_source(self, publisher):
        """Test if set source API payload."""
        sources = [self.shared_tests.prepare_source(SourceType.URL)]

        self.shared_tests.set_and_check_sources(sources)

    @patch.object(DNFModule, "supported_source_types", [SourceType.URL])
    @patch_dbus_publish_object
    def test_add_source(self, publisher):
        """Test module API to add source."""
        source1 = self.shared_tests.prepare_source(SourceType.URL, SourceState.NOT_APPLICABLE)

        sources = [source1]
        self.shared_tests.set_and_check_sources(sources)

        source2 = self.shared_tests.prepare_source(SourceType.URL)
        self.module.add_source(source2)

        sources.append(source2)
        self.shared_tests.check_sources(sources)

    @patch.object(DNFModule, "supported_source_types", [SourceType.URL])
    @patch_dbus_publish_object
    def test_add_source_incompatible_source_failed(self, publisher):
        """Test module API to add source failed with incompatible source."""
        source1 = self.shared_tests.prepare_source(SourceType.URL, SourceState.NOT_APPLICABLE)

        sources = [source1]
        self.shared_tests.set_and_check_sources(sources)

        source2 = self.shared_tests.prepare_source(SourceType.NFS)
        with pytest.raises(IncompatibleSourceError):
            self.module.add_source(source2)

        self.shared_tests.check_sources(sources)

    @patch.object(DNFModule, "supported_source_types", [SourceType.URL])
    @patch_dbus_publish_object
    def test_add_source_ready_failed(self, publisher):
        """Test module API to add source failed with ready source."""
        source1 = self.shared_tests.prepare_source(SourceType.URL, SourceState.READY)

        sources = [source1]
        self.shared_tests.set_and_check_sources(sources)

        source2 = self.shared_tests.prepare_source(SourceType.URL)
        with pytest.raises(SourceSetupError):
            self.module.add_source(source2)

        self.shared_tests.check_sources(sources)

    @patch.object(DNFModule, "supported_source_types", [SourceType.URL, SourceType.NFS])
    @patch_dbus_publish_object
    def test_set_multiple_source(self, publisher):
        """Test payload setting multiple compatible sources."""
        sources = [
            self.shared_tests.prepare_source(SourceType.NFS),
            self.shared_tests.prepare_source(SourceType.URL),
            self.shared_tests.prepare_source(SourceType.URL),
        ]

        self.shared_tests.set_and_check_sources(sources)

    @patch_dbus_publish_object
    def test_set_incompatible_source(self, publisher):
        """Test payload setting incompatible sources."""
        source = self.shared_tests.prepare_source(SourceType.LIVE_OS_IMAGE)
        cm = self.shared_tests.set_and_check_sources([source], exception=IncompatibleSourceError)
        msg = "Source type LIVE_OS_IMAGE is not supported by this payload."
        assert str(cm.value) == msg

    @patch.object(DNFModule, "supported_source_types", [SourceType.NFS, SourceType.URL])
    @patch_dbus_publish_object
    def test_set_when_initialized_source_fail(self, publisher):
        """Test payload can't set new sources if the old ones are initialized."""
        source1 = self.shared_tests.prepare_source(SourceType.NFS)
        source2 = self.shared_tests.prepare_source(SourceType.URL, state=SourceState.NOT_APPLICABLE)
        self.shared_tests.set_and_check_sources([source1])

        # can't switch source if attached source is ready
        source1.get_state.return_value = SourceState.READY
        self.shared_tests.set_sources([source2], SourceSetupError)
        self.shared_tests.check_sources([source1])

        # change to source2 when attached source state is UNREADY
        source1.get_state.return_value = SourceState.UNREADY
        self.shared_tests.set_and_check_sources([source2])

        # can change back anytime because source2 has state NOT_APPLICABLE
        self.shared_tests.set_and_check_sources([source1])

    @patch_dbus_publish_object
    def test_set_up_sources_with_task(self, publisher):
        """Test SetUpSourcesWithTask."""
        source = SourceFactory.create_source(SourceType.CDROM)
        self.module.add_source(source)

        repository = RepoConfigurationData()
        repository.name = "test"
        repository.url = "http://test"
        self.module.set_repositories([repository])

        configuration = PackagesConfigurationData()
        self.module.set_packages_configuration(configuration)

        task_path = self.interface.SetUpSourcesWithTask()
        obj = check_task_creation(task_path, publisher, SetUpDNFSourcesTask)
        assert obj.implementation._sources == [source]
        assert obj.implementation._repositories == [repository]
        assert obj.implementation._configuration == configuration

    @patch_dbus_publish_object
    def test_tear_down_sources_with_task(self, publisher):
        """Test TearDownSourcesWithTask."""
        s1 = SourceFactory.create_source(SourceType.CDROM)
        self.module.add_source(s1)

        s11 = SourceFactory.create_source(SourceType.URL)
        s12 = SourceFactory.create_source(SourceType.NFS)
        self.module._internal_sources = [s11, s12]

        task_path = self.interface.TearDownSourcesWithTask()
        obj = check_task_creation(task_path, publisher, TearDownDNFSourcesTask)
        assert obj.implementation._dnf_manager == self.module.dnf_manager
        assert obj.implementation._sources == [s11, s12, s1]

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

    @patch_dbus_get_proxy
    @patch_dbus_publish_object
    def test_harddrive_get_repo_configurations(self, publisher, proxy_getter):
        """Test DNF GetRepoConfigurations for HDD source."""
        configuration = RepoConfigurationData()
        configuration.url = "file:///install_source/hdd"

        source = self.shared_tests.prepare_source(SourceType.HDD)
        source._set_repository(configuration)
        self.shared_tests.set_sources([source])

        expected = [self._generate_repository_structure("file:///install_source/hdd")]
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

    def test_match_available_packages(self):
        """Test the MatchAvailablePackages method."""
        assert self.interface.MatchAvailablePackages("p") == []

        dnf_manager = Mock(spec=DNFManager)
        dnf_manager.match_available_packages.return_value = ["p1", "p2"]
        self.module._dnf_manager = dnf_manager

        assert self.interface.MatchAvailablePackages("p") == ["p1", "p2"]


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

    @patch("pyanaconda.modules.payloads.payload.dnf.dnf.calculate_required_space")
    def test_calculate_required_space(self, space_getter):
        """Test the calculate_required_space method."""
        space_getter.return_value = Size("1 MiB")
        assert self.module.calculate_required_space() == 1048576

    def test_get_kernel_version_list(self):
        """Test the get_kernel_version_list method."""
        with pytest.raises(UnavailableValueError):
            self.module.get_kernel_version_list()

        for task in self.module.install_with_tasks():
            if isinstance(task, InstallPackagesTask):
                task._set_result(["1.2-3.x86_64"])

            task.succeeded_signal.emit()

        assert self.module.get_kernel_version_list() == ["1.2-3.x86_64"]

    @patch_dbus_get_proxy_with_cache
    def test_update_protected_devices(self, proxy_getter):
        """Test the update of protected devices."""
        proxy = STORAGE.get_proxy(DISK_SELECTION)

        # Set some default protected devices.
        proxy.ProtectedDevices = ["dev1", "dev2"]

        # Make sure that HDD source will be protected.
        source = HardDriveSourceModule()
        source.configuration.url = "hd:dev3"
        self.module.set_sources([source])

        assert proxy.ProtectedDevices == ["dev1", "dev2", "dev3"]

        # Make sure that HDD repository will be protected.
        repository = RepoConfigurationData()
        repository.url = "hd:dev4:/local/path"
        self.module.set_repositories([repository])

        assert proxy.ProtectedDevices == ["dev1", "dev2", "dev3", "dev4"]

        # Replace the source.
        source = CdromSourceModule()
        self.module.set_sources([source])

        assert proxy.ProtectedDevices == ["dev1", "dev2", "dev4"]

        # Replace the repository.
        repository = RepoConfigurationData()
        repository.url = "http://test"
        self.module.set_repositories([repository])

        assert proxy.ProtectedDevices == ["dev1", "dev2"]

        # Replace both.
        self.module.set_sources([])
        self.module.set_repositories([])

        assert proxy.ProtectedDevices == ["dev1", "dev2"]

    def test_install_with_tasks(self):
        """Test the install_with_tasks method."""
        tasks = self.module.install_with_tasks()
        check_instances(tasks, [
            SetRPMMacrosTask,
            ResolvePackagesTask,
            PrepareDownloadLocationTask,
            DownloadPackagesTask,
            InstallPackagesTask,
            CleanUpDownloadLocationTask,
        ])

    def test_post_install_with_tasks(self):
        """Test the post_install_with_tasks method."""
        tasks = self.module.post_install_with_tasks()
        check_instances(tasks, [
            WriteRepositoriesTask,
            ImportRPMKeysTask,
            UpdateDNFConfigurationTask,
            ResetDNFManagerTask,
        ])

    def test_set_up_sources_on_success(self):
        """Test the on-set-up callback."""
        dnf_manager = DNFManager()

        assert self.module.dnf_manager is not None
        assert self.module.dnf_manager != dnf_manager
        assert self.module.repositories == []
        assert self.module._internal_sources == []

        repositories = [
            RepoConfigurationData.from_url("http://server/1"),
            RepoConfigurationData.from_url("nfs:server:2"),
            RepoConfigurationData.from_url("hdd:device:/3"),
        ]

        sources = [
            SourceFactory.create_source(SourceType.URL),
            SourceFactory.create_source(SourceType.NFS),
            SourceFactory.create_source(SourceType.HDD),
        ]

        result = SetUpDNFSourcesResult(
            dnf_manager=dnf_manager,
            repositories=repositories,
            sources=sources,
        )

        task = self.module.set_up_sources_with_task()
        task._set_result(result)
        task.succeeded_signal.emit()

        assert self.module.dnf_manager == dnf_manager
        assert self.module.repositories == repositories
        assert self.module._internal_sources == sources
