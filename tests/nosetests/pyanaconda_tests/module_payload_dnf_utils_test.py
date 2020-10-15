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
from unittest.mock import patch, Mock

from pyanaconda.modules.payloads.payload.dnf.utils import get_kernel_package


class DNFUtilsPackagesTestCase(unittest.TestCase):

    def get_kernel_package_excluded_test(self):
        """Test the get_kernel_package function with kernel excluded."""
        kernel = get_kernel_package(dnf_base=Mock(), exclude_list=["kernel"])
        self.assertEqual(kernel, None)

    @patch("pyanaconda.modules.payloads.payload.dnf.utils.dnf")
    def get_kernel_package_installable_test(self, mock_dnf):
        """Test the get_kernel_package function without installable packages."""
        subject = mock_dnf.subject.Subject.return_value
        subject.get_best_query.return_value = False

        with self.assertLogs(level="ERROR") as cm:
            kernel = get_kernel_package(dnf_base=Mock(), exclude_list=[])

        msg = "kernel: failed to select a kernel"
        self.assertTrue(any(map(lambda x: msg in x, cm.output)))
        self.assertEqual(kernel, None)

    @patch("pyanaconda.modules.payloads.payload.dnf.utils.dnf")
    @patch("pyanaconda.modules.payloads.payload.dnf.utils.is_lpae_available")
    def get_kernel_package_lpae_test(self, is_lpae, mock_dnf):
        """Test the get_kernel_package function with LPAE."""
        subject = mock_dnf.subject.Subject.return_value
        subject.get_best_query.return_value = True
        is_lpae.return_value = True

        kernel = get_kernel_package(dnf_base=Mock(), exclude_list=[])
        self.assertEqual(kernel, "kernel-lpae")

    @patch("pyanaconda.modules.payloads.payload.dnf.utils.dnf")
    @patch("pyanaconda.modules.payloads.payload.dnf.utils.is_lpae_available")
    def get_kernel_package_test(self, is_lpae, mock_dnf):
        """Test the get_kernel_package function."""
        subject = mock_dnf.subject.Subject.return_value
        subject.get_best_query.return_value = True
        is_lpae.return_value = False

        kernel = get_kernel_package(dnf_base=Mock(), exclude_list=[])
        self.assertEqual(kernel, "kernel")
