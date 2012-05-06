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
import datetime, os

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

    def initialize(self):
        NormalSpoke.initialize(self)
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

        self._radioButton24h = self.builder.get_object("timeFormatRB")
        if self._radioButton24h.get_active():
            self._set_amPm_part_sensitive(False)

        self._hoursLabel = self.builder.get_object("hoursLabel")
        self._minutesLabel = self.builder.get_object("minutesLabel")

        self._tzmap.set_timezone("Europe/Prague")

    @property
    def status(self):
        if self.data.timezone.timezone:
            return _("%s timezone") % self.data.timezone.timezone
        else:
            return _("%s timezone") % self._tzmap.get_timezone()

    def apply(self):
        GLib.source_remove(self._update_datetime_timer_id)
        self.data.timezone.timezone = self._tzmap.get_timezone()

    @property
    def completed(self):
        #Always completed -- some date, time and timezone are always set
        return True

    def refresh(self):
        self._update_datetime()

        #update the displayed time
        self._update_datetime_timer_id = GLib.timeout_add_seconds(1,
                                                    self._update_datetime)
        self._start_updating_timer_id = None

        if self.data.timezone.timezone:
            self._tzmap.set_timezone(self.data.timezone.timezone)

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

    def _get_active_city(self):
        cities_model = self._cityCombo.get_model()
        cities_iter = self._cityCombo.get_active_iter()
        if not cities_iter:
            return None

        return cities_model[cities_iter][0]

    def _get_active_region(self):
        regions_model = self._regionCombo.get_model()
        regions_iter = self._regionCombo.get_active_iter()
        if not regions_iter:
            return None

        return regions_model[regions_iter][0]

    def city_in_region(self, model, itr, user_data=None):
        if not itr:
            return False
        city = model[itr][0]

        region = self._get_active_region()
        if not region:
            return False

        return city in self._regions_zones[region]

    def _set_amPm_part_sensitive(self, sensitive):
        amPmUp = self.builder.get_object("amPmUpButton")
        amPmDown = self.builder.get_object("amPmDownButton")
        amPmLabel = self.builder.get_object("amPmLabel")

        for widget in (amPmUp, amPmDown, amPmLabel):
            widget.set_sensitive(sensitive)

    def _to_amPm(self, hours):
        if hours >= 12:
            day_phase = "PM"
        else:
            day_phase = "AM"

        new_hours = ((hours - 1) % 12) + 1

        return (new_hours, day_phase)

    def _to_24h(self, hours, day_phase):
        correction = 0

        if day_phase == "AM" and hours == 12:
            correction = -12

        elif day_phase == "PM" and hours != 12:
            correction = 12

        return (hours + correction) % 24

    def _update_datetime(self):
        now = datetime.datetime.now()
        if self._radioButton24h.get_active():
            self._hoursLabel.set_text("%0.2d" % now.hour)
        else:
            hours, amPm = self._to_amPm(now.hour)
            self._hoursLabel.set_text("%0.2d" % hours)
            amPm_label = self.builder.get_object("amPmLabel")
            amPm_label.set_text(amPm)

        self._minutesLabel.set_text("%0.2d" % now.minute)

        self._set_combo_selection(self._dayCombo, now.day)
        self._set_combo_selection(self._monthCombo,
                            datetime.date(2000, now.month, 1).strftime('%B'))
        self._set_combo_selection(self._yearCombo, now.year)

        #GLib's timer is driven by the return value of the function.
        #It runs the fuction periodically while the returned value
        #is True.
        return True

    def _save_system_time(self):
        #TODO: save system time here

        self._update_datetime_timer_id = GLib.timeout_add_seconds(1,
                                                        self._update_datetime)

        #run only once (after first 2 seconds of inactivity)
        return False

    def _stop_and_maybe_start_time_updating(self):
        """
        This method is called in every time-setting button's callback.
        It removes the timer for updating displayed time (do not want to change
        it wile user does it manually) and allows us to set new system time
        only after 2 seconds long idle on time-setting buttons. This is done
        by the _start_updating_timer that is reset in this method. So when
        there is a 2 seconds long idle on time-setting buttons,
        self._save_system_time method is invoked. Since it returns False,
        this timer is then removed and only reactivated in this method (thus
        in some time-setting button's callback).

        """

        #stop time updating
        GLib.source_remove(self._update_datetime_timer_id)

        #stop previous 2 seconds timer (see below)
        if self._start_updating_timer_id:
            GLib.source_remove(self._start_updating_timer_id)

        #let the user change time and after 2 seconds of inactivity save it as
        #the system time and start updating the displayed time
        self._start_updating_timer_id = GLib.timeout_add_seconds(2,
                                                    self._save_system_time)

    def _set_combo_selection(self, combo, item):
        model = combo.get_model()
        if not model:
            return False

        itr = model.get_iter_first()
        while itr:
            if model[itr][0] == item:
                combo.set_active_iter(itr)
                return True

            itr = model.iter_next(itr)

        return False

    def on_up_hours_clicked(self, *args):
        self._stop_and_maybe_start_time_updating()

        hours_label = self.builder.get_object("hoursLabel")
        hours = int(hours_label.get_text())

        button24h = self.builder.get_object("timeFormatRB")
        if button24h.get_active():
            new_hours = (hours + 1) % 24
        else:
            amPm_label = self.builder.get_object("amPmLabel")
            amPm = amPm_label.get_text()
            #let's not deal with magical AM/PM arithmetics
            new_hours = self._to_24h(hours, amPm)
            new_hours, new_amPm = self._to_amPm((new_hours + 1) % 24)
            amPm_label.set_text(new_amPm)

        new_hours_str = "%0.2d" % new_hours
        hours_label.set_text(new_hours_str)

    def on_down_hours_clicked(self, *args):
        self._stop_and_maybe_start_time_updating()

        hours_label = self.builder.get_object("hoursLabel")
        hours = int(hours_label.get_text())

        button24h = self.builder.get_object("timeFormatRB")
        if button24h.get_active():
            new_hours = (hours - 1) % 24
        else:
            amPm_label = self.builder.get_object("amPmLabel")
            amPm = amPm_label.get_text()
            #let's not deal with magical AM/PM arithmetics
            new_hours = self._to_24h(hours, amPm)
            new_hours, new_amPm = self._to_amPm((new_hours - 1) % 24)
            amPm_label.set_text(new_amPm)

        new_hours_str = "%0.2d" % new_hours
        hours_label.set_text(new_hours_str)

    def on_up_minutes_clicked(self, *args):
        self._stop_and_maybe_start_time_updating()

        minutes_label = self.builder.get_object("minutesLabel")
        minutes = int(minutes_label.get_text())
        minutes_str = "%0.2d" % ((minutes + 1) % 60)
        minutes_label.set_text(minutes_str)
        pass

    def on_down_minutes_clicked(self, *args):
        self._stop_and_maybe_start_time_updating()

        minutes_label = self.builder.get_object("minutesLabel")
        minutes = int(minutes_label.get_text())
        minutes_str = "%0.2d" % ((minutes - 1) % 60)
        minutes_label.set_text(minutes_str)

    def on_up_ampm_clicked(self, *args):
        self._stop_and_maybe_start_time_updating()

        label = self.builder.get_object("amPmLabel")
        if label.get_text() == "AM":
            label.set_text("PM")
        else:
            label.set_text("AM")

    def on_down_ampm_clicked(self, *args):
        self._stop_and_maybe_start_time_updating()

        label = self.builder.get_object("amPmLabel")
        if label.get_text() == "AM":
            label.set_text("PM")
        else:
            label.set_text("AM")

    def on_region_changed(self, *args):
        self._citiesFilter.refilter()

        # Attempt to set the city to the first one available in this newly
        # selected region.
        region = self._get_active_region()
        if not region:
            return

        zone = self._regions_zones[region]
        firstCity = sorted(list(zone))[0]

        self._set_combo_selection(self._cityCombo, firstCity)
        self._cityCombo.emit("changed")

    def on_city_changed(self, *args):
        timezone = None

        region = self._get_active_region()
        city = self._get_active_city()

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

        self._set_combo_selection(self._regionCombo, region)
        self._set_combo_selection(self._cityCombo, city)
        os.environ["TZ"] = timezone
        self._update_datetime()

    def on_timeformat_changed(self, button24h, *args):
        hours_label = self.builder.get_object("hoursLabel")
        hours = int(hours_label.get_text())
        amPm_label = self.builder.get_object("amPmLabel")
        amPm = amPm_label.get_text()

        #connected to 24-hour radio button
        if button24h.get_active():
            self._set_amPm_part_sensitive(False)
            new_hours = self._to_24h(hours, amPm)

        else:
            self._set_amPm_part_sensitive(True)
            new_hours, new_amPm = self._to_amPm(hours)
            amPm_label.set_text(new_amPm)

        hours_label.set_text("%0.2d" % new_hours)

