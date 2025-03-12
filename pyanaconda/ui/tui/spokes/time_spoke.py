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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from collections import namedtuple

from simpleline.render.containers import ListColumnContainer
from simpleline.render.prompt import Prompt
from simpleline.render.screen import InputState
from simpleline.render.screen_handler import ScreenHandler
from simpleline.render.widgets import TextWidget

from pyanaconda import ntp, timezone
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import constants
from pyanaconda.core.constants import TIME_SOURCE_SERVER
from pyanaconda.core.i18n import N_, _
from pyanaconda.flags import flags
from pyanaconda.modules.common.constants.services import TIMEZONE
from pyanaconda.modules.common.structures.timezone import TimeSourceData
from pyanaconda.modules.common.util import is_module_available
from pyanaconda.ntp import NTPServerStatusCache
from pyanaconda.ui.categories.localization import LocalizationCategory
from pyanaconda.ui.common import FirstbootSpokeMixIn
from pyanaconda.ui.tui.spokes import NormalTUISpoke

log = get_module_logger(__name__)

__all__ = ["TimeSpoke"]

# TRANSLATORS: 'b' to go back to region list
PROMPT_BACK_DESCRIPTION = N_("to go back to region list")
PROMPT_BACK_KEY = 'b'

CallbackTimezoneArgs = namedtuple("CallbackTimezoneArgs", ["region", "timezone"])


class TimeSpoke(FirstbootSpokeMixIn, NormalTUISpoke):
    category = LocalizationCategory

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

    def __init__(self, data, storage, payload):
        NormalTUISpoke.__init__(self, data, storage, payload)
        self.title = N_("Time settings")
        self._timezone_spoke = None
        self._container = None
        self._ntp_servers = []
        self._ntp_servers_states = NTPServerStatusCache()
        self._timezone_module = TIMEZONE.get_proxy()

    @property
    def indirect(self):
        return False

    def initialize(self):
        self.initialize_start()
        # We get the initial NTP servers (if any):
        # - from kickstart when running inside of Anaconda
        #   during the installation
        # - from config files when running in Initial Setup
        #   after the installation
        if constants.ANACONDA_ENVIRON in flags.environs:
            self._ntp_servers = TimeSourceData.from_structure_list(
                self._timezone_module.TimeSources
            )
        elif constants.FIRSTBOOT_ENVIRON in flags.environs:
            self._ntp_servers = ntp.get_servers_from_config()
        else:
            log.error("tui time spoke: unsupported environment configuration %s,"
                      "can't decide where to get initial NTP servers", flags.environs)

        # check if the newly added NTP servers work fine
        for server in self._ntp_servers:
            self._ntp_servers_states.check_status(server)

        # we assume that the NTP spoke is initialized enough even if some NTP
        # server check threads might still be running
        self.initialize_done()

    @property
    def timezone_spoke(self):
        if not self._timezone_spoke:
            self._timezone_spoke = TimeZoneSpoke(self.data, self.storage, self.payload)
        return self._timezone_spoke

    @property
    def completed(self):
        return bool(self._timezone_module.Timezone)

    @property
    def mandatory(self):
        return True

    @property
    def status(self):
        kickstart_timezone = self._timezone_module.Timezone

        if kickstart_timezone:
            return _("%s timezone") % kickstart_timezone
        else:
            return _("Timezone is not set.")

    def _summary_text(self):
        """Return summary of current timezone & NTP configuration.

        :returns: current status
        :rtype: str
        """
        msg = ""

        # timezone
        kickstart_timezone = self._timezone_module.Timezone
        timezone_msg = _("not set")
        if kickstart_timezone:
            timezone_msg = kickstart_timezone

        msg += _("Timezone: %s\n") % timezone_msg

        # newline section separator
        msg += "\n"

        # NTP
        msg += ntp.get_ntp_servers_summary(
            self._ntp_servers,
            self._ntp_servers_states
        )

        return msg

    def refresh(self, args=None):
        NormalTUISpoke.refresh(self, args)

        summary = self._summary_text()
        self.window.add_with_separator(TextWidget(summary))

        if self._timezone_module.Timezone:
            timezone_option = _("Change timezone")
        else:
            timezone_option = _("Set timezone")

        self._container = ListColumnContainer(1, columns_width=78, spacing=1)

        self._container.add(
            TextWidget(timezone_option),
            callback=self._timezone_callback
        )

        self._container.add(
            TextWidget(_("Configure NTP servers")),
            callback=self._configure_ntp_server_callback
        )

        self.window.add_with_separator(self._container)

    def _timezone_callback(self, data):
        ScreenHandler.push_screen_modal(self.timezone_spoke)
        self.close()

    def _configure_ntp_server_callback(self, data):
        new_spoke = NTPServersSpoke(
            self.data,
            self.storage,
            self.payload,
            self._ntp_servers,
            self._ntp_servers_states
        )
        ScreenHandler.push_screen_modal(new_spoke)
        self.apply()
        self.close()

    def input(self, args, key):
        """ Handle the input - visit a sub spoke or go back to hub."""
        if self._container.process_user_input(key):
            return InputState.PROCESSED
        else:
            return super().input(args, key)

    def apply(self):
        # update the NTP server list in kickstart
        self._timezone_module.TimeSources = \
            TimeSourceData.to_structure_list(self._ntp_servers)


