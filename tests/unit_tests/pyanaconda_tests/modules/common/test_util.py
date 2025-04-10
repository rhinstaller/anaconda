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
# Red Hat Author(s): Martin Kolman <mkolman@redhat.com>
#

import unittest
from unittest.mock import patch

from pyanaconda.modules.common.constants.services import SUBSCRIPTION
from pyanaconda.modules.common.util import is_module_available


class IsModuleAvailableTestCase(unittest.TestCase):
    """Test the is_module_available() utility function."""

    @patch("pyanaconda.modules.common.constants.services.BOSS.get_proxy")
    def test_is_module_available(self, get_proxy):
        """Test the is_module_available() function - module available."""
        # mock the Boss proxy
        boss_proxy = get_proxy.return_value
        # make sure it returns a list containing the Subscription module
        running_modules = [
            "org.fedoraproject.Anaconda.Modules.Timezone",
            "org.fedoraproject.Anaconda.Modules.Network",
            "org.fedoraproject.Anaconda.Modules.Localization",
            "org.fedoraproject.Anaconda.Modules.Security",
            "org.fedoraproject.Anaconda.Modules.Users",
            "org.fedoraproject.Anaconda.Modules.Payloads",
            "org.fedoraproject.Anaconda.Modules.Storage",
            "org.fedoraproject.Anaconda.Modules.Services",
            "org.fedoraproject.Anaconda.Modules.Subscription",
         ]
        boss_proxy.GetModules.return_value = running_modules
        # call the function
        assert is_module_available(SUBSCRIPTION)

    @patch("pyanaconda.modules.common.constants.services.BOSS.get_proxy")
    def test_is_module_not_available(self, get_proxy):
        """Test the is_module_available() function - module not available."""
        # mock the Boss proxy
        boss_proxy = get_proxy.return_value
        # make sure it returns a list not containing the Subscription module
        running_modules = [
            "org.fedoraproject.Anaconda.Modules.Timezone",
            "org.fedoraproject.Anaconda.Modules.Network",
            "org.fedoraproject.Anaconda.Modules.Localization",
            "org.fedoraproject.Anaconda.Modules.Security",
            "org.fedoraproject.Anaconda.Modules.Users",
            "org.fedoraproject.Anaconda.Modules.Payloads",
            "org.fedoraproject.Anaconda.Modules.Storage",
            "org.fedoraproject.Anaconda.Modules.Services",
         ]
        boss_proxy.GetModules.return_value = running_modules
        # call the function
        assert not is_module_available(SUBSCRIPTION)
