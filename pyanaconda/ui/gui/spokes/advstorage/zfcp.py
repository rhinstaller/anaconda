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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pyanaconda.modules.common.constants.objects import ZFCP
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.common.errors.configuration import StorageDiscoveryError
from pyanaconda.modules.common.task import async_run_task
from pyanaconda.ui.gui import GUIObject
from pyanaconda.ui.lib.storage import try_populate_devicetree

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

    def __init__(self, data):
        super().__init__(data)
        self._update_devicetree = False
        self._zfcp_proxy = STORAGE.get_proxy(ZFCP)

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
            try_populate_devicetree()
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

        # Get the input.
        device_name = self._deviceEntry.get_text().strip()
        wwpn_name = self._wwpnEntry.get_text().strip()
        lun_name = self._lunEntry.get_text().strip()

        # Get the discovery task.
        task_path = self._zfcp_proxy.DiscoverWithTask(device_name, wwpn_name, lun_name)
        task_proxy = STORAGE.get_proxy(task_path)

        # Start the discovery.
        async_run_task(task_proxy, self.process_result)
        self._spinner.start()

    def process_result(self, task_proxy):
        """Process the result of the task.

        :param task_proxy: a task proxy
        """
        # Stop the spinner.
        self._spinner.stop()
        self._cancelButton.set_sensitive(True)

        try:
            # Finish the task
            task_proxy.Finish()
        except StorageDiscoveryError as e:
            # Discovery has failed, show the error.
            self._errorLabel.set_text(str(e))
            self._set_configure_sensitive(True)
            self._conditionNotebook.set_current_page(2)
        else:
            # Discovery succeeded.
            self._update_devicetree = True
            self._okButton.set_sensitive(True)
            self._conditionNotebook.set_current_page(3)

    def on_entry_activated(self, entry, user_data=None):
        # When an entry is activated, press the discover or retry button
        current_page = self._conditionNotebook.get_current_page()
        if current_page == 0:
            self._startButton.clicked()
        elif current_page == 2:
            self._retryButton.clicked()
