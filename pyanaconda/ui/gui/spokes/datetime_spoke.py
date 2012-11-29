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

import logging
log = logging.getLogger("anaconda")

# pylint: disable-msg=E0611
from gi.repository import AnacondaWidgets, GLib, Gtk

from pyanaconda.ui.gui import GUIObject
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.categories.localization import LocalizationCategory
from pyanaconda.ui.gui.utils import enlightbox, gtk_thread_nowait, gtk_call_once

from pyanaconda import timezone
from pyanaconda import iutil
from pyanaconda import network
from pyanaconda import ntp
from pyanaconda import flags
from pyanaconda.threads import threadMgr, AnacondaThread

import datetime
import os
import threading

__all__ = ["DatetimeSpoke"]

SERVER_OK = 0
SERVER_NOK = 1
SERVER_QUERY = 2

DEFAULT_TZ = "America/New_York"

POOL_SERVERS_NOTE = N_("Note: pool servers may not be available all the time")

class NTPconfigDialog(GUIObject):
    builderObjects = ["ntpConfigDialog", "addImage", "serversStore"]
    mainWidgetName = "ntpConfigDialog"
    uiFile = "spokes/datetime_spoke.glade"

    def __init__(self, *args):
        GUIObject.__init__(self, *args)

        #used to ensure uniqueness of the threads' names
        self._threads_counter = 0

        #epoch is increased when serversStore is repopulated
        self._epoch = 0
        self._epoch_lock = threading.Lock()

    @property
    def working_server(self):
        for row in self._serversStore:
            if row[1] == SERVER_OK and row[2]:
                #server is checked and working
                return row[0]

        return None

    @property
    def servers(self):
        ret = list()

        for row in self._serversStore:
            if row[2]:
                #server checked
                ret.append(row[0])

        return ret

    def _render_working(self, column, renderer, model, itr, user_data=None):
        #get the value in the second column
        value = model[itr][1]

        if value == SERVER_QUERY:
            renderer.set_property("stock-id", "gtk-dialog-question")
        elif value == SERVER_OK:
            renderer.set_property("stock-id", "gtk-yes")
        else:
            renderer.set_property("stock-id", "gtk-no")

    def initialize(self):
        self.window.set_size_request(500, 400)

        workingColumn = self.builder.get_object("workingColumn")
        workingRenderer = self.builder.get_object("workingRenderer")
        workingColumn.set_cell_data_func(workingRenderer, self._render_working)

        self._serverEntry = self.builder.get_object("serverEntry")
        self._serversStore = self.builder.get_object("serversStore")
        self._poolsNote = self.builder.get_object("poolsNote")

        self._initialize_store_from_config()

    def _initialize_store_from_config(self):
        self._serversStore.clear()
        self._poolsNote.set_text("")

        if self.data.timezone.ntpservers:
            for server in self.data.timezone.ntpservers:
                self._add_server(server)
        else:
            try:
                for server in ntp.get_servers_from_config():
                    self._add_server(server)
            except ntp.NTPconfigError as ntperr:
                log.warning("Failed to load NTP servers configuration")

    def refresh(self):
        self._serverEntry.grab_focus()

    def refresh_servers_state(self):
        itr = self._serversStore.get_iter_first()
        while itr:
            self._refresh_server_working(itr)
            itr = self._serversStore.iter_next(itr)

    def run(self):
        self.window.show()
        rc = self.window.run()
        self.window.hide()

        #OK clicked
        if rc == 1:
            new_servers = list()

            for row in self._serversStore:
                #if server checked
                if row[2]:
                    new_servers.append(row[0])

            if flags.can_touch_runtime_system("save NTP servers configuration"):
                ntp.save_servers_to_config(new_servers)
                iutil.restart_service("chronyd")

        #Cancel clicked, window destroyed...
        else:
            self._epoch_lock.acquire()
            self._epoch += 1
            self._epoch_lock.release()

            self._initialize_store_from_config()

        return rc

    def _set_server_ok_nok(self, itr, epoch_started):
        """
        If the server is working, set its data to SERVER_OK, otherwise set its
        data to SERVER_NOK.

        @param itr: iterator of the $server's row in the self._serversStore

        """

        @gtk_thread_nowait
        def set_store_value(arg_tuple):
            """
            We need a function for this, because this way it can be added to
            the MainLoop with thread-safe GLib.idle_add (but only with one
            argument).

            @param arg_tuple: (store, itr, column, value)

            """

            (store, itr, column, value) = arg_tuple
            store.set_value(itr, column, value)

        orig_hostname = self._serversStore[itr][0]
        server_working = ntp.ntp_server_working(self._serversStore[itr][0])

        #do not let dialog change epoch while we are modifying data
        self._epoch_lock.acquire()

        #check if we are in the same epoch as the dialog (and the serversStore)
        #and if the server wasn't changed meanwhile
        if epoch_started == self._epoch:
            actual_hostname = self._serversStore[itr][0]

            if orig_hostname == actual_hostname:
                if server_working:
                    set_store_value((self._serversStore,
                                    itr, 1, SERVER_OK))
                else:
                    set_store_value((self._serversStore,
                                    itr, 1, SERVER_NOK))
        self._epoch_lock.release()

    @gtk_thread_nowait
    def _refresh_server_working(self, itr):
        """ Runs a new thread with _set_server_ok_nok(itr) as a taget. """

        self._serversStore.set_value(itr, 1, SERVER_QUERY)
        new_thread_name = "AnaNTPserver%d" % self._threads_counter
        threadMgr.add(AnacondaThread(name=new_thread_name,
                                     target=self._set_server_ok_nok,
                                     args=(itr, self._epoch)))
        self._threads_counter += 1

    def _add_server(self, server):
        """
        Checks if a given server is a valid hostname and if yes, adds it
        to the list of servers.

        @param server: string containing hostname

        """

        (valid, error) = network.sanityCheckHostname(server)
        if not valid:
            log.error("'%s' is not a valid hostname: %s" % (server, error))
            return

        for row in self._serversStore:
            if row[0] == server:
                #do not add duplicate items
                return

        itr = self._serversStore.append([server, SERVER_QUERY, True])

        if "pool" in server:
            self._poolsNote.set_text(_(POOL_SERVERS_NOTE))

        #do not block UI while starting thread (may take some time)
        self._refresh_server_working(itr)

    def on_entry_activated(self, entry, *args):
        self._add_server(entry.get_text())
        entry.set_text("")

    def on_add_clicked(self, *args):
        self._add_server(self._serverEntry.get_text())
        self._serverEntry.set_text("")

    def on_use_server_toggled(self, renderer, path, *args):
        itr = self._serversStore.get_iter(path)
        old_value = self._serversStore[itr][2]

        self._serversStore.set_value(itr, 2, not old_value)

    def on_server_edited(self, renderer, path, new_text, *args):
        if not path:
            return

        (valid, error) = network.sanityCheckHostname(new_text)
        if not valid:
            log.error("'%s' is not a valid hostname: %s" % (new_text, error))
            return

        itr = self._serversStore.get_iter(path)

        if self._serversStore[itr][0] == new_text:
            return

        self._serversStore.set_value(itr, 0, new_text)
        self._serversStore.set_value(itr, 1, SERVER_QUERY)

        self._refresh_server_working(itr)

