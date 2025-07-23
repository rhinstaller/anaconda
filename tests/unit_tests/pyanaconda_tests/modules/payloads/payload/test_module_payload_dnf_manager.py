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
from unittest.mock import Mock, call, patch

import libdnf5
import pytest
from blivet.size import ROUND_UP, Size
from dasbus.structure import compare_data

from pyanaconda.core.constants import (
    MULTILIB_POLICY_ALL,
    URL_TYPE_BASEURL,
    URL_TYPE_METALINK,
    URL_TYPE_MIRRORLIST,
)
from pyanaconda.modules.common.errors.installation import PayloadInstallationError
from pyanaconda.modules.common.errors.payload import (
    UnknownCompsEnvironmentError,
    UnknownCompsGroupError,
    UnknownRepositoryError,
)
from pyanaconda.modules.common.structures.comps import CompsEnvironmentData, CompsGroupData
from pyanaconda.modules.common.structures.packages import PackagesConfigurationData
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.payloads.payload.dnf.dnf_manager import (
    DNFManager,
    MetadataError,
)


class DNF5TestCase(unittest.TestCase):
    """Test the DNF5 library."""

    def test_runtime_error(self):
        base = libdnf5.base.Base()
        query = libdnf5.repo.RepoQuery(base)

        with pytest.raises(libdnf5.exception.Error):
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

        with pytest.raises(libdnf5.exception.UserAssertionError):
            goal.resolve()

    def test_environment_query(self):
        base = libdnf5.base.Base()
        base.setup()
        libdnf5.comps.EnvironmentQuery(base)

    def test_group_query(self):
        base = libdnf5.base.Base()
        base.setup()
        libdnf5.comps.GroupQuery(base)

    def test_disable_failed_repository(self):
        base = libdnf5.base.Base()
        sack = base.get_repo_sack()
        sack.create_repo("r1")
        base.setup()

        # First check that load_repos fails (because of missing baseurl of the r1 repo)
        with pytest.raises(libdnf5.exception.Error):
            sack.load_repos()
        # When the repo is disabled, load_repos succeeds
        repo = self._get_repo(base, "r1")
        repo.disable()
        sack.load_repos()

    def _get_repo(self, base, repo_id):
        repos = libdnf5.repo.RepoQuery(base)
        repos.filter_id(repo_id)
        weak_ref = repos.get()
        return weak_ref.get()

    def test_config(self):
        """Test accessing the dnf config."""
        base = libdnf5.base.Base()
        config = base.get_config()

        config.installroot = "/my/install/root"
        assert config.installroot == "/my/install/root"


