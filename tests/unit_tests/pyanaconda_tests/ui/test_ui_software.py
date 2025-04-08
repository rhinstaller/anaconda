#
# Copyright (C) 2023  Red Hat, Inc.
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
from unittest.mock import patch
from pyanaconda.ui.lib.software import get_kernel_from_properties, get_available_kernel_features, KernelFeatures
class SoftwareUITestCase(unittest.TestCase):
    """Test the UI functions and classes of the software-selection object."""
    def test_get_kernel_from_properties(self):
        assert get_kernel_from_properties(KernelFeatures(upstream=False, page_size_64k=False)) is None
        assert get_kernel_from_properties(KernelFeatures(upstream=True, page_size_64k=False)) == "kernel-redhat"
        assert get_kernel_from_properties(KernelFeatures(upstream=False, page_size_64k=True)) == "kernel-64k"
        assert get_kernel_from_properties(KernelFeatures(upstream=True, page_size_64k=True)) == "kernel-redhat-64k"

    @patch("pyanaconda.payload.dnf.payload")
    @patch("pyanaconda.ui.lib.software.is_aarch64")
    def test_get_available_kernel_features(self, is_aarch64, payload):
        payload.match_available_packages.return_value = ["ntoskrnl"]
        is_aarch64.return_value = False

        res = get_available_kernel_features(payload)
        assert isinstance(res, dict)
        assert len(res) > 0
        assert res["upstream"]
        assert res["64k"] is False
        is_aarch64.assert_called_once()

        is_aarch64.return_value = True
        assert is_aarch64()
        res = get_available_kernel_features(payload)
        assert res["upstream"]
        assert res["64k"]

        payload.match_available_packages.return_value = []
        res = get_available_kernel_features(payload)
        assert not res["upstream"]
        assert not res["64k"]