class DatetimeSpoke(NormalSpoke):
    builderObjects = ["datetimeWindow",
                      "days", "months", "years", "regions", "cities",
                      "upImage", "upImage1", "upImage2", "downImage",
                      "downImage1", "downImage2", "downImage3", "configImage",
                      "citiesFilter", "daysFilter", "citiesSort", "regionsSort",
                      ]

    mainWidgetName = "datetimeWindow"
    uiFile = "spokes/datetime_spoke.glade"

    category = LocalizationCategory

    icon = "preferences-system-time-symbolic"
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

        self._regions_zones = timezone.get_all_regions_and_timezones()

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
        self._citiesSort.set_sort_column_id(0, Gtk.SortType.ASCENDING)

        self._hoursLabel = self.builder.get_object("hoursLabel")
        self._minutesLabel = self.builder.get_object("minutesLabel")
        self._amPmUp = self.builder.get_object("amPmUpButton")
        self._amPmDown = self.builder.get_object("amPmDownButton")
        self._amPmLabel = self.builder.get_object("amPmLabel")
        self._radioButton24h = self.builder.get_object("timeFormatRB")

        self._ntpSwitch = self.builder.get_object("networkTimeSwitch")
        self._added_chrony = False
        self._enabled_chrony = False

        if self._radioButton24h.get_active():
            self._set_amPm_part_sensitive(False)

        self._update_datetime_timer_id = None
        if timezone.is_valid_timezone(self.data.timezone.timezone):
            self._tzmap.set_timezone(self.data.timezone.timezone)
        else:
            log.warning("%s is not a valid timezone, falling back to default "\
                        "(%s)" % (self.data.timezone.timezone, DEFAULT_TZ))
            self._tzmap.set_timezone(DEFAULT_TZ)
            self.data.timezone.timezone = DEFAULT_TZ

        if not flags.can_touch_runtime_system("modify system time and date"):
            self._set_date_time_setting_sensitive(False)

        self._config_dialog = NTPconfigDialog(self.data)
        self._config_dialog.initialize()

    @property
    def status(self):
        if self.data.timezone.timezone:
            if timezone.is_valid_timezone(self.data.timezone.timezone):
                return _("%s timezone") % self.data.timezone.timezone
            else:
                return _("Invalid timezone")

        else:
            return _("%s timezone") % self._tzmap.get_timezone()

    def apply(self):
        GLib.source_remove(self._update_datetime_timer_id)
        self._update_datetime_timer_id = None

        new_tz = self._tzmap.get_timezone()

        # get_timezone() may return "" if Etc/XXXXX is selected
        if not new_tz:
            # get selected "Etc/XXXXXX" zone
            region = self._get_active_region()
            city = self._get_active_city()
            new_tz = region + "/" + city

        self.data.timezone.timezone = new_tz

        if self._ntpSwitch.get_active():
            # turned ON
            self.data.timezone.nontp = False
            if not "chrony" in self.data.packages.packageList:
                self.data.packages.packageList.append("chrony")
                self._added_chrony = True

            if not "chronyd" in self.data.services.enabled and \
                    not "chronyd" in self.data.services.disabled:
                self.data.services.enabled.append("chronyd")
                self._enabled_chrony = True
        else:
            # turned OFF
            self.data.timezone.nontp = True
            if self._added_chrony and ("chrony" in
                                        self.data.packages.packageList):
                self.data.packages.packageList.remove("chrony")
                self._added_chrony = False

            if self._enabled_chrony and ("chronyd" in
                                            self.data.services.enabled):
                self.data.services.enabled.remove("chronyd")
                self._enabled_chrony = False

    @property
    def completed(self):
        return timezone.is_valid_timezone(self.data.timezone.timezone)

    def refresh(self):
        #update the displayed time
        self._update_datetime_timer_id = GLib.timeout_add_seconds(1,
                                                    self._update_datetime)
        self._start_updating_timer_id = None

        if timezone.is_valid_timezone(self.data.timezone.timezone):
            self._tzmap.set_timezone(self.data.timezone.timezone)

        self._update_datetime()

        has_active_network = network.hasActiveNetDev()
        if not has_active_network:
            self._show_no_network_warning()
        else:
            self.clear_info()
            gtk_call_once(self._config_dialog.refresh_servers_state)

        if flags.can_touch_runtime_system("get NTP service state"):
            ntp_working = has_active_network and iutil.service_running("chronyd")
        else:
            ntp_working = not self.data.timezone.nontp

        self._ntpSwitch.set_active(ntp_working)

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

        for widget in (self._amPmUp, self._amPmDown, self._amPmLabel):
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
            self._amPmLabel.set_text(amPm)

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
        """
        Returning False from this method removes the timer that would
        otherwise call it again and again.

        """

        if not flags.can_touch_runtime_system("save system time"):
            return False

        month = self._get_combo_selection(self._monthCombo)
        if not month:
            return False
        month = self._months_nums[month]

        year_str = self._get_combo_selection(self._yearCombo)
        if not year_str:
            return False
        year = int(year_str)

        hours = int(self._hoursLabel.get_text())
        if not self._radioButton24h.get_active():
            hours = self._to_24h(hours, self._amPmLabel.get_text())

        minutes = int(self._minutesLabel.get_text())

        day = self._get_combo_selection(self._dayCombo)
        #day may be None if there is no such in the selected year and month
        if day:
            day = int(day)
            seconds = datetime.datetime.now().second
            os.system("date -s '%0.2d/%0.2d/%0.4d %0.2d:%0.2d:%0.2d'" %
                                (month, day, year, hours, minutes, seconds))

        #start the timer only when the spoke is shown
        if self._update_datetime_timer_id is not None:
            self._update_datetime_timer_id = GLib.timeout_add_seconds(1,
                                                        self._update_datetime)

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
        if self._update_datetime_timer_id is None:
            self._update_datetime()
            self._save_system_time()
            return

        #stop time updating
        GLib.source_remove(self._update_datetime_timer_id)

        #stop previous $interval seconds timer (see below)
        if self._start_updating_timer_id:
            GLib.source_remove(self._start_updating_timer_id)

        #let the user change date/time and after $interval seconds of inactivity
        #save it as the system time and start updating the displayed date/time
        self._start_updating_timer_id = GLib.timeout_add_seconds(interval,
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

    def _get_combo_selection(self, combo):
        """
        Get the selected item of the combobox.

        @return: selected item or None

        """

        model = combo.get_model()
        itr = combo.get_active_iter()
        if not itr or not model:
            return None

        return model[itr][0]


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
        pass

    def on_down_minutes_clicked(self, *args):
        self._stop_and_maybe_start_time_updating()

        minutes = int(self._minutesLabel.get_text())
        minutes_str = "%0.2d" % ((minutes - 1) % 60)
        self._minutesLabel.set_text(minutes_str)

    def on_up_ampm_clicked(self, *args):
        self._stop_and_maybe_start_time_updating()

        if self._amPmLabel.get_text() == "AM":
            self._amPmLabel.set_text("PM")
        else:
            self._amPmLabel.set_text("AM")

    def on_down_ampm_clicked(self, *args):
        self._stop_and_maybe_start_time_updating()

        if self._amPmLabel.get_text() == "AM":
            self._amPmLabel.set_text("PM")
        else:
            self._amPmLabel.set_text("AM")

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

        if timezone is not None and region == "Etc":
            # Etc timezones cannot be displayed on the map, so let's set the map
            # to "" which sets it to "Europe/London" (UTC) without a city pin
            self._tzmap.set_timezone("")

            # Change to Etc/XXXXX emits timezone-changed with "" as timezone,
            # so let's help it a bit.
            self._tzmap.emit("timezone-changed", timezone)

        elif timezone and (self._tzmap.get_timezone() != timezone):
            self._tzmap.set_timezone(timezone)

    def on_month_changed(self, *args):
        self._stop_and_maybe_start_time_updating(interval=5)
        self._daysFilter.refilter()

    def on_day_changed(self, *args):
        self._stop_and_maybe_start_time_updating(interval=5)

    def on_year_changed(self, *args):
        self._stop_and_maybe_start_time_updating(interval=5)
        self._daysFilter.refilter()

    def on_timezone_changed(self, tz_map, timezone):
        fields = timezone.split("/", 1)
        if len(fields) == 1:
            # timezone may be ""
            return

        region, city = fields
        if region != "Etc":
            # If region is "Etc", TimezoneMap returns "" from get_timezone
            # and changing comboboxes here would create an endless loop.
            self._set_combo_selection(self._regionCombo, region)
            self._set_combo_selection(self._cityCombo, city)

        os.environ["TZ"] = timezone
        self._update_datetime()

    def on_timeformat_changed(self, button24h, *args):
        hours = int(self._hoursLabel.get_text())
        amPm = self._amPmLabel.get_text()

        #connected to 24-hour radio button
        if button24h.get_active():
            self._set_amPm_part_sensitive(False)
            new_hours = self._to_24h(hours, amPm)

        else:
            self._set_amPm_part_sensitive(True)
            new_hours, new_amPm = self._to_amPm(hours)
            self._amPmLabel.set_text(new_amPm)

        self._hoursLabel.set_text("%0.2d" % new_hours)

    def _set_date_time_setting_sensitive(self, sensitive):
        #contains all date/time setting widgets
        footer_alignment = self.builder.get_object("footerAlignment")
        footer_alignment.set_sensitive(sensitive)

    def _show_no_network_warning(self):
        self.set_warning(_("You need to set up networking first if you "\
                           "want to use NTP"))

    def _show_no_ntp_server_warning(self):
        self.set_warning(_("You have no working NTP server configured"))

    def on_ntp_switched(self, switch, *args):
        if switch.get_active():
            #turned ON
            if not flags.can_touch_runtime_system("start NTP service"):
                #cannot touch runtime system, not much to do here
                return

            if not network.hasActiveNetDev():
                self._show_no_network_warning()
                switch.set_active(False)
                return
            else:
                self.clear_info()

                working_server = self._config_dialog.working_server
                if working_server is None:
                    self._show_no_ntp_server_warning()
                else:
                    #we need a one-time sync here, because chronyd would not change
                    #the time as drastically as we need
                    ntp.one_time_sync_async(working_server)

            ret = iutil.start_service("chronyd")
            self._set_date_time_setting_sensitive(False)

            #if starting chronyd failed and chronyd is not running,
            #set switch back to OFF
            if (ret != 0) and not iutil.service_running("chronyd"):
                switch.set_active(False)

        else:
            #turned OFF
            if not flags.can_touch_runtime_system("stop NTP service"):
                #cannot touch runtime system, nothing to do here
                return

            self._set_date_time_setting_sensitive(True)
            ret = iutil.stop_service("chronyd")

            #if stopping chronyd failed and chronyd is running,
            #set switch back to ON
            if (ret != 0) and iutil.service_running("chronyd"):
                switch.set_active(True)

    def on_ntp_config_clicked(self, *args):
        self._config_dialog.refresh()

        with enlightbox(self.window, self._config_dialog.window):
            response = self._config_dialog.run()

        if response == 1:
            self.data.timezone.ntpservers = self._config_dialog.servers

            if self._config_dialog.working_server is None:
                self._show_no_ntp_server_warning()
            else:
                self.clear_info()

