#
# Copyright (C) 2026  Red Hat, Inc.
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

from pyanaconda.modules.common.structures.partitioning import PartitioningRequest
from pyanaconda.ui.tui.spokes import storage as tui_storage


class PartitionSchemeSpokeTests(unittest.TestCase):
    """Test the encryption selection in the partition scheme spoke."""

    def _make_spoke(self, encrypted=False):
        request = PartitioningRequest()
        request.encrypted = encrypted

        partitioning = Mock()
        partitioning.Request = PartitioningRequest.to_structure(request)

        with patch.object(tui_storage, "get_supported_autopart_choices",
                          return_value=[("LVM", 1)]):
            spoke = tui_storage.PartitionSchemeSpoke(
                data=Mock(), storage=Mock(), payload=Mock(),
                partitioning=partitioning,
            )

        return spoke, partitioning

    def test_encryption_toggle(self):
        """The encryption callback toggles the request's encrypted flag."""
        spoke, _partitioning = self._make_spoke(encrypted=False)

        spoke._set_encryption_callback(None)
        assert spoke._request.encrypted is True

        spoke._set_encryption_callback(None)
        assert spoke._request.encrypted is False

    def test_encryption_preserved_from_request(self):
        """A pre-set encrypted flag (kickstart or configuration default)
        is reflected without toggling."""
        spoke, _partitioning = self._make_spoke(encrypted=True)
        assert spoke._request.encrypted is True

    def test_apply_publishes_encryption(self):
        """apply() writes the toggled encryption back to the module."""
        spoke, partitioning = self._make_spoke(encrypted=False)

        spoke._set_encryption_callback(None)
        spoke.apply()

        request = PartitioningRequest.from_structure(partitioning.Request)
        assert request.encrypted is True

    def test_refresh_shows_encryption_checkbox(self):
        """refresh() offers the encryption choice in the option list."""
        spoke, _partitioning = self._make_spoke(encrypted=False)
        spoke.window = Mock()

        with patch.object(tui_storage.NormalTUISpoke, "refresh"), \
             patch.object(tui_storage, "ListColumnContainer") as container_cls, \
             patch.object(tui_storage, "CheckboxWidget") as checkbox_cls:
            spoke.refresh()

        titles = [call.kwargs.get("title") for call in checkbox_cls.call_args_list]
        assert "Encrypt my data" in titles

        # one entry per partition scheme plus the encryption checkbox
        assert container_cls.return_value.add.call_count == 2
