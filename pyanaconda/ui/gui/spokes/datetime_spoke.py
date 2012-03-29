# Datetime configuration spoke class
#
# Copyright (C) 2012 Red Hat, Inc.
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
# Red Hat Author(s): Vratislav Podzimek <vpodzime@redhat.com>
#

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)
N_ = lambda x: x

from gi.repository import AnacondaWidgets, GLib

from pyanaconda.ui.gui import UIObject
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.categories.localization import LocalizationCategory

__all__ = ["DatetimeSpoke"]

class DatetimeSpoke(NormalSpoke):
    builderObjects = ["datetimeWindow", "days", "months", "years", "regions",
                      "cities", "upImage", "upImage1", "upImage2", "downImage",
                      "downImage1", "downImage2", "downImage3", "citiesFilter",
                      "daysFilter", "citiesSort", "regionsSort"]
    mainWidgetName = "datetimeWindow"
    uiFile = "spokes/datetime_spoke.ui"

    category = LocalizationCategory

    icon = "preferences-system-date-and-time-symbolic"
    title = N_("DATE & TIME")

    def __init__(self, *args):
        NormalSpoke.__init__(self, *args)

    def initialize(self, cb=None):
        NormalSpoke.initialize(self, cb)
        self._daysStore = self.builder.get_object("days")
        self._monthsStore = self.builder.get_object("months")
        self._yearsStore = self.builder.get_object("years")
        self._regionsStore = self.builder.get_object("regions")
        self._citiesStore = self.builder.get_object("cities")
        self._tzmap = self.builder.get_object("tzmap")

        for day in xrange(1, 32):
            self.add_to_store(self._daysStore, day)

        for month in xrange(1, 13):
            self.add_to_store(self._monthsStore, month)

        for year in xrange(1990, 2051):
            self.add_to_store(self._yearsStore, year)

        #TODO: replace by regions from pytz
        for region in ["America", "Europe"]:
            self.add_to_store(self._regionsStore, region)

        #TODO: replace by cities from pytz
        for city in ["Westford", "Brno"]:
            self.add_to_store(self._regionsStore, region)

        self._tzmap.set_timezone("Europe/Prague")

    @property
    def status(self):
        return _("Something selected")

    def apply(self):
        pass

    @property
    def completed(self):
        #Always completed -- some date, time and timezone are always set
        return True

    def refresh(self):
        #TODO: setup timer here!
        pass

    def add_to_store(self, store, item):
        store.append([item])
