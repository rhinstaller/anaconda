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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pyanaconda import network, ntp
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import constants
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import TIME_SOURCE_POOL, TIME_SOURCE_SERVER
from pyanaconda.core.service import restart_service
from pyanaconda.core.timer import Timer
from pyanaconda.modules.common.structures.timezone import TimeSourceData
from pyanaconda.timezone import NTP_SERVICE
from pyanaconda.ui.gui import GUIObject
from pyanaconda.ui.gui.utils import override_cell_property

log = get_module_logger(__name__)

# constants for server store indices
SERVER_HOSTNAME = 0
SERVER_POOL = 1
SERVER_NTS = 2
SERVER_WORKING = 3
SERVER_OBJECT = 4

SERVER_STARTING_STRING = "<fill in server host name>"


class NTPConfigDialog(GUIObject):
    builderObjects = ["ntpConfigDialog", "serversStore"]
    mainWidgetName = "ntpConfigDialog"
    uiFile = "spokes/lib/ntp_dialog.glade"

    def __init__(self, data, servers, states):
        GUIObject.__init__(self, data)
        self._servers = servers
        self._active_server = None
        self._states = states

        # self.window.set_size_request(500, 400)

        working_column = self.builder.get_object("workingColumn")
        working_renderer = self.builder.get_object("workingRenderer")
        override_cell_property(working_column, working_renderer, "icon-name", self._render_working)

        self._serversView = self.builder.get_object("serversView")
        self._serversStore = self.builder.get_object("serversStore")

        self._update_timer = Timer()

    def _render_working(self, column, renderer, model, itr, user_data=None):
        value = self._serversStore[itr][SERVER_WORKING]

        if value == constants.NTP_SERVER_QUERY:
            return "dialog-question-symbolic"
        elif value == constants.NTP_SERVER_OK:
            return "emblem-default-symbolic"
        else:
            return "dialog-error-symbolic"

    def refresh(self):
        # Update the store.
        self._serversStore.clear()

        for server in self._servers:
            self._add_row(server)

        # Start to update the status.
        self._update_timer.timeout_sec(1, self._update_rows)

    def run(self):
        self.window.show()
        rc = self.window.run()
        self.window.hide()

        # OK clicked
        if rc == 1:
            # Clean up unedited entries
            self._cleanup_unedited_entry()
            # Restart the NTP service.
            if conf.system.can_set_time_synchronization:
                ntp.save_servers_to_config(self._servers)
                restart_service(NTP_SERVICE)

        return rc

    def _get_last_entry_itr(self):
        """Get itr of the last entry."""
        index = len(self._serversStore) - 1

        if index < 0:
            return None

        return self._serversStore.get_iter_from_string(str(index))

    def _is_last_entry_unedited(self):
        """Is the last entry unedited?"""
        itr = self._get_last_entry_itr()

        if not itr:
            return False

        server = self._serversStore[itr][SERVER_OBJECT]
        return server.hostname == SERVER_STARTING_STRING

    def _cleanup_unedited_entry(self):
        """Clean up unedited entry.

        There can be only one, at the very end.
        """
        if not self._is_last_entry_unedited():
            return

        itr = self._get_last_entry_itr()
        self._serversStore.remove(itr)
        del self._servers[-1]

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

    def on_add_button_clicked(self, *args):
        """Handler for Add button.

        Tries to add a new server for editing, or reuse an existing server that was not edited
        after adding.
        """
        # check if there is any unedited server
        # exactly zero or one such server can exist, at last position only
        if not self._is_last_entry_unedited():
            # no unedited leftover, so make a new server with a reasonable guess about the defaults
            server = TimeSourceData()
            server.type = TIME_SOURCE_SERVER
            server.hostname = SERVER_STARTING_STRING
            server.options = ["iburst"]
            # add the (still invalid) server
            self._servers.append(server)
            self._states.check_status(server)
            self._add_row(server)

        # select the correct row - it is always the last one
        itr = self._get_last_entry_itr()
        selection = self._serversView.get_selection()
        selection.select_iter(itr)
        self._serversView.grab_focus()

        # start editing the newly added server hostname
        # it is already selected so just "press" the edit button
        self.on_edit_button_clicked(*args)

    def on_edit_button_clicked(self, *args):
        """Handler for Edit button"""
        selection = self._serversView.get_selection()
        store, items = selection.get_selected_rows() # pylint: disable=unused-variable
        path = items[-1]  # take only the last item
        column = self._serversView.get_column(0)  # first column is server/hostname
        self._serversView.set_cursor(path, column, True)

    def on_remove_button_clicked(self, *args):
        """Handler for Remove button"""
        selection = self._serversView.get_selection()
        store, items = selection.get_selected_rows()
        for path in reversed(items):
            itr = store.get_iter(path)
            server = store[itr][SERVER_OBJECT]
            store.remove(itr)
            self._servers.remove(server)

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
