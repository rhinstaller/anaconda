# zFCP configuration dialog
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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Samantha N. Bueno <sbueno@redhat.com>
#

from pyanaconda.ui.gui import GUIObject
from pyanaconda.ui.gui.utils import gtk_action_nowait

from blivet.zfcp import ZFCPDevice

__all__ = ["ZFCPDialog"]

class ZFCPDialog(GUIObject):
    """ Gtk dialog which allows users to manually add zFCP devices without
        having previously specified them in a parm file.
    """
    builderObjects = ["zfcpDialog"]
    mainWidgetName = "zfcpDialog"
    uiFile = "spokes/advstorage/zfcp.glade"

    def __init__(self, data, storage):
        GUIObject.__init__(self, data)
        self.storage = storage
        self.zfcp = self.storage.zfcp()

        self._discoveryError = None

        self._update_devicetree = False

        # grab all of the ui objects
        self._zfcpNotebook = self.builder.get_object("zfcpNotebook")

        self._configureGrid = self.builder.get_object("configureGrid")
        self._conditionNotebook = self.builder.get_object("conditionNotebook")

        self._startButton = self.builder.get_object("startButton")
        self._okButton = self.builder.get_object("okButton")
        self._cancelButton = self.builder.get_object("cancelButton")

        self._deviceEntry = self.builder.get_object("deviceEntry")
        self._wwpnEntry = self.builder.get_object("wwpnEntry")
        self._lunEntry = self.builder.get_object("lunEntry")

    def refresh(self):
        self._deviceEntry.set_text("")
        self._deviceEntry.set_sensitive(True)
        self._startButton.set_sensitive(True)

    def run(self):
        rc = self.window.run()
        self.window.destroy()
        # We need to call this to get the device nodes to show up
        # in our devicetree.
        if self._update_devicetree:
            self.storage.devicetree.populate()
        return rc

    def _set_configure_sensitive(self, sensitivity):
        """ Set entries to a given sensitivity. """
        for child in self._configureGrid.get_children():
            child.set_sensitive(sensitivity)

    def on_start_clicked(self, *args):
        """ Go through the process of validating entry contents and then
            attempt to add the device.
        """
        # First update widgets
        self._startButton.hide()
        self._cancelButton.set_sensitive(False)
        self._okButton.set_sensitive(False)

        self._conditionNotebook.set_current_page(1)
        self._set_configure_sensitive(False)
        self._deviceEntry.set_sensitive(False)

        # Make a zFCP object with some dummy credentials so we can validate our
        # actual input
        self._conditionNotebook.set_current_page(1)
        dev = ZFCPDevice("0.0.0000", "0x0000000000000000", "0x0000000000000000")
        # below really, really is ugly and needs to be re-factored, but this
        # should give a good base idea as far as expected behavior should go
        try:
            device = dev.sanitizeDeviceInput(self._deviceEntry.get_text())
            wwpn = dev.sanitizeWWPNInput(self._wwpnEntry.get_text())
            lun = dev.sanitizeFCPLInput(self._lunEntry.get_text())
        except ValueError as e:
            _config_error = str(e)
            self.builder.get_object("deviceErrorLabel").set_text(_config_error)
            self._conditionNotebook.set_current_page(2)

        spinner = self.builder.get_object("waitSpinner")
        spinner.start()

        self._discover(device, wwpn, lun)
        self._check_discover()

    @gtk_action_nowait
    def _check_discover(self, *args):
        """ After the zFCP discover thread runs, check to see whether a valid
            device was discovered. Display an error message if not.
        """

        spinner = self.builder.get_object("waitSpinner")
        spinner.stop()

        if self._discoveryError:
            # Failure, display a message and leave the user on the dialog so
            # they can try again (or cancel)
            self.builder.get_object("deviceErrorLabel").set_text(self._discoveryError)
            self._discoveryError = None
            self._conditionNotebook.set_current_page(2)
            self._set_configure_sensitive(True)
        else:
            # Great success. Just return to the advanced storage window and let the
            # UI update with the newly-added device
            self.window.response(1)
            return True

        self._cancelButton.set_sensitive(True)
        return False

    def _discover(self, *args):
        """ Given the configuration options from a user, attempt to discover
            a zFCP device. This includes searching black-listed devices.
        """
        # attempt to add the device
        try:
            self.zfcp.addFCP(args[0], args[1], args[2])
            self._update_devicetree = True
        except ValueError as e:
            self._discoveryError = str(e)
            return
