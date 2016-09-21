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

import logging
log = logging.getLogger("anaconda")
from pyanaconda.ui.categories.localization import LocalizationCategory
from pyanaconda.ui.tui.spokes import NormalTUISpoke, EditTUIDialog
from pyanaconda.ui.tui.simpleline import TextWidget, ColumnWidget
from pyanaconda.ui.common import FirstbootSpokeMixIn
from pyanaconda import timezone
from pyanaconda import ntp
from pyanaconda import constants
from pyanaconda.i18n import N_, _, C_
from pyanaconda.constants_text import INPUT_PROCESSED
from pyanaconda.threads import threadMgr, AnacondaThread
from pyanaconda.flags import flags

from collections import OrderedDict
from threading import RLock

def format_ntp_status_list(servers):
    ntp_server_states = {
        constants.NTP_SERVER_OK: _("status: working"),
        constants.NTP_SERVER_NOK: _("status: not working"),
        constants.NTP_SERVER_QUERY: _("checking status")
    }
    status_list = []
    for server, server_state in servers.items():
        status_list.append("%s (%s)" % (server, ntp_server_states[server_state]))
    return status_list

__all__ = ["TimeSpoke"]

class TimeSpoke(FirstbootSpokeMixIn, NormalTUISpoke):
    title = N_("Time settings")
    category = LocalizationCategory

    def __init__(self, app, data, storage, payload, instclass):
        NormalTUISpoke.__init__(self, app, data, storage, payload, instclass)
        self._timezone_spoke = None
        # we use an ordered dict to keep the NTP server insertion order
        self._ntp_servers = OrderedDict()
        self._ntp_servers_lock = RLock()

    @property
    def indirect(self):
        return False

    def initialize(self):
        # We get the initial NTP servers (if any):
        # - from kickstart when running inside of Anaconda
        #   during the installation
        # - from config files when running in Initial Setup
        #   after the installation
        ntp_servers = []

        if constants.ANACONDA_ENVIRON in flags.environs:
            ntp_servers = self.data.timezone.ntpservers
        elif constants.FIRSTBOOT_ENVIRON in flags.environs:
            ntp_servers = ntp.get_servers_from_config()[1]  # returns a (NPT pools, NTP servers) tupple
        else:
            log.error("tui time spoke: unsupported environment configuration %s,"
                      "can't decide where to get initial NTP servers", flags.environs)

        # check if the NTP servers appear to be working or not
        if ntp_servers:
            for server in ntp_servers:
                self._ntp_servers[server] = constants.NTP_SERVER_QUERY

            # check if the newly added NTP servers work fine
            self._check_ntp_servers_async(self._ntp_servers.keys())

    def _check_ntp_servers_async(self, servers):
        """Asynchronously check if given NTP servers appear to be working.

        :param list servers: list of servers to check
        """
        for server in servers:
            threadMgr.add(AnacondaThread(prefix=constants.THREAD_NTP_SERVER_CHECK,
                                         target=self._check_ntp_server,
                                         args=(server,)))

    def _check_ntp_server(self, server):
        """Check if an NTP server appears to be working.

        :param str server: NTP server address
        :returns: True if the server appears to be working, False if not
        :rtype: bool
        """
        log.debug("checking NTP server %s", server)
        result = ntp.ntp_server_working(server)
        if result:
            log.debug("NTP server %s appears to be working", server)
            self.set_ntp_server_status(server, constants.NTP_SERVER_OK)
        else:
            log.debug("NTP server %s appears not to be working", server)
            self.set_ntp_server_status(server, constants.NTP_SERVER_NOK)

    @property
    def ntp_servers(self):
        """Return a list of NTP servers known to the Time spoke.

        :returns: a list of NTP servers
        :rtype: list of strings
        """
        return self._ntp_servers

    def add_ntp_server(self, server):
        """Add NTP server address to our internal NTP server tracking dictionary.

        :param str server: NTP server address to add
        """
        # the add & remove operations should (at least at the moment) be never
        # called from different threads at the same time, but lets just use
        # a lock there when we are at it
        with self._ntp_servers_lock:
            if server not in self._ntp_servers:
                self._ntp_servers[server] = constants.NTP_SERVER_QUERY
                self._check_ntp_servers_async([server])

    def remove_ntp_server(self, server):
        """Remove NTP server address from our internal NTP server tracking dictionary.

        :param str server: NTP server address to remove
        """
        # the remove-server and set-server-status operations need to be atomic,
        # so that we avoid reintroducing removed servers by setting their status
        with self._ntp_servers_lock:
            if server in self._ntp_servers:
                del self._ntp_servers[server]

    def set_ntp_server_status(self, server, status):
        """Set status for an NTP server in the NTP server dict.

        The status can be "working", "not working" or "check in progress",
        and is defined by three constants defined in constants.py.

        :param str server: an NTP server
        :param int status: status of the NTP server
        """

        # the remove-server and set-server-status operations need to be atomic,
        # so that we avoid reintroducing removed server by setting their status
        with self._ntp_servers_lock:
            if server in self._ntp_servers:
                self._ntp_servers[server] = status

    @property
    def timezone_spoke(self):
        if not self._timezone_spoke:
            self._timezone_spoke = TimeZoneSpoke(self.app, self.data, self.storage,
                                                 self.payload, self.instclass)
        return self._timezone_spoke

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

    def _summary_text(self):
        """Return summary of current timezone & NTP configuration.

        :returns: current status
        :rtype: str
        """
        msg = ""
        # timezone
        timezone_msg = _("not set")
        if self.data.timezone.timezone:
            timezone_msg = self.data.timezone.timezone

        msg += _("Timezone: %s\n") % timezone_msg

        # newline section separator
        msg += "\n"

        # NTP
        msg += _("NTP servers:")
        if self._ntp_servers:
            for status in format_ntp_status_list(self._ntp_servers):
                msg += "\n%s" % status
        else:
            msg += _("not configured")

        return msg

    def refresh(self, args=None):
        NormalTUISpoke.refresh(self, args)

        summary = self._summary_text()
        self._window += [TextWidget(summary), ""]

        if self.data.timezone.timezone:
            timezone_option = _("Change timezone")
        else:
            timezone_option = _("Set timezone")

        _options = [timezone_option, _("Configure NTP servers")]
        text = [TextWidget(m) for m in _options]

        def _prep(i, w):
            """ Mangle our text to make it look pretty on screen. """
            number = TextWidget("%2d)" % (i + 1))
            return ColumnWidget([(4, [number]), (None, [w])], 1)

        # gnarl and mangle all of our widgets so things look pretty on screen
        choices = [_prep(i, w) for i, w in enumerate(text)]

        displayed = ColumnWidget([(78, choices)], 1)
        self._window.append(displayed)

        return True

    def input(self, args, key):
        """ Handle the input - visit a sub spoke or go back to hub."""
        try:
            num = int(key)
        except ValueError:
            return key

        if num == 1:
            # set timezone
            self.app.switch_screen_modal(self.timezone_spoke)
            self.close()
            return INPUT_PROCESSED
        elif num == 2:
            # configure NTP servers
            newspoke = NTPServersSpoke(self.app, self.data, self.storage,
                                       self.payload, self.instclass, self)
            self.app.switch_screen_modal(newspoke)
            self.apply()
            self.close()
            return INPUT_PROCESSED
        else:
            # the user provided an invalid option number, just stay in the spoke
            return INPUT_PROCESSED

    def apply(self):
        # update the NTP server list in kickstart
        self.data.timezone.ntpservers = list(self.ntp_servers.keys())

