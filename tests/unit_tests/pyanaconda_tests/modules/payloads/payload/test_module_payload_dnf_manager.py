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
import unittest
from unittest.mock import Mock, patch

import pytest
from blivet.size import ROUND_UP, Size
from dnf.exceptions import MarkingErrors
from dnf.package import Package

from pyanaconda.core.constants import MULTILIB_POLICY_ALL
from pyanaconda.modules.common.structures.payload import PackagesConfigurationData
from pyanaconda.modules.payloads.payload.dnf.dnf_manager import DNFManager


class DNFMangerTestCase(unittest.TestCase):
    """Test the abstraction of the DNF base."""

    def setUp(self):
        self.maxDiff = None
        self.dnf_manager = DNFManager()

    def _check_configuration(self, *attributes):
        """Check the DNF configuration."""
        configuration = self.dnf_manager._base.conf.dump()
        configuration = configuration.splitlines(keepends=False)

        for attribute in attributes:
            assert attribute in configuration

    def _check_substitutions(self, substitutions):
        """Check the DNF substitutions."""
        assert dict(self.dnf_manager._base.conf.substitutions) == substitutions

    def _get_package(self, name):
        """Get a mocked package of the specified name."""
        package = Mock(spec=Package)
        package.name = name
        package.arch = "x86_64"
        package.evr = "1.2-3"
        package.buildtime = 100
        package.returnIdSum.return_value = ("", "1a2b3c")
        return package

    def test_create_base(self):
        """Test the creation of the DNF base."""
        assert self.dnf_manager._base is not None

    def test_reset_base(self):
        """Test the reset of the DNF base."""
        base_1 = self.dnf_manager._base
        assert self.dnf_manager._base == base_1
        self.dnf_manager.reset_base()

        base_2 = self.dnf_manager._base
        assert self.dnf_manager._base == base_2
        assert self.dnf_manager._base != base_1

    def test_clear_cache(self):
        """Test the clear_cache method."""
        self.dnf_manager.clear_cache()

    def test_set_default_configuration(self):
        """Test the default configuration of the DNF base."""
        self._check_configuration(
            "gpgcheck = 0",
            "skip_if_unavailable = 0"
        )
        self._check_configuration(
            "cachedir = /tmp/dnf.cache",
            "pluginconfpath = /tmp/dnf.pluginconf",
            "logdir = /tmp/",
        )
        self._check_configuration(
            "installroot = /mnt/sysroot",
            "persistdir = /mnt/sysroot/var/lib/dnf"
        )
        self._check_configuration(
            "reposdir = "
            "/etc/yum.repos.d, "
            "/etc/anaconda.repos.d"
        )
        self._check_substitutions({
            "arch": "x86_64",
            "basearch": "x86_64",
            "releasever": "rawhide",
            "releasever_major": "rawhide",
            "releasever_minor": "",
            "stream": "9-stream",
        })

    @patch("pyanaconda.modules.payloads.payload.dnf.dnf_manager.get_os_release_value")
    def test_set_module_platform_id(self, get_platform_id):
        """Test the configuration of module_platform_id."""
        get_platform_id.return_value = "platform:f32"
        self.dnf_manager.reset_base()
        self._check_configuration("module_platform_id = platform:f32")

    def test_configure_proxy(self):
        """Test the proxy configuration."""
        self.dnf_manager.configure_proxy("http://user:pass@example.com/proxy")
        self._check_configuration(
            "proxy = http://example.com:3128",
            "proxy_username = user",
            "proxy_password = pass",
        )

        self.dnf_manager.configure_proxy("@:/invalid")
        self._check_configuration(
            "proxy = ",
            "proxy_username = ",
            "proxy_password = ",
        )

        self.dnf_manager.configure_proxy("http://example.com/proxy")
        self._check_configuration(
            "proxy = http://example.com:3128",
            "proxy_username = ",
            "proxy_password = ",
        )

        self.dnf_manager.configure_proxy(None)
        self._check_configuration(
            "proxy = ",
            "proxy_username = ",
            "proxy_password = ",
        )

    def test_configure_base(self):
        """Test the configuration of the DNF base."""
        data = PackagesConfigurationData()

        self.dnf_manager.configure_base(data)
        self._check_configuration(
            "multilib_policy = best",
            "timeout = 30",
            "retries = 10",
            "install_weak_deps = 1",
        )

        assert self.dnf_manager._ignore_broken_packages is False
        assert self.dnf_manager._ignore_missing_packages is False

        data.multilib_policy = MULTILIB_POLICY_ALL
        data.timeout = 100
        data.retries = 5
        data.broken_ignored = True
        data.missing_ignored = True
        data.weakdeps_excluded = True

        self.dnf_manager.configure_base(data)
        self._check_configuration(
            "multilib_policy = all",
            "timeout = 100",
            "retries = 5",
            "install_weak_deps = 0",
        )

        assert self.dnf_manager._ignore_broken_packages is True
        assert self.dnf_manager._ignore_missing_packages is True

    def test_dump_configuration(self):
        """Test the dump of the DNF configuration."""
        with self.assertLogs(level="DEBUG") as cm:
            self.dnf_manager.dump_configuration()

        msg = "DNF configuration:"
        assert any(map(lambda x: msg in x, cm.output))

        msg = "installroot = /mnt/sysroot"
        assert any(map(lambda x: msg in x, cm.output))

    def test_get_installation_size(self):
        """Test the get_installation_size method."""
        # No transaction.
        size = self.dnf_manager.get_installation_size()
        assert size == Size("3000 MiB")

        # Fake transaction.
        tsi_1 = Mock()
        tsi_1.pkg.installsize = 1024 * 100
        tsi_1.pkg.files = ["/file"] * 10

        tsi_2 = Mock()
        tsi_2.pkg.installsize = 1024 * 200
        tsi_2.pkg.files = ["/file"] * 20

        self.dnf_manager._base.transaction = [tsi_1, tsi_2]
        size = self.dnf_manager.get_installation_size()
        size = size.round_to_nearest("KiB", ROUND_UP)

        assert size == Size("528 KiB")

    def test_get_download_size(self):
        """Test the get_download_size method."""
        # No transaction.
        size = self.dnf_manager.get_download_size()
        assert size == Size(0)

        # Fake transaction.
        tsi_1 = Mock()
        tsi_1.pkg.downloadsize = 1024 * 1024 * 100

        tsi_2 = Mock()
        tsi_2.pkg.downloadsize = 1024 * 1024 * 200

        self.dnf_manager._base.transaction = [tsi_1, tsi_2]
        size = self.dnf_manager.get_download_size()

        assert size == Size("450 MiB")

    def test_environments(self):
        """Test the environments property."""
        assert self.dnf_manager.environments == []

        # Fake environments.
        env_1 = Mock(id="environment-1")
        env_2 = Mock(id="environment-2")
        env_3 = Mock(id="environment-3")

        # Fake comps.
        comps = Mock(environments=[env_1, env_2, env_3])

        self.dnf_manager._base._comps = comps
        assert self.dnf_manager.environments == [
            "environment-1",
            "environment-2",
            "environment-3",
        ]

    @patch("dnf.base.Base.install_specs")
    def test_apply_specs(self, install_specs):
        """Test the apply_specs method."""
        self.dnf_manager.apply_specs(
            include_list=["@g1", "p1"],
            exclude_list=["@g2", "p2"]
        )

        install_specs.assert_called_once_with(
            install=["@g1", "p1"],
            exclude=["@g2", "p2"],
            strict=True
        )

    @patch("dnf.base.Base.install_specs")
    def test_apply_specs_error(self, install_specs):
        """Test the apply_specs method with an error."""
        install_specs.side_effect = MarkingErrors(
            error_group_specs=["@g1"]
        )

        with pytest.raises(MarkingErrors):
            self.dnf_manager.apply_specs(
                include_list=["@g1", "p1"],
                exclude_list=["@g2", "p2"]
            )

    @patch("dnf.base.Base.install_specs")
    def test_apply_specs_ignore_broken(self, install_specs):
        """Test the apply_specs method with ignored broken packages."""
        self.dnf_manager._ignore_broken_packages = True
        self.dnf_manager.apply_specs(
            include_list=["@g1", "p1"],
            exclude_list=["@g2", "p2"]
        )

        install_specs.assert_called_once_with(
            install=["@g1", "p1"],
            exclude=["@g2", "p2"],
            strict=False
        )

    @patch("dnf.base.Base.install_specs")
    def test_apply_specs_ignore_missing(self, install_specs):
        """Test the apply_specs method with ignored missing packages."""
        self.dnf_manager._ignore_missing_packages = True

        # Ignore a missing package.
        install_specs.side_effect = MarkingErrors(
            no_match_pkg_specs=["p1"]
        )

        self.dnf_manager.apply_specs(
            include_list=["@g1", "p1"],
            exclude_list=["@g2", "p2"]
        )

        install_specs.assert_called_once_with(
            install=["@g1", "p1"],
            exclude=["@g2", "p2"],
            strict=True
        )

        # Don't ignore a broken transaction.
        install_specs.side_effect = MarkingErrors(
            error_pkg_specs=["p1"]
        )

        with pytest.raises(MarkingErrors):
            self.dnf_manager.apply_specs(
                include_list=["@g1", "p1"],
                exclude_list=["@g2", "p2"]
            )

    def test_match_available_packages(self):
        """Test the match_available_packages method"""
        p1 = self._get_package("langpacks-cs")
        p2 = self._get_package("langpacks-core-cs")
        p3 = self._get_package("langpacks-core-font-cs")

        sack = Mock()
        sack.query.return_value.available.return_value.filter.return_value = [
            p1, p2, p3
        ]

        # With metadata.
        self.dnf_manager._base._sack = sack
        assert self.dnf_manager.match_available_packages("langpacks-*") == [
            "langpacks-cs",
            "langpacks-core-cs",
            "langpacks-core-font-cs"
        ]

        # No metadata.
        self.dnf_manager._base._sack = None

        with self.assertLogs(level="WARNING") as cm:
            assert self.dnf_manager.match_available_packages("langpacks-*") == []

        msg = "There is no metadata about packages!"
        assert any(map(lambda x: msg in x, cm.output))
