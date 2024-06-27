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
import os.path
import unittest
from textwrap import dedent

import pytest

from tempfile import TemporaryDirectory
from unittest.mock import patch, Mock, call

from blivet.size import Size, ROUND_UP
from dasbus.structure import compare_data

from dnf.callback import STATUS_OK, STATUS_FAILED, PKG_SCRIPTLET
from dnf.comps import Environment, Comps, Group
from dnf.exceptions import MarkingErrors, DepsolveError, RepoError
from dnf.package import Package
from dnf.transaction import PKG_INSTALL, TRANS_POST
from dnf.repo import Repo
import libdnf.transaction

from pyanaconda.core.constants import MULTILIB_POLICY_ALL, URL_TYPE_BASEURL, URL_TYPE_MIRRORLIST, \
    URL_TYPE_METALINK
from pyanaconda.modules.common.errors.installation import PayloadInstallationError
from pyanaconda.modules.common.errors.payload import UnknownCompsEnvironmentError, \
    UnknownCompsGroupError, UnknownRepositoryError
from pyanaconda.modules.common.structures.comps import CompsEnvironmentData, CompsGroupData
from pyanaconda.modules.common.structures.packages import PackagesConfigurationData
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.payloads.payload.dnf.dnf_manager import DNFManager, \
    InvalidSelectionError, BrokenSpecsError, MissingSpecsError, MetadataError


