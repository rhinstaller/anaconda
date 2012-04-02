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

from pyanaconda import localization
import datetime

__all__ = ["DatetimeSpoke"]

class DatetimeSpoke(NormalSpoke):
    builderObjects = ["datetimeWindow",
                      "days", "months", "years", "regions", "cities",
                      "upImage", "upImage1", "upImage2", "downImage",
                      "downImage1", "downImage2", "downImage3",
                      "citiesFilter", "daysFilter", "citiesSort", "regionsSort",
                      ]

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

        self._regions_zones = localization.get_all_regions_and_timezones()

        for day in xrange(1, 32):
            self.add_to_store(self._daysStore, day)

        self._months_nums = dict()
        for i in xrange(1, 13):
            #a bit hacky way, but should return the translated string
            #TODO: how to handle language change? Clear and populate again?
            month = datetime.date(2000, i, 1).strftime('%B')
            self.add_to_store(self._monthsStore, month)
            self._months_nums[month] = i

        for year in xrange(1990, 2051):
            self.add_to_store(self._yearsStore, year)

        for region in self._regions_zones.keys():
            self.add_to_store(self._regionsStore, region)
            for city in self._regions_zones[region]:
                self.add_to_store(self._citiesStore, city)

        self._regionCombo = self.builder.get_object("regionCombobox")
        self._cityCombo = self.builder.get_object("cityCombobox")
        self._monthCombo = self.builder.get_object("monthCombobox")
        self._dayCombo = self.builder.get_object("dayCombobox")
        self._yearCombo = self.builder.get_object("yearCombobox")

        self._daysFilter = self.builder.get_object("daysFilter")
        self._daysFilter.set_visible_func(self.existing_date, None)

        self._citiesFilter = self.builder.get_object("citiesFilter")
        self._citiesFilter.set_visible_func(self.city_in_region, None)

        self._citiesSort = self.builder.get_object("citiesSort")
        self._citiesSort.set_sort_column_id(0, 0) #column 0, Ascending

        self._mod_hours = 13 #TODO: change on timeformat RB change
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

    def existing_date(self, model, itr, user_data=None):
        if not itr:
            return False
        day = model[itr][0]

        #days 1-28 are in every month every year
        if day < 29:
            return True

        months_model = self._monthCombo.get_model()
        months_iter = self._monthCombo.get_active_iter()
        if not months_iter:
            return True
        month = months_model[months_iter][0]

        years_model = self._yearCombo.get_model()
        years_iter = self._yearCombo.get_active_iter()
        if not years_iter:
            return True
        year = years_model[years_iter][0]

        try:
            datetime.date(year, self._months_nums[month], day)
            return True
        except ValueError as valerr:
            return False

    def city_in_region(self, model, itr, user_data=None):
        if not itr:
            return False
        city = model[itr][0]

        regions_model = self._regionCombo.get_model()
        regions_iter = self._regionCombo.get_active_iter()
        if not regions_iter:
            return False
        region = regions_model[regions_iter][0]

        return city in self._regions_zones[region]

    def on_up_hours_clicked(self, *args):
        hours_label = self.builder.get_object("hoursLabel")
        hours = int(hours_label.get_text())
        hours_str = "%0.2d" % ((hours + 1) % self._mod_hours)
        hours_label.set_text(hours_str)

    def on_down_hours_clicked(self, *args):
        hours_label = self.builder.get_object("hoursLabel")
        hours = int(hours_label.get_text())
        hours_str = "%0.2d" % ((hours - 1) % self._mod_hours)
        hours_label.set_text(hours_str)

    def on_up_minutes_clicked(self, *args):
        minutes_label = self.builder.get_object("minutesLabel")
        minutes = int(minutes_label.get_text())
        minutes_str = "%0.2d" % ((minutes + 1) % 60)
        minutes_label.set_text(minutes_str)
        pass

    def on_down_minutes_clicked(self, *args):
        minutes_label = self.builder.get_object("minutesLabel")
        minutes = int(minutes_label.get_text())
        minutes_str = "%0.2d" % ((minutes - 1) % 60)
        minutes_label.set_text(minutes_str)

    def on_up_ampm_clicked(self, *args):
        label = self.builder.get_object("amPmLabel")
        if label.get_text() == "AM":
            label.set_text("PM")
        else:
            label.set_text("AM")

    def on_down_ampm_clicked(self, *args):
        label = self.builder.get_object("amPmLabel")
        if label.get_text() == "AM":
            label.set_text("PM")
        else:
            label.set_text("AM")

    def on_region_changed(self, *args):
        self._citiesFilter.refilter()

    def on_city_changed(self, *args):
        timezone = None

        regions_model = self._regionCombo.get_model()
        regions_iter = self._regionCombo.get_active_iter()
        if regions_iter:
            region = regions_model[regions_iter][0]
        else:
            region = None

        cities_model = self._cityCombo.get_model()
        cities_iter = self._cityCombo.get_active_iter()
        if cities_iter: #there can be no city selected
            city = cities_model[cities_iter][0]
        else:
            city = None

        if city and region:
            timezone = region + "/" + city

        if timezone and (self._tzmap.get_timezone() != timezone):
            self._tzmap.set_timezone(timezone)

    def on_month_changed(self, *args):
        self._daysFilter.refilter()

    def on_day_changed(self, *args):
        pass

    def on_year_changed(self, *args):
        self._daysFilter.refilter()

    def on_timezone_changed(self, tz_map, timezone):
        fields = timezone.split("/", 1)
        if len(fields) == 1:
            #initial ""
            return
        else:
            region, city = fields

        itr = self._regionsStore.get_iter_first()
        while itr:
            if self._regionsStore[itr][0] == region:
                self._regionCombo.set_active_iter(itr)
                break

            itr = self._regionsStore.iter_next(itr)

        itr = self._citiesSort.get_iter_first()
        while itr:
            if self._citiesSort[itr][0] == city:
                self._cityCombo.set_active_iter(itr)
                break

            itr = self._citiesSort.iter_next(itr)

    def on_timeformat_changed(self, *args):
        pass
