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
from tempfile import TemporaryDirectory
from unittest.mock import patch, Mock, call

from blivet.size import Size, ROUND_UP
from dasbus.structure import compare_data

from dnf.callback import STATUS_OK, STATUS_FAILED, PKG_SCRIPTLET
from dnf.comps import Environment, Comps, Group
from dnf.exceptions import MarkingErrors, DepsolveError, RepoError
from dnf.package import Package
from dnf.transaction import PKG_INSTALL, TRANS_POST, PKG_VERIFY
from dnf.repo import Repo

from pyanaconda.core.constants import MULTILIB_POLICY_ALL
from pyanaconda.modules.common.errors.installation import PayloadInstallationError
from pyanaconda.modules.common.errors.payload import UnknownCompsEnvironmentError, \
    UnknownCompsGroupError, UnknownRepositoryError
from pyanaconda.modules.common.structures.comps import CompsEnvironmentData, CompsGroupData
from pyanaconda.modules.common.structures.packages import PackagesConfigurationData
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
            self.assertIn(attribute, configuration)

    def _check_substitutions(self, substitutions):
        """Check the DNF substitutions."""
        self.assertEqual(dict(self.dnf_manager._base.conf.substitutions), substitutions)

    def create_base_test(self):
        """Test the creation of the DNF base."""
        self.assertIsNotNone(self.dnf_manager._base)

    def reset_base_test(self):
        """Test the reset of the DNF base."""
        base_1 = self.dnf_manager._base
        self.assertEqual(self.dnf_manager._base, base_1)
        self.dnf_manager.reset_base()

        base_2 = self.dnf_manager._base
        self.assertEqual(self.dnf_manager._base, base_2)
        self.assertNotEqual(self.dnf_manager._base, base_1)

    def clear_cache_test(self):
        """Test the clear_cache method."""
        self.dnf_manager.clear_cache()

    def set_default_configuration_test(self):
        """Test the default configuration of the DNF base."""
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
            "releasever": "rawhide"
        })

    @patch("pyanaconda.modules.payloads.payload.dnf.dnf_manager.get_os_release_value")
    def set_module_platform_id_test(self, get_platform_id):
        """Test the configuration of module_platform_id."""
        get_platform_id.return_value = "platform:f32"
        self.dnf_manager.reset_base()
        self._check_configuration("module_platform_id = platform:f32")

    def configure_proxy_test(self):
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

    def configure_base_test(self):
        """Test the configuration of the DNF base."""
        data = PackagesConfigurationData()

        self.dnf_manager.configure_base(data)
        self._check_configuration(
            "multilib_policy = best",
            "timeout = 30",
            "retries = 10",
            "install_weak_deps = 1",
        )

        self.assertEqual(self.dnf_manager._ignore_broken_packages, False)
        self.assertEqual(self.dnf_manager._ignore_missing_packages, False)

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

        self.assertEqual(self.dnf_manager._ignore_broken_packages, True)
        self.assertEqual(self.dnf_manager._ignore_missing_packages, True)

    def dump_configuration_test(self):
        """Test the dump of the DNF configuration."""
        with self.assertLogs(level="DEBUG") as cm:
            self.dnf_manager.dump_configuration()

        msg = "DNF configuration:"
        self.assertTrue(any(map(lambda x: msg in x, cm.output)))

        msg = "installroot = /mnt/sysroot"
        self.assertTrue(any(map(lambda x: msg in x, cm.output)))

    def get_installation_size_test(self):
        """Test the get_installation_size method."""
        # No transaction.
        size = self.dnf_manager.get_installation_size()
        self.assertEqual(size, Size("3000 MiB"))

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

        self.assertEqual(size, Size("528 KiB"))

    def get_download_size_test(self):
        """Test the get_download_size method."""
        # No transaction.
        size = self.dnf_manager.get_download_size()
        self.assertEqual(size, Size(0))

        # Fake transaction.
        tsi_1 = Mock()
        tsi_1.pkg.downloadsize = 1024 * 1024 * 100

        tsi_2 = Mock()
        tsi_2.pkg.downloadsize = 1024 * 1024 * 200

        self.dnf_manager._base.transaction = [tsi_1, tsi_2]
        size = self.dnf_manager.get_download_size()

        self.assertEqual(size, Size("450 MiB"))

    @patch("dnf.module.module_base.ModuleBase.enable")
    def enable_modules_test(self, module_base_enable):
        """Test the enable_modules method."""
        self.dnf_manager.enable_modules(
            module_specs=["m1", "m2:latest"]
        )
        module_base_enable.assert_called_once_with(
            ["m1", "m2:latest"]
        )

    @patch("dnf.module.module_base.ModuleBase.enable")
    def enable_modules_error_test(self, module_base_enable):
        """Test the failed enable_modules method."""
        module_base_enable.side_effect = MarkingErrors(
            module_depsolv_errors=["e1", "e2"]
        )

        with self.assertRaises(BrokenSpecsError):
            self.dnf_manager.enable_modules(
                module_specs=["m1", "m2:latest"]
            )

    @patch("dnf.module.module_base.ModuleBase.disable")
    def disable_modules_test(self, module_base_disable):
        """Test the enable_modules method."""
        self.dnf_manager.disable_modules(
            module_specs=["m1", "m2:latest"]
        )
        module_base_disable.assert_called_once_with(
            ["m1", "m2:latest"]
        )

    @patch("dnf.module.module_base.ModuleBase.disable")
    def disable_modules_error_test(self, module_base_disable):
        """Test the failed enable_modules method."""
        module_base_disable.side_effect = MarkingErrors(
            module_depsolv_errors=["e1", "e2"]
        )

        with self.assertRaises(BrokenSpecsError):
            self.dnf_manager.disable_modules(
                module_specs=["m1", "m2:latest"]
            )

    @patch("dnf.base.Base.install_specs")
    def apply_specs_test(self, install_specs):
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
    def apply_specs_error_test(self, install_specs):
        """Test the apply_specs method with an error."""
        install_specs.side_effect = MarkingErrors(
            error_group_specs=["@g1"]
        )

        with self.assertRaises(BrokenSpecsError):
            self.dnf_manager.apply_specs(
                include_list=["@g1", "p1"],
                exclude_list=["@g2", "p2"]
            )

        install_specs.side_effect = MarkingErrors(
            no_match_group_specs=["@g1"]
        )

        with self.assertRaises(MissingSpecsError):
            self.dnf_manager.apply_specs(
                include_list=["@g1", "p1"],
                exclude_list=["@g2", "p2"]
            )

    @patch("dnf.base.Base.install_specs")
    def apply_specs_ignore_broken_test(self, install_specs):
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
    def apply_specs_ignore_missing_test(self, install_specs):
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

        with self.assertRaises(BrokenSpecsError):
            self.dnf_manager.apply_specs(
                include_list=["@g1", "p1"],
                exclude_list=["@g2", "p2"]
            )

    @patch("dnf.base.Base.download_packages")
    @patch("dnf.base.Base.transaction")
    def download_packages_test(self, transaction, download_packages):
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

        self.assertEqual(progress.downloads, {
            "p1": 100,
            "p2": 100,
            "p3": 100
        })

    @patch("dnf.base.Base.download_packages")
    @patch("dnf.base.Base.transaction")
    def download_packages_failed_test(self, transaction, download_packages):
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

        self.assertEqual(progress.downloads, {
            "p1": 25,
            "p2": 25,
            "p3": 25
        })

    @patch("dnf.base.Base.do_transaction")
    def install_packages_test(self, do_transaction):
        """Test the install_packages method."""
        calls = []
        do_transaction.side_effect = self._install_packages

        self.dnf_manager.install_packages(calls.append)

        self.assertEqual(calls, [
            'Installing p1.x86_64 (0/3)',
            'Installing p2.x86_64 (1/3)',
            'Installing p3.x86_64 (2/3)',
            'Performing post-installation setup tasks',
            'Configuring p1.x86_64',
            'Configuring p2.x86_64',
            'Configuring p3.x86_64',
            'Verifying p1.x86_64 (1/3)',
            'Verifying p2.x86_64 (2/3)',
            'Verifying p3.x86_64 (3/3)',
        ])

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

        for ts_done, package in enumerate(packages):
            progress.progress(package, PKG_VERIFY, 100, 100, ts_done + 1, ts_total)

    @patch("dnf.base.Base.do_transaction")
    def install_packages_failed_test(self, do_transaction):
        """Test the failed install_packages method."""
        calls = []
        do_transaction.side_effect = self._install_packages_failed

        with self.assertRaises(PayloadInstallationError) as cm:
            self.dnf_manager.install_packages(calls.append)

        msg = "An error occurred during the transaction: " \
              "The p1 package couldn't be installed!"

        self.assertEqual(str(cm.exception), msg)
        self.assertEqual(calls, [])

    def _install_packages_failed(self, progress):
        """Simulate the failed installation of packages."""
        progress.error("The p1 package couldn't be installed!")

    @patch("dnf.base.Base.do_transaction")
    def install_packages_quit_test(self, do_transaction):
        """Test the terminated install_packages method."""
        calls = []
        do_transaction.side_effect = self._install_packages_quit

        with self.assertRaises(RuntimeError) as cm:
            self.dnf_manager.install_packages(calls.append)

        msg = "The transaction process has ended abruptly: " \
              "Something went wrong with the p1 package!"

        self.assertIn(msg, str(cm.exception))
        self.assertEqual(calls, [])

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

    def set_download_location_test(self):
        """Test the set_download_location method."""
        r1 = self._add_repo("r1")
        r2 = self._add_repo("r2")
        r3 = self._add_repo("r3")

        self.dnf_manager.set_download_location("/my/download/location")

        self.assertEqual(r1.pkgdir, "/my/download/location")
        self.assertEqual(r2.pkgdir, "/my/download/location")
        self.assertEqual(r3.pkgdir, "/my/download/location")

    def download_location_test(self):
        """Test the download_location property."""
        self.assertEqual(self.dnf_manager.download_location, None)

        self.dnf_manager.set_download_location("/my/location")
        self.assertEqual(self.dnf_manager.download_location, "/my/location")

        self.dnf_manager.reset_base()
        self.assertEqual(self.dnf_manager.download_location, None)

    def substitute_test(self):
        """Test the substitute method."""
        # No variables.
        self.assertEqual(self.dnf_manager.substitute(None), "")
        self.assertEqual(self.dnf_manager.substitute(""), "")
        self.assertEqual(self.dnf_manager.substitute("/"), "/")
        self.assertEqual(self.dnf_manager.substitute("/text"), "/text")

        # Unknown variables.
        self.assertEqual(self.dnf_manager.substitute("/$unknown"), "/$unknown")

        # Supported variables.
        self.assertNotEqual(self.dnf_manager.substitute("/$basearch"), "/$basearch")
        self.assertNotEqual(self.dnf_manager.substitute("/$releasever"), "/$releasever")

    @patch("dnf.subject.Subject.get_best_query")
    def is_package_available_test(self, get_best_query):
        """Test the is_package_available method."""
        self.dnf_manager._base._sack = Mock()
        self.assertEqual(self.dnf_manager.is_package_available("kernel"), True)

        # No package.
        get_best_query.return_value = None
        self.assertEqual(self.dnf_manager.is_package_available("kernel"), False)

        # No metadata.
        self.dnf_manager._base._sack = None

        with self.assertLogs(level="WARNING") as cm:
            self.assertEqual(self.dnf_manager.is_package_available("kernel"), False)

        msg = "There is no metadata about packages!"
        self.assertTrue(any(map(lambda x: msg in x, cm.output)))

    def match_available_packages_test(self):
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
        self.assertEqual(self.dnf_manager.match_available_packages("langpacks-*"), [
            "langpacks-cs",
            "langpacks-core-cs",
            "langpacks-core-font-cs"
        ])

        # No metadata.
        self.dnf_manager._base._sack = None

        with self.assertLogs(level="WARNING") as cm:
            self.assertEqual(self.dnf_manager.match_available_packages("langpacks-*"), [])

        msg = "There is no metadata about packages!"
        self.assertTrue(any(map(lambda x: msg in x, cm.output)))

    @patch("dnf.base.Base.resolve")
    def resolve_selection_test(self, resolve):
        """Test the resolve_selection method."""
        self.dnf_manager._base.transaction = [Mock(), Mock()]

        with self.assertLogs(level="INFO") as cm:
            self.dnf_manager.resolve_selection()

        expected = "The software selection has been resolved (2 packages selected)."
        self.assertIn(expected, "\n".join(cm.output))

        resolve.assert_called_once()

    @patch("dnf.base.Base.resolve")
    def resolve_selection_failed_test(self, resolve):
        """Test the failed resolve_selection method."""
        resolve.side_effect = DepsolveError("e1")

        with self.assertRaises(InvalidSelectionError) as cm:
            self.dnf_manager.resolve_selection()

        expected = \
            "The following software marked for installation has errors.\n" \
            "This is likely caused by an error with your installation source.\n\n" \
            "e1"

        self.assertEqual(expected, str(cm.exception))

    def clear_selection_test(self):
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
                if name in (e.id, e.ui_name):
                    return e

            return None

        comps.environment_by_pattern = environment_by_pattern

        def group_by_pattern(name):
            for e in comps.groups:
                if name in (e.id, e.ui_name):
                    return e

            return None

        comps.group_by_pattern = group_by_pattern
        return comps

    def _add_group(self, grp_id, visible=True):
        """Add a mocked group with the specified id."""
        group = Mock(spec=Group)
        group.id = grp_id
        group.ui_name = "The '{}' group".format(grp_id)
        group.ui_description = "This is the '{}' group.".format(grp_id)
        group.visible = visible

        self.comps.groups.append(group)

    def _add_environment(self, env_id, optional=(), default=()):
        """Add a mocked environment with the specified id."""
        environment = Mock(spec=Environment)
        environment.id = env_id
        environment.ui_name = "The '{}' environment".format(env_id)
        environment.ui_description = "This is the '{}' environment.".format(env_id)
        environment.option_ids = []

        for opt_id in optional:
            option = Mock()
            option.name = opt_id
            option.default = opt_id in default
            environment.option_ids.append(option)

        self.comps.environments.append(environment)

    def groups_test(self):
        """Test the groups property."""
        self.assertEqual(self.dnf_manager.groups, [])

        self._add_group("g1")
        self._add_group("g2")
        self._add_group("g3")

        self.assertEqual(self.dnf_manager.groups, [
            "g1", "g2", "g3",
        ])

    def resolve_group_test(self):
        """Test the resolve_group method."""
        self.assertEqual(self.dnf_manager.resolve_group(""), None)
        self.assertEqual(self.dnf_manager.resolve_group("g1"), None)

        self._add_group("g1")

        self.assertEqual(self.dnf_manager.resolve_group("g1"), "g1")
        self.assertEqual(self.dnf_manager.resolve_group("g2"), None)

    def get_group_data_error_test(self):
        """Test the failed get_group_data method."""
        with self.assertRaises(UnknownCompsGroupError):
            self.dnf_manager.get_group_data("g1")

    def get_group_data_test(self):
        """Test the get_group_data method."""
        self._add_group("g1")

        expected = CompsGroupData()
        expected.id = "g1"
        expected.name = "The 'g1' group"
        expected.description = "This is the 'g1' group."

        data = self.dnf_manager.get_group_data("g1")
        self.assertIsInstance(data, CompsGroupData)
        self.assertTrue(compare_data(data, expected))

    def no_default_environment_test(self):
        """Test the default_environment property with no environments."""
        self.assertEqual(self.dnf_manager.default_environment, None)

    def default_environment_test(self):
        """Test the default_environment property with some environments."""
        self._add_environment("e1")
        self._add_environment("e2")
        self._add_environment("e3")

        with patch("pyanaconda.modules.payloads.payload.dnf.dnf_manager.conf") as conf:
            # Choose the first environment.
            conf.payload.default_environment = ""
            self.assertEqual(self.dnf_manager.default_environment, "e1")

            # Choose the configured environment.
            conf.payload.default_environment = "e2"
            self.assertEqual(self.dnf_manager.default_environment, "e2")

    def environments_test(self):
        """Test the environments property."""
        self.assertEqual(self.dnf_manager.environments, [])

        self._add_environment("e1")
        self._add_environment("e2")
        self._add_environment("e3")

        self.assertEqual(self.dnf_manager.environments, [
            "e1", "e2", "e3",
        ])

    def resolve_environment_test(self):
        """Test the resolve_environment method."""
        self.assertEqual(self.dnf_manager.resolve_environment(""), None)
        self.assertEqual(self.dnf_manager.resolve_environment("e1"), None)

        self._add_environment("e1")

        self.assertEqual(self.dnf_manager.resolve_environment("e1"), "e1")
        self.assertEqual(self.dnf_manager.resolve_environment("e2"), None)

    def is_environment_valid_test(self):
        """Test the is_environment_valid method."""
        self.assertEqual(self.dnf_manager.is_environment_valid(""), False)
        self.assertEqual(self.dnf_manager.is_environment_valid("e1"), False)

        self._add_environment("e1")

        self.assertEqual(self.dnf_manager.is_environment_valid("e1"), True)
        self.assertEqual(self.dnf_manager.is_environment_valid("e2"), False)

    def get_environment_data_error_test(self):
        """Test the failed get_environment_data method."""
        with self.assertRaises(UnknownCompsEnvironmentError):
            self.dnf_manager.get_environment_data("e1")

    def get_environment_data_test(self):
        """Test the get_environment_data method."""
        self._add_environment("e1")

        expected = CompsEnvironmentData()
        expected.id = "e1"
        expected.name = "The 'e1' environment"
        expected.description = "This is the 'e1' environment."

        data = self.dnf_manager.get_environment_data("e1")
        self.assertIsInstance(data, CompsEnvironmentData)
        self.assertTrue(compare_data(data, expected))

    def get_environment_data_visible_groups_test(self):
        """Test the get_environment_data method with visible groups."""
        self._add_group("g1")
        self._add_group("g2", visible=False)
        self._add_group("g3")
        self._add_group("g4", visible=False)

        self._add_environment("e1")

        data = self.dnf_manager.get_environment_data("e1")
        self.assertEqual(data.visible_groups, ["g1", "g3"])

    def get_environment_data_optional_groups_test(self):
        """Test the get_environment_data method with optional groups."""
        self._add_group("g1")
        self._add_group("g2")
        self._add_group("g3")
        self._add_group("g4")

        self._add_environment("e1", optional=["g1", "g3"])

        data = self.dnf_manager.get_environment_data("e1")
        self.assertEqual(data.optional_groups, ["g1", "g3"])

    def get_environment_data_default_groups_test(self):
        """Test the get_environment_data method with default groups."""
        self._add_group("g1")
        self._add_group("g2")
        self._add_group("g3")
        self._add_group("g4")

        self._add_environment("e1", optional=["g1", "g2", "g3"], default=["g1", "g3"])

        data = self.dnf_manager.get_environment_data("e1")
        self.assertEqual(data.default_groups, ["g1", "g3"])

    def environment_data_available_groups_test(self):
        """Test the get_available_groups method."""
        data = CompsEnvironmentData()
        self.assertEqual(data.get_available_groups(), [])

        data.optional_groups = ["g1", "g2", "g3"]
        data.visible_groups = ["g3", "g4", "g5"]
        data.default_groups = ["g1", "g3"]

        self.assertEqual(data.get_available_groups(), [
            "g1", "g2", "g3", "g4", "g5"
        ])


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

    def repositories_test(self):
        """Test the repositories property."""
        self.assertEqual(self.dnf_manager.repositories, [])

        self._add_repo("r1")
        self._add_repo("r2")
        self._add_repo("r3")

        self.assertEqual(self.dnf_manager.repositories, ["r1", "r2", "r3"])

    def load_repository_unknown_test(self):
        """Test the load_repository method with an unknown repo."""
        with self.assertRaises(UnknownRepositoryError):
            self.dnf_manager.load_repository("r1")

    def load_repository_failed_test(self):
        """Test the load_repository method with a failure."""
        repo = self._add_repo("r1")
        repo.load = Mock(side_effect=RepoError("Fake error!"))

        with self.assertRaises(MetadataError) as cm:
            self.dnf_manager.load_repository("r1")

        repo.load.assert_called_once()
        self.assertEqual(repo.enabled, False)
        self.assertEqual(str(cm.exception), "Fake error!")

    def load_repository_test(self):
        """Test the load_repository method."""
        repo = self._add_repo("r1")
        repo.load = Mock()

        self.dnf_manager.load_repository("r1")

        repo.load.assert_called_once()
        self.assertEqual(repo.enabled, True)

    def _create_repo(self, repo, repo_dir):
        """Generate fake metadata for the repo."""
        # Create the repodata directory.
        os.makedirs(os.path.join(repo_dir, "repodata"))

        # Create the repomd.xml file.
        md_path = os.path.join(repo_dir, "repodata", "repomd.xml")
        md_content = "Metadata for {}.".format(repo.id)

        with open(md_path, 'w') as f:
            f.write(md_content)

        # Set up the baseurl.
        repo.baseurl.append("file://" + repo_dir)

    def load_no_repomd_hashes_test(self):
        """Test the load_repomd_hashes method with no repositories."""
        self.dnf_manager.load_repomd_hashes()
        self.assertEqual(self.dnf_manager._md_hashes, {})

    def load_one_repomd_hash_test(self):
        """Test the load_repomd_hashes method with one repository."""
        with TemporaryDirectory() as d:
            r1 = self._add_repo("r1")
            self._create_repo(r1, d)

            self.dnf_manager.load_repomd_hashes()
            self.assertEqual(self.dnf_manager._md_hashes, {
                'r1': b"\x90\xa0\xb7\xce\xc2H\x85#\xa3\xfci"
                      b"\x9e+\xf4\xe2\x19D\xbc\x9b'\xeb\xb7"
                      b"\x90\x1d\xcey\xb3\xd4p\xc3\x1d\xfb",
            })

    def load_repomd_hashes_test(self):
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

            self.assertEqual(self.dnf_manager._md_hashes, {
                'r1': b"\x90\xa0\xb7\xce\xc2H\x85#\xa3\xfci"
                      b"\x9e+\xf4\xe2\x19D\xbc\x9b'\xeb\xb7"
                      b"\x90\x1d\xcey\xb3\xd4p\xc3\x1d\xfb",
                'r2': None,
                'r3': None,
                'r4': None,
            })

    def verify_repomd_hashes_test(self):
        """Test the verify_repomd_hashes method."""
        with TemporaryDirectory() as d:
            # Test no repository.
            self.assertEqual(self.dnf_manager.verify_repomd_hashes(), False)

            # Create a repository.
            r = self._add_repo("r1")
            self._create_repo(r, d)

            # Test no loaded repository.
            self.assertEqual(self.dnf_manager.verify_repomd_hashes(), False)

            # Test a loaded repository.
            self.dnf_manager.load_repomd_hashes()
            self.assertEqual(self.dnf_manager.verify_repomd_hashes(), True)

            # Test a different content of metadata.
            with open(os.path.join(d, "repodata", "repomd.xml"), 'w') as f:
                f.write("Different metadata for r1.")

            self.assertEqual(self.dnf_manager.verify_repomd_hashes(), False)

            # Test a reloaded repository.
            self.dnf_manager.load_repomd_hashes()
            self.assertEqual(self.dnf_manager.verify_repomd_hashes(), True)

            # Test the base reset.
            self.dnf_manager.reset_base()
            self.assertEqual(self.dnf_manager.verify_repomd_hashes(), False)
