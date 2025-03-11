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
#
import unittest

import pytest

from pyanaconda.core.constants import SOURCE_TYPE_CDN
from pyanaconda.modules.common.constants.services import BOSS, SUBSCRIPTION
from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.payloads.source.cdn.cdn import CDNSourceModule
from pyanaconda.modules.payloads.source.cdn.cdn_interface import CDNSourceInterface
from pyanaconda.modules.payloads.source.cdn.initialization import SetUpCDNSourceTask
from tests.unit_tests.pyanaconda_tests import patch_dbus_get_proxy_with_cache


class CDNSourceInterfaceTestCase(unittest.TestCase):
    """Test the DBus interface of the CDN source module."""

    def setUp(self):
        self.module = CDNSourceModule()
        self.interface = CDNSourceInterface(self.module)

    def test_type(self):
        """Test the type of CDN."""
        assert SOURCE_TYPE_CDN == self.interface.Type

    def test_description(self):
        """Test the description of CDN."""
        assert "Red Hat CDN" == self.interface.Description

    def test_required_space(self):
        """Test the required_space property."""
        assert self.module.required_space == 0

    def test_repr(self):
        assert repr(self.module) == "Source(type='CDN')"


class CDNSourceModuleTestCase(unittest.TestCase):
    """Test the CDN source module."""

    def setUp(self):
        self.module = CDNSourceModule()
        self.interface = CDNSourceInterface(self.module)

    def test_set_up_with_tasks(self):
        """Test the set_up_with_tasks method."""
        tasks = self.module.set_up_with_tasks()
        assert len(tasks) == 1
        assert isinstance(tasks[0], SetUpCDNSourceTask)


class SetUpCDNSourceTaskTestCase(unittest.TestCase):
    """Test the SetUpCDNSourceTask task."""

    @patch_dbus_get_proxy_with_cache
    def test_disabled_module(self, proxy_getter):
        """Run the SetUpCDNSourceTask task with a disabled module."""
        boss_proxy = BOSS.get_proxy()
        boss_proxy.GetModules.return_value = []

        with pytest.raises(SourceSetupError) as cm:
            task = SetUpCDNSourceTask()
            task.run()

        assert str(cm.value) == "Red Hat CDN is unavailable for this installation."

    @patch_dbus_get_proxy_with_cache
    def test_missing_subscription(self, proxy_getter):
        """Run the SetUpCDNSourceTask task with a missing subscription."""
        boss_proxy = BOSS.get_proxy()
        boss_proxy.GetModules.return_value = [SUBSCRIPTION.service_name]

        subscription_proxy = SUBSCRIPTION.get_proxy()
        subscription_proxy.IsSubscriptionAttached = False

        with pytest.raises(SourceSetupError) as cm:
            task = SetUpCDNSourceTask()
            task.run()

        msg = "To access the Red Hat CDN, a valid Red Hat subscription is required."
        assert str(cm.value) == msg

    @patch_dbus_get_proxy_with_cache
    def test_valid_configuration(self, proxy_getter):
        """Run the SetUpCDNSourceTask task with a valid configuration."""
        boss_proxy = BOSS.get_proxy()
        boss_proxy.GetModules.return_value = [SUBSCRIPTION.service_name]

        subscription_proxy = SUBSCRIPTION.get_proxy()
        subscription_proxy.IsSubscriptionAttached = True

        task = SetUpCDNSourceTask()
        task.run()

        assert task.name == "Set up the CDN source"
