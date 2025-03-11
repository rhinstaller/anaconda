# Datetime configuration spoke class
#
# Copyright (C) 2012-2013 Red Hat, Inc.
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
import copy
import datetime
import functools
import locale as locale_mod
import re
import time

import gi

from pyanaconda import flags, ntp
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import constants
from pyanaconda.core.async_utils import async_action_nowait
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.i18n import CN_, _
from pyanaconda.core.service import is_service_running, start_service, stop_service
from pyanaconda.core.threads import thread_manager
from pyanaconda.core.timer import Timer
from pyanaconda.localization import get_xlated_timezone, resolve_date_format
from pyanaconda.modules.common.constants.services import NETWORK, TIMEZONE
from pyanaconda.modules.common.structures.timezone import TimeSourceData
from pyanaconda.modules.common.util import is_module_available
from pyanaconda.ntp import NTPServerStatusCache
from pyanaconda.timezone import (
    NTP_SERVICE,
    get_all_regions_and_timezones,
    get_timezone,
    is_valid_timezone,
    parse_timezone,
    set_system_date_time,
)
from pyanaconda.ui.categories.localization import LocalizationCategory
from pyanaconda.ui.common import FirstbootSpokeMixIn
from pyanaconda.ui.communication import hubQ
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.spokes.lib.ntp_dialog import NTPConfigDialog
from pyanaconda.ui.gui.utils import blockedHandler as blocked_handler

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")

from gi.repository import Gdk, Gtk

log = get_module_logger(__name__)

__all__ = ["DatetimeSpoke"]

DEFAULT_TZ = "America/New_York"

SPLIT_NUMBER_SUFFIX_RE = re.compile(r'([^0-9]*)([-+])([0-9]+)')


def _compare_regions(reg_xlated1, reg_xlated2):
    """Compare two pairs of regions and their translations."""

    reg1, xlated1 = reg_xlated1
    reg2, xlated2 = reg_xlated2

    # sort the Etc timezones to the end
    if reg1 == "Etc" and reg2 == "Etc":
        return 0
    elif reg1 == "Etc":
        return 1
    elif reg2 == "Etc":
        return -1
    else:
        # otherwise compare the translated names
        return locale_mod.strcoll(xlated1, xlated2)


def _compare_cities(city_xlated1, city_xlated2):
    """Compare two paris of cities and their translations."""

    # if there are "cities" ending with numbers (like GMT+-X), we need to sort
    # them based on their numbers
    val1 = city_xlated1[1]
    val2 = city_xlated2[1]

    match1 = SPLIT_NUMBER_SUFFIX_RE.match(val1)
    match2 = SPLIT_NUMBER_SUFFIX_RE.match(val2)

    if match1 is None and match2 is None:
        # no +-X suffix, just compare the strings
        return locale_mod.strcoll(val1, val2)

    if match1 is None or match2 is None:
        # one with the +-X suffix, compare the prefixes
        if match1:
            prefix, _sign, _suffix = match1.groups()
            return locale_mod.strcoll(prefix, val2)
        else:
            prefix, _sign, _suffix = match2.groups()
            return locale_mod.strcoll(val1, prefix)

    # both have the +-X suffix
    prefix1, sign1, suffix1 = match1.groups()
    prefix2, sign2, suffix2 = match2.groups()

    if prefix1 == prefix2:
        # same prefixes, let signs determine

        def _cmp(a, b):
            if a < b:
                return -1
            elif a > b:
                return 1
            else:
                return 0

        return _cmp(int(sign1 + suffix1), int(sign2 + suffix2))
    else:
        # compare prefixes
        return locale_mod.strcoll(prefix1, prefix2)


def _new_date_field_box(store):
    """
    Creates new date field box (a combobox and a label in a horizontal box) for
    a given store.

    """

    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    suffix_label = Gtk.Label()
    renderer = Gtk.CellRendererText()
    combo = Gtk.ComboBox(model=store)
    combo.pack_start(renderer, False)

    # idx is column 0, string we want to show is 1
    combo.add_attribute(renderer, "text", 1)
    combo.set_wrap_width(1)

    box.pack_start(combo, False, False, 0)
    box.pack_start(suffix_label, False, False, 6)

    return (box, combo, suffix_label)


