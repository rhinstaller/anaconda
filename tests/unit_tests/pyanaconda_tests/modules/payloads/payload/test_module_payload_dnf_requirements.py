#
# Copyright (C) 2020  Red Hat, Inc.
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
import tempfile
import unittest
from unittest.mock import Mock, patch

from pyanaconda.core.constants import REQUIREMENT_TYPE_PACKAGE, REQUIREMENT_TYPE_GROUP, \
    MULTILIB_POLICY_ALL, MULTILIB_POLICY_BEST
from pyanaconda.modules.common.constants.services import LOCALIZATION, BOSS
from pyanaconda.modules.common.structures.requirement import Requirement
from pyanaconda.modules.payloads.payload.dnf.dnf_manager import DNFManager
from pyanaconda.modules.payloads.payload.dnf.requirements import collect_language_requirements, \
    collect_platform_requirements, collect_driver_disk_requirements, collect_remote_requirements, \
    apply_requirements, collect_dnf_requirements
from tests.unit_tests.pyanaconda_tests import patch_dbus_get_proxy_with_cache
from pyanaconda.modules.common.structures.packages import PackagesConfigurationData


class DNFRequirementsTestCase(unittest.TestCase):

    def _create_group(self, name):
        """Create a mocked group object."""
        group = Mock()
        group.id = name
        return group

    def _create_requirement(self, name, reason, req_type=REQUIREMENT_TYPE_PACKAGE):
        """Create a new requirement."""
        requirement = Requirement()
        requirement.type = req_type
        requirement.name = name
        requirement.reason = reason
        return requirement

    def _compare_requirements(self, requirements, expected):
        """Compare the given lists of requirements."""
        assert str(requirements) == str(expected)

    @patch_dbus_get_proxy_with_cache
    def test_collect_language_requirements(self, proxy_getter):
        """Test the function collect_language_requirements."""
        boss = BOSS.get_proxy()
        boss.GetModules.return_value = [LOCALIZATION.service_name]

        proxy = LOCALIZATION.get_proxy()
        proxy.Language = "cs_CZ.UTF-8"
        proxy.LanguageSupport = ["en_GB.UTF-8", "sr_RS@cyrilic"]

        dnf_manager = Mock(spec=DNFManager)
        dnf_manager.match_available_packages.return_value = [
            "langpacks-cs",
            "langpacks-core-cs",
            "langpacks-core-font-cs",
            "langpacks-en",
            "langpacks-en_GB",
            "langpacks-core-en",
            "langpacks-core-en_GB",
            "langpacks-core-font-en"
        ]

        with self.assertLogs(level="WARNING") as cm:
            requirements = collect_language_requirements(dnf_manager)

        r1 = self._create_requirement(
            "langpacks-cs", "Required to support the locale 'cs_CZ.UTF-8'."
        )
        r2 = self._create_requirement(
            "langpacks-en_GB", "Required to support the locale 'en_GB.UTF-8'."
        )
        self._compare_requirements(requirements, [r1, r2])

        msg = "Selected locale 'sr_RS@cyrilic' does not match any available langpacks."
        assert any(map(lambda x: msg in x, cm.output))

    @patch('pyanaconda.core.hw.execWithCapture')
    def test_collect_platform_requirements(self, execute):
        """Test the function collect_platform_requirements."""
        dnf_manager = Mock(spec=DNFManager)
        dnf_manager.groups = [
            "platform-vmware",
            "platform-kvm",
            "network-server",
            "virtualization"
        ]

        # No platform is detected.
        execute.return_value = None
        requirements = collect_platform_requirements(dnf_manager)
        assert requirements == []

        # Unsupported platform is detected.
        execute.return_value = "qemu"
        requirements = collect_platform_requirements(dnf_manager)
        assert requirements == []

        # Supported platform is detected.
        execute.return_value = "vmware"
        requirements = collect_platform_requirements(dnf_manager)

        r1 = self._create_requirement(
            name="platform-vmware",
            reason="Required for the vmware platform.",
            req_type=REQUIREMENT_TYPE_GROUP
        )

        self._compare_requirements(requirements, [r1])

    @patch('pyanaconda.core.hw.execWithCapture')
    def test_collect_dnf_requirements(self, execute):
        """Test the function collect_dnf_requirements."""

        data = PackagesConfigurationData()
        data.multilib_policy = MULTILIB_POLICY_BEST
        dnf_manager = Mock(spec=DNFManager)
        dnf_manager.is_package_available.return_value = True

        # No need for dnf config
        execute.return_value = None
        requirements = collect_dnf_requirements(dnf_manager, data)
        assert requirements == []

        data.multilib_policy = MULTILIB_POLICY_ALL

        # Require dnf-5 version of plugins
        dnf_manager.is_package_available.return_value = True
        requirements = collect_dnf_requirements(dnf_manager, data)
        r = self._create_requirement(
            name="dnf5-modules",
            reason="Needed to enable multilib support."
        )
        self._compare_requirements(requirements, [r])

        # Require dnf-4 version of plugins
        dnf_manager.is_package_available.return_value = False
        requirements = collect_dnf_requirements(dnf_manager, data)
        r = self._create_requirement(
            name="dnf-plugins-core",
            reason="Needed to enable multilib support."
        )
        self._compare_requirements(requirements, [r])

    def test_collect_driver_disk_requirements(self):
        """Test the function collect_driver_disk_requirements."""
        requirements = collect_driver_disk_requirements("/non/existent/file")
        assert requirements == []

        r1 = self._create_requirement(
            name="p1",
            reason="Required by the driver updates disk."
        )
        r2 = self._create_requirement(
            name="p2",
            reason="Required by the driver updates disk."
        )
        r3 = self._create_requirement(
            name="p3",
            reason="Required by the driver updates disk."
        )

        with tempfile.NamedTemporaryFile(mode="w+t") as f:
            f.write("p1\np2 \np3  ")
            f.flush()

            requirements = collect_driver_disk_requirements(f.name)
            self._compare_requirements(requirements, [r1, r2, r3])

    @patch_dbus_get_proxy_with_cache
    def test_collect_remote_requirements(self, proxy_getter):
        """Test the function collect_remote_requirements."""
        r1 = self._create_requirement("a", "Required by A.")
        r2 = self._create_requirement("b", "Required by B.")
        r3 = self._create_requirement("c", "Required by C.")

        boss = BOSS.get_proxy()
        boss.CollectRequirements.return_value = \
            Requirement.to_structure_list([r1, r2, r3])

        requirements = collect_remote_requirements()
        self._compare_requirements(requirements, [r1, r2, r3])

    def test_apply_requirements_invalid_requirement(self):
        """Test the function apply_requirements with an invalid requirement."""
        r1 = self._create_requirement("a", "Required by A.", req_type="INVALID")

        include_list = []
        exclude_list = []
        requirements = [r1]

        with self.assertLogs(level="WARNING") as cm:
            apply_requirements(requirements, include_list, exclude_list)

        msg = "Unsupported type 'INVALID' of the requirement."
        assert any(map(lambda x: msg in x, cm.output))

        assert include_list == []
        assert exclude_list == []

    @patch('pyanaconda.modules.payloads.payload.dnf.requirements.conf')
    def test_apply_requirements_ignored_packages(self, conf_mock):
        """Test the function apply_requirements with ignored packages."""
        conf_mock.payload.ignored_packages = ["a"]
        r1 = self._create_requirement("a", "Required by A.")

        include_list = []
        exclude_list = []
        requirements = [r1]

        with self.assertLogs(level="DEBUG") as cm:
            apply_requirements(requirements, include_list, exclude_list)

        msg = "Requirement 'a' is ignored by the configuration."
        assert any(map(lambda x: msg in x, cm.output))

        assert include_list == []
        assert exclude_list == []

    @patch('pyanaconda.modules.payloads.payload.dnf.requirements.conf')
    def test_apply_requirements_excluded_packages(self, conf_mock):
        """Test the function apply_requirements with excluded packages."""
        conf_mock.payload.ignored_packages = []
        r1 = self._create_requirement("a", "Required by A.")

        include_list = []
        exclude_list = ["a"]
        requirements = [r1]

        with self.assertLogs(level="DEBUG") as cm:
            apply_requirements(requirements, include_list, exclude_list)

        msg = "Requirement 'a' is ignored because it's excluded."
        assert any(map(lambda x: msg in x, cm.output))

        assert include_list == []
        assert exclude_list == ["a"]

    @patch('pyanaconda.modules.payloads.payload.dnf.requirements.conf')
    def test_apply_requirements(self, conf_mock):
        """Test the function apply_requirements."""
        conf_mock.payload.ignored_packages = []

        r1 = self._create_requirement("a", "Required by A.")
        r2 = self._create_requirement("b", "Required by B.")
        r3 = self._create_requirement("c", "Required by C.", req_type=REQUIREMENT_TYPE_GROUP)
        r4 = self._create_requirement("d", "Required by D.", req_type=REQUIREMENT_TYPE_GROUP)

        include_list = ["p1", "p2", "@g1", "@g2"]
        exclude_list = ["b", "@d"]
        requirements = [r1, r2, r3, r4]

        with self.assertLogs(level="DEBUG") as cm:
            apply_requirements(requirements, include_list, exclude_list)

        msg = "Requirement 'a' is applied. Reason: Required by A."
        assert any(map(lambda x: msg in x, cm.output))

        msg = "Requirement '@c' is applied. Reason: Required by C."
        assert any(map(lambda x: msg in x, cm.output))

        assert include_list == ["p1", "p2", "@g1", "@g2", "a", "@c"]
        assert exclude_list == ["b", "@d"]
