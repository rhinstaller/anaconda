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
import os
import subprocess
import unittest
from tempfile import TemporaryDirectory
from textwrap import dedent
from unittest.mock import patch, Mock, call

import libdnf5
import pytest

from blivet.size import Size, ROUND_UP

from pyanaconda.core.constants import MULTILIB_POLICY_ALL, URL_TYPE_BASEURL, URL_TYPE_MIRRORLIST, \
    URL_TYPE_METALINK
from pyanaconda.modules.common.errors.installation import PayloadInstallationError
from pyanaconda.modules.common.errors.payload import UnknownRepositoryError, \
    UnknownCompsGroupError, UnknownCompsEnvironmentError
from pyanaconda.modules.common.structures.comps import CompsEnvironmentData
from pyanaconda.modules.common.structures.packages import PackagesConfigurationData
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.payloads.payload.dnf.dnf_manager import DNFManager, simplify_config


class DNF5TestCase(unittest.TestCase):
    """Test the DNF5 library."""

    def test_runtime_error(self):
        base = libdnf5.base.Base()
        query = libdnf5.repo.RepoQuery(base)

        with pytest.raises(RuntimeError):
            query.get()

    def test_undefined_variables(self):
        base = libdnf5.base.Base()
        variables = base.get_vars()

        with pytest.raises(IndexError):
            variables.get_value("undefined")

    def test_resolve_without_setup(self):
        """Call resolve without setting up the base."""
        base = libdnf5.base.Base()
        goal = libdnf5.base.Goal(base)

        with pytest.raises(RuntimeError):
            goal.resolve()

    def test_environment_query(self):
        base = libdnf5.base.Base()
        base.setup()
        libdnf5.comps.EnvironmentQuery(base)

    def test_group_query(self):
        base = libdnf5.base.Base()
        base.setup()
        libdnf5.comps.GroupQuery(base)

    # def test_disable_failed_repository(self):
    #     base = libdnf5.base.Base()
    #     sack = base.get_repo_sack()
    #     sack.create_repo("r1")
    #     base.setup()

    #     repo = self._get_repo(base, "r1")

    #     try:
    #         repo.fetch_metadata()
    #         repo.load()
    #     except RuntimeError:
    #         print("Print something")
    #         # It will crash here.
    #         repo.disable()

    def _get_repo(self, base, repo_id):
        repos = libdnf5.repo.RepoQuery(base)
        repos.filter_id(repo_id)
        weak_ref = repos.get()
        return weak_ref.get()

    def test_simplify_config(self):
        """Test the simplify_config function."""
        base = libdnf5.base.Base()
        config = simplify_config(
            base.get_config()
        )

        config.get_installroot_option = "/my/install/root"
        assert config.get_installroot_option == "/my/install/root"


