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
# Red Hat Author(s): Chris Lumens <clumens@redhat.com>
#

from pyanaconda import constants
from pyanaconda.threads import threadMgr, AnacondaThread
from pyanaconda.ui.gui import GUIObject
from pyanaconda.ui.gui.utils import gtk_action_wait
from pyanaconda import nm

__all__ = ["FCoEDialog"]

class FCoEDialog(GUIObject):
    builderObjects = ["fcoeDialog"]
    mainWidgetName = "fcoeDialog"
    uiFile = "spokes/advstorage/fcoe.glade"

    def __init__(self, data, storage):
        GUIObject.__init__(self, data)

        self._addError = None

        self.storage = storage
        self.fcoe = self.storage.fcoe()
        self._update_devicetree = False

        self._addButton = self.builder.get_object("addButton")
        self._cancelButton = self.builder.get_object("cancelButton")
        self._addSpinner = self.builder.get_object("addSpinner")
        self._errorBox = self.builder.get_object("errorBox")

        self._nicCombo = self.builder.get_object("nicCombo")

        self._dcbCheckbox = self.builder.get_object("dcbCheckbox")
        self._autoCheckbox = self.builder.get_object("autoCheckbox")

    def refresh(self):
        self._nicCombo.remove_all()

        for devname in nm.nm_devices():
            if nm.nm_device_type_is_ethernet(devname):
                self._nicCombo.append_text("%s - %s" % (devname, nm.nm_device_hwaddress(devname)))

        self._nicCombo.set_active(0)

    def run(self):
        rc = self.window.run()
        self.window.destroy()
        if self._update_devicetree:
            self.storage.devicetree.populate()
        return rc

    @property
    def nic(self):
        text = self._nicCombo.get_active_text()
        return text.split()[0]

    @property
    def use_dcb(self):
        return self._dcbCheckbox.get_active()

    @property
    def use_auto_vlan(self):
        return self._autoCheckbox.get_active()

    def _add(self):
        try:
            self._addError = self.fcoe.addSan(self.nic, self.use_dcb, self.use_auto_vlan)
        except (IOError, OSError) as e:
            self._addError = str(e)

        self._after_add()

    @gtk_action_wait
    def _after_add(self):
        # When fcoe discovery is done, update the UI.  We don't need to worry
        # about the user escaping from the dialog because all the buttons are
        # marked insensitive.
        self._addSpinner.stop()
        self._addSpinner.hide()

        for widget in [self._addButton, self._cancelButton, self._nicCombo,
                       self._dcbCheckbox, self._autoCheckbox]:
            widget.set_sensitive(True)

        if self._addError:
            # Failure.  Display some error message and leave the user on the
            # dialog to try again.
            self.builder.get_object("errorLabel").set_text(self._addError)
            self._errorBox.set_visible(True)
            self._errorBox.set_no_show_all(False)
            self._errorBox.show()

            self._addError = None
            self._addButton.set_sensitive(True)
            self._cancelButton.set_sensitive(True)
        else:
            # Success.  There's nothing else the user can do on this dialog.
            self.fcoe.added_nics.append(self.nic)
            self._update_devicetree = True
            self.window.response(1)

    def on_add_clicked(self, *args):
        # Set some widgets to visible/not while we work.
        self._errorBox.hide()
        self._addSpinner.set_visible(True)
        self._addSpinner.show()

        for widget in [self._addButton, self._cancelButton, self._nicCombo,
                       self._dcbCheckbox, self._autoCheckbox]:
            widget.set_sensitive(False)

        self._addSpinner.start()

        threadMgr.add(AnacondaThread(name=constants.THREAD_FCOE, target=self._add))