class TimeZoneSpoke(NormalTUISpoke):
    """
       .. inheritance-diagram:: TimeZoneSpoke
          :parts: 3
    """
    category = LocalizationCategory

    def __init__(self, data, storage, payload):
        super().__init__(data, storage, payload)

        self.title = N_("Timezone settings")
        self._container = None
        # it's stupid to call get_all_regions_and_timezones twice, but regions
        # needs to be unsorted in order to display in the same order as the GUI
        # so whatever
        self._regions = list(timezone.get_all_regions_and_timezones().keys())
        self._timezones = dict((k, sorted(v)) for k, v in timezone.get_all_regions_and_timezones().items())
        self._lower_regions = [r.lower() for r in self._regions]

        self._zones = ["%s/%s" % (region, z) for region in self._timezones for z in self._timezones[region]]
        # for lowercase lookup
        self._lower_zones = [z.lower().replace("_", " ") for region in self._timezones for z in self._timezones[region]]
        self._selection = ""

        self._timezone_module = TIMEZONE.get_proxy()

    @property
    def indirect(self):
        return True

    def refresh(self, args=None):
        """args is None if we want a list of zones or "zone" to show all timezones in that zone."""
        super().refresh(args)

        self._container = ListColumnContainer(3, columns_width=24)

        if args and args in self._timezones:
            self.window.add(TextWidget(_("Available timezones in region %s") % args))
            for tz in self._timezones[args]:
                self._container.add(TextWidget(tz), self._select_timezone_callback, CallbackTimezoneArgs(args, tz))
        else:
            self.window.add(TextWidget(_("Available regions")))
            for region in self._regions:
                self._container.add(TextWidget(region), self._select_region_callback, region)

        self.window.add_with_separator(self._container)

    def _select_timezone_callback(self, data):
        self._selection = "%s/%s" % (data.region, data.timezone)
        self.apply()
        self.close()

    def _select_region_callback(self, data):
        region = data
        selected_timezones = self._timezones[region]
        if len(selected_timezones) == 1:
            self._selection = "%s/%s" % (region, selected_timezones[0])
            self.apply()
            self.close()
        else:
            ScreenHandler.replace_screen(self, region)

    def input(self, args, key):
        if self._container.process_user_input(key):
            return InputState.PROCESSED
        else:
            if key.lower().replace("_", " ") in self._lower_zones:
                index = self._lower_zones.index(key.lower().replace("_", " "))
                self._selection = self._zones[index]
                self.apply()
                return InputState.PROCESSED_AND_CLOSE
            elif key.lower() in self._lower_regions:
                index = self._lower_regions.index(key.lower())
                if len(self._timezones[self._regions[index]]) == 1:
                    self._selection = "%s/%s" % (self._regions[index],
                                                 self._timezones[self._regions[index]][0])
                    self.apply()
                    self.close()
                else:
                    ScreenHandler.replace_screen(self, self._regions[index])
                return InputState.PROCESSED
            elif key.lower() == PROMPT_BACK_KEY:
                ScreenHandler.replace_screen(self)
                return InputState.PROCESSED
            else:
                return key

    def prompt(self, args=None):
        """ Customize default prompt. """
        prompt = NormalTUISpoke.prompt(self, args)
        prompt.set_message(_("Please select the timezone. Use numbers or type names directly"))
        prompt.add_option(PROMPT_BACK_KEY, _(PROMPT_BACK_DESCRIPTION))
        return prompt

    def apply(self):
        self._timezone_module.SetTimezoneWithPriority(
            self._selection,
            constants.TIMEZONE_PRIORITY_USER
        )
        self._timezone_module.Kickstarted = False