class DNFManagerTestCase(unittest.TestCase):
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

        assert base_1._closed
        assert not base_2._closed

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

    @patch("dnf.module.module_base.ModuleBase.enable")
    def test_enable_modules(self, module_base_enable):
        """Test the enable_modules method."""
        self.dnf_manager.enable_modules(
            module_specs=["m1", "m2:latest"]
        )
        module_base_enable.assert_called_once_with(
            ["m1", "m2:latest"]
        )

    @patch("dnf.module.module_base.ModuleBase.enable")
    def test_enable_modules_error(self, module_base_enable):
        """Test the failed enable_modules method."""
        module_base_enable.side_effect = MarkingErrors(
            module_depsolv_errors=["e1", "e2"]
        )

        with pytest.raises(BrokenSpecsError):
            self.dnf_manager.enable_modules(
                module_specs=["m1", "m2:latest"]
            )

    @patch("dnf.module.module_base.ModuleBase.disable")
    def test_disable_modules(self, module_base_disable):
        """Test the enable_modules method."""
        self.dnf_manager.disable_modules(
            module_specs=["m1", "m2:latest"]
        )
        module_base_disable.assert_called_once_with(
            ["m1", "m2:latest"]
        )

    @patch("dnf.module.module_base.ModuleBase.disable")
    def test_disable_modules_error(self, module_base_disable):
        """Test the failed enable_modules method."""
        module_base_disable.side_effect = MarkingErrors(
            module_depsolv_errors=["e1", "e2"]
        )

        with pytest.raises(BrokenSpecsError):
            self.dnf_manager.disable_modules(
                module_specs=["m1", "m2:latest"]
            )

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

        with pytest.raises(BrokenSpecsError):
            self.dnf_manager.apply_specs(
                include_list=["@g1", "p1"],
                exclude_list=["@g2", "p2"]
            )

        install_specs.side_effect = MarkingErrors(
            no_match_group_specs=["@g1"]
        )

        with pytest.raises(MissingSpecsError):
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

        with pytest.raises(BrokenSpecsError):
            self.dnf_manager.apply_specs(
                include_list=["@g1", "p1"],
                exclude_list=["@g2", "p2"]
            )

    @patch("dnf.base.Base.download_packages")
    @patch("dnf.base.Base.transaction")
    def test_download_packages(self, transaction, download_packages):
        """Test the download_packages method."""
        callback = Mock()
        transaction.install_set = ["p1", "p2", "p3"]
        download_packages.side_effect = self._download_packages

        self.dnf_manager.download_packages(callback)

        callback.assert_has_calls([
            call('Downloading 3 RPMs, 25 B / 300 B (8%) done.'),
            call('Downloading 3 RPMs, 75 B / 300 B (25%) done.'),
            call('Downloading 3 RPMs, 100 B / 300 B (33%) done.'),
            call('Downloading 3 RPMs, 125 B / 300 B (41%) done.'),
            call('Downloading 3 RPMs, 175 B / 300 B (58%) done.'),
            call('Downloading 3 RPMs, 200 B / 300 B (66%) done.'),
            call('Downloading 3 RPMs, 225 B / 300 B (75%) done.'),
            call('Downloading 3 RPMs, 275 B / 300 B (91%) done.'),
            call('Downloading 3 RPMs, 300 B / 300 B (100%) done.')
        ])

    def _download_packages(self, packages, progress):
        """Simulate the download of packages."""
        progress.start(total_files=3, total_size=300)

        for name in packages:
            payload = Mock()
            payload.__str__ = Mock(return_value=name)
            payload.download_size = 100

            progress.last_time = 0
            progress.progress(payload, 25)

            progress.last_time += 3600
            progress.progress(payload, 50)

            progress.last_time = 0
            progress.progress(payload, 75)

            progress.last_time = 0
            progress.end(payload, STATUS_OK, "Message!")

        assert progress.downloads == {
            "p1": 100,
            "p2": 100,
            "p3": 100
        }

    @patch("dnf.base.Base.download_packages")
    @patch("dnf.base.Base.transaction")
    def test_download_packages_failed(self, transaction, download_packages):
        """Test the download_packages method with failed packages."""
        callback = Mock()
        transaction.install_set = ["p1", "p2", "p3"]
        download_packages.side_effect = self._download_packages_failed

        self.dnf_manager.download_packages(callback)

        callback.assert_has_calls([
            call('Downloading 3 RPMs, 25 B / 300 B (8%) done.'),
            call('Downloading 3 RPMs, 50 B / 300 B (16%) done.'),
            call('Downloading 3 RPMs, 75 B / 300 B (25%) done.')
        ])

    def _download_packages_failed(self, packages, progress):
        """Simulate the failed download of packages."""
        progress.start(total_files=3, total_size=300)

        for name in packages:
            payload = Mock()
            payload.__str__ = Mock(return_value=name)
            payload.download_size = 100

            progress.last_time = 0
            progress.progress(payload, 25)

            progress.last_time = 0
            progress.end(payload, STATUS_FAILED, "Message!")

        assert progress.downloads == {
            "p1": 25,
            "p2": 25,
            "p3": 25
        }

    @patch("dnf.base.Base.do_transaction")
    def test_install_packages(self, do_transaction):
        """Test the install_packages method."""
        calls = []
        do_transaction.side_effect = self._install_packages

        # Fake transaction.
        self.dnf_manager._base.transaction = [Mock(), Mock(), Mock()]

        self.dnf_manager.install_packages(calls.append)

        assert calls == [
            'Installing p1.x86_64 (0/3)',
            'Installing p2.x86_64 (1/3)',
            'Installing p3.x86_64 (2/3)',
            'Performing post-installation setup tasks',
            'Configuring p1.x86_64',
            'Configuring p2.x86_64',
            'Configuring p3.x86_64',
        ]

    def _get_package(self, name):
        """Get a mocked package of the specified name."""
        package = Mock(spec=Package)
        package.name = name
        package.arch = "x86_64"
        package.evr = "1.2-3"
        package.buildtime = 100
        package.returnIdSum.return_value = ("", "1a2b3c")
        return package

    def _install_packages(self, progress):
        """Simulate the installation of packages."""
        packages = list(map(self._get_package, ["p1", "p2", "p3"]))
        ts_total = len(packages)

        for ts_done, package in enumerate(packages):
            progress.progress(package, PKG_INSTALL, 0, 100, ts_done, ts_total)
            progress.progress(package, PKG_INSTALL, 50, 100, ts_done, ts_total)
            progress.progress(package, PKG_SCRIPTLET, 75, 100, ts_done, ts_total)
            progress.progress(package, PKG_INSTALL, 100, 100, ts_done + 1, ts_total)

        progress.progress(None, TRANS_POST, None, None, None, None)

        for ts_done, package in enumerate(packages):
            progress.progress(package, PKG_SCRIPTLET, 100, 100, ts_done + 1, ts_total)

    @patch("dnf.base.Base.do_transaction")
    def test_install_packages_failed(self, do_transaction):
        """Test the failed install_packages method."""
        calls = []
        do_transaction.side_effect = self._install_packages_failed

        with pytest.raises(PayloadInstallationError) as cm:
            self.dnf_manager.install_packages(calls.append)

        msg = "An error occurred during the transaction: " \
              "The p1 package couldn't be installed!"

        assert str(cm.value) == msg
        assert calls == []

    def _install_packages_failed(self, progress):
        """Simulate the failed installation of packages."""
        progress.error("The p1 package couldn't be installed!")

    @patch("dnf.base.Base.do_transaction")
    def test_install_packages_dnf_ts_item_error(self, do_transaction):
        """Test install_packages method failing on transaction item error."""
        calls = []

        # Fake transaction.
        tsi_1 = Mock()
        tsi_1.state = libdnf.transaction.TransactionItemState_ERROR

        tsi_2 = Mock()

        self.dnf_manager._base.transaction = [tsi_1, tsi_2]

        with pytest.raises(PayloadInstallationError) as cm:
            self.dnf_manager.install_packages(calls.append)

        msg = "An error occurred during the transaction: " \
              "The transaction process has ended with errors."

        assert str(cm.value) == msg
        assert calls == []

    @patch("dnf.base.Base.do_transaction")
    def test_install_packages_quit(self, do_transaction):
        """Test the terminated install_packages method."""
        calls = []
        do_transaction.side_effect = self._install_packages_quit

        with pytest.raises(PayloadInstallationError) as cm:
            self.dnf_manager.install_packages(calls.append)

        msg = "An error occurred during the transaction: " \
              "The transaction process has ended abruptly: " \
              "Something went wrong with the p1 package!"

        assert msg in str(cm.value)
        assert calls == []

    def _install_packages_quit(self, progress):
        """Simulate the terminated installation of packages."""
        raise IOError("Something went wrong with the p1 package!")

    def _add_repo(self, name, enabled=True):
        """Add the DNF repo object."""
        repo = Repo(name, self.dnf_manager._base.conf)
        self.dnf_manager._base.repos.add(repo)

        if enabled:
            repo.enable()

        return repo

    def test_set_download_location(self):
        """Test the set_download_location method."""
        r1 = self._add_repo("r1")
        r2 = self._add_repo("r2")
        r3 = self._add_repo("r3")

        self.dnf_manager.set_download_location("/my/download/location")

        assert r1.pkgdir == "/my/download/location"
        assert r2.pkgdir == "/my/download/location"
        assert r3.pkgdir == "/my/download/location"

    def test_download_location(self):
        """Test the download_location property."""
        assert self.dnf_manager.download_location is None

        self.dnf_manager.set_download_location("/my/location")
        assert self.dnf_manager.download_location == "/my/location"

        self.dnf_manager.reset_base()
        assert self.dnf_manager.download_location is None

    def test_substitute(self):
        """Test the substitute method."""
        # No variables.
        assert self.dnf_manager.substitute(None) == ""
        assert self.dnf_manager.substitute("") == ""
        assert self.dnf_manager.substitute("/") == "/"
        assert self.dnf_manager.substitute("/text") == "/text"

        # Unknown variables.
        assert self.dnf_manager.substitute("/$unknown") == "/$unknown"

        # Supported variables.
        assert self.dnf_manager.substitute("/$basearch") != "/$basearch"
        assert self.dnf_manager.substitute("/$releasever") != "/$releasever"

    def test_configure_substitution(self):
        """Test the configure_substitution function."""
        self.dnf_manager.configure_substitution(
            release_version="123"
        )
        self._check_substitutions({
            "arch": "x86_64",
            "basearch": "x86_64",
            "releasever": "123",
            "releasever_major": "123",
            "releasever_minor": "",
        })

        # Ignore an undefined release version.
        self.dnf_manager.configure_substitution(
            release_version=""
        )
        self._check_substitutions({
            "arch": "x86_64",
            "basearch": "x86_64",
            "releasever": "123",
            "releasever_major": "123",
            "releasever_minor": "",
        })

    @patch("dnf.subject.Subject.get_best_query")
    def test_is_package_available(self, get_best_query):
        """Test the is_package_available method."""
        self.dnf_manager._base._sack = Mock()
        assert self.dnf_manager.is_package_available("kernel") is True

        # No package.
        get_best_query.return_value = None
        assert self.dnf_manager.is_package_available("kernel") is False

        # No metadata.
        self.dnf_manager._base._sack = None

        with self.assertLogs(level="WARNING") as cm:
            assert self.dnf_manager.is_package_available("kernel") is False

        msg = "There is no metadata about packages!"
        assert any(map(lambda x: msg in x, cm.output))

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

    @patch("dnf.base.Base.resolve")
    def test_resolve_selection(self, resolve):
        """Test the resolve_selection method."""
        self.dnf_manager._base.transaction = [Mock(), Mock()]

        with self.assertLogs(level="INFO") as cm:
            self.dnf_manager.resolve_selection()

        expected = "The software selection has been resolved (2 packages selected)."
        assert expected in "\n".join(cm.output)

        resolve.assert_called_once()

    @patch("dnf.base.Base.resolve")
    def test_resolve_selection_failed(self, resolve):
        """Test the failed resolve_selection method."""
        resolve.side_effect = DepsolveError("e1")

        with pytest.raises(InvalidSelectionError) as cm:
            self.dnf_manager.resolve_selection()

        expected = \
            "The following software marked for installation has errors.\n" \
            "This is likely caused by an error with your installation source.\n\n" \
            "e1"

        assert expected == str(cm.value)

    def test_clear_selection(self):
        """Test the clear_selection method."""
        self.dnf_manager.clear_selection()


