# Disk configuration refresh dialog
#
# Copyright (C) 2013  Red Hat, Inc.
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
from pyanaconda.core.timer import Timer
from pyanaconda.threading import threadMgr, AnacondaThread
from pyanaconda.ui.gui import GUIObject
from pyanaconda.core import constants
from pyanaconda.ui.lib.storage import reset_storage

__all__ = ["RefreshDialog"]


class RefreshDialog(GUIObject):
    builderObjects = ["refreshDialog"]
    mainWidgetName = "refreshDialog"
    uiFile = "spokes/lib/refresh.glade"

    def __init__(self, data):
        super().__init__(data)
        self._notebook = self.builder.get_object("refreshNotebook")
        self._cancel_button = self.builder.get_object("refreshCancelButton")
        self._ok_button = self.builder.get_object("refreshOKButton")

        self._elapsed = 0
        self._rescan_timer = Timer()

    def run(self):
        rc = self.window.run()
        self.window.destroy()
        return rc

    def _check_rescan(self, *args):
        if threadMgr.get(constants.THREAD_STORAGE):
            self._elapsed += 1

            # If more than five seconds has elapsed since the rescan started,
            # give the user the option to return to the hub.
            if self._elapsed >= 5:
                self._notebook.set_current_page(2)

            return True

        # Seems a little silly to have this warning text still displayed
        # when everything is done.
        box = self.builder.get_object("warningBox")
        box.set_visible(False)

        self._cancel_button.set_sensitive(False)
        self._ok_button.set_sensitive(True)
        self._notebook.set_current_page(3)
        return False

    def on_return_to_hub_link_clicked(self, label, uri):
        # The user clicked on the link that takes them back to the hub.  We need
        # to kill the _check_rescan watcher and then emit a special response ID
        # indicating the user did not press OK.
        #
        # NOTE: There is no button with response_id=2.
        self._rescan_timer.cancel()
        self.window.response(2)

    def on_rescan_clicked(self, button):
        # Once the rescan button is clicked, the option to cancel expires.
        # We also need to display the spinner showing activity.
        self._cancel_button.set_sensitive(False)
        self._ok_button.set_sensitive(False)
        self._notebook.set_current_page(1)

        # And now to fire up the storage reinitialization.
        threadMgr.add(AnacondaThread(name=constants.THREAD_STORAGE,
                                     target=reset_storage,
                                     kwargs={"scan_all": True}))

        self._elapsed = 0

        # This watches for the rescan to be finished and updates the dialog when
        # that happens.
        self._rescan_timer.timeout_sec(1, self._check_rescan)
