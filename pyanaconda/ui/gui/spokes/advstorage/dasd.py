# DASD configuration dialog
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

import gi
gi.require_version("BlockDev", "2.0")

from gi.repository import BlockDev as blockdev

from pyanaconda.ui.gui import GUIObject
from pyanaconda.async_utils import async_action_nowait
from pyanaconda.storage_utils import try_populate_devicetree
from pyanaconda.regexes import DASD_DEVICE_NUMBER
from pyanaconda.threading import threadMgr, AnacondaThread
from pyanaconda.core.timer import Timer
from pyanaconda import constants

__all__ = ["DASDDialog"]

class DASDDialog(GUIObject):
    """ Gtk dialog which allows users to manually add DASD devices without
        having previously specified them in a parm file.

       .. inheritance-diagram:: DASDDialog
          :parts: 3
    """
    builderObjects = ["dasdDialog"]
    mainWidgetName = "dasdDialog"
    uiFile = "spokes/advstorage/dasd.glade"

    def __init__(self, data, storage):
        GUIObject.__init__(self, data)
        self.storage = storage
        self.dasd = [d for d in self.storage.devices if d.type == "dasd"]
        self.dasd.sort(key=lambda d: d.name)

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

    def on_start_clicked(self, *args):
        """ Go through the process of validating entry contents and then
            attempt to add the device.
        """
        # First update widgets
        self._startButton.hide()
        self._okButton.set_sensitive(False)
        self._cancelButton.set_sensitive(False)
        self._deviceEntry.set_sensitive(False)
        self._conditionNotebook.set_current_page(1)

        # Initialize.
        config_error = None
        device = None
        device_name = self._deviceEntry.get_text().strip()

        # Check the format of the given device name.
        if not DASD_DEVICE_NUMBER.match(device_name):
            config_error = "Incorrect format of the given device number."
        else:
            try:
                # Get full device name.
                device = blockdev.s390.sanitize_dev_input(device_name)
            except (blockdev.S390Error, ValueError) as e:
                config_error = str(e)

        # Process the configuration error.
        if config_error:
            self._errorLabel.set_text(config_error)
            self._deviceEntry.set_sensitive(True)
            self._cancelButton.set_sensitive(True)
            self._conditionNotebook.set_current_page(2)
        # Run the discovery.
        else:
            # Discover.
            self._spinner.start()
            threadMgr.add(AnacondaThread(name=constants.THREAD_DASD_DISCOVER,
                                         target=self._discover,
                                         args=(device,)))

            # Periodically call the check till it is done.
            Timer().timeout_msec(250, self._check_discover)

    @async_action_nowait
    def _check_discover(self):
        """ After the DASD discover thread runs, check to see whether a valid
            device was discovered. Display an error message if not.

            If the discover is not done, return True to indicate that the check
            has to be run again, otherwise check the discovery and return False.
        """
        # Discovery is not done, return True.
        if threadMgr.get(constants.THREAD_DASD_DISCOVER):
            return True

        # Discovery has finished, run the check.
        self._spinner.stop()

        if self._discoveryError:
            # Failure, display a message and leave the user on the dialog so
            # they can try again (or cancel)
            self._errorLabel.set_text(self._discoveryError)
            self._discoveryError = None

            self._deviceEntry.set_sensitive(True)
            self._conditionNotebook.set_current_page(2)
        else:
            # Great success. Since DASDs go under local disks, update dialog to
            # show users that's where they'll be
            self._okButton.set_sensitive(True)
            self._conditionNotebook.set_current_page(3)

        self._cancelButton.set_sensitive(True)
        # Discovery and the check have finished, return False.
        return False

    def _discover(self, device):
        """ Given the configuration options from a user, attempt to discover
            a DASD device. This includes searching black-listed devices.
        """
        # Attempt to add the device.
        try:
            # If the device does not exist, dasd_online will return False,
            # otherwise an exception will be raised.
            if not blockdev.s390.dasd_online(device):
                self._discoveryError = "The device could not be switched online. It may not exist."
            else:
                self._update_devicetree = True
        except blockdev.S390Error as err:
            self._discoveryError = str(err)

    def on_device_entry_activate(self, entry, user_data=None):
        # If the user hit Enter while the start button is displayed, activate
        # whichever button is displayed.
        current_page = self._conditionNotebook.get_current_page()
        if current_page == 0:
            self._startButton.clicked()
        elif current_page == 2:
            self._retryButton.clicked()