class DNFManagerTestCase(unittest.TestCase):
    """Test the DNFManager class."""

    def setUp(self):
        self.maxDiff = None
        self.dnf_manager = DNFManager()
        self.download_progress = None

    def _get_configuration(self):
        """Get the configuration of the DNF base."""
        return self.dnf_manager._base.get_config()

    def _check_variables(self, **expected_variables):
        """Check values of the expected substitution variables."""
        variables = self.dnf_manager._base.get_vars()

        for name, value in expected_variables.items():
            assert variables.get_value(name) == value

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
        assert config.pkg_gpgcheck is False
        assert config.skip_if_unavailable is False
        assert config.cachedir == "/tmp/dnf.cache"
        assert config.pluginconfpath == "/tmp/dnf.pluginconf"
        assert config.logdir == "/tmp/"
        assert config.installroot == "/mnt/sysroot"
        assert config.persistdir == "/mnt/sysroot/var/lib/dnf"
        assert config.reposdir == (
            "/etc/yum.repos.d",
            "/etc/anaconda.repos.d"
        )

    def test_configure_proxy(self):
        """Test the proxy configuration."""
        config = self._get_configuration()

        self.dnf_manager.configure_proxy("http://user:pass@example.com/proxy")
        assert config.proxy == "http://example.com:3128"
        assert config.proxy_username == "user"
        assert config.proxy_password == "pass"

        self.dnf_manager.configure_proxy("@:/invalid")
        assert config.proxy == ""
        assert config.proxy_username == ""
        assert config.proxy_password == ""

        self.dnf_manager.configure_proxy("http://example.com/proxy")
        assert config.proxy == "http://example.com:3128"
        assert config.proxy_username == ""
        assert config.proxy_password == ""

        self.dnf_manager.configure_proxy(None)
        assert config.proxy == ""
        assert config.proxy_username == ""
        assert config.proxy_password == ""

    def test_configure_base_default(self):
        """Test the default configuration of the DNF base."""
        data = PackagesConfigurationData()
        self.dnf_manager.configure_base(data)
        config = self._get_configuration()

        assert config.multilib_policy == "best"
        assert config.timeout == 30
        assert config.retries == 10
        assert config.install_weak_deps is True

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

        assert config.multilib_policy == "all"
        assert config.timeout == 100
        assert config.retries == 5
        assert config.install_weak_deps is False

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

    @patch("libdnf5.base.Goal.add_install")
    def test_apply_specs(self, add_install):
        """Test the apply_specs method."""
        self.dnf_manager.setup_base()

        self.dnf_manager.apply_specs(
            include_list=["@g1", "p1"],
            exclude_list=["@g2", "p2"]
        )

        add_install.assert_called()

    def test_resolve_no_selection(self):
        """Test the resolve_selection method with no selection."""
        self.dnf_manager.setup_base()

        with self.assertLogs(level="INFO") as cm:
            report = self.dnf_manager.resolve_selection()

        expected = "The software selection has been resolved (0 packages selected)."
        assert expected in "\n".join(cm.output)
        assert report.error_messages == []
        assert report.warning_messages == []

    def test_resolve_missing_selection(self):
        """Test the resolve selection method with missing selection."""
        self.dnf_manager.setup_base()

        self.dnf_manager.apply_specs(
            include_list=["@g1", "p1"],
            exclude_list=["@g2", "p2"]
        )

        report = self.dnf_manager.resolve_selection()
        assert report.error_messages == []
        assert report.warning_messages == [
            'No match for argument: p1',
            'No match for argument: g1',
        ]

    def test_ignore_missing_packages(self):
        """Test the ignore_missing_packages attribute."""
        data = PackagesConfigurationData()
        data.missing_ignored = True
        self.dnf_manager.configure_base(data)
        self.dnf_manager.setup_base()

        self.dnf_manager.apply_specs(
            include_list=["@g1", "p1"],
            exclude_list=["@g2", "p2"]
        )

        report = self.dnf_manager.resolve_selection()

        assert report.error_messages == []
        assert report.warning_messages == []

    @pytest.mark.skip("Not implemented")
    def test_ignore_broken_packages(self):
        """Test the ignore_broken_packages attribute."""

    @patch("libdnf5.base.Transaction.get_resolve_logs_as_strings")
    @patch("libdnf5.base.Transaction.get_problems")
    def test_resolve_selection_error(self, get_problems, get_resolve_logs):
        """Test the resolve selection method when there are resolvement errors."""
        self.dnf_manager.setup_base()

        get_problems.return_value = libdnf5.base.GoalProblem_MODULE_SOLVER_ERROR
        get_resolve_logs.return_value = ["Solver error!"]

        report = self.dnf_manager.resolve_selection()
        assert report.error_messages == [
            "The following software marked for installation has errors.\n"
            "This is likely caused by an error with your installation source.\n\n",
            "Solver error!",
        ]
        assert report.warning_messages == []

    def test_clear_selection(self):
        """Test the clear_selection method."""
        self.dnf_manager.setup_base()

        self.dnf_manager.resolve_selection()

        g = self.dnf_manager._goal
        t = self.dnf_manager._transaction

        self.dnf_manager.clear_selection()
        assert g is not self.dnf_manager._goal
        assert t is not self.dnf_manager._transaction

    def test_substitute(self):
        """Test the substitute method."""
        self.dnf_manager.setup_base()

        # No variables.
        assert self.dnf_manager.substitute(None) == ""
        assert self.dnf_manager.substitute("") == ""
        assert self.dnf_manager.substitute("/") == "/"
        assert self.dnf_manager.substitute("/text") == "/text"

        # Unknown variables.
        assert self.dnf_manager.substitute("/$unknown") == "/$unknown"

        # Supported variables.
        assert self.dnf_manager.substitute("/$arch") != "/$arch"
        assert self.dnf_manager.substitute("/$basearch") != "/$basearch"
        assert self.dnf_manager.substitute("/$releasever") != "/$releasever"

    def test_configure_substitution(self):
        """Test the configure_substitution function."""
        self.dnf_manager.configure_substitution(release_version="35")
        self._check_variables(releasever="35")

    @patch.object(DNFManager, '_set_download_callbacks')
    @patch("libdnf5.repo.PackageDownloader.download")
    @patch("libdnf5.repo.PackageDownloader.add")
    def test_download_packages(self, add_package, download_packages, set_download_callbacks):
        """Test the download_packages method."""
        self.dnf_manager.setup_base()

        tspkg = Mock(spec=libdnf5.base.TransactionPackage)
        tspkg.get_package.return_value = Mock(spec=libdnf5.rpm.Package)
        tspkg.get_action.return_value = libdnf5.transaction.TransactionItemAction_INSTALL
        self.dnf_manager._transaction = Mock(spec=libdnf5.base.Transaction)
        self.dnf_manager._transaction.get_transaction_packages.return_value = [tspkg]

        callback = Mock()
        add_package.return_value = None
        download_packages.side_effect = self._download_packages
        # The DNFManager._set_download_callbacks method needs to be mocked, because otherwise
        # we wouldn't have access to the DownloadProgress.last_time attribute.
        set_download_callbacks.side_effect = self._set_download_callbacks

        self.dnf_manager.download_packages(callback)

        callback.assert_has_calls([
            call('Downloading 1 RPMs, 0 B / 100 B (0%) done.'),
            call('Downloading 2 RPMs, 0 B / 200 B (0%) done.'),
            call('Downloading 3 RPMs, 0 B / 300 B (0%) done.'),
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

    def _download_packages(self):
        """Simulate the download of packages."""
        download_size = 100

        for i, name in enumerate(["p1", "p2", "p3"]):
            self.download_progress.last_time = 0
            self.download_progress.add_new_download(i, name, download_size)

        for i in range(3):
            self.download_progress.last_time = 0
            self.download_progress.progress(i, download_size, 25)
            self.download_progress.last_time += 3600
            self.download_progress.progress(i, download_size, 50)
            self.download_progress.last_time = 0
            self.download_progress.progress(i, download_size, 75)
            self.download_progress.last_time = 0
            self.download_progress.progress(i, download_size, 100)
            self.download_progress.end(i, libdnf5.repo.DownloadCallbacks.TransferStatus_SUCCESSFUL, "Message!")

        assert self.download_progress.downloads == {
            "p1": 100,
            "p2": 100,
            "p3": 100
        }

    def _set_download_callbacks(self, callbacks):
        """Mock the DNFManager._set_download_callbacks, so that we can store the
        DownloadProgress and can set DownloadProgress.last_time attribute later.
        """
        self.dnf_manager._base.set_download_callbacks(
            libdnf5.repo.DownloadCallbacksUniquePtr(callbacks)
        )
        self.download_progress = callbacks

    @patch.object(DNFManager, '_set_download_callbacks')
    @patch("libdnf5.repo.PackageDownloader.download")
    @patch("libdnf5.repo.PackageDownloader.add")
    def test_download_packages_failed(self, add_package, download_packages, set_download_callbacks):
        """Test the download_packages method with failed packages."""
        self.dnf_manager.setup_base()

        tspkg = Mock(spec=libdnf5.base.TransactionPackage)
        tspkg.get_package.return_value = Mock(spec=libdnf5.rpm.Package)
        tspkg.get_action.return_value = libdnf5.transaction.TransactionItemAction_INSTALL
        self.dnf_manager._transaction = Mock(spec=libdnf5.base.Transaction)
        self.dnf_manager._transaction.get_transaction_packages.return_value = [tspkg]

        callback = Mock()
        add_package.return_value = None
        download_packages.side_effect = self._download_packages_failed
        # The DNFManager._set_download_callbacks method needs to be mocked, because otherwise
        # we wouldn't have access to the DownloadProgress.last_time attribute.
        set_download_callbacks.side_effect = self._set_download_callbacks

        self.dnf_manager.download_packages(callback)

        callback.assert_has_calls([
            call('Downloading 1 RPMs, 0 B / 100 B (0%) done.'),
            call('Downloading 2 RPMs, 0 B / 200 B (0%) done.'),
            call('Downloading 3 RPMs, 0 B / 300 B (0%) done.'),
            call('Downloading 3 RPMs, 25 B / 300 B (8%) done.'),
            call('Downloading 3 RPMs, 50 B / 300 B (16%) done.'),
            call('Downloading 3 RPMs, 75 B / 300 B (25%) done.'),
        ])

    def _download_packages_failed(self):
        """Simulate the failed download of packages."""
        download_size = 100

        for i, name in enumerate(["p1", "p2", "p3"]):
            self.download_progress.last_time = 0
            self.download_progress.add_new_download(i, name, download_size)

        for i in range(3):
            self.download_progress.last_time = 0
            self.download_progress.progress(i, download_size, 25)
            self.download_progress.last_time = 0
            self.download_progress.end(i, libdnf5.repo.DownloadCallbacks.TransferStatus_ERROR, "Message!")

        assert self.download_progress.downloads == {
            "p1": 25,
            "p2": 25,
            "p3": 25
        }

    @patch.object(DNFManager, '_run_transaction')
    def test_install_packages(self, run_transaction):
        """Test the install_packages method."""
        self.dnf_manager.setup_base()

        calls = []

        run_transaction.side_effect = self._install_packages

        self.dnf_manager.install_packages(calls.append)

        assert calls == [
            'Installing p1.x86_64 (1/3)',
            'Configuring p1.x86_64',
            'Installing p2.x86_64 (2/3)',
            'Configuring p2.x86_64',
            'Installing p3.x86_64 (3/3)',
            'Configuring p3.x86_64',
            'Configuring p1.x86_64',
            'Configuring p2.x86_64',
            'Configuring p3.x86_64'
        ]

    def _get_transaction_item(self, name, action=libdnf5.transaction.TransactionItemAction_INSTALL):
        """Get a mocked package of the specified name."""
        package = Mock(spec=libdnf5.transaction.Package)
        package.get_name.return_value = name
        package.get_epoch.return_value = "0"
        package.get_release.return_value = "3"
        package.get_arch.return_value = "x86_64"
        package.get_version.return_value = "1.2"
        package.to_string.return_value = name + "-1.2-3.x86_64"
        package.get_action.return_value = action

        nevra = Mock(spec=libdnf5.rpm.Nevra)
        nevra.get_name.return_value = name
        nevra.get_arch.return_value = "x86_64"

        item = Mock(spec=libdnf5.base.TransactionPackage)
        item.get_package.return_value = package
        item.nevra = nevra
        item.get_action.return_value = action

        return item

    def _install_packages(self, base, transaction, progress):
        """Simulate the installation of packages."""
        try:
            transaction_items = list(map(self._get_transaction_item, ["p1", "p2", "p3"]))
            ts_total = len(transaction_items)
            progress.before_begin(ts_total)
            for item in transaction_items:
                progress.install_start(item, 0)
                progress.script_start(
                    item,
                    item.nevra,
                    libdnf5.rpm.TransactionCallbacks.ScriptType_PRE_INSTALL
                )

            for item in transaction_items:
                progress.script_start(
                    item,
                    item.nevra,
                    libdnf5.rpm.TransactionCallbacks.ScriptType_POST_TRANSACTION
                )
        finally:
            # The quit must be called even if there is an error, otherwise the process never quits.
            progress.quit("DNF quit")

    @patch.object(DNFManager, '_run_transaction')
    def test_install_packages_failed(self, run_transaction):
        """Test the failed install_packages method."""
        self.dnf_manager.setup_base()

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

    def test_install_packages_dnf_ts_item_ok(self):
        """Test install_packages method failing on transaction environment error."""
        env = Mock(spec=libdnf5.base.TransactionEnvironment)
        env.get_state.return_value = libdnf5.transaction.TransactionItemState_OK
        grp = Mock(spec=libdnf5.base.TransactionGroup)
        grp.get_state.return_value = libdnf5.transaction.TransactionItemState_OK
        pkg = Mock(spec=libdnf5.base.TransactionPackage)
        pkg.get_state.return_value = libdnf5.transaction.TransactionItemState_OK

        self.dnf_manager._transaction = Mock(spec=libdnf5.base.Transaction)
        self.dnf_manager._transaction.get_transaction_environments.return_value = [env]
        self.dnf_manager._transaction.get_transaction_groups.return_value = [grp]
        self.dnf_manager._transaction.get_transaction_packages.return_value = [pkg]

        calls = []

        with pytest.raises(PayloadInstallationError) as cm:
            self.dnf_manager.install_packages(calls.append)

        msg = "An error occurred during the transaction: " \
              "The transaction process has ended with errors."

        assert str(cm.value) == msg
        assert calls == []

    def test_install_packages_dnf_ts_item_error_environment(self):
        """Test install_packages method failing on transaction environment error."""
        env = Mock(spec=libdnf5.base.TransactionEnvironment)
        env.get_state.return_value = libdnf5.transaction.TransactionItemState_ERROR
        env2 = Mock(spec=libdnf5.base.TransactionEnvironment)
        env2.get_state.return_value = libdnf5.transaction.TransactionItemState_OK
        grp = Mock(spec=libdnf5.base.TransactionGroup)
        grp.get_state.return_value = libdnf5.transaction.TransactionItemState_OK
        pkg = Mock(spec=libdnf5.base.TransactionPackage)
        pkg.get_state.return_value = libdnf5.transaction.TransactionItemState_OK

        self.dnf_manager._transaction = Mock(spec=libdnf5.base.Transaction)
        self.dnf_manager._transaction.get_transaction_environments.return_value = [env, env2]
        self.dnf_manager._transaction.get_transaction_groups.return_value = [grp]
        self.dnf_manager._transaction.get_transaction_packages.return_value = [pkg]

        calls = []

        with pytest.raises(PayloadInstallationError) as cm:
            self.dnf_manager.install_packages(calls.append)

        msg = "An error occurred during the transaction: " \
              "The transaction process has ended with errors."

        assert str(cm.value) == msg
        assert calls == []

    def test_install_packages_dnf_ts_item_error_group(self):
        """Test install_packages method failing on transaction group error."""
        env = Mock(spec=libdnf5.base.TransactionEnvironment)
        env.get_state.return_value = libdnf5.transaction.TransactionItemState_OK
        grp = Mock(spec=libdnf5.base.TransactionGroup)
        grp.get_state.return_value = libdnf5.transaction.TransactionItemState_ERROR
        grp2 = Mock(spec=libdnf5.base.TransactionEnvironment)
        grp2.get_state.return_value = libdnf5.transaction.TransactionItemState_OK
        pkg = Mock(spec=libdnf5.base.TransactionPackage)
        pkg.get_state.return_value = libdnf5.transaction.TransactionItemState_OK

        self.dnf_manager._transaction = Mock(spec=libdnf5.base.Transaction)
        self.dnf_manager._transaction.get_transaction_environments.return_value = [env]
        self.dnf_manager._transaction.get_transaction_groups.return_value = [grp, grp2]
        self.dnf_manager._transaction.get_transaction_packages.return_value = [pkg]

        calls = []

        with pytest.raises(PayloadInstallationError) as cm:
            self.dnf_manager.install_packages(calls.append)

        msg = "An error occurred during the transaction: " \
              "The transaction process has ended with errors."

        assert str(cm.value) == msg
        assert calls == []

    def test_install_packages_dnf_ts_item_error_package(self):
        """Test install_packages method failing on transaction package error."""
        env = Mock(spec=libdnf5.base.TransactionEnvironment)
        env.get_state.return_value = libdnf5.transaction.TransactionItemState_OK
        grp = Mock(spec=libdnf5.base.TransactionGroup)
        grp.get_state.return_value = libdnf5.transaction.TransactionItemState_OK
        pkg = Mock(spec=libdnf5.base.TransactionPackage)
        pkg.get_state.return_value = libdnf5.transaction.TransactionItemState_ERROR
        pkg2 = Mock(spec=libdnf5.base.TransactionEnvironment)
        pkg2.get_state.return_value = libdnf5.transaction.TransactionItemState_OK

        self.dnf_manager._transaction = Mock(spec=libdnf5.base.Transaction)
        self.dnf_manager._transaction.get_transaction_environments.return_value = [env]
        self.dnf_manager._transaction.get_transaction_groups.return_value = [grp]
        self.dnf_manager._transaction.get_transaction_packages.return_value = [pkg, pkg2]

        calls = []

        with pytest.raises(PayloadInstallationError) as cm:
            self.dnf_manager.install_packages(calls.append)

        msg = "An error occurred during the transaction: " \
              "The transaction process has ended with errors."

        assert str(cm.value) == msg
        assert calls == []

    def test_install_packages_quit(self):
        """Test the terminated install_packages method."""
        self.dnf_manager._transaction = Mock(spec=libdnf5.base.Transaction)
        self.dnf_manager._transaction.run.side_effect = self._transaction_quit

        calls = []

        with pytest.raises(PayloadInstallationError) as cm:
            self.dnf_manager.install_packages(calls.append)

        msg = "An error occurred during the transaction: " \
              "The transaction process has ended abruptly: " \
              "Something went wrong with the p1 package!"

        assert msg in str(cm.value)
        assert calls == []

    def _transaction_quit(self):
        """Simulate the terminated installation of packages."""
        raise RuntimeError("Something went wrong with the p1 package!")

    def test_set_download_location(self):
        """Test the set_download_location method."""
        self.dnf_manager.set_download_location("/my/download/location")
        assert self._get_configuration().destdir == "/my/download/location"

    def test_download_location(self):
        """Test the download_location property."""
        assert self.dnf_manager.download_location is None

        self.dnf_manager.set_download_location("/my/location")
        assert self.dnf_manager.download_location == "/my/location"

        self.dnf_manager.reset_base()
        assert self.dnf_manager.download_location is None

    def test_is_package_available(self):
        """Test the is_package_available method."""
        self.dnf_manager.setup_base()

        # No metadata.
        with self.assertLogs(level="WARNING") as cm:
            assert self.dnf_manager.is_package_available("kernel") is False

        msg = "There is no metadata about packages!"
        assert any(map(lambda x: msg in x, cm.output))

        # No package.
        self.dnf_manager._repositories_loaded = True
        assert self.dnf_manager.is_package_available("kernel") is False

    @patch("libdnf5.rpm.PackageQuery.empty")
    def test_is_package_available_query_empty(self, package_query_empty):
        """Test the is_package_available method."""
        self.dnf_manager.setup_base()
        self.dnf_manager._repositories_loaded = True

        package_query_empty.return_value = False

        assert self.dnf_manager.is_package_available("kernel") is True

    def _query_next(self):
        return None

    class MockPackageQuery():
        def __init__(self, base):
            self.items = []
            for name in ["langpacks-cs", "langpacks-core-cs", "langpacks-core-font-cs"]:
                package = Mock(spec=libdnf5.rpm.Package)
                package.get_name.return_value = name
                self.items.append(package)

        def filter_name(self, pattern, cmp=None):
            pass

        def filter_available(self):
            pass

        def __iter__(self):
            return (i for i in self.items)

        def __next__(self):
            return next(self.items)

    @patch("libdnf5.rpm.PackageQuery")
    def test_match_available_packages(self, query):
        """Test the match_available_packages method"""
        self.dnf_manager.setup_base()

        # No metadata.
        with self.assertLogs(level="WARNING") as cm:
            assert self.dnf_manager.match_available_packages("langpacks-*") == []

        msg = "There is no metadata about packages!"
        assert any(map(lambda x: msg in x, cm.output))

        # No packages.
        self.dnf_manager._repositories_loaded = True
        assert self.dnf_manager.match_available_packages("langpacks-*") == []

        # With packages
        query.side_effect = self.MockPackageQuery
        assert self.dnf_manager.match_available_packages("langpacks-*") == [
            "langpacks-cs",
            "langpacks-core-cs",
            "langpacks-core-font-cs"
        ]


class DNFManagerCompsTestCase(unittest.TestCase):
    """Test the comps abstraction of the DNF base."""

    def setUp(self):
        self.maxDiff = None
        self.dnf_manager = DNFManager()
        self.dnf_manager.setup_base()

    def _group(self, group_id, visible=True, default=False):
        """Add a mocked group with the specified id."""
        group = Mock(spec=libdnf5.comps.Group)
        group.get_groupid.return_value = group_id
        group.get_name.return_value = "The '{}' group".format(group_id)
        group.get_description.return_value = "This is the '{}' group.".format(group_id)
        group.get_translated_name.return_value = "The '{}' group".format(group_id)
        group.get_translated_description.return_value = "This is the '{}' group.".format(group_id)
        group.get_order.return_value = "1"
        group.get_order_int.return_value = 1
        group.get_uservisible.return_value = visible
        group.get_default.return_value = default
        #group.get_packages.return_value = []
        #group.get_packages_of_type.return_value = []
        #group.get_repos.return_value = set()

        return group

    def _environment(self, env_id, optional=()):
        """Add a mocked environment with the specified id."""
        environment = Mock(spec=libdnf5.comps.Environment)
        environment.get_environmentid.return_value = env_id
        environment.get_name.return_value = "The '{}' environment".format(env_id)
        environment.get_description.return_value = "This is the '{}' environment.".format(env_id)
        environment.get_translated_name.return_value = "The '{}' environment".format(env_id)
        environment.get_translated_description.return_value = "This is the '{}' environment.".format(env_id)
        environment.get_optional_groups.return_value = list(optional)
        environment.get_order.return_value = "1"
        environment.get_order_int.return_value = 1

        return environment

    def test_groups(self):
        """Test the groups property."""
        assert self.dnf_manager.groups == []

        # Replace the DNFManager._query_groups which store the GroupQuery with mocked groups.
        self.dnf_manager._query_groups = [
            self._group("g1"),
            self._group("g2"),
            self._group("g3")
        ]
        self.dnf_manager._repositories_loaded = True

        assert self.dnf_manager.groups == ["g1", "g2", "g3"]

    def test_resolve_group(self):
        """Test the resolve_group method."""
        assert self.dnf_manager.resolve_group("") is None
        assert self.dnf_manager.resolve_group("g1") is None

        # Replace the DNFManager._query_groups which store the GroupQuery with mocked groups.
        self.dnf_manager._query_groups = [self._group("g1")]
        self.dnf_manager._repositories_loaded = True

        assert self.dnf_manager.resolve_group("g1") == "g1"
        assert self.dnf_manager.resolve_group("g2") is None

    def test_get_group_data_error(self):
        """Test the failed get_group_data method."""
        with pytest.raises(UnknownCompsGroupError):
            self.dnf_manager.get_group_data("g1")

    def test_get_group_data(self):
        """Test the get_group_data method."""
        # Replace the DNFManager._query_groups which store the GroupQuery with mocked groups.
        self.dnf_manager._query_groups = [
            self._group("g1")
        ]
        self.dnf_manager._repositories_loaded = True

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
        # Replace the DNFManager._query_environments which store the EnvironmentQuery
        # with mocked environments.
        self.dnf_manager._query_environments = [
            self._environment("e1"),
            self._environment("e2"),
            self._environment("e3")
        ]
        self.dnf_manager._repositories_loaded = True

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

        # Replace the DNFManager._query_environments which store the EnvironmentQuery
        # with mocked environments.
        self.dnf_manager._query_environments = [
            self._environment("e1"),
            self._environment("e2"),
            self._environment("e3")
        ]
        self.dnf_manager._repositories_loaded = True

        assert self.dnf_manager.environments == ["e1", "e2", "e3"]

    def test_resolve_environment(self):
        """Test the resolve_environment method."""
        assert self.dnf_manager.resolve_environment("") is None
        assert self.dnf_manager.resolve_environment("e1") is None

        # Replace the DNFManager._query_environments which store the EnvironmentQuery
        # with mocked environments.
        self.dnf_manager._query_environments = [
            self._environment("e1")
        ]
        self.dnf_manager._repositories_loaded = True

        assert self.dnf_manager.resolve_environment("e1") == "e1"
        assert self.dnf_manager.resolve_environment("e2") is None

    def test_get_environment_data_error(self):
        """Test the failed get_environment_data method."""
        with pytest.raises(UnknownCompsEnvironmentError):
            self.dnf_manager.get_environment_data("e1")

    def test_get_environment_data(self):
        """Test the get_environment_data method."""
        # Replace the DNFManager._query_environments which store the EnvironmentQuery
        # with mocked environments.
        self.dnf_manager._query_environments = [
            self._environment("e1")
        ]
        self.dnf_manager._repositories_loaded = True

        expected = CompsEnvironmentData()
        expected.id = "e1"
        expected.name = "The 'e1' environment"
        expected.description = "This is the 'e1' environment."

        data = self.dnf_manager.get_environment_data("e1")
        assert isinstance(data, CompsEnvironmentData)
        assert compare_data(data, expected)

    def test_get_environment_data_visible_groups(self):
        """Test the get_environment_data method with visible groups."""
        # Replace the DNFManager._query_environments and DNFManager._query_groups
        # with mocked environments and groups.
        self.dnf_manager._query_groups = [
            self._group("g1"),
            self._group("g2", visible=False),
            self._group("g3"),
            self._group("g4", visible=False)
        ]
        self.dnf_manager._query_environments = [
            self._environment("e1")
        ]
        self.dnf_manager._repositories_loaded = True

        data = self.dnf_manager.get_environment_data("e1")
        assert data.visible_groups == ["g1", "g3"]

    def test_get_environment_data_optional_groups(self):
        """Test the get_environment_data method with optional groups."""
        # Replace the DNFManager._query_environments and DNFManager._query_groups
        # with mocked environments and groups.
        self.dnf_manager._query_groups = [
            self._group("g1"),
            self._group("g2"),
            self._group("g3"),
            self._group("g4")
        ]
        self.dnf_manager._query_environments = [
            self._environment("e1", optional=["g1", "g3"])
        ]
        self.dnf_manager._repositories_loaded = True

        data = self.dnf_manager.get_environment_data("e1")
        assert data.optional_groups == ["g1", "g3"]

    def test_get_environment_data_default_groups(self):
        """Test the get_environment_data method with default groups."""
        # Replace the DNFManager._query_environments and DNFManager._query_groups
        # with mocked environments and groups.
        self.dnf_manager._query_groups = [
            self._group("g1", default=True),
            self._group("g2"),
            self._group("g3", default=True),
            self._group("g4")
        ]
        self.dnf_manager._query_environments = [
            self._environment("e1", optional=["g1", "g2", "g3"])
        ]
        self.dnf_manager._repositories_loaded = True

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
        self.dnf_manager.setup_base()

    def _add_repository(self, repo_id, repo_dir=None, **kwargs):
        """Add the DNF repository with the specified id."""
        data = RepoConfigurationData()
        data.name = repo_id
        self.dnf_manager.add_repository(data)

        if repo_dir:
            # Generate repo data.
            os.makedirs(os.path.join(repo_dir), exist_ok=True)
            subprocess.run(["createrepo_c", "."], cwd=repo_dir, check=True)

            # Update the baseurl.
            baseurl = kwargs.get("baseurl", [])
            baseurl.append("file://" + repo_dir)
            kwargs["baseurl"] = baseurl

        config = self._get_configuration(repo_id)
        for name, value in kwargs.items():
            setattr(config, name, value)

        return self._get_repository(repo_id)

    def _get_repository(self, repo_id):
        """Get the DNF repository."""
        return self.dnf_manager._get_repository(repo_id)

    def _get_configuration(self, repo_id):
        """Get a configuration of the DNF repository."""
        return self._get_repository(repo_id).get_config()

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

        assert config.baseurl == ("", )
        assert config.proxy == ""
        assert config.sslverify is True
        assert config.sslcacert == ""
        assert config.sslclientcert == ""
        assert config.sslclientkey == ""
        assert config.cost == 1000
        assert config.includepkgs == ()
        assert config.excludepkgs == ()

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
        assert config.baseurl == ("http://repo", )

    def test_add_repository_mirrorlist(self):
        """Test the add_repository method with mirrorlist."""
        data = RepoConfigurationData()
        data.name = "r1"
        data.type = URL_TYPE_MIRRORLIST
        data.url = "http://mirror"

        self.dnf_manager.add_repository(data)
        config = self._get_configuration("r1")
        assert config.mirrorlist == "http://mirror"

    def test_add_repository_metalink(self):
        """Test the add_repository method with metalink."""
        data = RepoConfigurationData()
        data.name = "r1"
        data.type = URL_TYPE_METALINK
        data.url = "http://metalink"

        self.dnf_manager.add_repository(data)
        config = self._get_configuration("r1")
        assert config.metalink == "http://metalink"

    def test_add_repository_no_ssl_configuration(self):
        """Test the add_repository method without the ssl configuration."""
        data = RepoConfigurationData()
        data.name = "r1"
        data.ssl_verification_enabled = False

        self.dnf_manager.add_repository(data)
        config = self._get_configuration("r1")
        assert config.sslverify is False

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
        assert config.sslverify is True
        assert config.sslcacert == "file:///ca-cert"
        assert config.sslclientcert == "file:///client-cert"
        assert config.sslclientkey == "file:///client-key"

    def test_add_repository_invalid_proxy(self):
        """Test the add_repository method the invalid proxy configuration."""
        data = RepoConfigurationData()
        data.name = "r1"
        data.proxy = "@:/invalid"

        self.dnf_manager.add_repository(data)
        config = self._get_configuration("r1")
        assert config.proxy == ""

    def test_add_repository_no_auth_proxy(self):
        """Test the add_repository method the no auth proxy configuration."""
        data = RepoConfigurationData()
        data.name = "r1"
        data.proxy = "http://example.com:1234"

        self.dnf_manager.add_repository(data)
        config = self._get_configuration("r1")
        assert config.proxy == "http://example.com:1234"

    def test_add_repository_proxy(self):
        """Test the add_repository method with the proxy configuration."""
        data = RepoConfigurationData()
        data.name = "r1"
        data.proxy = "http://user:pass@example.com:1234"

        self.dnf_manager.add_repository(data)
        config = self._get_configuration("r1")
        assert config.proxy == "http://example.com:1234"
        assert config.proxy_username == "user"
        assert config.proxy_password == "pass"

    def test_add_repository_cost(self):
        """Test the add_repository method with a cost."""
        data = RepoConfigurationData()
        data.name = "r1"
        data.cost = 256

        self.dnf_manager.add_repository(data)
        config = self._get_configuration("r1")
        assert config.cost == 256

    def test_add_repository_packages(self):
        """Test the add_repository method with packages."""
        data = RepoConfigurationData()
        data.name = "r1"
        data.included_packages = ["p1", "p2"]
        data.excluded_packages = ["p3", "p4"]

        self.dnf_manager.add_repository(data)
        config = self._get_configuration("r1")
        assert config.includepkgs == ("p1", "p2")
        assert config.excludepkgs == ("p3", "p4")

    def test_add_repository_replace(self):
        """Test the add_repository method with a replacement."""
        data = RepoConfigurationData()
        data.name = "r1"
        data.url = "http://u1"

        self.dnf_manager.add_repository(data)
        config = self._get_configuration("r1")
        assert config.baseurl == ("http://u1",)

        data.url = "http://u2"

        self.dnf_manager.add_repository(data)
        config = self._get_configuration("r1")
        assert config.baseurl == ("http://u2",)

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

        # Try to recreate the generated repository.
        expected_attrs = expected_content.splitlines(keepends=False)
        self.dnf_manager.add_repository(repo_data)
        self._check_repo(repo_data.name, expected_attrs)

    def _check_repo(self, repo_id, expected_attrs):
        """Check the repository attributes."""
        repo_config = self.dnf_manager._get_repository(repo_id).get_config()
        # Check all attributes. Skip the first line that contains just "[repo_id]".
        for attr in expected_attrs[1:]:
            key, value = attr.split('=')
            # Skip name, because that is not set (it's actually id).
            if key.strip() == "name":
                continue
            option = repo_config.__getattribute__("get_{}_option".format(key.strip()))()
            if isinstance(option.get_value(), bool):
                assert option.get_value() == (value.strip() == "1")
            else:
                assert option.get_value_string() == value.strip()

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

    def test_load_repository_failed(self):
        """Test the load_repositories method with a failure."""
        self._add_repository("r1")

        with pytest.raises(MetadataError, match="Failed to download metadata"):
            self.dnf_manager.load_repositories()

    def test_load_repositories_disabled(self):
        """Test the load_repositories method with a disabled repo."""
        repo = self._add_repository("r1")
        repo.disable()

        self.dnf_manager.load_repositories()

        repo = self._get_repository("r1")
        assert repo.is_enabled() is False

    def test_load_repositories(self):
        """Test the load_repositories method."""
        with TemporaryDirectory() as d:
            self._add_repository("r1", repo_dir=d)
            self.dnf_manager.load_repositories()

        repo = self._get_repository("r1")
        assert repo.is_enabled() is True

    def test_load_no_repomd_hashes(self):
        """Test the load_repomd_hashes method with no repositories."""
        self.dnf_manager.load_repomd_hashes()
        assert self.dnf_manager._md_hashes == {}

    def test_load_one_repomd_hash(self):
        """Test the load_repomd_hashes method with one repository."""
        with TemporaryDirectory() as d:
            self._add_repository("r1", repo_dir=d)
            self.dnf_manager.load_repositories()

            # Replace repomd.xml, so that the hash is deterministic
            with open(os.path.join(d, "repodata", "repomd.xml"), 'w') as f:
                f.write("Metadata for r1.")

            self.dnf_manager.load_repomd_hashes()
            assert self.dnf_manager._md_hashes == {
                'r1': b"\x90\xa0\xb7\xce\xc2H\x85#\xa3\xfci"
                      b"\x9e+\xf4\xe2\x19D\xbc\x9b'\xeb\xb7"
                      b"\x90\x1d\xcey\xb3\xd4p\xc3\x1d\xfb",
            }

    def test_load_repomd_hashes(self):
        """Test the load_repomd_hashes method."""
        with TemporaryDirectory() as d:
            self._add_repository(
                repo_id="r1",
                baseurl=[
                    "file://nonexistent/1",
                    "file://nonexistent/2",
                    "file://nonexistent/3",
                ],
                repo_dir=os.path.join(d, "r1"),
            )
            self._add_repository(
                repo_id="r2",
                baseurl=[
                    "file://nonexistent/1",
                    "file://nonexistent/2",
                    "file://nonexistent/3",
                ]
            )
            self._add_repository(
                repo_id="r3",
                metalink="file://metalink"
            )
            self._add_repository(
                repo_id="r4",
                mirrorlist="file://mirrorlist"
            )

            try:
                self.dnf_manager.load_repositories()
            except MetadataError:
                pass

            # Replace repomd.xml, so that the hash is deterministic
            with open(os.path.join(d, "r1", "repodata", "repomd.xml"), 'w') as f:
                f.write("Metadata for r1.")

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
            self._add_repository(repo_id="r1", repo_dir=d)
            self.dnf_manager.load_repositories()

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
