# DASD format dialog
#
# Copyright (C) 2014  Red Hat, Inc.
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
# Red Hat Author(s): Samantha N. Bueno <sbueno@redhat.com>
#                    Chris Lumens <clumens@redhat.com>
#

from pyanaconda.threads import threadMgr, AnacondaThread
from pyanaconda.ui.gui import GUIObject
from pyanaconda.ui.gui.utils import gtk_action_wait, gtk_call_once
from pyanaconda import constants
from pyanaconda.i18n import _
import threading

from blivet.devicelibs.dasd import format_dasd
from blivet.errors import DasdFormatError

import logging
log = logging.getLogger("anaconda")

__all__ = ["DasdFormatDialog"]

class DasdFormatDialog(GUIObject):
    builderObjects = ["unformattedDasdDialog"]
    mainWidgetName = "unformattedDasdDialog"
    uiFile = "spokes/lib/dasdfmt.glade"

    def __init__(self, data, storage, to_format):
        GUIObject.__init__(self, data)

        self.storage = storage
        self.to_format = to_format

        self._notebook = self.builder.get_object("formatNotebook")
        self._cancel_button = self.builder.get_object("udCancelButton")
        self._ok_button = self.builder.get_object("udOKButton")
        self._unformatted_label = self.builder.get_object("udLabel")
        self._formatting_label = self.builder.get_object("formatLabel")
        self._warn_box = self.builder.get_object("warningBox")
        self._hub_label = self.builder.get_object("returnToHubLabel1")

        if len(self.to_format) > 0:
            self._unformatted_label.set_text("\n".join("/dev/" + d for d in to_format))
        else:
            self._unformatted_label.set_text("")

        # epoch is only increased when user interrupts action to return to hub
        self._epoch = 0
        self._epoch_lock = threading.Lock()

    def run(self):
        rc = self.window.run()
        with self._epoch_lock:
            # Destroy window with epoch lock so we don't accidentally end
            # formatting
            self.window.destroy()
            if rc == 2:
                # User clicked uri to return to hub. We need to catch this here so
                # that we can halt all further dialog actions
                self._epoch += 1
        return rc

    def return_to_hub_link_clicked(self, label, uri):
        """
        The user clicked on the link that takes them back to the hub.  We need
        to kill the _check_format watcher and then emit a special response ID
        indicating the user did not press OK.

        NOTE: There is no button with response_id=2.
        """
        self.window.response(2)

    def run_dasdfmt(self, epoch_started, *args):
        """ Loop through our disks and run dasdfmt against them. """
        for disk in self.to_format:
            try:
                gtk_call_once(self._formatting_label.set_text, _("Formatting /dev/%s. This may take a moment.") % disk)
                format_dasd(disk)
            except DasdFormatError as err:
                # Log errors if formatting fails, but don't halt the installer
                log.error(str(err))
                continue

        with self._epoch_lock:
            self.update_dialog(epoch_started)

    def on_format_clicked(self, *args):
        """
        Once the format button is clicked, the option to cancel expires.
        We also need to display the spinner showing activity.
        """
        self._cancel_button.set_sensitive(False)
        self._ok_button.set_sensitive(False)
        self._notebook.set_current_page(1)

        # Loop through all of our unformatted DASDs and format them
        threadMgr.add(AnacondaThread(name=constants.THREAD_DASDFMT,
                                target=self.run_dasdfmt, args=(self._epoch,)))

    @gtk_action_wait
    def update_dialog(self, epoch_started):
        """
        This optionally updates the Gtk dialog box, assuming the user has not
        clicked to return back to the summary hub.
        """
        if epoch_started == self._epoch:
            # we only want to change anything on the dialog if we are in the
            # same epoch as it is; the only time we should not be running these
            # commands is if a user clicks return_to_hub
            self._notebook.set_current_page(2)
            self._cancel_button.set_sensitive(False)
            self._ok_button.set_sensitive(True)

            # Seems a little silly to have some of this text still displayed
            # when everything is done.
            self._unformatted_label.set_text("")
            self._hub_label.set_text("")
            self._warn_box.set_visible(False)
