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

import gi
gi.require_version("BlockDev", "2.0")

from gi.repository import GLib, BlockDev as blockdev

from blivet import zfcp
from pyanaconda.ui.gui import GUIObject
from pyanaconda.async_utils import async_action_nowait
from pyanaconda.storage_utils import try_populate_devicetree
from pyanaconda.regexes import DASD_DEVICE_NUMBER, ZFCP_WWPN_NUMBER, ZFCP_LUN_NUMBER
from pyanaconda.threading import threadMgr, AnacondaThread
from pyanaconda import constants

__all__ = ["ZFCPDialog"]

class ZFCPDialog(GUIObject):
    """ Gtk dialog which allows users to manually add zFCP devices without
        having previously specified them in a parm file.

       .. inheritance-diagram:: ZFCPDialog
          :parts: 3
    """
    builderObjects = ["zfcpDialog"]
    mainWidgetName = "zfcpDialog"
    uiFile = "spokes/advstorage/zfcp.glade"

    def __init__(self, data, storage):
        GUIObject.__init__(self, data)
        self.storage = storage
        self.zfcp = zfcp.zFCP()

        self._discoveryError = None

        self._update_devicetree = False

        # grab all of the ui objects
        self._configureGrid = self.builder.get_object("configureGrid")
        self._conditionNotebook = self.builder.get_object("conditionNotebook")

        self._startButton = self.builder.get_object("startButton")
        self._okButton = self.builder.get_object("okButton")
        self._cancelButton = self.builder.get_object("cancelButton")
        self._retryButton = self.builder.get_object("retryButton")
        self._errorLabel = self.builder.get_object("deviceErrorLabel")

        self._deviceEntry = self.builder.get_object("deviceEntry")
        self._wwpnEntry = self.builder.get_object("wwpnEntry")
        self._lunEntry = self.builder.get_object("lunEntry")

        self._spinner = self.builder.get_object("waitSpinner")

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
            try_populate_devicetree(self.storage.devicetree)
        return rc

    def _set_configure_sensitive(self, sensitivity):
        """ Set entries to a given sensitivity. """
        self._deviceEntry.set_sensitive(sensitivity)
        self._wwpnEntry.set_sensitive(sensitivity)
        self._lunEntry.set_sensitive(sensitivity)

    def on_start_clicked(self, *args):
        """ Go through the process of validating entry contents and then
            attempt to add the device.
        """
        # First update widgets
        self._startButton.hide()
        self._cancelButton.set_sensitive(False)
        self._okButton.set_sensitive(False)
        self._set_configure_sensitive(False)
        self._conditionNotebook.set_current_page(1)

        # Initialize.
        config_error = None
        device = None
        wwpn = None
        lun = None

        # Get the input.
        device_name = self._deviceEntry.get_text().strip()
        wwpn_name = self._wwpnEntry.get_text().strip()
        lun_name = self._lunEntry.get_text().strip()

        # Check the input.
        if not DASD_DEVICE_NUMBER.match(device_name):
            config_error = "Incorrect format of the given device number."
        elif not ZFCP_WWPN_NUMBER.match(wwpn_name):
            config_error = "Incorrect format of the given WWPN number."
        elif not ZFCP_LUN_NUMBER.match(lun_name):
            config_error = "Incorrect format of the given LUN number."
        else:
            try:
                # Get the full ids.
                device = blockdev.s390.sanitize_dev_input(device_name)
                wwpn = blockdev.s390.zfcp_sanitize_wwpn_input(wwpn_name)
                lun = blockdev.s390.zfcp_sanitize_lun_input(lun_name)
            except (blockdev.S390Error, ValueError) as err:
                config_error = str(err)

        # Process the configuration error.
        if config_error:
            self._errorLabel.set_text(config_error)
            self._conditionNotebook.set_current_page(2)
            self._set_configure_sensitive(True)
            self._cancelButton.set_sensitive(True)
        # Start the discovery.
        else:
            # Discover.
            self._spinner.start()
            threadMgr.add(AnacondaThread(name=constants.THREAD_ZFCP_DISCOVER,
                                         target=self._discover,
                                         args=(device, wwpn, lun)))

            # Periodically call the check till it is done.
            GLib.timeout_add(250, self._check_discover)

    @async_action_nowait
    def _check_discover(self, *args):
        """ After the zFCP discover thread runs, check to see whether a valid
            device was discovered. Display an error message if not.

            If the discover is not done, return True to indicate that the check
            has to be run again, otherwise check the discovery and return False.
        """
        # Discovery is not done, return True.
        if threadMgr.get(constants.THREAD_ZFCP_DISCOVER):
            return True

        # Discovery has finished, run the check.
        self._spinner.stop()

        if self._discoveryError:
            # Failure, display a message and leave the user on the dialog so
            # they can try again (or cancel)
            self._errorLabel.set_text(self._discoveryError)
            self._discoveryError = None

            self._conditionNotebook.set_current_page(2)
            self._set_configure_sensitive(True)
        else:
            # Great success. Just return to the advanced storage window and let the
            # UI update with the newly-added device
            self.window.response(1)
            return False

        self._cancelButton.set_sensitive(True)
        # Discovery and the check have finished, return False.
        return False

    def _discover(self, *args):
        """ Given the configuration options from a user, attempt to discover
            a zFCP device. This includes searching black-listed devices.
        """
        # attempt to add the device
        try:
            self.zfcp.add_fcp(args[0], args[1], args[2])
            self._update_devicetree = True
        except ValueError as e:
            self._discoveryError = str(e)

    def on_entry_activated(self, entry, user_data=None):
        # When an entry is activated, press the discover or retry button
        current_page = self._conditionNotebook.get_current_page()
        if current_page == 0:
            self._startButton.clicked()
        elif current_page == 2:
            self._retryButton.clicked()
