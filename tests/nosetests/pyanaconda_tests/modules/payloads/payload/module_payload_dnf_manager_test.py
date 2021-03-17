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
from unittest.mock import patch, Mock, call

from blivet.size import Size, ROUND_UP
from dnf.callback import STATUS_OK, STATUS_FAILED, PKG_SCRIPTLET
from dnf.exceptions import MarkingErrors
from dnf.package import Package
from dnf.transaction import PKG_INSTALL, TRANS_POST, PKG_VERIFY

from pyanaconda.core.constants import MULTILIB_POLICY_ALL
from pyanaconda.modules.common.errors.installation import PayloadInstallationError
from pyanaconda.modules.common.structures.packages import PackagesConfigurationData
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

    def environments_test(self):
        """Test the environments property."""
        self.assertEqual(self.dnf_manager.environments, [])

        # Fake environments.
        env_1 = Mock(id="environment-1")
        env_2 = Mock(id="environment-2")
        env_3 = Mock(id="environment-3")

        # Fake comps.
        comps = Mock(environments=[env_1, env_2, env_3])

        self.dnf_manager._base._comps = comps
        self.assertEqual(self.dnf_manager.environments, [
            "environment-1",
            "environment-2",
            "environment-3",
        ])

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

        with self.assertRaises(MarkingErrors):
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

        with self.assertRaises(MarkingErrors):
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

        with self.assertRaises(MarkingErrors):
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

        with self.assertRaises(MarkingErrors):
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