class TimeZoneSpoke(NormalTUISpoke):
    """
       .. inheritance-diagram:: TimeZoneSpoke
          :parts: 3
    """
    title = N_("Timezone settings")
    category = LocalizationCategory

    def __init__(self, app, data, storage, payload, instclass):
        NormalTUISpoke.__init__(self, app, data, storage, payload, instclass)

        # it's stupid to call get_all_regions_and_timezones twice, but regions
        # needs to be unsorted in order to display in the same order as the GUI
        # so whatever
        self._regions = list(timezone.get_all_regions_and_timezones().keys())
        self._timezones = dict((k, sorted(v)) for k, v in timezone.get_all_regions_and_timezones().items())
        self._lower_regions = [r.lower() for r in self._timezones]

        self._zones = ["%s/%s" % (region, z) for region in self._timezones for z in self._timezones[region]]
        # for lowercase lookup
        self._lower_zones = [z.lower().replace("_", " ") for region in self._timezones for z in self._timezones[region]]
        self._selection = ""

    @property
    def indirect(self):
        return True

    def refresh(self, args=None):
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
        left = [_prep(i, w) for i, w in enumerate(displayed) if i <= middle]
        center = [_prep(i, w) for i, w in enumerate(displayed) if i > middle and i <= 2 * middle]
        right = [_prep(i, w) for i, w in enumerate(displayed) if i > 2 * middle]

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
                    self.app.switch_screen(self, self._regions[index])
                return INPUT_PROCESSED
            # TRANSLATORS: 'b' to go back
            elif key.lower() == C_('TUI|Spoke Navigation|Time Settings', 'b'):
                self.app.switch_screen(self, None)
                return INPUT_PROCESSED
            else:
                return key

        if keyid < 0:
            return key
        if args:
            if keyid >= len(self._timezones[args]):
                return key
            self._selection = "%s/%s" % (args, self._timezones[args][keyid])
            self.apply()
            self.close()
        else:
            if keyid >= len(self._regions):
                return key
            region = self._regions[keyid]
            selected_timezones = self._timezones[region]
            if len(selected_timezones) == 1:
                self._selection = "%s/%s" % (region, selected_timezones[0])
                self.apply()
                self.close()
            else:
                self.app.switch_screen(self, region)
            return INPUT_PROCESSED

    def prompt(self, args=None):
        return _("Please select the timezone.\nUse numbers or type names directly ['%(back)s' to region list, '%(quit)s' to quit]: ") % {
            # TRANSLATORS: 'b' to go back
            'back': C_('TUI|Spoke Navigation|Time Settings', 'b'),
            # TRANSLATORS:'q' to quit
            'quit': C_('TUI|Spoke Navigation|Time Settings', 'q')
        }

    def apply(self):
        self.data.timezone.timezone = self._selection
        self.data.timezone.seen = False

