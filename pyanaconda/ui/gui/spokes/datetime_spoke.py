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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Vratislav Podzimek <vpodzime@redhat.com>
#

import logging
log = logging.getLogger("anaconda")

from gi.repository import GLib, Gdk, Gtk, TimezoneMap

from pyanaconda.ui.communication import hubQ
from pyanaconda.ui.common import FirstbootSpokeMixIn
from pyanaconda.ui.gui import GUIObject
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.categories.localization import LocalizationCategory
from pyanaconda.ui.gui.utils import gtk_action_nowait, gtk_action_wait, gtk_call_once, override_cell_property
from pyanaconda.ui.gui.helpers import GUIDialogInputCheckHandler
from pyanaconda.ui.helpers import InputCheck

from pyanaconda.i18n import _, CN_
from pyanaconda.timezone import NTP_SERVICE, get_all_regions_and_timezones, get_timezone, is_valid_timezone
from pyanaconda.localization import get_xlated_timezone, resolve_date_format
from pyanaconda import iutil
from pyanaconda import isys
from pyanaconda import network
from pyanaconda import nm
from pyanaconda import ntp
from pyanaconda import flags
from pyanaconda import constants
from pyanaconda.threads import threadMgr, AnacondaThread

import datetime
import re
import threading
import locale as locale_mod

__all__ = ["DatetimeSpoke"]

SERVER_OK = 0
SERVER_NOK = 1
SERVER_QUERY = 2

SERVER_HOSTNAME = 0
SERVER_POOL = 1
SERVER_WORKING = 2
SERVER_USE = 3

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
        return cmp(int(sign1 + suffix1), int(sign2 + suffix2))
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

    box.pack_start(combo, False, False, 0)
    box.pack_start(suffix_label, False, False, 0)

    return (box, combo, suffix_label)

