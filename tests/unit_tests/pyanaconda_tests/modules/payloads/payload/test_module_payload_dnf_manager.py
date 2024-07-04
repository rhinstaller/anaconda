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
import libdnf5

from tempfile import TemporaryDirectory
from unittest.mock import patch, Mock, call

from blivet.size import Size, ROUND_UP
from dasbus.structure import compare_data

#from dnf.callback import STATUS_OK, STATUS_FAILED, PKG_SCRIPTLET
#from dnf.comps import Environment, Comps, Group
#from dnf.exceptions import MarkingErrors, DepsolveError, RepoError
#from dnf.package import Package
#from dnf.transaction import PKG_INSTALL, TRANS_POST
#from dnf.repo import Repo
#import libdnf.transaction

from pyanaconda.core.constants import MULTILIB_POLICY_ALL, URL_TYPE_BASEURL, URL_TYPE_MIRRORLIST, \
    URL_TYPE_METALINK
from pyanaconda.modules.common.errors.installation import PayloadInstallationError
from pyanaconda.modules.common.errors.payload import UnknownCompsEnvironmentError, \
    UnknownCompsGroupError, UnknownRepositoryError
from pyanaconda.modules.common.structures.comps import CompsEnvironmentData, CompsGroupData
from pyanaconda.modules.common.structures.packages import PackagesConfigurationData
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.payloads.payload.dnf.dnf_manager import DNFManager, \
    InvalidSelectionError, BrokenSpecsError, MissingSpecsError, MetadataError, simplify_config


class DNFManagerTestCase(unittest.TestCase):

    def _get_package(self, name):
        """Get a mocked package of the specified name."""
        package = Mock(spec=Package)
        package.name = name
        package.arch = "x86_64"
        package.evr = "1.2-3"
        package.buildtime = 100
        package.returnIdSum.return_value = ("", "1a2b3c")
        return package

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