class DNFManagerCompsTestCase(unittest.TestCase):
    """Test the comps abstraction of the DNF base."""

    def setUp(self):
        self.maxDiff = None
        self.dnf_manager = DNFManager()
        self.dnf_manager._base._comps = self._create_comps()

    @property
    def comps(self):
        """The mocked comps object."""
        return self.dnf_manager._base._comps

    def _create_comps(self):
        """Create a mocked comps object."""
        comps = Mock(spec=Comps)
        comps.environments = []
        comps.groups = []

        def environment_by_pattern(name):
            for e in comps.environments:
                # pylint: disable=no-member
                if name in (e.id, e.ui_name):
                    return e

            return None

        comps.environment_by_pattern = environment_by_pattern

        def group_by_pattern(name):
            for e in comps.groups:
                # pylint: disable=no-member
                if name in (e.id, e.ui_name):
                    return e

            return None

        comps.group_by_pattern = group_by_pattern
        return comps

    def _add_group(self, grp_id, visible=True):
        """Add a mocked group with the specified id."""
        group = Mock(spec=Group)
        group.id = grp_id
        group.ui_name = f"The '{grp_id}' group"
        group.ui_description = f"This is the '{grp_id}' group."
        group.visible = visible

        self.comps.groups.append(group)

    def _add_environment(self, env_id, optional=(), default=()):
        """Add a mocked environment with the specified id."""
        environment = Mock(spec=Environment)
        environment.id = env_id
        environment.ui_name = f"The '{env_id}' environment"
        environment.ui_description = f"This is the '{env_id}' environment."
        environment.option_ids = []

        for opt_id in optional:
            option = Mock()
            option.name = opt_id
            option.default = opt_id in default
            environment.option_ids.append(option)

        self.comps.environments.append(environment)

    def test_groups(self):
        """Test the groups property."""
        assert self.dnf_manager.groups == []

        self._add_group("g1")
        self._add_group("g2")
        self._add_group("g3")

        assert self.dnf_manager.groups == [
            "g1", "g2", "g3",
        ]

    def test_resolve_group(self):
        """Test the resolve_group method."""
        assert self.dnf_manager.resolve_group("") is None
        assert self.dnf_manager.resolve_group("g1") is None

        self._add_group("g1")

        assert self.dnf_manager.resolve_group("g1") == "g1"
        assert self.dnf_manager.resolve_group("g2") is None

    def test_get_group_data_error(self):
        """Test the failed get_group_data method."""
        with pytest.raises(UnknownCompsGroupError):
            self.dnf_manager.get_group_data("g1")

    def test_get_group_data(self):
        """Test the get_group_data method."""
        self._add_group("g1")

        expected = CompsGroupData()
        expected.id = "g1"
        expected.name = "The 'g1' group"
        expected.description = "This is the 'g1' group."

        data = self.dnf_manager.get_group_data("g1")
        assert isinstance(data, CompsGroupData)
        assert compare_data(data, expected)

    def test_no_default_environment(self):
        """Test the default_environment property with no environments."""
        assert self.dnf_manager.default_environment is None

    def test_default_environment(self):
        """Test the default_environment property with some environments."""
        self._add_environment("e1")
        self._add_environment("e2")
        self._add_environment("e3")

        with patch("pyanaconda.modules.payloads.payload.dnf.dnf_manager.conf") as conf:
            # Choose the first environment.
            conf.payload.default_environment = ""
            assert self.dnf_manager.default_environment == "e1"

            # Choose the configured environment.
            conf.payload.default_environment = "e2"
            assert self.dnf_manager.default_environment == "e2"

    def test_environments(self):
        """Test the environments property."""
        assert self.dnf_manager.environments == []

        self._add_environment("e1")
        self._add_environment("e2")
        self._add_environment("e3")

        assert self.dnf_manager.environments == [
            "e1", "e2", "e3",
        ]

    def test_resolve_environment(self):
        """Test the resolve_environment method."""
        assert self.dnf_manager.resolve_environment("") is None
        assert self.dnf_manager.resolve_environment("e1") is None

        self._add_environment("e1")

        assert self.dnf_manager.resolve_environment("e1") == "e1"
        assert self.dnf_manager.resolve_environment("e2") is None

    def test_get_environment_data_error(self):
        """Test the failed get_environment_data method."""
        with pytest.raises(UnknownCompsEnvironmentError):
            self.dnf_manager.get_environment_data("e1")

    def test_get_environment_data(self):
        """Test the get_environment_data method."""
        self._add_environment("e1")

        expected = CompsEnvironmentData()
        expected.id = "e1"
        expected.name = "The 'e1' environment"
        expected.description = "This is the 'e1' environment."

        data = self.dnf_manager.get_environment_data("e1")
        assert isinstance(data, CompsEnvironmentData)
        assert compare_data(data, expected)

    def test_get_environment_data_visible_groups(self):
        """Test the get_environment_data method with visible groups."""
        self._add_group("g1")
        self._add_group("g2", visible=False)
        self._add_group("g3")
        self._add_group("g4", visible=False)

        self._add_environment("e1")

        data = self.dnf_manager.get_environment_data("e1")
        assert data.visible_groups == ["g1", "g3"]

    def test_get_environment_data_optional_groups(self):
        """Test the get_environment_data method with optional groups."""
        self._add_group("g1")
        self._add_group("g2")
        self._add_group("g3")
        self._add_group("g4")

        self._add_environment("e1", optional=["g1", "g3"])

        data = self.dnf_manager.get_environment_data("e1")
        assert data.optional_groups == ["g1", "g3"]

    def test_get_environment_data_default_groups(self):
        """Test the get_environment_data method with default groups."""
        self._add_group("g1")
        self._add_group("g2")
        self._add_group("g3")
        self._add_group("g4")

        self._add_environment("e1", optional=["g1", "g2", "g3"], default=["g1", "g3"])

        data = self.dnf_manager.get_environment_data("e1")
        assert data.default_groups == ["g1", "g3"]

    def test_environment_data_available_groups(self):
        """Test the get_available_groups method."""
        data = CompsEnvironmentData()
        assert data.get_available_groups() == []

        data.optional_groups = ["g1", "g2", "g3"]
        data.visible_groups = ["g3", "g4", "g5"]
        data.default_groups = ["g1", "g3"]

        assert data.get_available_groups() == [
            "g1", "g2", "g3", "g4", "g5"
        ]


