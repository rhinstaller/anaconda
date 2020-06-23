#
# Copyright (C) 2019  Red Hat, Inc.
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
# Red Hat Author(s): Vendula Poncova <vponcova@redhat.com>
#
import sys
import unittest

from unittest.mock import Mock, patch, create_autospec
from pyanaconda.ui import UserInterface
from pyanaconda.ui.common import StandaloneSpoke, Hub
from tests.nosetests.pyanaconda_tests import patch_dbus_get_proxy


class SimpleUITestCase(unittest.TestCase):
    """Simple test case for UI.

    The goal of this test is to at least import all UI elements.
    """
    maxDiff = None

    def setUp(self):
        self.interface = None
        self.data = Mock()
        self.storage = Mock()
        self.payload = Mock()

        # Mock the TimezoneMap hack.
        sys.modules["gi.repository.TimezoneMap"] = Mock()

    def tearDown(self):
        sys.modules.pop("gi.repository.TimezoneMap")

    @property
    def paths(self):
        return self.interface.paths

    @property
    def hubs(self):
        return self.interface._list_hubs()

    @property
    def action_classes(self):
        return self.interface._collectActionClasses(self.paths["spokes"], StandaloneSpoke)

    @property
    def ordered_action_classes(self):
        return self.interface._orderActionClasses(self.action_classes, self.hubs)

    def _get_action_class_names(self):
        classes = self.interface._orderActionClasses(self.action_classes, self.hubs)
        return [cls.__name__ for cls in classes]

    def _get_categories(self, hub_class):
        hub = hub_class(self.data, self.storage, self.payload)
        hub.set_path("spokes", self.paths["spokes"])
        hub.set_path("categories", self.paths["categories"])
        return hub._collectCategoriesAndSpokes()

    def _get_category_names(self, hub_class):
        categories = self._get_categories(hub_class)
        return {c.__name__:  list(sorted(s.__name__ for s in categories[c])) for c in categories}

    def _check_spokes_priority_uniqueness(self):
        # Force us to always decide order of standalone spokes based on priority not by name.
        # This will ordering errors easier to spot.
        spokes = self.ordered_action_classes

        for hub in self.hubs:
            pre_spokes = UserInterface._filter_spokes_by_pre_for_hub_reference(spokes, hub)
            self._check_spokes_with_same_priority(pre_spokes)
            post_spokes = UserInterface._filter_spokes_by_post_for_hub_reference(spokes, hub)
            self._check_spokes_with_same_priority(post_spokes)

    def _check_spokes_with_same_priority(self, spokes):
        res = dict()

        for spoke in spokes:
            priority = spoke.priority
            name = spoke.__name__

            if priority in res:
                msg = "Spokes {} and {} have the same priority!".format(res[priority], name)
                self.assertNotIn(priority, res, msg)
            res[priority] = name

    @patch_dbus_get_proxy
    def tui_test(self, proxy_getter):
        # Create the interface.
        from pyanaconda.ui.tui import TextUserInterface
        self.interface = TextUserInterface(self.storage, self.payload)

        # Check the hubs
        from pyanaconda.ui.tui.hubs.summary import SummaryHub
        self.assertEqual(self.hubs, [SummaryHub])

        # Check the actions classes.
        self.assertEqual(self._get_action_class_names(), [
            "UnsupportedHardwareSpoke",
            "KernelWarningSpoke",
            "SummaryHub",
            "ProgressSpoke"
        ])

        # Check the Summary hub.
        self.assertEqual(self._get_category_names(SummaryHub), {
            'CustomizationCategory': [],
            'LocalizationCategory': [
                'LangSpoke',
                'TimeSpoke'
            ],
            'SoftwareCategory': [
                'SoftwareSpoke',
                'SourceSpoke'
            ],
            'SystemCategory': [
                'NetworkSpoke',
                'ShellSpoke',
                'StorageSpoke'
            ],
            'UserSettingsCategory': [
                'PasswordSpoke',
                'UserSpoke'
            ]
        })

        # Force us to always decide order of standalone spokes based on priority not by name.
        # This will ordering errors easier to spot.
        self._check_spokes_priority_uniqueness()

    @patch_dbus_get_proxy
    @patch("pyanaconda.ui.gui.Gtk.Builder")
    @patch("pyanaconda.ui.gui.meh")
    @patch("pyanaconda.ui.gui.MainWindow")
    @patch("pyanaconda.ui.gui.ANACONDA_WINDOW_GROUP")
    def gui_test(self, window_group, window, meh, builder, proxy_getter):
        # Create the interface.
        from pyanaconda.ui.gui import GraphicalUserInterface
        self.interface = GraphicalUserInterface(self.storage, self.payload)

        # Check the hubs.
        from pyanaconda.ui.gui.hubs.summary import SummaryHub
        self.assertEqual(self.hubs, [SummaryHub])

        # Check the actions classes.
        self.assertEqual(self._get_action_class_names(), [
            'WelcomeLanguageSpoke',
            'NetworkStandaloneSpoke',
            'SummaryHub',
            'ProgressSpoke'
        ])

        # Check the Summary hub.
        self.assertEqual(self._get_category_names(SummaryHub), {
            'CustomizationCategory': [],
            'LocalizationCategory': [
                'DatetimeSpoke',
                'KeyboardSpoke',
                'LangsupportSpoke'
            ],
            'SoftwareCategory': [
                'SoftwareSelectionSpoke',
                'SourceSpoke',
                'SubscriptionSpoke'
            ],
            'SystemCategory': [
                'CustomPartitioningSpoke',
                'FilterSpoke',
                'NetworkSpoke',
                'StorageSpoke'
            ],
            'UserSettingsCategory': [
                'PasswordSpoke',
                'UserSpoke'
            ]}
        )

        # Force us to always decide order of standalone spokes based on priority not by name.
        # This will ordering errors easier to spot.
        self._check_spokes_priority_uniqueness()

    def correct_spokes_ordering_test(self):
        # create fake spokes with the same priority
        hub = create_autospec(Hub)

        class SpokeA(StandaloneSpoke):  # pylint: disable=abstract-method
            preForHub = hub

        class SpokeB(StandaloneSpoke):  # pylint: disable=abstract-method
            preForHub = hub

        class SpokeC(StandaloneSpoke):  # pylint: disable=abstract-method
            preForHub = hub

        class SpokeD(StandaloneSpoke):  # pylint: disable=abstract-method
            postForHub = hub

        class SpokeE(StandaloneSpoke):  # pylint: disable=abstract-method
            postForHub = hub

        list1 = [SpokeC, SpokeB, SpokeE, SpokeD, SpokeA]

        # the input list ordering shouldn't matter sorting should be based on class names
        self.assertEqual([SpokeA, SpokeB, SpokeC, hub, SpokeD, SpokeE],
                         UserInterface._orderActionClasses(list1, [hub]))
