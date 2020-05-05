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
# Red Hat Author(s): Martin Kolman <mkolman@redhat.com>
#
import os
import tempfile

import unittest

from pyanaconda.core import util
from pyanaconda.core.constants import RHSM_SYSPURPOSE_FILE_PATH

from pyanaconda.core.subscription import check_system_purpose_set


class CheckSystemPurposeSetTestCase(unittest.TestCase):
    """Test the check_system_purpose_set helper function."""

    def check_system_purpose_set_test(self):
        """Test the check_system_purpose_set() helper function."""
        # system purpose set
        with tempfile.TemporaryDirectory() as sysroot:
            # create a dummy syspurpose file
            syspurpose_path = RHSM_SYSPURPOSE_FILE_PATH
            directory = os.path.split(syspurpose_path)[0]
            os.makedirs(util.join_paths(sysroot, directory))
            os.mknod(util.join_paths(sysroot, syspurpose_path))
            self.assertTrue(check_system_purpose_set(sysroot))

        # system purpose not set
        with tempfile.TemporaryDirectory() as sysroot:
            self.assertFalse(check_system_purpose_set(sysroot))