class DNFManagerReposTestCase(unittest.TestCase):
    """Test the repo abstraction of the DNF base."""

    def setUp(self):
        self.maxDiff = None
        self.dnf_manager = DNFManager()

    def _add_repo(self, repo_id):
        """Add a mocked repo with the specified id."""
        repo = Repo(repo_id, self.dnf_manager._base.conf)
        self.dnf_manager._base.repos.add(repo)
        return repo

    def _check_repo(self, repo_id, attributes):
        """Check the DNF repo configuration."""
        repo = self.dnf_manager._base.repos[repo_id]
        repo_conf = repo.dump()
        repo_conf = repo_conf.splitlines(keepends=False)

        print(repo.dump())

        for attribute in attributes:
            assert attribute in repo_conf

    def _check_content(self, repo_data, expected_content):
        """Check the generated content of the .repo file."""
        expected_content = dedent(expected_content).strip()
        content = self.dnf_manager.generate_repo_file(repo_data)
        assert content == expected_content

        expected_attrs = expected_content.splitlines(keepends=False)
        self.dnf_manager.add_repository(repo_data)
        self._check_repo(repo_data.name, expected_attrs)

    def test_repositories(self):
        """Test the repositories property."""
        assert self.dnf_manager.repositories == []

        self._add_repo("r1")
        self._add_repo("r2")
        self._add_repo("r3")

        assert self.dnf_manager.repositories == ["r1", "r2", "r3"]

    def test_enabled_repositories(self):
        """Test the enabled_repositories property."""
        assert self.dnf_manager.enabled_repositories == []

        self._add_repo("r1").disable()
        self._add_repo("r2").enable()
        self._add_repo("r3").disable()
        self._add_repo("r4").enable()

        assert self.dnf_manager.enabled_repositories == ["r2", "r4"]

    def test_get_matching_repositories(self):
        """Test the get_matching_repositories method."""
        assert self.dnf_manager.get_matching_repositories("r*") == []

        self._add_repo("r1")
        self._add_repo("r20")
        self._add_repo("r21")
        self._add_repo("r3")

        assert self.dnf_manager.get_matching_repositories("") == []
        assert self.dnf_manager.get_matching_repositories("*1") == ["r1", "r21"]
        assert self.dnf_manager.get_matching_repositories("*2*") == ["r20", "r21"]
        assert self.dnf_manager.get_matching_repositories("r3") == ["r3"]
        assert self.dnf_manager.get_matching_repositories("r4") == []
        assert self.dnf_manager.get_matching_repositories("r*") == ["r1", "r20", "r21", "r3"]

    def test_set_repository_enabled(self):
        """Test the set_repository_enabled function."""
        self._add_repo("r1").disable()

        # Enable a disabled repository.
        with self.assertLogs(level="INFO") as cm:
            self.dnf_manager.set_repository_enabled("r1", True)

        msg = "The 'r1' repository is enabled."
        assert any(map(lambda x: msg in x, cm.output))
        assert "r1" in self.dnf_manager.enabled_repositories

        # Enable an enabled repository.
        with self.assertNoLogs(level="INFO"):
            self.dnf_manager.set_repository_enabled("r1", True)

        # Disable an enabled repository.
        with self.assertLogs(level="INFO") as cm:
            self.dnf_manager.set_repository_enabled("r1", False)

        msg = "The 'r1' repository is disabled."
        assert any(map(lambda x: msg in x, cm.output))
        assert "r1" not in self.dnf_manager.enabled_repositories

        # Disable a disabled repository.
        with self.assertNoLogs(level="INFO"):
            self.dnf_manager.set_repository_enabled("r1", False)

        # Enable an unknown repository.
        with pytest.raises(UnknownRepositoryError):
            self.dnf_manager.set_repository_enabled("r2", True)

    def test_add_repository_default(self):
        """Test the add_repository method with defaults."""
        data = RepoConfigurationData()
        data.name = "r1"

        self.dnf_manager.add_repository(data)

        self._check_repo("r1", [
            "baseurl = ",
            "proxy = ",
            "sslverify = 1",
            "sslcacert = ",
            "sslclientcert = ",
            "sslclientkey = ",
            "cost = 1000",
            "includepkgs = ",
            "excludepkgs = ",
        ])

    def test_add_repository_enabled(self):
        """Test the add_repository method with enabled repo."""
        data = RepoConfigurationData()
        data.name = "r1"
        data.enabled = True

        self.dnf_manager.add_repository(data)

        self._check_repo("r1", [
            "enabled = 1",
        ])

    def test_add_repository_disabled(self):
        """Test the add_repository method with disabled repo."""
        data = RepoConfigurationData()
        data.name = "r1"
        data.enabled = False

        self.dnf_manager.add_repository(data)

        self._check_repo("r1", [
            "enabled = 0",
        ])

    def test_add_repository_baseurl(self):
        """Test the add_repository method with baseurl."""
        data = RepoConfigurationData()
        data.name = "r1"
        data.type = URL_TYPE_BASEURL
        data.url = "http://repo"

        self.dnf_manager.add_repository(data)

        self._check_repo("r1", [
            "baseurl = http://repo",
        ])

    def test_add_repository_mirrorlist(self):
        """Test the add_repository method with mirrorlist."""
        data = RepoConfigurationData()
        data.name = "r1"
        data.type = URL_TYPE_MIRRORLIST
        data.url = "http://mirror"

        self.dnf_manager.add_repository(data)
        self._check_repo("r1", [
            "mirrorlist = http://mirror",
        ])

    def test_add_repository_metalink(self):
        """Test the add_repository method with metalink."""
        data = RepoConfigurationData()
        data.name = "r1"
        data.type = URL_TYPE_METALINK
        data.url = "http://metalink"

        self.dnf_manager.add_repository(data)
        self._check_repo("r1", [
            "metalink = http://metalink",
        ])

    def test_add_repository_no_ssl_configuration(self):
        """Test the add_repository method without the ssl configuration."""
        data = RepoConfigurationData()
        data.name = "r1"
        data.ssl_verification_enabled = False

        self.dnf_manager.add_repository(data)
        self._check_repo("r1", [
            "sslverify = 0",
        ])

    def test_add_repository_ssl_configuration(self):
        """Test the add_repository method with the ssl configuration."""
        data = RepoConfigurationData()
        data.name = "r1"
        data.ssl_verification_enabled = True
        data.ssl_configuration.ca_cert_path = "file:///ca-cert"
        data.ssl_configuration.client_cert_path = "file:///client-cert"
        data.ssl_configuration.client_key_path = "file:///client-key"

        self.dnf_manager.add_repository(data)
        self._check_repo("r1", [
            "sslverify = 1",
            "sslcacert = file:///ca-cert",
            "sslclientcert = file:///client-cert",
            "sslclientkey = file:///client-key",
        ])

    def test_add_repository_invalid_proxy(self):
        """Test the add_repository method the invalid proxy configuration."""
        data = RepoConfigurationData()
        data.name = "r1"
        data.proxy = "@:/invalid"

        self.dnf_manager.add_repository(data)
        self._check_repo("r1", [
            "proxy = ",
        ])

    def test_add_repository_no_auth_proxy(self):
        """Test the add_repository method the no auth proxy configuration."""
        data = RepoConfigurationData()
        data.name = "r1"
        data.proxy = "http://example.com:1234"

        self.dnf_manager.add_repository(data)
        self._check_repo("r1", [
            "proxy = http://example.com:1234",
        ])

    def test_add_repository_proxy(self):
        """Test the add_repository method with the proxy configuration."""
        data = RepoConfigurationData()
        data.name = "r1"
        data.proxy = "http://user:pass@example.com:1234"

        self.dnf_manager.add_repository(data)
        self._check_repo("r1", [
            "proxy = http://example.com:1234",
            "proxy_username = user",
            "proxy_password = pass",
        ])

    def test_add_repository_cost(self):
        """Test the add_repository method with a cost."""
        data = RepoConfigurationData()
        data.name = "r1"
        data.cost = 256

        self.dnf_manager.add_repository(data)
        self._check_repo("r1", [
            "cost = 256"
        ])

    def test_add_repository_packages(self):
        """Test the add_repository method with packages."""
        data = RepoConfigurationData()
        data.name = "r1"
        data.included_packages = ["p1", "p2"]
        data.excluded_packages = ["p3", "p4"]

        self.dnf_manager.add_repository(data)
        self._check_repo("r1", [
            "includepkgs = p1, p2",
            "excludepkgs = p3, p4",
        ])

    def test_add_repository_replace(self):
        """Test the add_repository method with a replacement."""
        data = RepoConfigurationData()
        data.name = "r1"
        data.url = "http://u1"

        self.dnf_manager.add_repository(data)
        self._check_repo("r1", [
            "baseurl = http://u1",
        ])

        data.url = "http://u2"

        self.dnf_manager.add_repository(data)
        self._check_repo("r1", [
            "baseurl = http://u2",
        ])

    def test_generate_repo_file_baseurl(self):
        """Test the generate_repo_file method with baseurl."""
        data = RepoConfigurationData()
        data.name = "r1"
        data.type = URL_TYPE_BASEURL
        data.url = "http://repo"
        data.proxy = "http://example.com:1234"
        data.cost = 256

        self._check_content(
            data,
            """
            [r1]
            name = r1
            enabled = 1
            baseurl = http://repo
            proxy = http://example.com:1234
            cost = 256
            """
        )

    def test_generate_repo_file_mirrorlist(self):
        """Test the generate_repo_file method with mirrorlist."""
        data = RepoConfigurationData()
        data.name = "r1"
        data.type = URL_TYPE_MIRRORLIST
        data.url = "http://mirror"
        data.ssl_verification_enabled = False
        data.proxy = "http://user:pass@example.com:1234"

        self._check_content(
            data,
            """
            [r1]
            name = r1
            enabled = 1
            mirrorlist = http://mirror
            sslverify = 0
            proxy = http://example.com:1234
            proxy_username = user
            proxy_password = pass
            """
        )

    def test_generate_repo_file_metalink(self):
        """Test the generate_repo_file method with metalink."""
        data = RepoConfigurationData()
        data.name = "r1"
        data.enabled = False
        data.type = URL_TYPE_METALINK
        data.url = "http://metalink"
        data.included_packages = ["p1", "p2"]
        data.excluded_packages = ["p3", "p4"]

        self._check_content(
            data,
            """
            [r1]
            name = r1
            enabled = 0
            metalink = http://metalink
            includepkgs = p1, p2
            excludepkgs = p3, p4
            """
        )

    def test_read_system_repositories(self):
        """Test the read_system_repositories method."""
        self.dnf_manager.read_system_repositories()

        # There should be some repositories in the testing environment.
        assert self.dnf_manager.repositories

        # All these repositories should be disabled.
        assert not self.dnf_manager.enabled_repositories

        # However, we should remember which ones were enabled.
        assert self.dnf_manager._enabled_system_repositories

        for repo_id in self.dnf_manager._enabled_system_repositories:
            assert repo_id in self.dnf_manager.repositories

        # Don't read system repositories again.
        with pytest.raises(RuntimeError):
            self.dnf_manager.read_system_repositories()

        # Unless we cleared the cache.
        self.dnf_manager.clear_cache()
        assert not self.dnf_manager._enabled_system_repositories
        self.dnf_manager.read_system_repositories()

        # Or reset the base.
        self.dnf_manager.reset_base()
        assert not self.dnf_manager._enabled_system_repositories
        self.dnf_manager.read_system_repositories()

    def test_restore_system_repositories(self):
        """Test the restore_system_repositories."""
        # Read repositories from the testing environment and disable them.
        self.dnf_manager.read_system_repositories()
        assert not self.dnf_manager.enabled_repositories
        assert self.dnf_manager._enabled_system_repositories

        # Re-enable repositories from the testing environment.
        self.dnf_manager.restore_system_repositories()
        assert self.dnf_manager.enabled_repositories
        assert self.dnf_manager._enabled_system_repositories

        assert self.dnf_manager.enabled_repositories == \
            self.dnf_manager._enabled_system_repositories

        # Skip unknown repositories.
        self.dnf_manager._enabled_system_repositories.append("r1")
        self.dnf_manager.restore_system_repositories()

    def test_load_repository_unknown(self):
        """Test the load_repository method with an unknown repo."""
        with pytest.raises(UnknownRepositoryError):
            self.dnf_manager.load_repository("r1")

    def test_load_repository_failed(self):
        """Test the load_repository method with a failure."""
        repo = self._add_repo("r1")
        repo.load = Mock(side_effect=RepoError("Fake error!"))
        repo.enable()

        with pytest.raises(MetadataError) as cm:
            self.dnf_manager.load_repository("r1")

        repo.load.assert_called_once()
        assert repo.enabled is False
        assert str(cm.value) == "Fake error!"

    def test_load_repository_disabled(self):
        """Test the load_repository method with a disabled repo."""
        repo = self._add_repo("r1")
        repo.load = Mock()
        repo.disable()

        self.dnf_manager.load_repository("r1")

        repo.load.assert_not_called()
        assert repo.enabled is False

    def test_load_repository(self):
        """Test the load_repository method."""
        repo = self._add_repo("r1")
        repo.load = Mock()
        repo.enable()

        self.dnf_manager.load_repository("r1")

        repo.load.assert_called_once()
        assert repo.enabled is True

    def test_load_packages_metadata(self):
        """Test the load_packages_metadata method."""
        sack = self.dnf_manager._base.sack
        comps = self.dnf_manager._base.comps

        self.dnf_manager.load_packages_metadata()

        # The metadata should be reloaded.
        assert sack != self.dnf_manager._base.sack
        assert comps != self.dnf_manager._base.comps

    def _create_repo(self, repo, repo_dir):
        """Generate fake metadata for the repo."""
        # Create the repodata directory.
        os.makedirs(os.path.join(repo_dir, "repodata"))

        # Create the repomd.xml file.
        md_path = os.path.join(repo_dir, "repodata", "repomd.xml")
        md_content = f"Metadata for {repo.id}."

        with open(md_path, 'w') as f:
            f.write(md_content)

        # Set up the baseurl.
        repo.baseurl.append("file://" + repo_dir)

    def test_load_no_repomd_hashes(self):
        """Test the load_repomd_hashes method with no repositories."""
        self.dnf_manager.load_repomd_hashes()
        assert self.dnf_manager._md_hashes == {}

    def test_load_one_repomd_hash(self):
        """Test the load_repomd_hashes method with one repository."""
        with TemporaryDirectory() as d:
            r1 = self._add_repo("r1")
            self._create_repo(r1, d)

            self.dnf_manager.load_repomd_hashes()
            assert self.dnf_manager._md_hashes == {
                'r1': b"\x90\xa0\xb7\xce\xc2H\x85#\xa3\xfci"
                      b"\x9e+\xf4\xe2\x19D\xbc\x9b'\xeb\xb7"
                      b"\x90\x1d\xcey\xb3\xd4p\xc3\x1d\xfb",
            }

    def test_load_repomd_hashes(self):
        """Test the load_repomd_hashes method."""
        with TemporaryDirectory() as d:
            r1 = self._add_repo("r1")
            r1.baseurl = [
                "file://nonexistent/1",
                "file://nonexistent/2",
                "file://nonexistent/3",
            ]
            self._create_repo(r1, d + "/r1")

            r2 = self._add_repo("r2")
            r2.baseurl = [
                "file://nonexistent/1",
                "file://nonexistent/2",
                "file://nonexistent/3",
            ]

            r3 = self._add_repo("r3")
            r3.metalink = "file://metalink"

            r4 = self._add_repo("r4")
            r4.mirrorlist = "file://mirrorlist"

            self.dnf_manager.load_repomd_hashes()

            assert self.dnf_manager._md_hashes == {
                'r1': b"\x90\xa0\xb7\xce\xc2H\x85#\xa3\xfci"
                      b"\x9e+\xf4\xe2\x19D\xbc\x9b'\xeb\xb7"
                      b"\x90\x1d\xcey\xb3\xd4p\xc3\x1d\xfb",
                'r2': None,
                'r3': None,
                'r4': None,
            }

    def test_verify_repomd_hashes(self):
        """Test the verify_repomd_hashes method."""
        with TemporaryDirectory() as d:
            # Test no repository.
            assert self.dnf_manager.verify_repomd_hashes() is False

            # Create a repository.
            r = self._add_repo("r1")
            self._create_repo(r, d)

            # Test no loaded repository.
            assert self.dnf_manager.verify_repomd_hashes() is False

            # Test a loaded repository.
            self.dnf_manager.load_repomd_hashes()
            assert self.dnf_manager.verify_repomd_hashes() is True

            # Test a different content of metadata.
            with open(os.path.join(d, "repodata", "repomd.xml"), 'w') as f:
                f.write("Different metadata for r1.")

            assert self.dnf_manager.verify_repomd_hashes() is False

            # Test a reloaded repository.
            self.dnf_manager.load_repomd_hashes()
            assert self.dnf_manager.verify_repomd_hashes() is True

            # Test the base reset.
            self.dnf_manager.reset_base()
            assert self.dnf_manager.verify_repomd_hashes() is False