class NTPServersSpoke(NormalTUISpoke):
    title = N_("NTP configuration")
    category = LocalizationCategory

    def __init__(self, app, data, storage, payload, instclass, time_spoke):
        NormalTUISpoke.__init__(self, app, data, storage, payload, instclass)
        self._time_spoke = time_spoke

    @property
    def indirect(self):
        return True

    def _summary_text(self):
        """Return summary of NTP configuration."""
        msg = _("NTP servers:")
        if self._time_spoke.ntp_servers:
            for status in format_ntp_status_list(self._time_spoke.ntp_servers):
                msg += "\n%s" % status
        else:
            msg += _("no NTP servers have been configured")
        return msg

    def refresh(self, args=None):
        NormalTUISpoke.refresh(self, args)

        summary = self._summary_text()
        self._window += [TextWidget(summary), ""]

        _options = [_("Add NTP server")]
        # only add the remove option when we can remove something
        if self._time_spoke.ntp_servers:
            _options.append(_("Remove NTP server"))
        text = [TextWidget(m) for m in _options]

        def _prep(i, w):
            """ Mangle our text to make it look pretty on screen. """
            number = TextWidget("%2d)" % (i + 1))
            return ColumnWidget([(4, [number]), (None, [w])], 1)

        # gnarl and mangle all of our widgets so things look pretty on screen
        choices = [_prep(i, w) for i, w in enumerate(text)]

        displayed = ColumnWidget([(78, choices)], 1)
        self._window.append(displayed)

        return True

    def input(self, args, key):
        try:
            num = int(key)
        except ValueError:
            return key

        if num == 1:
            # add an NTP server
            newspoke = AddNTPServerSpoke(self.app, self.data, self.storage,
                                         self.payload, self.instclass, self._time_spoke)
            self.app.switch_screen_modal(newspoke)
            return INPUT_PROCESSED
        elif self._time_spoke.ntp_servers and num == 2:
            # remove an NTP server
            newspoke = RemoveNTPServerSpoke(self.app, self.data, self.storage,
                                            self.payload, self.instclass, self._time_spoke)
            self.app.switch_screen_modal(newspoke)
            return INPUT_PROCESSED
        else:
            # the user provided an invalid option number,
            # just stay in the spoke
            return INPUT_PROCESSED

    def apply(self):
        pass

