# Timezone text spoke
#
# Copyright (C) 2012  Red Hat, Inc.
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
# Red Hat Author(s): Martin Sivak <msivak@redhat.com>
#

from pyanaconda.ui.tui.spokes import NormalTUISpoke
from pyanaconda.ui.tui.simpleline import TextWidget, ColumnWidget
from pyanaconda.ui.common import FirstbootSpokeMixIn
from pyanaconda import timezone
from pyanaconda.i18n import _
from pyanaconda.constants_text import INPUT_PROCESSED

class TimeZoneSpoke(FirstbootSpokeMixIn, NormalTUISpoke):
    title = _("Timezone settings")
    category = "localization"

    def __init__(self, app, data, storage, payload, instclass):
        NormalTUISpoke.__init__(self, app, data, storage, payload, instclass)

    def initialize(self):
        self._timezones = dict((k, sorted(v)) for k,v in timezone.get_all_regions_and_timezones().iteritems())
        self._regions = [r for r in self._timezones]
        self._lower_regions = [r.lower() for r in self._timezones]

        self._zones = ["%s/%s" % (region, z) for region in self._timezones for z in self._timezones[region]]
        self._lower_zones = [z.lower().replace("_", " ") for region in self._timezones for z in self._timezones[region]] # for lowercase lookup

        self._selection = ""

    @property
    def completed(self):
        return bool(self.data.timezone.timezone)

    @property
    def mandatory(self):
        return True

    @property
    def status(self):
        if self.data.timezone.timezone:
            return _("%s timezone") % self.data.timezone.timezone
        else:
            return _("Timezone is not set.")


    def refresh(self, args = None):
        """args is None if we want a list of zones or "zone" to show all timezones in that zone."""
        NormalTUISpoke.refresh(self, args)

        if args and args in self._timezones:
            self._window += [TextWidget(_("Available timezones in region %s") % args)]
            displayed = [TextWidget(z) for z in self._timezones[args]]
        else:
            self._window += [TextWidget(_("Available regions"))]
            displayed = [TextWidget(z) for z in self._regions]

        def _prep(i, w):
            number = TextWidget("%2d)" % (i + 1))
            return ColumnWidget([(4, [number]), (None, [w])], 1)

        # split zones to three columns
        middle = len(displayed) / 3
        left = [_prep(i, w) for i,w in enumerate(displayed) if i <= middle]
        center = [_prep(i, w) for i,w in enumerate(displayed) if i > middle and i <= 2*middle]
        right = [_prep(i, w) for i,w in enumerate(displayed) if i > 2*middle]

        c = ColumnWidget([(24, left), (24, center), (24, right)], 3)
        self._window.append(c)

        return True

    def input(self, args, key):
        try:
            keyid = int(key) - 1
        except ValueError:
            if key.lower().replace("_", " ") in self._lower_zones:
                index = self._lower_zones.index(key.lower().replace("_", " "))
                self._selection = self._zones[index]
                self.apply()
                self.close()
                return INPUT_PROCESSED
            elif key.lower() in self._lower_regions:
                index = self._lower_regions.index(key.lower())
                if len(self._timezones[self._regions[index]]) == 1:
                    self._selection = "%s/%s" % (self._regions[index],
                                                 self._timezones[self._regions[index]][0])
                    self.apply()
                    self.close()
                else:
                    self.app.switch_screen(self, self._regions[id])
                return INPUT_PROCESSED
            elif key.lower() == "b":
                self.app.switch_screen(self, None)
                return INPUT_PROCESSED
            else:
                return key

        if args:
            self._selection = "%s/%s" % (args, self._timezones[args][keyid])
            self.apply()
            self.close()
        else:
            if len(self._timezones[self._regions[keyid]]) == 1:
                self._selection = "%s/%s" % (self._regions[keyid],
                                             self._timezones[self._regions[keyid]][0])
                self.apply()
                self.close()
            else:
                self.app.switch_screen(self, self._regions[keyid])
            return INPUT_PROCESSED

    def prompt(self, args = None):
        return _("Please select the timezone.\nUse numbers or type names directly [b to region list, q to quit]: ")

    def apply(self):
        self.data.timezone.timezone = self._selection
        self.data.timezone.seen = False
