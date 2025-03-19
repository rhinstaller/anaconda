#
# Copyright (C) 2022  Red Hat, Inc.
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

from pyanaconda.modules.payloads.payload.dnf.dnf_manager import DNFManager
from pyanaconda.modules.payloads.payload.dnf.tear_down import ResetDNFManagerTask


class ResetDNFManagerTaskTestCase(unittest.TestCase):
    """Test the installation task for setting the RPM macros."""

    def test_reset_dnf_manager_task(self):
        """Test the ResetDNFManagerTask task."""
        dnf_manager = DNFManager()
        dnf_base = dnf_manager._base

        task = ResetDNFManagerTask(
            dnf_manager=dnf_manager
        )
        task.run()

        assert dnf_base._closed