class AddNTPServerSpoke(EditTUIDialog):
    title = N_("Add NTP server address")
    category = LocalizationCategory

    def __init__(self, app, data, storage, payload, instclass, time_spoke):
        EditTUIDialog.__init__(self, app, data, storage, payload, instclass)
        self._time_spoke = time_spoke
        self._new_ntp_server = None

    @property
    def indirect(self):
        return True

    def refresh(self, args=None):
        EditTUIDialog.refresh(self, args)
        return True

    def prompt(self, args=None):
        # the title is enough, no custom prompt is needed
        if self.value is None:  # first run or nothing entered
            return _("Enter an NTP server address and press Enter\n")

        # an NTP server address has been entered
        self._new_ntp_server = self.value

        self.apply()
        self.close()

    def input(self, entry, key):
        # we accept any string as NTP server address, as we do an automatic
        # working/not-working check on the address later
        self.value = key
        return True

    def apply(self):
        if self._new_ntp_server:
            self._time_spoke.add_ntp_server(self._new_ntp_server)

class RemoveNTPServerSpoke(NormalTUISpoke):
    title = N_("Select an NTP server to remove")
    category = LocalizationCategory

    def __init__(self, app, data, storage, payload, instclass, timezone_spoke):
        NormalTUISpoke.__init__(self, app, data, storage, payload, instclass)
        self._time_spoke = timezone_spoke
        self._ntp_server_index = None

    @property
    def indirect(self):
        return True

    def _summary_text(self):
        """Return a numbered listing of NTP servers."""
        msg = ""
        for index, status in enumerate(format_ntp_status_list(self._time_spoke.ntp_servers), start=1):
            msg += "%d) %s" % (index, status)
            if index < len(self._time_spoke.ntp_servers):
                msg += "\n"
        return msg

    def refresh(self, args=None):
        NormalTUISpoke.refresh(self, args)
        summary = self._summary_text()
        self._window += [TextWidget(summary), ""]
        return True

    def input(self, args, key):
        try:
            num = int(key)
        except ValueError:
            return key

        # we expect a number corresponding to one of the NTP servers
        # in the listing - the server corresponding to the number will be
        # removed from the NTP server tracking (ordered) dict
        if num > 0 and num <= len(self._time_spoke.ntp_servers):
            self._ntp_server_index = num - 1
            self.apply()
            self.close()
            return INPUT_PROCESSED
        else:
            # the user enter a number that is out of range of the
            # available NTP servers, ignore it and stay in spoke
            return INPUT_PROCESSED

    def apply(self):
        if self._ntp_server_index is not None:
            ntp_server_address = list(self._time_spoke.ntp_servers.keys())[self._ntp_server_index]
            self._time_spoke.remove_ntp_server(ntp_server_address)