class DNFManagerTestCase(unittest.TestCase):
    """Test the DNFManager class."""

    def setUp(self):
        self.maxDiff = None
        self.dnf_manager = DNFManager()

    def _get_configuration(self):
        """Get the configuration of the DNF base."""
        return simplify_config(self.dnf_manager._base.get_config())

    def _check_variables(self, **expected_variables):
        """Check values of the expected substitution variables."""
        variables = self.dnf_manager._base.get_vars()

        for name, value in expected_variables.items():
            assert variables.get_value(name) == value

    def _check_base_setup(self):
        """Make sure that the base is set up."""
        # FIXME: Figure this out on the manager level.
        base = self.dnf_manager._base
        assert base

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
        config = self._get_configuration()
        assert config.get_gpgcheck_option is False
        assert config.get_skip_if_unavailable_option is False
        assert config.get_cachedir_option == "/tmp/dnf.cache"
        assert config.get_pluginconfpath_option == "/tmp/dnf.pluginconf"
        assert config.get_logdir_option == "/tmp/"
        assert config.get_installroot_option == "/mnt/sysroot"
        assert config.get_persistdir_option == "/mnt/sysroot/var/lib/dnf"
        assert config.get_reposdir_option == (
            "/etc/yum.repos.d",
            "/etc/anaconda.repos.d"
        )
        self._check_variables(releasever="rawhide")

    @patch("pyanaconda.modules.payloads.payload.dnf.dnf_manager.get_os_release_value")
    def test_set_module_platform_id(self, get_platform_id):
        """Test the configuration of module_platform_id."""
        get_platform_id.return_value = "platform:f32"

        self.dnf_manager.reset_base()
        config = self._get_configuration()

        assert config.get_module_platform_id_option == "platform:f32"

    def test_configure_proxy(self):
        """Test the proxy configuration."""
        config = self._get_configuration()

        self.dnf_manager.configure_proxy("http://user:pass@example.com/proxy")
        assert config.get_proxy_option == "http://example.com:3128"
        assert config.get_proxy_username_option == "user"
        assert config.get_proxy_password_option == "pass"

        self.dnf_manager.configure_proxy("@:/invalid")
        assert config.get_proxy_option == ""
        assert config.get_proxy_username_option == ""
        assert config.get_proxy_password_option == ""

        self.dnf_manager.configure_proxy("http://example.com/proxy")
        assert config.get_proxy_option == "http://example.com:3128"
        assert config.get_proxy_username_option == ""
        assert config.get_proxy_password_option == ""

        self.dnf_manager.configure_proxy(None)
        assert config.get_proxy_option == ""
        assert config.get_proxy_username_option == ""
        assert config.get_proxy_password_option == ""

    def test_configure_base_default(self):
        """Test the default configuration of the DNF base."""
        data = PackagesConfigurationData()
        self.dnf_manager.configure_base(data)
        config = self._get_configuration()

        assert config.get_multilib_policy_option == "best"
        assert config.get_timeout_option == 30
        assert config.get_retries_option == 10
        assert config.get_install_weak_deps_option is True

        assert self.dnf_manager._ignore_broken_packages is False
        assert self.dnf_manager._ignore_missing_packages is False

    def test_configure_base(self):
        """Test the configuration of the DNF base."""
        data = PackagesConfigurationData()
        data.multilib_policy = MULTILIB_POLICY_ALL
        data.timeout = 100
        data.retries = 5
        data.broken_ignored = True
        data.missing_ignored = True
        data.weakdeps_excluded = True

        self.dnf_manager.configure_base(data)
        config = self._get_configuration()

        assert config.get_multilib_policy_option == "all"
        assert config.get_timeout_option == 100
        assert config.get_retries_option == 5
        assert config.get_install_weak_deps_option is False

        assert self.dnf_manager._ignore_broken_packages is True
        assert self.dnf_manager._ignore_missing_packages is True

    @pytest.mark.skip("Dump is unsupported.")
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
        self.dnf_manager._transaction = self._get_transaction()
        size = self.dnf_manager.get_installation_size()
        size = size.round_to_nearest("KiB", ROUND_UP)
        assert size == Size("528 KiB")

    def test_get_download_size(self):
        """Test the get_download_size method."""
        # No transaction.
        size = self.dnf_manager.get_download_size()
        assert size == Size(0)

        # Fake transaction.
        self.dnf_manager._transaction = self._get_transaction()
        size = self.dnf_manager.get_download_size()
        assert size == Size("450 MiB")

    def _get_transaction(self, packages=2):
        """Create a mocked DNF transaction with some packages."""
        tspkgs = []

        for i in range(1, packages+1):
            # Create a package.
            pkg = Mock(spec=libdnf5.rpm.Package)
            pkg.get_download_size.return_value = 1024 * 1024 * 100 * i
            pkg.get_install_size.return_value = 1024 * 100 * i
            pkg.get_files.return_value = ["/file"] * 10 * i

            # Create a transaction package.
            tspkg = Mock(spec=libdnf5.base.TransactionPackage)
            tspkg.get_package.return_value = pkg
            tspkgs.append(tspkg)

        # Create a transaction.
        transaction = Mock(spec=libdnf5.base.Transaction)
        transaction.get_transaction_packages.return_value = tspkgs
        return transaction

    def test_apply_specs(self):
        """Test the apply_specs method."""
        self.dnf_manager.apply_specs(
            include_list=["@g1", "p1"],
            exclude_list=["@g2", "p2"]
        )

        # FIXME: Check the goal.
        assert self.dnf_manager._goal

    def test_resolve_no_selection(self):
        """Test the resolve_selection method with no selection."""
        self._check_base_setup()

        with self.assertLogs(level="INFO") as cm:
            report = self.dnf_manager.resolve_selection()

        expected = "The software selection has been resolved (0 packages selected)."
        assert expected in "\n".join(cm.output)
        assert report.error_messages == []
        assert report.warning_messages == []

    def test_resolve_missing_selection(self):
        """Test the resolve selection method with missing selection."""
        self._check_base_setup()

        self.dnf_manager.apply_specs(
            include_list=["@g1", "p1"],
            exclude_list=["@g2", "p2"]
        )

        report = self.dnf_manager.resolve_selection()
        assert report.error_messages == [
            'No match for argument: p1',
            'No packages to remove for argument: p2',
            'No match for argument: g1',
            'No groups to remove for argument: g2',
        ]
        assert report.warning_messages == []

    @pytest.mark.skip("Not implemented")
    def test_ignore_missing_packages(self):
        """Test the ignore_missing_packages attribute."""

    @pytest.mark.skip("Not implemented")
    def test_ignore_broken_packages(self):
        """Test the ignore_missing_packages attribute."""

    def test_clear_selection(self):
        """Test the clear_selection method."""
        self._check_base_setup()
        self.dnf_manager.resolve_selection()

        g = self.dnf_manager._goal
        t = self.dnf_manager._transaction

        self.dnf_manager.clear_selection()
        assert g is not self.dnf_manager._goal
        assert t is not self.dnf_manager._transaction

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
        # Check base.setup() was called, since it sets some variables.
        self._check_base_setup()
        assert self.dnf_manager.substitute("/$arch") != "/$arch"
        assert self.dnf_manager.substitute("/$basearch") != "/$basearch"
        assert self.dnf_manager.substitute("/$releasever") != "/$releasever"

    def test_configure_substitution(self):
        """Test the configure_substitution function."""
        self.dnf_manager.configure_substitution(release_version="35")
        self._check_variables(releasever="35")

    # For this test, mocked Transaction is needed, but it can't be easily
    # created, because it doesn't have a public constructor, it's supposed
    # to be taken from resolved Goal.
    @pytest.mark.skip("There is no transaction to use")
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
            progress.end(
                payload, libdnf5.repo.DownloadCallbacks_TransferStatus_SUCCESSFUL, "Message!"
            )

        assert progress.downloads == {
            "p1": 100,
            "p2": 100,
            "p3": 100
        }

    # For this test, mocked Transaction is needed, but it can't be easily
    # created, because it doesn't have a public constructor, it's supposed
    # to be taken from resolved Goal.
    @pytest.mark.skip("There is no transaction to use")
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
            progress.end(payload, libdnf5.repo.DownloadCallbacks_TransferStatus_ERROR, "Message!")

        assert progress.downloads == {
            "p1": 25,
            "p2": 25,
            "p3": 25
        }

    @patch.object(DNFManager, '_run_transaction')
    def test_install_packages(self, run_transaction):
        """Test the install_packages method."""
        calls = []

        run_transaction.side_effect = self._install_packages

        self.dnf_manager.install_packages(calls.append)

        assert calls == [
            'Installing p1-1.2-3.x86_64',
            'Configuring p1-1.2-3.x86_64',
            'Installing p2-1.2-3.x86_64',
            'Configuring p2-1.2-3.x86_64',
            'Installing p3-1.2-3.x86_64',
            'Configuring p3-1.2-3.x86_64',
            'Configuring p1-1.2-3.x86_64',
            'Configuring p2-1.2-3.x86_64',
            'Configuring p3-1.2-3.x86_64'
        ]

    def _get_package(self, name, action=libdnf5.transaction.TransactionItemAction_INSTALL):
        """Get a mocked package of the specified name."""
        package = Mock(spec=libdnf5.transaction.Package)
        package.get_name.return_value = name
        package.get_epoch.return_value = "0"
        package.get_release.return_value = "3"
        package.get_arch.return_value = "x86_64"
        package.get_version.return_value = "1.2"
        package.to_string.return_value = name + "-1.2-3.x86_64"
        package.get_action.return_value = action
        return package

    def _install_packages(self, base, transaction, progress):
        """Simulate the installation of packages."""
        packages = list(map(self._get_package, ["p1", "p2", "p3"]))
        ts_total = len(packages)
        for ts_done, package in enumerate(packages):
            progress.install_start(package, ts_total)
            progress.install_progress(package, ts_done, ts_total)
            progress.script_start(package, package.to_string(), libdnf5.rpm.TransactionCallbacks.ScriptType_PRE_INSTALL)
            progress.install_progress(package, ts_done + 1, ts_total)

        for ts_done, package in enumerate(packages):
            progress.script_start(package, package.to_string(), libdnf5.rpm.TransactionCallbacks.ScriptType_POST_TRANSACTION)

        progress.quit("DNF quit")

    @patch.object(DNFManager, '_run_transaction')
    def test_install_packages_failed(self, run_transaction):
        """Test the failed install_packages method."""
        calls = []
        run_transaction.side_effect = self._install_packages_failed

        with pytest.raises(PayloadInstallationError) as cm:
            self.dnf_manager.install_packages(calls.append)

        msg = "An error occurred during the transaction: " \
              "The p1 package couldn't be installed!"

        assert str(cm.value) == msg
        assert calls == []

    def _install_packages_failed(self, base, transaction, progress):
        """Simulate the failed installation of packages."""
        progress.error("The p1 package couldn't be installed!")

    @pytest.mark.skip("Not implemented")
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

