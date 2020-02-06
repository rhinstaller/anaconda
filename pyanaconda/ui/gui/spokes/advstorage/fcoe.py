# FCoE configuration dialog
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
from pyanaconda.modules.common.constants.objects import FCOE
from pyanaconda.modules.common.constants.services import STORAGE, NETWORK
from pyanaconda.modules.common.structures.network import NetworkDeviceInfo
from pyanaconda.modules.common.errors.configuration import StorageDiscoveryError
from pyanaconda.modules.common.task import async_run_task
from pyanaconda.ui.gui import GUIObject
from pyanaconda.storage.utils import try_populate_devicetree

import gi
gi.require_version("NM", "1.0")
from gi.repository import NM

__all__ = ["FCoEDialog"]


class FCoEDialog(GUIObject):
    """
       .. inheritance-diagram:: FCoEDialog
          :parts: 3
    """
    builderObjects = ["fcoeDialog"]
    mainWidgetName = "fcoeDialog"
    uiFile = "spokes/advstorage/fcoe.glade"

    def __init__(self, data, storage):
        super().__init__(data)
        self._storage = storage
        self._update_devicetree = False
        self._fcoe_proxy = STORAGE.get_proxy(FCOE)

        self._addButton = self.builder.get_object("addButton")
        self._cancelButton = self.builder.get_object("cancelButton")
        self._spinner = self.builder.get_object("addSpinner")
        self._errorBox = self.builder.get_object("errorBox")
        self._errorLabel = self.builder.get_object("errorLabel")
        self._nicCombo = self.builder.get_object("nicCombo")
        self._dcbCheckbox = self.builder.get_object("dcbCheckbox")
        self._autoCheckbox = self.builder.get_object("autoCheckbox")

    def refresh(self):
        self._nicCombo.remove_all()

        network_proxy = NETWORK.get_proxy()
        ethernet_devices = [NetworkDeviceInfo.from_structure(device)
                            for device in network_proxy.GetSupportedDevices()
                            if device['device-type'] == NM.DeviceType.ETHERNET]
        for dev_info in ethernet_devices:
            self._nicCombo.append_text("%s - %s" % (dev_info.device_name, dev_info.hw_address))

        self._nicCombo.set_active(0)

    def run(self):
        rc = self.window.run()
        self.window.destroy()

        if self._update_devicetree:
            try_populate_devicetree(self._storage.devicetree)

        return rc

    @property
    def nic(self):
        text = self._nicCombo.get_active_text()
        if text:
            return text.split()[0]
        else:
            return None

    @property
    def use_dcb(self):
        return self._dcbCheckbox.get_active()

    @property
    def use_auto_vlan(self):
        return self._autoCheckbox.get_active()

    def _set_configure_sensitive(self, sensitivity):
        """Set widgets to the given sensitivity."""
        self._addButton.set_sensitive(sensitivity)
        self._cancelButton.set_sensitive(sensitivity)
        self._nicCombo.set_sensitive(sensitivity)
        self._dcbCheckbox.set_sensitive(sensitivity)
        self._autoCheckbox.set_sensitive(sensitivity)

    def on_add_clicked(self, *args):
        """Start the discovery task."""
        # First update widgets.
        self._set_configure_sensitive(False)
        self._errorBox.hide()

        # Get the discovery task.
        if self.nic:
            task_path = self._fcoe_proxy.DiscoverWithTask(self.nic, self.use_dcb, self.use_auto_vlan)
        else:
            self._errorLabel.set_text("There is no nic detected!")
            self._errorBox.show()
            return
        task_proxy = STORAGE.get_proxy(task_path)

        # Start the discovery.
        async_run_task(task_proxy, self.process_result)

        self._spinner.start()
        self._spinner.show()

    def process_result(self, task_proxy):
        """Process the result of the task.

        :param task_proxy: a task proxy
        """
        # Stop the spinner.
        self._spinner.stop()
        self._spinner.hide()

        try:
            # Finish the task
            task_proxy.Finish()
        except StorageDiscoveryError as e:
            # Discovery has failed, show the error.
            self._set_configure_sensitive(True)
            self._errorLabel.set_text(str(e))
            self._errorBox.show()
        else:
            # Discovery succeeded.
            self._update_devicetree = True
            self.window.response(1)
