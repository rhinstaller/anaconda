#
# Copyright (C) 2018  Red Hat, Inc.
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
import unittest
from unittest.mock import Mock

from pyanaconda.modules.common.constants.services import SUBSCRIPTION
from pyanaconda.modules.subscription.subscription import SubscriptionInterface, SubscriptionModule
from tests.nosetests.pyanaconda_tests import check_kickstart_interface


class SubscriptionInterfaceTestCase(unittest.TestCase):
    """Test DBus interface for the subscription module."""

    def setUp(self):
        """Set up the subscription module."""
        self.subscription_module = SubscriptionModule()
        self.subscription_interface = SubscriptionInterface(self.subscription_module)

        # Connect to the properties changed signal.
        self.callback = Mock()
        self.subscription_interface.PropertiesChanged.connect(self.callback)

    def kickstart_properties_test(self):
        """Test kickstart properties."""
        self.assertEqual(self.subscription_interface.KickstartCommands, ["syspurpose"])
        self.assertEqual(self.subscription_interface.KickstartSections, [])
        self.assertEqual(self.subscription_interface.KickstartAddons, [])
        self.callback.assert_not_called()

    def default_property_values_test(self):
        """Test the default subscription module values are as expected."""
        self.assertEqual(self.subscription_interface.Role, "")
        self.assertEqual(self.subscription_interface.SLA, "")
        self.assertEqual(self.subscription_interface.Usage, "")
        self.assertEqual(self.subscription_interface.Addons, [])
        # check the lists of valid values look reasonably sane:
        # - they are either an empty list
        # - or they contain a non zero amount of items
        valid_roles = self.subscription_interface.ValidRoles
        valid_slas = self.subscription_interface.ValidSLAs
        valid_usage_types = self.subscription_interface.ValidUsageTypes
        self.assertTrue(len(valid_roles) > 0 or valid_roles == [])
        self.assertTrue(len(valid_slas) > 0 or valid_slas == [])
        self.assertTrue(len(valid_usage_types) > 0 or valid_usage_types == [])

    def set_role_test(self):
        """Test if setting role from DBUS works correctly."""
        self.subscription_interface.SetRole("FOO ROLE")
        self.assertEqual(self.subscription_interface.Role, "FOO ROLE")
        self.callback.assert_called_once_with(SUBSCRIPTION.interface_name, {'Role': 'FOO ROLE', 'IsSystemPurposeSet': True}, [])

    def set_sla_test(self):
        """Test if setting SLA from DBUS works correctly."""
        self.subscription_interface.SetSLA("BAR SLA")
        self.assertEqual(self.subscription_interface.SLA, "BAR SLA")
        self.callback.assert_called_once_with(SUBSCRIPTION.interface_name, {'SLA': 'BAR SLA', 'IsSystemPurposeSet': True}, [])

    def set_usage_test(self):
        """Test if setting usage from DBUS works correctly."""
        self.subscription_interface.SetUsage("BAZ USAGE")
        self.callback.assert_called_once_with(SUBSCRIPTION.interface_name, {'Usage': 'BAZ USAGE', 'IsSystemPurposeSet': True}, [])
        self.assertEqual(self.subscription_interface.Usage, "BAZ USAGE")

    def set_addons_test(self):
        """Test if setting addons from DBUS works correctly."""
        self.subscription_interface.SetAddons(["foo product", "bar feature"])
        self.callback.assert_called_once_with(SUBSCRIPTION.interface_name, {'Addons': ["foo product", "bar feature"],
                                                                            'IsSystemPurposeSet': True}, [])
        self.assertEqual(self.subscription_interface.Addons, ["foo product", "bar feature"])

    def ks_set_role_test(self):
        """Test if setting role from kickstart works correctly."""
        self.subscription_interface.ReadKickstart('syspurpose --role="ROLE FOO"')
        self.assertEqual(self.subscription_interface.Role, 'ROLE FOO')

    def ks_set_sla_test(self):
        """Test if setting SLA from kickstart works correctly."""
        self.subscription_interface.ReadKickstart('syspurpose --sla="SLA BAR"')
        self.assertEqual(self.subscription_interface.SLA, 'SLA BAR')

    def ks_set_usage_test(self):
        """Test if setting usage from kickstart works correctly."""
        self.subscription_interface.ReadKickstart('syspurpose --usage="USAGE BAZ"')
        self.assertEqual(self.subscription_interface.Usage, 'USAGE BAZ')

    def ks_set_addons_test(self):
        """Test if setting addons from kickstart works correctly."""
        self.subscription_interface.ReadKickstart('syspurpose --addon="Foo Product" --addon="Bar Feature"')
        self.assertEqual(self.subscription_interface.Addons, ["Foo Product", "Bar Feature"])

    def ks_set_all_test(self):
        """Test if setting all options from kickstart works correctly."""
        self.subscription_interface.ReadKickstart('syspurpose --role="FOO" --sla="BAR" --usage="BAZ" --addon="Foo Product" --addon="Bar Feature"')
        self.assertEqual(self.subscription_interface.Role, 'FOO')
        self.assertEqual(self.subscription_interface.SLA, 'BAR')
        self.assertEqual(self.subscription_interface.Usage, 'BAZ')
        self.assertEqual(self.subscription_interface.Addons, ["Foo Product", "Bar Feature"])

    def ks_set_nothing_test(self):
        """Test what happens if just the syspurpose command is used."""
        self.subscription_interface.ReadKickstart('syspurpose')
        self.assertEqual(self.subscription_interface.Role, "")
        self.assertEqual(self.subscription_interface.SLA, "")
        self.assertEqual(self.subscription_interface.Usage, "")
        self.assertEqual(self.subscription_interface.Addons, [])

    def _test_kickstart(self, ks_in, ks_out):
        check_kickstart_interface(self, self.subscription_interface, ks_in, ks_out)

    def ks_out_no_kickstart_test(self):
        """Test with no kickstart."""
        ks_in = None
        ks_out = ""
        self._test_kickstart(ks_in, ks_out)

    def ks_out_command_only_test(self):
        """Test with only syspurpose command being used."""
        ks_in = "syspurpose"
        ks_out = ""
        self._test_kickstart(ks_in, ks_out)

    def ks_out_set_role_test(self):
        """Check kickstart with role being used."""
        ks_in = 'syspurpose --role="FOO ROLE"'
        ks_out = '# Intended system purpose\nsyspurpose --role="FOO ROLE"'
        self._test_kickstart(ks_in, ks_out)

    def ks_out_set_sla_test(self):
        """Check kickstart with SLA being used."""
        ks_in = 'syspurpose --sla="FOO SLA"'
        ks_out = '# Intended system purpose\nsyspurpose --sla="FOO SLA"'
        self._test_kickstart(ks_in, ks_out)

    def ks_out_set_usage_test(self):
        """Check kickstart with usage being used."""
        ks_in = 'syspurpose --usage="FOO USAGE"'
        ks_out = '# Intended system purpose\nsyspurpose --usage="FOO USAGE"'
        self._test_kickstart(ks_in, ks_out)

    def ks_out_set_addons_test(self):
        """Check kickstart with addons being used."""
        ks_in = 'syspurpose --addon="Foo Product" --addon="Bar Feature"'
        ks_out = '# Intended system purpose\nsyspurpose --addon="Foo Product" --addon="Bar Feature"'
        self._test_kickstart(ks_in, ks_out)

    def ks_out_set_all_usage_test(self):
        """Check kickstart with all options being used."""
        ks_in = 'syspurpose --role="FOO" --sla="BAR" --usage="BAZ" --addon="Foo Product" --addon="Bar Feature"'
        ks_out = '# Intended system purpose\nsyspurpose --role="FOO" --sla="BAR" --usage="BAZ" --addon="Foo Product" --addon="Bar Feature"'
        self._test_kickstart(ks_in, ks_out)