class DNFManagerCompsTestCase(unittest.TestCase):
    """Test the comps abstraction of the DNF base."""

    def setUp(self):
        self.maxDiff = None
        self.dnf_manager = DNFManager()

    def _check_base_setup(self):
        """Make sure that the base is set up."""
        # FIXME: Figure this out on the manager level.
        base = self.dnf_manager._base
        assert base

    def test_groups(self):
        """Test the groups property."""
        self._check_base_setup()
        assert self.dnf_manager.groups == []

    def test_get_group_data_error(self):
        """Test the failed get_group_data method."""
        with pytest.raises(UnknownCompsGroupError):
            self.dnf_manager.get_group_data("g1")

    def test_no_default_environment(self):
        """Test the default_environment property with no environments."""
        self._check_base_setup()
        assert self.dnf_manager.default_environment is None

    def test_environments(self):
        """Test the environments property."""
        self._check_base_setup()
        assert self.dnf_manager.environments == []

    def test_get_environment_data_error(self):
        """Test the failed get_environment_data method."""
        with pytest.raises(UnknownCompsEnvironmentError):
            self.dnf_manager.get_environment_data("e1")

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

    def _check_base_setup(self):
        """Make sure that the base is set up."""
        # FIXME: Figure this out on the manager level.
        base = self.dnf_manager._base
        assert base

    def _add_repository(self, repo_id, repo_dir=None, **kwargs):
        """Add the DNF repository with the specified id."""
        data = RepoConfigurationData()
        data.name = repo_id
        self.dnf_manager.add_repository(data)

        if repo_dir:
            # Generate repo data.
            os.makedirs(os.path.join(repo_dir), exist_ok=True)
            subprocess.run(["createrepo_c", "."], cwd=repo_dir)

            # Update the baseurl.
            baseurl = kwargs.get("get_baseurl_option", [])
            baseurl.append("file://" + repo_dir)
            kwargs["get_baseurl_option"] = baseurl

        config = self._get_configuration(repo_id)
        for name, value in kwargs.items():
            setattr(config, name, value)

        return self._get_repository(repo_id)

    def _get_repository(self, repo_id):
        """Get the DNF repository."""
        return self.dnf_manager._get_repository(repo_id)

    def _get_configuration(self, repo_id):
        """Get a configuration of the DNF repository."""
        repo = self._get_repository(repo_id)
        return simplify_config(repo.get_config())

    def test_repositories(self):
        """Test the repositories property."""
        assert self.dnf_manager.repositories == []

        self._add_repository("r1")
        self._add_repository("r2")
        self._add_repository("r3")

        assert self.dnf_manager.repositories == ["r1", "r2", "r3"]

    def test_enabled_repositories(self):
        """Test the enabled_repositories property."""
        assert self.dnf_manager.enabled_repositories == []

        self._add_repository("r1").disable()
        self._add_repository("r2").enable()
        self._add_repository("r3").disable()
        self._add_repository("r4").enable()

        assert self.dnf_manager.enabled_repositories == ["r2", "r4"]

    def test_get_matching_repositories(self):
        """Test the get_matching_repositories method."""
        assert self.dnf_manager.get_matching_repositories("r*") == []

        self._add_repository("r1")
        self._add_repository("r20")
        self._add_repository("r21")
        self._add_repository("r3")

        assert self.dnf_manager.get_matching_repositories("") == []
        assert self.dnf_manager.get_matching_repositories("*1") == ["r1", "r21"]
        assert self.dnf_manager.get_matching_repositories("*2*") == ["r20", "r21"]
        assert self.dnf_manager.get_matching_repositories("r3") == ["r3"]
        assert self.dnf_manager.get_matching_repositories("r4") == []
        assert self.dnf_manager.get_matching_repositories("r*") == ["r1", "r20", "r21", "r3"]

    def test_set_repository_enabled(self):
        """Test the set_repository_enabled function."""
        self._add_repository("r1").disable()

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
        repo = self._get_repository("r1")
        config = self._get_configuration("r1")

        assert repo.get_id() == "r1"
        assert repo.get_name() == ""
        assert repo.is_enabled()

        assert config.get_baseurl_option == ("", )
        assert config.get_proxy_option == ""
        assert config.get_sslverify_option is True
        assert config.get_sslcacert_option == ""
        assert config.get_sslclientcert_option == ""
        assert config.get_sslclientkey_option == ""
        assert config.get_cost_option == 1000
        assert config.get_includepkgs_option == ()
        assert config.get_excludepkgs_option == ()

    def test_add_repository_enabled(self):
        """Test the add_repository method with enabled repo."""
        data = RepoConfigurationData()
        data.name = "r1"
        data.enabled = True

        self.dnf_manager.add_repository(data)
        repo = self._get_repository("r1")
        assert repo.is_enabled() is True

    def test_add_repository_disabled(self):
        """Test the add_repository method with disabled repo."""
        data = RepoConfigurationData()
        data.name = "r1"
        data.enabled = False

        self.dnf_manager.add_repository(data)
        repo = self._get_repository("r1")
        assert repo.is_enabled() is False

    def test_add_repository_baseurl(self):
        """Test the add_repository method with baseurl."""
        data = RepoConfigurationData()
        data.name = "r1"
        data.type = URL_TYPE_BASEURL
        data.url = "http://repo"

        self.dnf_manager.add_repository(data)
        config = self._get_configuration("r1")
        assert config.get_baseurl_option == ("http://repo", )

    def test_add_repository_mirrorlist(self):
        """Test the add_repository method with mirrorlist."""
        data = RepoConfigurationData()
        data.name = "r1"
        data.type = URL_TYPE_MIRRORLIST
        data.url = "http://mirror"

        self.dnf_manager.add_repository(data)
        config = self._get_configuration("r1")
        assert config.get_mirrorlist_option == "http://mirror"

    def test_add_repository_metalink(self):
        """Test the add_repository method with metalink."""
        data = RepoConfigurationData()
        data.name = "r1"
        data.type = URL_TYPE_METALINK
        data.url = "http://metalink"

        self.dnf_manager.add_repository(data)
        config = self._get_configuration("r1")
        assert config.get_metalink_option == "http://metalink"

    def test_add_repository_no_ssl_configuration(self):
        """Test the add_repository method without the ssl configuration."""
        data = RepoConfigurationData()
        data.name = "r1"
        data.ssl_verification_enabled = False

        self.dnf_manager.add_repository(data)
        config = self._get_configuration("r1")
        assert config.get_sslverify_option is False

    def test_add_repository_ssl_configuration(self):
        """Test the add_repository method with the ssl configuration."""
        data = RepoConfigurationData()
        data.name = "r1"
        data.ssl_verification_enabled = True
        data.ssl_configuration.ca_cert_path = "file:///ca-cert"
        data.ssl_configuration.client_cert_path = "file:///client-cert"
        data.ssl_configuration.client_key_path = "file:///client-key"

        self.dnf_manager.add_repository(data)
        config = self._get_configuration("r1")
        assert config.get_sslverify_option is True
        assert config.get_sslcacert_option == "file:///ca-cert"
        assert config.get_sslclientcert_option == "file:///client-cert"
        assert config.get_sslclientkey_option == "file:///client-key"

    def test_add_repository_invalid_proxy(self):
        """Test the add_repository method the invalid proxy configuration."""
        data = RepoConfigurationData()
        data.name = "r1"
        data.proxy = "@:/invalid"

        self.dnf_manager.add_repository(data)
        config = self._get_configuration("r1")
        assert config.get_proxy_option == ""

    def test_add_repository_no_auth_proxy(self):
        """Test the add_repository method the no auth proxy configuration."""
        data = RepoConfigurationData()
        data.name = "r1"
        data.proxy = "http://example.com:1234"

        self.dnf_manager.add_repository(data)
        config = self._get_configuration("r1")
        assert config.get_proxy_option == "http://example.com:1234"

    def test_add_repository_proxy(self):
        """Test the add_repository method with the proxy configuration."""
        data = RepoConfigurationData()
        data.name = "r1"
        data.proxy = "http://user:pass@example.com:1234"

        self.dnf_manager.add_repository(data)
        config = self._get_configuration("r1")
        assert config.get_proxy_option == "http://example.com:1234"
        assert config.get_proxy_username_option == "user"
        assert config.get_proxy_password_option == "pass"

    def test_add_repository_cost(self):
        """Test the add_repository method with a cost."""
        data = RepoConfigurationData()
        data.name = "r1"
        data.cost = 256

        self.dnf_manager.add_repository(data)
        config = self._get_configuration("r1")
        assert config.get_cost_option == 256

    def test_add_repository_packages(self):
        """Test the add_repository method with packages."""
        data = RepoConfigurationData()
        data.name = "r1"
        data.included_packages = ["p1", "p2"]
        data.excluded_packages = ["p3", "p4"]

        self.dnf_manager.add_repository(data)
        config = self._get_configuration("r1")
        assert config.get_includepkgs_option == ("p1", "p2")
        assert config.get_excludepkgs_option == ("p3", "p4")

    @pytest.mark.skip("Not implemented")
    def test_add_repository_replace(self):
        """Test the add_repository method with a replacement."""
        data = RepoConfigurationData()
        data.name = "r1"
        data.url = "http://u1"

        self.dnf_manager.add_repository(data)
        config = self._get_configuration("r1")
        assert config.get_baseurl_option == ("http://u1",)

        data.url = "http://u2"

        self.dnf_manager.add_repository(data)
        config = self._get_configuration("r1")
        assert config.get_baseurl_option == ("http://u2",)

    @pytest.mark.skip("Not implemented")
    def test_remove_repository(self):
        """Test the remove_repository method."""
        assert self.dnf_manager.repositories == []

        self._add_repository("r1")
        self._add_repository("r2")

        assert self.dnf_manager.repositories == ["r1", "r2"]

        self.dnf_manager.remove_repository("r1")
        assert self.dnf_manager.repositories == ["r2"]

        self.dnf_manager.remove_repository("r3")
        assert self.dnf_manager.repositories == ["r2"]

        self.dnf_manager.remove_repository("r2")
        assert self.dnf_manager.repositories == []

    def test_generate_repo_file_baseurl(self):
        """Test the generate_repo_file method with baseurl."""
        data = RepoConfigurationData()
        data.name = "r1"
        data.type = URL_TYPE_BASEURL
        data.url = "http://repo"
        data.proxy = "http://example.com:1234"
        data.cost = 256

        self._check_repo_file_content(
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

        self._check_repo_file_content(
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

        self._check_repo_file_content(
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

    def _check_repo_file_content(self, repo_data, expected_content):
        """Check the generated content of the .repo file."""
        # Generate the content of the .repo file.
        expected_content = dedent(expected_content).strip()
        content = self.dnf_manager.generate_repo_file(repo_data)
        assert content == expected_content

        # FIXME: Try to recreate the generated repository.
        # expected_attrs = expected_content.splitlines(keepends=False)
        # self.dnf_manager.add_repository(repo_data)
        # self._check_repo(repo_data.name, expected_attrs)

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

        # FIXME: Unless we cleared the cache.
        # self.dnf_manager.clear_cache()
        # assert not self.dnf_manager._enabled_system_repositories
        # self.dnf_manager.read_system_repositories()

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

    # def test_load_repository_unknown(self):
    #     """Test the load_repository method with an unknown repo."""
    #     self._check_base_setup()
    #
    #     with pytest.raises(UnknownRepositoryError):
    #         self.dnf_manager.load_repository("r1")
    #
    # def test_load_repository_failed(self):
    #     """Test the load_repository method with a failure."""
    #     self._check_base_setup()
    #     self._add_repository("r1")
    #
    #     with pytest.raises(MetadataError, match="Failed to download metadata"):
    #         self.dnf_manager.load_repository("r1")
    #
    #     repo = self._get_repository("r1")
    #     assert repo.is_enabled() is False
    #
    # def test_load_repository_disabled(self):
    #     """Test the load_repository method with a disabled repo."""
    #     self._check_base_setup()
    #
    #     repo = self._add_repository("r1")
    #     repo.disable()
    #
    #     self.dnf_manager.load_repository("r1")
    #
    #     repo = self._get_repository("r1")
    #     assert repo.is_enabled() is False
    #
    # def test_load_repository(self):
    #     """Test the load_repository method."""
    #     self._check_base_setup()
    #
    #     with TemporaryDirectory() as d:
    #         self._add_repository("r1", repo_dir=d)
    #         self.dnf_manager.load_repository("r1")
    #
    #     repo = self._get_repository("r1")
    #     assert repo.is_enabled() is True
    #
    # def test_load_packages_metadata(self):
    #     """Test the load_packages_metadata method."""
    #     self._check_base_setup()
    #     self.dnf_manager.load_packages_metadata()

    def test_load_no_repomd_hashes(self):
        """Test the load_repomd_hashes method with no repositories."""
        self.dnf_manager.load_repomd_hashes()
        assert self.dnf_manager._md_hashes == {}

    @pytest.mark.skip("Not implemented")
    def test_load_one_repomd_hash(self):
        """Test the load_repomd_hashes method with one repository."""
        with TemporaryDirectory() as d:
            self._add_repository("r1", repo_dir=d)
            self.dnf_manager.load_repomd_hashes()
            assert self.dnf_manager._md_hashes == {
                'r1': b"\x90\xa0\xb7\xce\xc2H\x85#\xa3\xfci"
                      b"\x9e+\xf4\xe2\x19D\xbc\x9b'\xeb\xb7"
                      b"\x90\x1d\xcey\xb3\xd4p\xc3\x1d\xfb",
            }

    @pytest.mark.skip("Not implemented")
    def test_load_repomd_hashes(self):
        """Test the load_repomd_hashes method."""
        with TemporaryDirectory() as d:
            self._add_repository(
                repo_id="r1",
                get_baseurl_option=[
                    "file://nonexistent/1",
                    "file://nonexistent/2",
                    "file://nonexistent/3",
                ],
                repo_dir=d + "/r1",
            )
            self._add_repository(
                repo_id="r2",
                get_baseurl_option=[
                    "file://nonexistent/1",
                    "file://nonexistent/2",
                    "file://nonexistent/3",
                ]
            )
            self._add_repository(
                repo_id="r3",
                get_metalink_option="file://metalink"
            )
            self._add_repository(
                repo_id="r4",
                get_mirrorlist_option="file://mirrorlist"
            )
            self.dnf_manager.load_repomd_hashes()
            assert self.dnf_manager._md_hashes == {
                'r1': b"\x90\xa0\xb7\xce\xc2H\x85#\xa3\xfci"
                      b"\x9e+\xf4\xe2\x19D\xbc\x9b'\xeb\xb7"
                      b"\x90\x1d\xcey\xb3\xd4p\xc3\x1d\xfb",
                'r2': None,
                'r3': None,
                'r4': None,
            }

    @pytest.mark.skip("Not implemented")
    def test_verify_repomd_hashes(self):
        """Test the verify_repomd_hashes method."""
        with TemporaryDirectory() as d:
            # Test no repository.
            assert self.dnf_manager.verify_repomd_hashes() is False

            # Create a repository.
            self._add_repository(repo_id="r1", repo_dir=d)

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
