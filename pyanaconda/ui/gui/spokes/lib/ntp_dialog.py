# Datetime configuration spoke class
#
# Copyright (C) 2021 Red Hat, Inc.
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
from pyanaconda import network
from pyanaconda import ntp
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import util, constants
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import TIME_SOURCE_POOL, TIME_SOURCE_SERVER
from pyanaconda.core.timer import Timer
from pyanaconda.modules.common.structures.timezone import TimeSourceData
from pyanaconda.ui.gui import GUIObject
from pyanaconda.ui.gui.utils import override_cell_property
from pyanaconda.ui.gui.helpers import GUIDialogInputCheckHandler
from pyanaconda.ui.helpers import InputCheck
from pyanaconda.timezone import NTP_SERVICE

log = get_module_logger(__name__)

# constants for server store indices
SERVER_HOSTNAME = 0
SERVER_POOL = 1
SERVER_NTS = 2
SERVER_WORKING = 3
SERVER_USE = 4
SERVER_OBJECT = 5


class NTPConfigDialog(GUIObject, GUIDialogInputCheckHandler):
    builderObjects = ["ntpConfigDialog", "addImage", "serversStore"]
    mainWidgetName = "ntpConfigDialog"
    uiFile = "spokes/datetime_spoke.glade"

    def __init__(self, data, servers, states):
        GUIObject.__init__(self, data)
        self._servers = servers
        self._active_server = None
        self._states = states

        # Use GUIDialogInputCheckHandler to manipulate the sensitivity of the
        # add button, and check for valid input in on_entry_activated
        add_button = self.builder.get_object("addButton")
        GUIDialogInputCheckHandler.__init__(self, add_button)

        self.window.set_size_request(500, 400)

        working_column = self.builder.get_object("workingColumn")
        working_renderer = self.builder.get_object("workingRenderer")
        override_cell_property(working_column, working_renderer, "icon-name", self._render_working)

        self._serverEntry = self.builder.get_object("serverEntry")
        self._serversStore = self.builder.get_object("serversStore")
        self._addButton = self.builder.get_object("addButton")
        self._poolCheckButton = self.builder.get_object("poolCheckButton")
        self._ntsCheckButton = self.builder.get_object("ntsCheckButton")

        self._serverCheck = self.add_check(self._serverEntry, self._validate_server)
        self._serverCheck.update_check_status()

        self._update_timer = Timer()

    def _render_working(self, column, renderer, model, itr, user_data=None):
        value = self._serversStore[itr][SERVER_WORKING]

        if value == constants.NTP_SERVER_QUERY:
            return "dialog-question"
        elif value == constants.NTP_SERVER_OK:
            return "emblem-default"
        else:
            return "dialog-error"

    def _validate_server(self, inputcheck):
        server = self.get_input(inputcheck.input_obj)

        # If not set, fail the check to keep the button insensitive, but don't
        # display an error
        if not server:
            return InputCheck.CHECK_SILENT

        (valid, error) = network.is_valid_hostname(server)
        if not valid:
            return "'%s' is not a valid hostname: %s" % (server, error)
        else:
            return InputCheck.CHECK_OK

    def refresh(self):
        # Update the store.
        self._serversStore.clear()

        for server in self._servers:
            self._add_row(server)

        # Start to update the status.
        self._update_timer.timeout_sec(1, self._update_rows)

        # Focus on the server entry.
        self._serverEntry.grab_focus()

    def run(self):
        self.window.show()
        rc = self.window.run()
        self.window.hide()

        # OK clicked
        if rc == 1:
            # Remove servers.
            for row in self._serversStore:
                if not row[SERVER_USE]:
                    server = row[SERVER_OBJECT]
                    self._servers.remove(server)

            # Restart the NTP service.
            if conf.system.can_set_time_synchronization:
                ntp.save_servers_to_config(self._servers)
                util.restart_service(NTP_SERVICE)

        return rc

    def _add_row(self, server):
        """Add a new row for the given NTP server.

        :param server: an NTP server
        :type server: an instance of TimeSourceData
        """
        itr = self._serversStore.append([
            "",
            False,
            False,
            constants.NTP_SERVER_QUERY,
            True,
            server
        ])

        self._refresh_row(itr)

    def _refresh_row(self, itr):
        """Refresh the given row."""
        server = self._serversStore[itr][SERVER_OBJECT]
        self._serversStore.set_value(itr, SERVER_HOSTNAME, server.hostname)
        self._serversStore.set_value(itr, SERVER_POOL, server.type == TIME_SOURCE_POOL)
        self._serversStore.set_value(itr, SERVER_NTS, "nts" in server.options)

    def _update_rows(self):
        """Periodically update the status of all rows.

        :return: True to repeat, otherwise False
        """
        for row in self._serversStore:
            server = row[SERVER_OBJECT]

            if server is self._active_server:
                continue

            status = self._states.get_status(server)
            row[SERVER_WORKING] = status

        return True

    def on_entry_activated(self, entry, *args):
        # Check that the input check has passed
        if self._serverCheck.check_status != InputCheck.CHECK_OK:
            return

        server = TimeSourceData()

        if self._poolCheckButton.get_active():
            server.type = TIME_SOURCE_POOL
        else:
            server.type = TIME_SOURCE_SERVER

        server.hostname = entry.get_text()
        server.options = ["iburst"]

        if self._ntsCheckButton.get_active():
            server.options.append("nts")

        self._servers.append(server)
        self._states.check_status(server)
        self._add_row(server)

        entry.set_text("")
        self._poolCheckButton.set_active(False)
        self._ntsCheckButton.set_active(False)

    def on_add_clicked(self, *args):
        self._serverEntry.emit("activate")

    def on_use_server_toggled(self, renderer, path, *args):
        itr = self._serversStore.get_iter(path)
        old_value = self._serversStore[itr][SERVER_USE]
        self._serversStore.set_value(itr, SERVER_USE, not old_value)

    def on_pool_toggled(self, renderer, path, *args):
        itr = self._serversStore.get_iter(path)
        server = self._serversStore[itr][SERVER_OBJECT]

        if server.type == TIME_SOURCE_SERVER:
            server.type = TIME_SOURCE_POOL
        else:
            server.type = TIME_SOURCE_SERVER

        self._refresh_row(itr)

    def on_nts_toggled(self, renderer, path, *args):
        itr = self._serversStore.get_iter(path)
        server = self._serversStore[itr][SERVER_OBJECT]

        if "nts" in server.options:
            server.options.remove("nts")
        else:
            server.options.append("nts")

        self._states.check_status(server)
        self._refresh_row(itr)

    def on_server_editing_started(self, renderer, editable, path):
        itr = self._serversStore.get_iter(path)
        self._active_server = self._serversStore[itr][SERVER_OBJECT]

    def on_server_editing_canceled(self, renderer):
        self._active_server = None

    def on_server_edited(self, renderer, path, new_text, *args):
        self._active_server = None

        if not path:
            return

        (valid, error) = network.is_valid_hostname(new_text)
        if not valid:
            log.error("'%s' is not a valid hostname: %s", new_text, error)
            return

        itr = self._serversStore.get_iter(path)
        server = self._serversStore[itr][SERVER_OBJECT]

        if server.hostname == new_text:
            return

        server.hostname = new_text
        self._states.check_status(server)
        self._refresh_row(itr)
