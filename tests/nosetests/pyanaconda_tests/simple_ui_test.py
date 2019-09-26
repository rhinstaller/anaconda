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

from unittest.mock import Mock, patch
from pyanaconda.ui.common import StandaloneSpoke
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
                'SourceSpoke'
            ],
            'SystemCategory': [
                'BlivetGuiSpoke',
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
