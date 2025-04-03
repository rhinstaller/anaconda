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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import unittest
from unittest.mock import Mock, patch

#import libdnf.transaction
import pytest
from pyanaconda.modules.common.errors.installation import PayloadInstallationError


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

    # For this test, mocked Transaction is needed, but it can't be easily
    # created, because it doesn't have a public constructor, it's supposed
    # to be taken from resolved Goal.
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

    # For this test, mocked Transaction is needed, but it can't be easily
    # created, because it doesn't have a public constructor, it's supposed
    # to be taken from resolved Goal.
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