class NTPconfigDialog(GUIObject, GUIDialogInputCheckHandler):
    builderObjects = ["ntpConfigDialog", "addImage", "serversStore"]
    mainWidgetName = "ntpConfigDialog"
    uiFile = "spokes/datetime_spoke.glade"

    def __init__(self, *args):
        GUIObject.__init__(self, *args)
        GUIDialogInputCheckHandler.__init__(self)

        #epoch is increased when serversStore is repopulated
        self._epoch = 0
        self._epoch_lock = threading.Lock()

    @property
    def working_server(self):
        for row in self._serversStore:
            if row[SERVER_WORKING] == SERVER_OK and row[SERVER_USE]:
                #server is checked and working
                return row[SERVER_HOSTNAME]

        return None

    @property
    def pools_servers(self):
        pools = list()
        servers = list()

        for used_row in (row for row in self._serversStore if row[SERVER_USE]):
            if used_row[SERVER_POOL]:
                pools.append(used_row[SERVER_HOSTNAME])
            else:
                servers.append(used_row[SERVER_HOSTNAME])

        return (pools, servers)

    def _render_working(self, column, renderer, model, itr, user_data=None):
        value = model[itr][SERVER_WORKING]

        if value == SERVER_QUERY:
            return "dialog-question"
        elif value == SERVER_OK:
            return "emblem-default"
        else:
            return "dialog-error"

    def initialize(self):
        self.window.set_size_request(500, 400)

        workingColumn = self.builder.get_object("workingColumn")
        workingRenderer = self.builder.get_object("workingRenderer")
        override_cell_property(workingColumn, workingRenderer, "icon-name",
                self._render_working)

        self._serverEntry = self.builder.get_object("serverEntry")
        self._serversStore = self.builder.get_object("serversStore")

        self._addButton = self.builder.get_object("addButton")

        self._poolCheckButton = self.builder.get_object("poolCheckButton")

        # Validate the server entry box
        self._serverCheck = self.add_check(self._serverEntry, self._validateServer)
        self._serverCheck.update_check_status()

        self._initialize_store_from_config()

    def _initialize_store_from_config(self):
        self._serversStore.clear()

        if self.data.timezone.ntpservers:
            pools, servers = ntp.internal_to_pools_and_servers(self.data.timezone.ntpservers)
        else:
            try:
                pools, servers = ntp.get_servers_from_config()
            except ntp.NTPconfigError:
                log.warning("Failed to load NTP servers configuration")
                return

        for pool in pools:
            self._add_server(pool, True)
        for server in servers:
            self._add_server(server, False)


    def _validateServer(self, inputcheck):
        server = self.get_input(inputcheck.input_obj)

        # If not set, fail the check to keep the button insensitive, but don't
        # display an error
        if not server:
            return InputCheck.CHECK_SILENT

        (valid, error) = network.sanityCheckHostname(server)
        if not valid:
            return "'%s' is not a valid hostname: %s" % (server, error)
        else:
            return InputCheck.CHECK_OK

    def set_status(self, inputcheck):
        # Use GUIDialogInputCheckHandler to set the error message
        GUIDialogInputCheckHandler.set_status(self, inputcheck)

        # Set the sensitivity of the add button based on the result
        self._addButton.set_sensitive(inputcheck.check_status == InputCheck.CHECK_OK)

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
            new_pools, new_servers = self.pools_servers

            if flags.can_touch_runtime_system("save NTP servers configuration"):
                ntp.save_servers_to_config(new_pools, new_servers)
                iutil.restart_service(NTP_SERVICE)

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

        :param itr: iterator of the $server's row in the self._serversStore

        """

        @gtk_action_nowait
        def set_store_value(arg_tuple):
            """
            We need a function for this, because this way it can be added to
            the MainLoop with thread-safe GLib.idle_add (but only with one
            argument).

            :param arg_tuple: (store, itr, column, value)

            """

            (store, itr, column, value) = arg_tuple
            store.set_value(itr, column, value)

        orig_hostname = self._serversStore[itr][SERVER_HOSTNAME]
        server_working = ntp.ntp_server_working(self._serversStore[itr][SERVER_HOSTNAME])

        #do not let dialog change epoch while we are modifying data
        self._epoch_lock.acquire()

        #check if we are in the same epoch as the dialog (and the serversStore)
        #and if the server wasn't changed meanwhile
        if epoch_started == self._epoch:
            actual_hostname = self._serversStore[itr][SERVER_HOSTNAME]

            if orig_hostname == actual_hostname:
                if server_working:
                    set_store_value((self._serversStore,
                                    itr, SERVER_WORKING, SERVER_OK))
                else:
                    set_store_value((self._serversStore,
                                    itr, SERVER_WORKING, SERVER_NOK))
        self._epoch_lock.release()

    @gtk_action_nowait
    def _refresh_server_working(self, itr):
        """ Runs a new thread with _set_server_ok_nok(itr) as a taget. """

        self._serversStore.set_value(itr, SERVER_WORKING, SERVER_QUERY)
        threadMgr.add(AnacondaThread(prefix="AnaNTPserver",
                                     target=self._set_server_ok_nok,
                                     args=(itr, self._epoch)))

    def _add_server(self, server, pool=False):
        """
        Checks if a given server is a valid hostname and if yes, adds it
        to the list of servers.

        :param server: string containing hostname

        """

        itr = self._serversStore.append([server, pool, SERVER_QUERY, True])

        #do not block UI while starting thread (may take some time)
        self._refresh_server_working(itr)

    def on_entry_activated(self, entry, *args):
        # Check that the input check has passed
        if self._serverCheck.check_status == InputCheck.CHECK_OK:
            self._add_server(entry.get_text(), self._poolCheckButton.get_active())
            entry.set_text("")
            self._poolCheckButton.set_active(False)

    def on_add_clicked(self, *args):
        self._serverEntry.emit("activate")

    def on_use_server_toggled(self, renderer, path, *args):
        itr = self._serversStore.get_iter(path)
        old_value = self._serversStore[itr][SERVER_USE]

        self._serversStore.set_value(itr, SERVER_USE, not old_value)

    def on_pool_toggled(self, renderer, path, *args):
        itr = self._serversStore.get_iter(path)
        old_value = self._serversStore[itr][SERVER_POOL]

        self._serversStore.set_value(itr, SERVER_POOL, not old_value)

    def on_server_edited(self, renderer, path, new_text, *args):
        if not path:
            return

        (valid, error) = network.sanityCheckHostname(new_text)
        if not valid:
            log.error("'%s' is not a valid hostname: %s", new_text, error)
            return

        itr = self._serversStore.get_iter(path)

        if self._serversStore[itr][SERVER_HOSTNAME] == new_text:
            return

        self._serversStore.set_value(itr, SERVER_HOSTNAME, new_text)
        self._serversStore.set_value(itr, SERVER_WORKING, SERVER_QUERY)

        self._refresh_server_working(itr)

class DatetimeSpoke(FirstbootSpokeMixIn, NormalSpoke):
    builderObjects = ["datetimeWindow",
                      "days", "months", "years", "regions", "cities",
                      "upImage", "upImage1", "upImage2", "downImage",
                      "downImage1", "downImage2", "downImage3", "configImage",
                      "citiesFilter", "daysFilter",
                      "cityCompletion", "regionCompletion",
                      ]

    mainWidgetName = "datetimeWindow"
    uiFile = "spokes/datetime_spoke.glade"
    helpFile = "DateTimeSpoke.xml"

    category = LocalizationCategory

    icon = "preferences-system-time-symbolic"
    title = CN_("GUI|Spoke", "_TIME & DATE")

    # Hack to get libtimezonemap loaded for GtkBuilder
    # see https://bugzilla.gnome.org/show_bug.cgi?id=712184
    _hack = TimezoneMap.TimezoneMap()
    del(_hack)

    def __init__(self, *args):
        NormalSpoke.__init__(self, *args)

        # taking values from the kickstart file?
        self._kickstarted = flags.flags.automatedInstall

        self._update_datetime_timer_id = None
        self._start_updating_timer_id = None
        self._shown = False
        self._tz = None

    def initialize(self):
        NormalSpoke.initialize(self)
        self._daysStore = self.builder.get_object("days")
        self._monthsStore = self.builder.get_object("months")
        self._yearsStore = self.builder.get_object("years")
        self._regionsStore = self.builder.get_object("regions")
        self._citiesStore = self.builder.get_object("cities")
        self._tzmap = self.builder.get_object("tzmap")
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

        self._ntpSwitch = self.builder.get_object("networkTimeSwitch")

        self._regions_zones = get_all_regions_and_timezones()

        # Set the initial sensitivity of the AM/PM toggle based on the time-type selected
        self._radioButton24h.emit("toggled")

        if not flags.can_touch_runtime_system("modify system time and date"):
            self._set_date_time_setting_sensitive(False)

        self._config_dialog = NTPconfigDialog(self.data)
        self._config_dialog.initialize()

        threadMgr.add(AnacondaThread(name=constants.THREAD_DATE_TIME,
                                     target=self._initialize))

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
        for region, xlated in sorted(xlated_regions, cmp=_compare_regions):
            self.add_to_store_xlated(self._regionsStore, region, xlated)
            for city in self._regions_zones[region]:
                cities.add((city, get_xlated_timezone(city)))

        for city, xlated in sorted(cities, cmp=_compare_cities):
            self.add_to_store_xlated(self._citiesStore, city, xlated)

        self._update_datetime_timer_id = None
        if is_valid_timezone(self.data.timezone.timezone):
            self._set_timezone(self.data.timezone.timezone)
        elif not flags.flags.automatedInstall:
            log.warning("%s is not a valid timezone, falling back to default (%s)",
                        self.data.timezone.timezone, DEFAULT_TZ)
            self._set_timezone(DEFAULT_TZ)
            self.data.timezone.timezone = DEFAULT_TZ

        time_init_thread = threadMgr.get(constants.THREAD_TIME_INIT)
        if time_init_thread is not None:
            hubQ.send_message(self.__class__.__name__,
                             _("Restoring hardware time..."))
            threadMgr.wait(constants.THREAD_TIME_INIT)

        hubQ.send_ready(self.__class__.__name__, False)

    @property
    def status(self):
        if self.data.timezone.timezone:
            if is_valid_timezone(self.data.timezone.timezone):
                return _("%s timezone") % get_xlated_timezone(self.data.timezone.timezone)
            else:
                return _("Invalid timezone")
        else:
            location = self._tzmap.get_location()
            if location and location.get_property("zone"):
                return _("%s timezone") % get_xlated_timezone(location.get_property("zone"))
            else:
                return _("Nothing selected")

    def apply(self):
        self._shown = False

        # we could use self._tzmap.get_timezone() here, but it returns "" if
        # Etc/XXXXXX timezone is selected
        region = self._get_active_region()
        city = self._get_active_city()
        # nothing selected, just leave the spoke and
        # return to hub without changing anything
        if not region or not city:
            return

        old_tz = self.data.timezone.timezone
        new_tz = region + "/" + city

        self.data.timezone.timezone = new_tz

        if old_tz != new_tz:
            # new values, not from kickstart
            self.data.timezone.seen = False
            self._kickstarted = False

        self.data.timezone.nontp = not self._ntpSwitch.get_active()

    def execute(self):
        if self._update_datetime_timer_id is not None:
            GLib.source_remove(self._update_datetime_timer_id)
        self._update_datetime_timer_id = None
        self.data.timezone.setup(self.data)

    @property
    def ready(self):
        return not threadMgr.get("AnaDateTimeThread")

    @property
    def completed(self):
        if self._kickstarted and not self.data.timezone.seen:
            # taking values from kickstart, but not specified
            return False
        else:
            return is_valid_timezone(self.data.timezone.timezone)

    @property
    def mandatory(self):
        return True

    def refresh(self):
        self._shown = True

        #update the displayed time
        self._update_datetime_timer_id = GLib.timeout_add_seconds(1,
                                                    self._update_datetime)
        self._start_updating_timer_id = None

        if is_valid_timezone(self.data.timezone.timezone):
            self._tzmap.set_timezone(self.data.timezone.timezone)

        self._update_datetime()

        has_active_network = nm.nm_is_connected()
        if not has_active_network:
            self._show_no_network_warning()
        else:
            self.clear_info()
            gtk_call_once(self._config_dialog.refresh_servers_state)

        if flags.can_touch_runtime_system("get NTP service state"):
            ntp_working = has_active_network and iutil.service_running(NTP_SERVICE)
        else:
            ntp_working = not self.data.timezone.nontp

        self._ntpSwitch.set_active(ntp_working)

    @gtk_action_wait
    def _set_timezone(self, timezone):
        """
        Sets timezone to the city/region comboboxes and the timezone map.

        :param timezone: timezone to set
        :type timezone: str
        :return: if successfully set or not
        :rtype: bool

        """

        parts = timezone.split("/", 1)
        if len(parts) != 2:
            # invalid timezone cannot be set
            return False

        region, city = parts
        self._set_combo_selection(self._regionCombo, region)
        self._set_combo_selection(self._cityCombo, city)

        return True

    @gtk_action_nowait
    def add_to_store_xlated(self, store, item, xlated):
        store.append([item, xlated])

    @gtk_action_nowait
    def add_to_store(self, store, item):
        store.append([item])

    @gtk_action_nowait
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

        self._start_updating_timer_id = None

        if not flags.can_touch_runtime_system("save system time"):
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
            isys.set_system_date_time(year, month, day, hours, minutes, tz=self._tz)

        #start the timer only when the spoke is shown
        if self._shown and not self._update_datetime_timer_id:
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
        if not self._shown:
            self._update_datetime()
            self._save_system_time()
            return

        #stop time updating
        if self._update_datetime_timer_id:
            GLib.source_remove(self._update_datetime_timer_id)
            self._update_datetime_timer_id = None

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
            self._set_timezone(self._old_region + "/" + self._old_city)

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

        timezone = None

        region = self._get_active_region()
        city = self._get_active_city()

        if not region or not city or (region == self._old_region and
                                      city == self._old_city):
            # entry being edited or no change, no actions needed
            return

        if city and region:
            timezone = region + "/" + city
        else:
            # both city and region are needed to form a valid timezone
            return

        if region == "Etc":
            # Etc timezones cannot be displayed on the map, so let's reset the
            # location and manually set a highlight with no location pin.
            self._tzmap.clear_location()
            if city in ("GMT", "UTC"):
                offset = 0.0
            # The tzdb data uses POSIX-style signs for the GMT zones, which is
            # the opposite of whatever everyone else expects. GMT+4 indicates a
            # zone four hours west of Greenwich; i.e., four hours before. Reverse
            # the sign to match the libtimezone map.
            else:
                # Take the part after "GMT"
                offset = -float(city[3:])

            self._tzmap.set_selected_offset(offset)
        else:
            # we don't want the timezone-changed signal to be emitted
            self._tzmap.set_timezone(timezone)

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

    def on_location_changed(self, tz_map, location):
        if not location:
            return

        timezone = location.get_property('zone')
        if self._set_timezone(timezone):
            # timezone successfully set
            self._tz = get_timezone(timezone)
            self._update_datetime()

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

            if not nm.nm_is_connected():
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

            ret = iutil.start_service(NTP_SERVICE)
            self._set_date_time_setting_sensitive(False)

            #if starting chronyd failed and chronyd is not running,
            #set switch back to OFF
            if (ret != 0) and not iutil.service_running(NTP_SERVICE):
                switch.set_active(False)

        else:
            #turned OFF
            if not flags.can_touch_runtime_system("stop NTP service"):
                #cannot touch runtime system, nothing to do here
                return

            self._set_date_time_setting_sensitive(True)
            ret = iutil.stop_service(NTP_SERVICE)

            #if stopping chronyd failed and chronyd is running,
            #set switch back to ON
            if (ret != 0) and iutil.service_running(NTP_SERVICE):
                switch.set_active(True)

            self.clear_info()

    def on_ntp_config_clicked(self, *args):
        self._config_dialog.refresh()

        with self.main_window.enlightbox(self._config_dialog.window):
            response = self._config_dialog.run()

        if response == 1:
            pools, servers = self._config_dialog.pools_servers
            self.data.timezone.ntpservers = ntp.pools_servers_to_internal(pools, servers)

            if self._config_dialog.working_server is None:
                self._show_no_ntp_server_warning()
            else:
                self.clear_info()

