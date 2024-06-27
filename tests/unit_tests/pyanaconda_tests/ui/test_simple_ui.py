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
import os
import re
import unittest

from unittest.mock import Mock, patch, create_autospec
from pyanaconda.ui import UserInterface
from pyanaconda.ui.common import StandaloneSpoke, Hub, Screen
from tests.unit_tests.pyanaconda_tests import patch_dbus_get_proxy


# blivet-gui is supported on Fedora, but not ELN/CentOS/RHEL
HAVE_BLIVET_GUI = os.path.exists("/usr/bin/blivet-gui")


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

    @property
    def paths(self):
        return self.interface.paths

    @property
    def hubs(self):
        return self.interface._list_hubs()

    @property
    def action_classes(self):
        actions = self.interface._collectActionClasses(self.paths["spokes"], StandaloneSpoke)
        return self.interface._orderActionClasses(actions, self.hubs)

    @property
    def screens(self):
        screens = self._get_subclasses(Screen)
        prefixes = set(mask % "" for mask, _ in self.paths["hubs"])
        prefixes.update(mask % "" for mask, _ in self.paths["spokes"])
        return self._filter_prefixes(prefixes, screens)

    def _get_subclasses(self, cls):
        subclasses = set()

        for subcls in cls.__subclasses__():
            subclasses.add(subcls)
            subclasses.update(self._get_subclasses(subcls))

        return subclasses

    def _filter_prefixes(self, prefixes, classes):
        return list(filter(lambda s: any(map(s.__module__.startswith, prefixes)), classes))

    def _get_screen_ids(self, screens):
        return [cls.get_screen_id() for cls in screens]

    def _check_hubs(self, expected_hubs):
        """Check hub classes."""
        assert self.hubs == expected_hubs

    def _check_actions(self, expected_ids):
        """Check the action classes."""
        screen_ids = self._get_screen_ids(self.action_classes)
        assert screen_ids == expected_ids

    def _check_categories(self, hub_class, expected_ids):
        """Check categories and spoke classes."""
        categories = self._get_categories(hub_class)
        actual_ids = {c.__name__:  self._get_screen_ids(s) for c, s in categories.items()}

        assert {c: sorted(s) for c, s in actual_ids.items()} \
            == {c: sorted(s) for c, s in expected_ids.items()}

    def _get_categories(self, hub_class):
        hub = hub_class(self.data, self.storage, self.payload)
        hub.set_path("spokes", self.paths["spokes"])
        hub.set_path("categories", self.paths["categories"])
        return hub._collectCategoriesAndSpokes()

    def _check_screens(self, expected_ids):
        """Check the screens."""
        screen_ids = set()

        for screen in self.screens:
            screen_id = screen.get_screen_id()

            # FIXME: Require the screen id.
            if screen_id is None:
                continue

            # Check the format of the screen id.
            assert re.fullmatch(r'[a-z][a-z-]*', screen_id)

            # Don't mention 'hub' or 'spoke' in the screen id.
            assert "hub" not in screen_id.split("-")
            assert "spoke" not in screen_id.split("-")

            # Check uniqueness of screen ids.
            assert screen_id not in screen_ids
            screen_ids.add(screen_id)

        # Check the expected ids.
        assert sorted(screen_ids) == sorted(expected_ids)

    def _check_interface(self):
        """Check the user interface."""
        self._check_spokes_priority_uniqueness()

    def _check_spokes_priority_uniqueness(self):
        # Force us to always decide order of standalone spokes based on priority not by name.
        # This will ordering errors easier to spot.
        spokes = self.action_classes

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
                msg = f"Spokes {res[priority]} and {name} have the same priority!"
                assert priority not in res, msg
            res[priority] = name

    @patch_dbus_get_proxy
    def test_tui(self, proxy_getter):
        # Create the interface.
        from pyanaconda.ui.tui import TextUserInterface
        self.interface = TextUserInterface(self.storage, self.payload)

        # Check the hubs
        from pyanaconda.ui.tui.hubs.summary import SummaryHub
        self._check_hubs([SummaryHub])

        # Check the actions classes.
        self._check_actions([
            "kernel-warning",
            "installation-summary",
            "installation-progress",
        ])

        # Check the Summary hub.
        self._check_categories(SummaryHub, {
            'CustomizationCategory': [],
            'LocalizationCategory': [
                'language-configuration',
                'date-time-configuration',
            ],
            'SoftwareCategory': [
                'software-selection',
                'software-source-configuration',
            ],
            'SystemCategory': [
                'network-configuration',
                'storage-configuration',
                'shell',
            ],
            'UserSettingsCategory': [
                'root-configuration',
                'user-configuration',
            ]
        })

        # Check the screens.
        self._check_screens([
            # Warnings
            "kernel-warning",

            # Installation
            'installation-summary',
            'installation-progress',

            # Localization
            'date-time-configuration',
            'language-configuration',

            # Software
            'software-selection',
            'software-source-configuration',

            # System
            'network-configuration',
            'storage-configuration',
            'shell',

            # User settings
            'root-configuration',
            'user-configuration',
        ])

        # Run general checks on the user interface.
        self._check_interface()

    @patch_dbus_get_proxy
    @patch("pyanaconda.ui.gui.Gtk.Builder")
    @patch("pyanaconda.ui.gui.meh")
    @patch("pyanaconda.ui.gui.MainWindow")
    @patch("pyanaconda.ui.gui.ANACONDA_WINDOW_GROUP")
    def test_gui(self, window_group, window, meh, builder, proxy_getter):
        # Create the interface.
        from pyanaconda.ui.gui import GraphicalUserInterface
        self.interface = GraphicalUserInterface(self.storage, self.payload)

        # Check the hubs.
        from pyanaconda.ui.gui.hubs.summary import SummaryHub
        self._check_hubs([SummaryHub])

        # Check the actions classes.
        self._check_actions([
            'language-pre-configuration',
            'network-pre-configuration',
            'installation-summary',
            'installation-progress'
        ])

        # Check the Summary hub.
        system_category = [
            'blivet-gui-partitioning',
            'interactive-partitioning',
            'storage-advanced-configuration',
            'network-configuration',
            'storage-configuration'
        ]

        if not HAVE_BLIVET_GUI:
            system_category.remove('blivet-gui-partitioning')

        self._check_categories(SummaryHub, {
            'CustomizationCategory': [],
            'LocalizationCategory': [
                'date-time-configuration',
                'keyboard-configuration',
                'language-configuration'
            ],
            'SoftwareCategory': [
                'software-selection',
                'software-source-configuration',
                'subscription-configuration'
            ],
            'SystemCategory': system_category,
            'UserSettingsCategory': [
                'root-configuration',
                'user-configuration'
            ]
        })

        # Check the screens.
        screen_ids = [
            # Installation
            'installation-summary',
            'installation-progress',

            # Localization
            'language-pre-configuration',
            'language-configuration',
            'date-time-configuration',
            'keyboard-configuration',

            # Software
            'software-selection',
            'software-source-configuration',
            'subscription-configuration',

            # System
            'network-pre-configuration',
            'network-configuration',

            # Storage
            'storage-configuration',
            'storage-advanced-configuration',
            'interactive-partitioning',
            'blivet-gui-partitioning',

            # User settings
            'root-configuration',
            'user-configuration',
        ]

        if not HAVE_BLIVET_GUI:
            screen_ids.remove('blivet-gui-partitioning')

        self._check_screens(screen_ids)

        # Run general checks on the user interface.
        self._check_interface()

    def test_correct_spokes_ordering(self):
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
        assert [SpokeA, SpokeB, SpokeC, hub, SpokeD, SpokeE] == \
            UserInterface._orderActionClasses(list1, [hub])