class NTPServersSpoke(NormalTUISpoke):
    category = LocalizationCategory

    def __init__(self, data, storage, payload, servers, states):
        super().__init__(data, storage, payload)
        self.title = N_("NTP configuration")
        self._container = None
        self._servers = servers
        self._states = states

    @property
    def indirect(self):
        return True

    def refresh(self, args=None):
        super().refresh(args)

        summary = ntp.get_ntp_servers_summary(
            self._servers,
            self._states
        )

        self.window.add_with_separator(TextWidget(summary))

        self._container = ListColumnContainer(1, columns_width=78, spacing=1)
        self._container.add(TextWidget(_("Add NTP server")), self._add_ntp_server)

        # only add the remove option when we can remove something
        if self._servers:
            self._container.add(TextWidget(_("Remove NTP server")), self._remove_ntp_server)

        self.window.add_with_separator(self._container)

    def _add_ntp_server(self, data):
        new_spoke = AddNTPServerSpoke(
            self.data,
            self.storage,
            self.payload,
            self._servers,
            self._states
        )
        ScreenHandler.push_screen_modal(new_spoke)
        self.redraw()

    def _remove_ntp_server(self, data):
        new_spoke = RemoveNTPServerSpoke(
            self.data,
            self.storage,
            self.payload,
            self._servers,
            self._states
        )
        ScreenHandler.push_screen_modal(new_spoke)
        self.redraw()

    def input(self, args, key):
        if self._container.process_user_input(key):
            return InputState.PROCESSED
        else:
            return super().input(args, key)

    def apply(self):
        pass


class AddNTPServerSpoke(NormalTUISpoke):
    category = LocalizationCategory

    def __init__(self, data, storage, payload, servers, states):
        super().__init__(data, storage, payload)
        self.title = N_("Add NTP server address")
        self._servers = servers
        self._states = states
        self._value = None

    @property
    def indirect(self):
        return True

    def refresh(self, args=None):
        super().refresh(args)
        self._value = None

    def prompt(self, args=None):
        # the title is enough, no custom prompt is needed
        if self._value is None:  # first run or nothing entered
            return Prompt(_("Enter an NTP server address and press %s") % Prompt.ENTER)

        # an NTP server address has been entered
        self._add_ntp_server(self._value)

        self.close()

    def _add_ntp_server(self, server_hostname):
        for server in self._servers:
            if server.hostname == server_hostname:
                return

        server = TimeSourceData()
        server.type = TIME_SOURCE_SERVER
        server.hostname = server_hostname
        server.options = ["iburst"]

        self._servers.append(server)
        self._states.check_status(server)

    def input(self, args, key):
        # we accept any string as NTP server address, as we do an automatic
        # working/not-working check on the address later
        self._value = key
        return InputState.DISCARDED

    def apply(self):
        pass


class RemoveNTPServerSpoke(NormalTUISpoke):
    category = LocalizationCategory

    def __init__(self, data, storage, payload, servers, states):
        super().__init__(data, storage, payload)
        self.title = N_("Select an NTP server to remove")
        self._servers = servers
        self._states = states
        self._container = None

    @property
    def indirect(self):
        return True

    def refresh(self, args=None):
        super().refresh(args)
        self._container = ListColumnContainer(1)

        for server in self._servers:
            description = ntp.get_ntp_server_summary(
                server, self._states
            )

            self._container.add(
                TextWidget(description),
                self._remove_ntp_server,
                server
            )

        self.window.add_with_separator(self._container)

    def _remove_ntp_server(self, server):
        self._servers.remove(server)

    def input(self, args, key):
        if self._container.process_user_input(key):
            return InputState.PROCESSED_AND_CLOSE

        return super().input(args, key)

    def apply(self):
        pass