class DatetimeSpoke(FirstbootSpokeMixIn, NormalSpoke):
    """
       .. inheritance-diagram:: DatetimeSpoke
          :parts: 3
    """
    builderObjects = ["datetimeWindow",
                      "days", "months", "years", "regions", "cities",
                      "upImage", "upImage1", "upImage2", "downImage",
                      "downImage1", "downImage2", "downImage3", "configImage",
                      "citiesFilter", "daysFilter",
                      "cityCompletion", "regionCompletion",
                      ]

    mainWidgetName = "datetimeWindow"
    uiFile = "spokes/datetime_spoke.glade"
    category = LocalizationCategory
    icon = "preferences-system-time-symbolic"
    title = CN_("GUI|Spoke", "_Time & Date")

    @staticmethod
    def get_screen_id():
        """Return a unique id of this UI screen."""
        return "date-time-configuration"

    @classmethod
    def should_run(cls, environment, data):
        """Should the spoke run?"""
        if not is_module_available(TIMEZONE):
            return False

        return FirstbootSpokeMixIn.should_run(environment, data)

    def __init__(self, *args):
        NormalSpoke.__init__(self, *args)

        # taking values from the kickstart file?
        self._kickstarted = flags.flags.automatedInstall

        self._update_datetime_timer = None
        self._start_updating_timer = None
        self._shown = False
        self._tz = None

        self._timezone_module = TIMEZONE.get_proxy()
        self._network_module = NETWORK.get_proxy()

        self._ntp_servers = []
        self._ntp_servers_states = NTPServerStatusCache()

    def initialize(self):
        NormalSpoke.initialize(self)
        self.initialize_start()
        self._daysStore = self.builder.get_object("days")
        self._monthsStore = self.builder.get_object("months")
        self._yearsStore = self.builder.get_object("years")
        self._regionsStore = self.builder.get_object("regions")
        self._citiesStore = self.builder.get_object("cities")
        self._dateBox = self.builder.get_object("dateBox")

        # we need to know it the new value is the same as previous or not
        self._old_region = None
        self._old_city = None

        self._regionCombo = self.builder.get_object("regionCombobox")
        self._cityCombo = self.builder.get_object("cityCombobox")

        self._daysFilter = self.builder.get_object("daysFilter")
        self._daysFilter.set_visible_func(self.existing_date, None)

        self._citiesFilter = self.builder.get_object("citiesFilter")
        self._citiesFilter.set_visible_func(self.city_in_region, None)

        self._hoursLabel = self.builder.get_object("hoursLabel")
        self._minutesLabel = self.builder.get_object("minutesLabel")
        self._amPmUp = self.builder.get_object("amPmUpButton")
        self._amPmDown = self.builder.get_object("amPmDownButton")
        self._amPmLabel = self.builder.get_object("amPmLabel")
        self._radioButton24h = self.builder.get_object("timeFormatRB")
        self._amPmRevealer = self.builder.get_object("amPmRevealer")

        # Set the entry completions.
        # The text_column property needs to be set here. If we set
        # it in the glade file, the completion doesn't show text.
        region_completion = self.builder.get_object("regionCompletion")
        region_completion.set_text_column(0)

        city_completion = self.builder.get_object("cityCompletion")
        city_completion.set_text_column(0)

        # create widgets for displaying/configuring date
        day_box, self._dayCombo, day_label = _new_date_field_box(self._daysFilter)
        self._dayCombo.connect("changed", self.on_day_changed)
        month_box, self._monthCombo, month_label = _new_date_field_box(self._monthsStore)
        self._monthCombo.connect("changed", self.on_month_changed)
        year_box, self._yearCombo, year_label = _new_date_field_box(self._yearsStore)
        self._yearCombo.connect("changed", self.on_year_changed)

        # get the right order for date widgets and respective formats and put
        # widgets in place
        widgets, formats = resolve_date_format(year_box, month_box, day_box)
        for widget in widgets:
            self._dateBox.pack_start(widget, False, False, 0)

        self._day_format, suffix = formats[widgets.index(day_box)]
        day_label.set_text(suffix)
        self._month_format, suffix = formats[widgets.index(month_box)]
        month_label.set_text(suffix)
        self._year_format, suffix = formats[widgets.index(year_box)]
        year_label.set_text(suffix)

        self._ntp_radio_button = self.builder.get_object("ntpRadioButton")
        self._ntp_config_button = self.builder.get_object("ntpConfigButton")
        self._manual_radio_button = self.builder.get_object("manualRadioButton")

        self._regions_zones = get_all_regions_and_timezones()

        # Set the initial sensitivity of the AM/PM toggle based on the time-type selected
        self._radioButton24h.emit("toggled")

        if not conf.system.can_set_system_clock:
            self._hide_date_time_setting()

        thread_manager.add_thread(
            name=constants.THREAD_DATE_TIME,
            target=self._initialize
        )

    def _initialize(self):
        # a bit hacky way, but should return the translated strings
        for i in range(1, 32):
            day = datetime.date(2000, 1, i).strftime(self._day_format)
            self.add_to_store_idx(self._daysStore, i, day)

        for i in range(1, 13):
            month = datetime.date(2000, i, 1).strftime(self._month_format)
            self.add_to_store_idx(self._monthsStore, i, month)

        for i in range(1990, 2051):
            year = datetime.date(i, 1, 1).strftime(self._year_format)
            self.add_to_store_idx(self._yearsStore, i, year)

        cities = set()
        xlated_regions = ((region, get_xlated_timezone(region))
                          for region in self._regions_zones.keys())
        for region, xlated in sorted(xlated_regions, key=functools.cmp_to_key(_compare_regions)):
            self.add_to_store_xlated(self._regionsStore, region, xlated)
            for city in self._regions_zones[region]:
                cities.add((city, get_xlated_timezone(city)))

        for city, xlated in sorted(cities, key=functools.cmp_to_key(_compare_cities)):
            self.add_to_store_xlated(self._citiesStore, city, xlated)

        self._update_datetime_timer = None

        time_init_thread = thread_manager.get(constants.THREAD_TIME_INIT)
        if time_init_thread is not None:
            hubQ.send_message(self.__class__.__name__,
                             _("Restoring hardware time..."))
            thread_manager.wait(constants.THREAD_TIME_INIT)

        hubQ.send_ready(self.__class__.__name__)

        # report that we are done
        self.initialize_done()

    @property
    def status(self):
        timezone = self._timezone_module.Timezone

        if not timezone:
            return _("Nothing selected")

        if not is_valid_timezone(timezone):
            return _("Invalid timezone")

        return _("%s timezone") % get_xlated_timezone(timezone)

    def apply(self):
        self._shown = False

        region = self._get_active_region()
        city = self._get_active_city()

        # nothing selected, just leave the spoke and return to hub without changing anything
        if not region or not city:
            return

        self._timezone_module.SetTimezoneWithPriority(
            region + "/" + city,
            constants.TIMEZONE_PRIORITY_USER
        )
        self._timezone_module.NTPEnabled = self._ntp_radio_button.get_active()
        self._kickstarted = False

    def execute(self):
        if self._update_datetime_timer is not None:
            self._update_datetime_timer.cancel()
        self._update_datetime_timer = None

    @property
    def ready(self):
        return not thread_manager.get(constants.THREAD_DATE_TIME)

    @property
    def completed(self):
        if self._kickstarted and not self._timezone_module.Kickstarted:
            # taking values from kickstart, but not specified
            return False
        else:
            return is_valid_timezone(self._timezone_module.Timezone)

    @property
    def mandatory(self):
        return True

    def refresh(self):
        self._shown = True

        # update the displayed time
        self._update_datetime_timer = Timer()
        self._update_datetime_timer.timeout_sec(1, self._update_datetime)
        self._start_updating_timer = None

        # Update the timezone configuration.
        timezone = self._get_valid_timezone(self._timezone_module.Timezone)
        self._set_region_and_city_from_timezone(timezone)
        self._set_timezone(timezone)

        # update the ntp configuration
        self._ntp_servers = TimeSourceData.from_structure_list(
            self._timezone_module.TimeSources
        )

        # Set up the NTP servers.
        if not self._ntp_servers:
            try:
                self._ntp_servers = ntp.get_servers_from_config()
            except ntp.NTPconfigError:
                log.warning("Failed to load NTP servers configuration")

        self._ntp_servers_states = NTPServerStatusCache()
        self._ntp_servers_states.changed.connect(self._update_ntp_server_warning)

        if self._network_module.Connected:
            for server in self._ntp_servers:
                self._ntp_servers_states.check_status(server)

        # Set up the NTP widgets.
        self._set_ntp_enabled(self._timezone_module.NTPEnabled)

    @async_action_nowait
    def add_to_store_xlated(self, store, item, xlated):
        store.append([item, xlated])

    @async_action_nowait
    def add_to_store_idx(self, store, idx, item):
        store.append([idx, item])

    def existing_date(self, days_model, days_iter, user_data=None):
        if not days_iter:
            return False
        day = days_model[days_iter][0]

        #days 1-28 are in every month every year
        if day < 29:
            return True

        months_model = self._monthCombo.get_model()
        months_iter = self._monthCombo.get_active_iter()
        if not months_iter:
            return True

        years_model = self._yearCombo.get_model()
        years_iter = self._yearCombo.get_active_iter()
        if not years_iter:
            return True

        try:
            datetime.date(years_model[years_iter][0],
                          months_model[months_iter][0], day)
            return True
        except ValueError:
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

        for widget in (self._amPmUp, self._amPmDown, self._amPmLabel):
            widget.set_sensitive(sensitive)

    def _to_amPm(self, hours):
        if hours >= 12:
            day_phase = _("PM")
        else:
            day_phase = _("AM")

        new_hours = ((hours - 1) % 12) + 1

        return (new_hours, day_phase)

    def _to_24h(self, hours, day_phase):
        correction = 0

        if day_phase == _("AM") and hours == 12:
            correction = -12

        elif day_phase == _("PM") and hours != 12:
            correction = 12

        return (hours + correction) % 24

    def _update_datetime(self):
        now = datetime.datetime.now(self._tz)
        if self._radioButton24h.get_active():
            self._hoursLabel.set_text("%0.2d" % now.hour)
        else:
            hours, amPm = self._to_amPm(now.hour)
            self._hoursLabel.set_text("%0.2d" % hours)
            self._amPmLabel.set_text(amPm)

        self._minutesLabel.set_text("%0.2d" % now.minute)

        self._set_combo_selection(self._dayCombo, now.day)
        self._set_combo_selection(self._monthCombo, now.month)
        self._set_combo_selection(self._yearCombo, now.year)

        #GLib's timer is driven by the return value of the function.
        #It runs the fuction periodically while the returned value
        #is True.
        return True

    def _save_system_time(self):
        """
        Returning False from this method removes the timer that would
        otherwise call it again and again.
        """
        self._start_updating_timer = None

        if not conf.system.can_set_system_clock:
            return False

        month = self._get_combo_selection(self._monthCombo)[0]
        if not month:
            return False

        year = self._get_combo_selection(self._yearCombo)[0]
        if not year:
            return False

        hours = int(self._hoursLabel.get_text())
        if not self._radioButton24h.get_active():
            hours = self._to_24h(hours, self._amPmLabel.get_text())

        minutes = int(self._minutesLabel.get_text())

        day = self._get_combo_selection(self._dayCombo)[0]
        #day may be None if there is no such in the selected year and month
        if day:
            log.debug("Setting year %s, month %s, day %s, hours %s, minutes %s, tz %s",
                      year, month, day, hours, minutes, self._tz.key)
            set_system_date_time(year, month, day, hours, minutes, tz=self._tz.key)

        #start the timer only when the spoke is shown
        if self._shown and not self._update_datetime_timer:
            self._update_datetime_timer = Timer()
            self._update_datetime_timer.timeout_sec(1, self._update_datetime)

        #run only once (after first 2 seconds of inactivity)
        return False

    def _stop_and_maybe_start_time_updating(self, interval=2):
        """
        This method is called in every date/time-setting button's callback.
        It removes the timer for updating displayed date/time (do not want to
        change it while user does it manually) and allows us to set new system
        date/time only after $interval seconds long idle on time-setting buttons.
        This is done by the _start_updating_timer that is reset in this method.
        So when there is $interval seconds long idle on date/time-setting
        buttons, self._save_system_time method is invoked. Since it returns
        False, this timer is then removed and only reactivated in this method
        (thus in some date/time-setting button's callback).
        """
        #do not start timers if the spoke is not shown
        if not self._shown:
            self._update_datetime()
            self._save_system_time()
            return

        #stop time updating
        if self._update_datetime_timer:
            self._update_datetime_timer.cancel()
            self._update_datetime_timer = None

        #stop previous $interval seconds timer (see below)
        if self._start_updating_timer:
            self._start_updating_timer.cancel()

        #let the user change date/time and after $interval seconds of inactivity
        #save it as the system time and start updating the displayed date/time
        self._start_updating_timer = Timer()
        self._start_updating_timer.timeout_sec(interval, self._save_system_time)

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

    def _get_combo_selection(self, combo):
        """Get the selected item of the combobox.

        :return: selected item or None
        """
        model = combo.get_model()
        itr = combo.get_active_iter()
        if not itr or not model:
            return None, None

        return model[itr][0], model[itr][1]

    def _restore_old_city_region(self):
        """Restore stored "old" (or last valid) values."""
        # check if there are old values to go back to
        if self._old_region and self._old_city:
            self._set_combo_selection(self._regionCombo, self._old_region)
            self._set_combo_selection(self._cityCombo, self._old_city)

    def on_up_hours_clicked(self, *args):
        self._stop_and_maybe_start_time_updating()

        hours = int(self._hoursLabel.get_text())

        if self._radioButton24h.get_active():
            new_hours = (hours + 1) % 24
        else:
            amPm = self._amPmLabel.get_text()
            #let's not deal with magical AM/PM arithmetics
            new_hours = self._to_24h(hours, amPm)
            new_hours, new_amPm = self._to_amPm((new_hours + 1) % 24)
            self._amPmLabel.set_text(new_amPm)

        new_hours_str = "%0.2d" % new_hours
        self._hoursLabel.set_text(new_hours_str)

    def on_down_hours_clicked(self, *args):
        self._stop_and_maybe_start_time_updating()

        hours = int(self._hoursLabel.get_text())

        if self._radioButton24h.get_active():
            new_hours = (hours - 1) % 24
        else:
            amPm = self._amPmLabel.get_text()
            #let's not deal with magical AM/PM arithmetics
            new_hours = self._to_24h(hours, amPm)
            new_hours, new_amPm = self._to_amPm((new_hours - 1) % 24)
            self._amPmLabel.set_text(new_amPm)

        new_hours_str = "%0.2d" % new_hours
        self._hoursLabel.set_text(new_hours_str)

    def on_up_minutes_clicked(self, *args):
        self._stop_and_maybe_start_time_updating()

        minutes = int(self._minutesLabel.get_text())
        minutes_str = "%0.2d" % ((minutes + 1) % 60)
        self._minutesLabel.set_text(minutes_str)

    def on_down_minutes_clicked(self, *args):
        self._stop_and_maybe_start_time_updating()

        minutes = int(self._minutesLabel.get_text())
        minutes_str = "%0.2d" % ((minutes - 1) % 60)
        self._minutesLabel.set_text(minutes_str)

    def on_updown_ampm_clicked(self, *args):
        self._stop_and_maybe_start_time_updating()

        if self._amPmLabel.get_text() == _("AM"):
            self._amPmLabel.set_text(_("PM"))
        else:
            self._amPmLabel.set_text(_("AM"))

    def on_region_changed(self, combo, *args):
        """
        :see: on_city_changed
        """
        region = self._get_active_region()

        if not region or region == self._old_region:
            # region entry being edited or old_value chosen, no action needed
            # @see: on_city_changed
            return

        self._citiesFilter.refilter()

        # Set the city to the first one available in this newly selected region.
        zone = self._regions_zones[region]
        firstCity = sorted(list(zone))[0]

        self._set_combo_selection(self._cityCombo, firstCity)
        self._old_region = region
        self._old_city = firstCity

    def on_city_changed(self, combo, *args):
        """
        ComboBox emits ::changed signal not only when something is selected, but
        also when its entry's text is changed. We need to distinguish between
        those two cases ('London' typed in the entry => no action until ENTER is
        hit etc.; 'London' chosen in the expanded combobox => update timezone
        map and do all necessary actions). Fortunately when entry is being
        edited, self._get_active_city returns None.
        """
        region = self._get_active_region()
        city = self._get_active_city()

        # Both, city and region, are needed to form a valid timezone.
        if not region or not city:
            return

        # Entry being edited or no change, no actions needed.
        if region == self._old_region and city == self._old_city:
            return

        # Update the local timezone.
        self._set_timezone(region + "/" + city)

        # update "old" values
        self._old_city = city

    def on_entry_left(self, entry, *args):
        # user clicked somewhere else or hit TAB => finished editing
        entry.emit("activate")

    def on_city_region_key_released(self, entry, event, *args):
        if event.type == Gdk.EventType.KEY_RELEASE and \
                event.keyval == Gdk.KEY_Escape:
            # editing canceled
            self._restore_old_city_region()

    def on_completion_match_selected(self, combo, model, itr):
        item = None
        if model and itr:
            item = model[itr][0]
        if item:
            self._set_combo_selection(combo, item)

    def on_city_region_text_entry_activated(self, entry):
        combo = entry.get_parent()

        # It's gotta be up there somewhere, right? right???
        while not isinstance(combo, Gtk.ComboBox):
            combo = combo.get_parent()

        model = combo.get_model()
        entry_text = entry.get_text().lower()

        for row in model:
            if entry_text == row[0].lower():
                self._set_combo_selection(combo, row[0])
                return

        # non-matching value entered, reset to old values
        self._restore_old_city_region()

    def on_month_changed(self, *args):
        self._stop_and_maybe_start_time_updating(interval=5)
        self._daysFilter.refilter()

    def on_day_changed(self, *args):
        self._stop_and_maybe_start_time_updating(interval=5)

    def on_year_changed(self, *args):
        self._stop_and_maybe_start_time_updating(interval=5)
        self._daysFilter.refilter()

    def _get_valid_timezone(self, preferred_timezone):
        """Return a valid timezone to use in the user interface."""
        if not preferred_timezone:
            return DEFAULT_TZ

        if not is_valid_timezone(preferred_timezone):
            return DEFAULT_TZ

        region, city = parse_timezone(preferred_timezone)

        if not region or not city:
            return DEFAULT_TZ

        return preferred_timezone

    def _set_region_and_city_from_timezone(self, timezone):
        """Set up the region and the city from the specified timezone."""
        # Set up the region and city widgets.
        with blocked_handler(self._cityCombo, self.on_city_changed):
            region, city = parse_timezone(timezone)
            self._set_combo_selection(self._regionCombo, region)
            self._set_combo_selection(self._cityCombo, city)

    def _set_timezone(self, timezone):
        """Set the timezone."""
        # Update the datetime widgets.
        self._tz = get_timezone(timezone)
        self._update_datetime()

        # Set the local timezone to the value stored in os.environ['TZ'].
        time.tzset()

    def on_timeformat_changed(self, button24h, *args):
        hours = int(self._hoursLabel.get_text())
        amPm = self._amPmLabel.get_text()

        #connected to 24-hour radio button
        if button24h.get_active():
            self._set_amPm_part_sensitive(False)
            new_hours = self._to_24h(hours, amPm)
            self._amPmRevealer.set_reveal_child(False)
        else:
            self._set_amPm_part_sensitive(True)
            new_hours, new_amPm = self._to_amPm(hours)
            self._amPmLabel.set_text(new_amPm)
            self._amPmRevealer.set_reveal_child(True)

        self._hoursLabel.set_text("%0.2d" % new_hours)

    def _hide_date_time_setting(self):
        #contains all date/time setting widgets
        container_widget = self.builder.get_object("manualGrid")
        container_widget.set_no_show_all(True)
        container_widget.hide()

    def _set_date_time_setting_sensitive(self, sensitive):
        #contains all date/time setting widgets
        container_widget = self.builder.get_object("manualGrid")
        container_widget.set_sensitive(sensitive)

    def _get_working_server(self):
        """Get a working NTP server."""
        for server in self._ntp_servers:
            status = self._ntp_servers_states.get_status(server)
            if status == constants.NTP_SERVER_OK:
                return server

        return None

    def _show_no_network_warning(self):
        self.set_warning(_("You need to set up networking first if you "
                           "want to use NTP"))

    def _show_no_ntp_server_warning(self):
        self.set_warning(_("You have no working NTP server configured"))

    def _cancel_planned_update(self):
        """Cancel system time update planned by manual setting"""
        # cancel system time update
        if self._start_updating_timer:
            self._start_updating_timer.cancel()
            self._start_updating_timer = None

        # re-enable UI update because it will not be done by the
        # system time update we've just cancelled
        if not self._update_datetime_timer:
            self._update_datetime_timer = Timer()
            self._update_datetime_timer.timeout_sec(1, self._update_datetime)

    def on_ntp_button_toggled(self, button):
        """Toggle the NTP configuration."""
        log.debug("Toggled the NTP configuration.")
        self._set_ntp_enabled(self._ntp_radio_button.get_active())

    def _set_ntp_enabled(self, ntp_requested):
        """Set the NTP enabled configuration."""
        # Clear warnings.
        self.clear_info()

        # Try to configure the NTP service.
        ntp_enabled = self._start_ntp_service() if ntp_requested else self._stop_ntp_service()

        # Update the widgets.
        with blocked_handler(self._ntp_radio_button, self.on_ntp_button_toggled):
            self._ntp_radio_button.set_active(ntp_enabled)
            self._ntp_config_button.set_sensitive(ntp_enabled)

            self._manual_radio_button.set_active(not ntp_enabled)
            self._set_date_time_setting_sensitive(not ntp_enabled)

        # Update the timers.
        if ntp_enabled:
            self._cancel_planned_update()

    def _start_ntp_service(self):
        """Start the NTP service.

        :return bool: True if NTP is enabled, otherwise False
        """
        log.debug("Starting the NTP service...")

        # Cannot touch runtime system, not much to do here.
        # Pretend that the NTP service is enabled.
        if not conf.system.can_set_time_synchronization:
            return True

        # Check the network connection.
        if not self._network_module.Connected:
            log.debug("No network. The NTP service cannot be started.")
            self._show_no_network_warning()
            return False

        # Start the NTP service.
        if start_service(NTP_SERVICE) == 0:
            self._update_ntp_server_warning()
            return True

        # Or check if it's running.
        if is_service_running(NTP_SERVICE):
            self._update_ntp_server_warning()
            return True

        log.debug("Failed to start the NTP service.")
        return False

    def _stop_ntp_service(self):
        """Stop the NTP service.

        :return bool: True if NTP is enabled, otherwise False
        """
        log.debug("Stopping the NTP service...")

        # Cannot touch runtime system, not much to do here.
        # Pretend that the NTP service isn't enabled.
        if not conf.system.can_set_time_synchronization:
            return False

        # Stop the NTP service.
        if stop_service(NTP_SERVICE) == 0:
            return False

        # Or check if it's NOT running.
        if not is_service_running(NTP_SERVICE):
            return False

        log.debug("Failed to stop the NTP service.")
        return True

    def on_ntp_config_clicked(self, *args):
        servers = copy.deepcopy(self._ntp_servers)
        states = self._ntp_servers_states

        # Temporarily disconnect the update callback.
        states.changed.disconnect(self._update_ntp_server_warning)

        dialog = NTPConfigDialog(self.data, servers, states)
        dialog.refresh()

        with self.main_window.enlightbox(dialog.window):
            response = dialog.run()

        # Connect the update callback again.
        states.changed.connect(self._update_ntp_server_warning)

        if response == 1:
            self._timezone_module.TimeSources = \
                TimeSourceData.to_structure_list(servers)

            self._ntp_servers = servers
            self._update_ntp_server_warning()

    def _update_ntp_server_warning(self):
        """Update the warning about working NTP servers."""
        if not self._ntp_radio_button.get_active():
            return

        self.clear_info()
        working_server = self._get_working_server()

        if working_server is None:
            self._show_no_ntp_server_warning()
