# Disk shopping cart
#
# Copyright (C) 2011, 2012  Red Hat, Inc.
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
from blivet import arch

from pyanaconda.modules.common.structures.storage import DeviceData
from pyanaconda.core.constants import BOOTLOADER_ENABLED, BOOTLOADER_LOCATION_MBR, \
    BOOTLOADER_DRIVE_UNSET, BOOTLOADER_SKIPPED
from pyanaconda.core.i18n import C_
from pyanaconda.modules.common.constants.objects import BOOTLOADER, DEVICE_TREE
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.ui.gui import GUIObject
from pyanaconda.ui.lib.storage import get_disks_summary
from blivet.size import Size

__all__ = ["SelectedDisksDialog"]

IS_BOOT_COL = 0
DESCRIPTION_COL = 1
SIZE_COL = 2
FREE_SPACE_COL = 3
NAME_COL = 4


class SelectedDisksDialog(GUIObject):
    builderObjects = ["selected_disks_dialog", "disk_store", "disk_tree_view"]
    mainWidgetName = "selected_disks_dialog"
    uiFile = "spokes/lib/cart.glade"

    def __init__(self, data, disks, show_remove=True, set_boot=True):
        super().__init__(data)
        self._disks = disks[:]
        self._previous_boot_device = None

        self._device_tree = STORAGE.get_proxy(DEVICE_TREE)
        self._bootloader_module = STORAGE.get_proxy(BOOTLOADER)

        self._view = self.builder.get_object("disk_tree_view")
        self._store = self.builder.get_object("disk_store")
        self._selection = self.builder.get_object("disk_selection")
        self._summary_label = self.builder.get_object("summary_label")
        self._set_button = self.builder.get_object("set_as_boot_button")
        self._remove_button = self.builder.get_object("remove_button")
        self._secure_boot_box = self.builder.get_object("secure_boot_box")
        self._secure_boot_combo = self.builder.get_object("secure_boot_combo")

        self._initialize_zipl_secure_boot()

        self._update_disks()
        self._update_summary()
        self._update_boot_device()

        if not show_remove:
            self.builder.get_object("remove_button").hide()

        if not set_boot:
            self._set_button.hide()

        # no disk is selected by default, inactivate the buttons
        self._set_button.set_sensitive(False)
        self._remove_button.set_sensitive(False)

    @property
    def disks(self):
        """Selected disks.

        :return: a list of device names
        """
        return self._disks

    def run(self):
        rc = self.window.run()
        self.window.destroy()
        return rc

    def _update_disks(self):
        for device_name in self._disks:
            device_data = DeviceData.from_structure(
                self._device_tree.GetDeviceData(device_name)
            )

            device_free_space = self._device_tree.GetDiskFreeSpace(
                [device_name]
            )

            self._store.append([
                False,
                "{} ({})".format(
                    device_data.description,
                    device_data.attrs.get("serial", "")
                ),
                str(Size(device_data.size)),
                str(Size(device_free_space)),
                device_name
            ])

    def _update_summary(self):
        self._summary_label.set_markup("<b>{}</b>".format(
            get_disks_summary(self._disks)
        ))

    def _update_boot_device(self):
        if not self._disks:
            return

        # Don't select a boot device if no boot device is asked for.
        if self._bootloader_module.BootloaderMode != BOOTLOADER_ENABLED:
            return

        # Set up the default boot device. Use what's in the module
        # if anything, then fall back to the first device.
        boot_drive = self._bootloader_module.Drive

        if boot_drive not in self._disks:
            boot_drive = self._disks[0]

        # And then select it in the UI.
        for row in self._store:
            if row[NAME_COL] == boot_drive:
                self._previous_boot_device = row[NAME_COL]
                row[IS_BOOT_COL] = True
                break

    def on_remove_clicked(self, button):
        itr = self._selection.get_selected()[1]
        if not itr:
            return

        disk = self._store[itr][NAME_COL]
        if disk not in self._disks:
            return

        # If this disk was marked as the boot device, just change to the first one
        # instead.
        reset_boot_device = self._store[itr][IS_BOOT_COL]

        # remove the selected disk(s) from the list and update the summary label
        self._store.remove(itr)
        self._disks.remove(disk)

        if reset_boot_device and len(self._store) > 0:
            self._store[0][IS_BOOT_COL] = True
            self._previous_boot_device = self._store[0][NAME_COL]
            self._toggle_button_text(self._store[0])

        self._update_summary()

        # If no disks are available in the cart anymore, grey out the buttons.
        self._set_button.set_sensitive(len(self._store) > 0)
        self._remove_button.set_sensitive(len(self._store) > 0)

    def on_close_clicked(self, button):
        # Save the secure boot settings.
        self._apply_zipl_secure_boot()

        # Save the boot device setting, if something was selected.
        boot_device = None

        for row in self._store:
            if row[IS_BOOT_COL]:
                boot_device = row[NAME_COL]
                break

        if boot_device and boot_device in self._disks:
            # Save the boot device setting, if something was selected.
            self._bootloader_module.SetBootloaderMode(BOOTLOADER_ENABLED)
            self._bootloader_module.SetPreferredLocation(BOOTLOADER_LOCATION_MBR)
            self._bootloader_module.SetDrive(boot_device)
        else:
            # No device was selected. The user does not want to install a boot loader.
            self._bootloader_module.SetBootloaderMode(BOOTLOADER_SKIPPED)
            self._bootloader_module.SetDrive(BOOTLOADER_DRIVE_UNSET)

    def _toggle_button_text(self, row):
        if row[IS_BOOT_COL]:
            self._set_button.set_label(C_(
                "GUI|Selected Disks Dialog",
                "_Do not install boot loader"
            ))
        else:
            self._set_button.set_label(C_(
                "GUI|Selected Disks Dialog",
                "_Set as Boot Device"
            ))

    def on_selection_changed(self, *args):
        itr = self._selection.get_selected()[1]

        # make the buttons (in)active if something/nothing is  selected
        self._set_button.set_sensitive(bool(itr))
        self._remove_button.set_sensitive(bool(itr))

        if not itr:
            return

        self._toggle_button_text(self._store[itr])

    def on_set_as_boot_clicked(self, button):
        itr = self._selection.get_selected()[1]
        if not itr:
            return

        # There's only two cases:
        if self._store[itr][NAME_COL] == self._previous_boot_device:
            # Either the user clicked on the device they'd previously selected,
            # in which case we are just toggling here.
            self._store[itr][IS_BOOT_COL] = not self._store[itr][IS_BOOT_COL]
        else:
            # Or they clicked on a different device.  First we unselect the
            # previously selected device.
            for row in self._store:
                if row[NAME_COL] == self._previous_boot_device:
                    row[IS_BOOT_COL] = False
                    break

            # Then we select the new row.
            self._store[itr][IS_BOOT_COL] = True
            self._previous_boot_device = self._store[itr][NAME_COL]

        self._toggle_button_text(self._store[itr])

    def _initialize_zipl_secure_boot(self):
        if not arch.is_s390():
            self._secure_boot_box.hide()
            return

        secure_boot = self._bootloader_module.ZIPLSecureBoot
        self._secure_boot_combo.set_active_id(secure_boot)

    def _apply_zipl_secure_boot(self):
        if not arch.is_s390():
            return

        secure_boot = self._secure_boot_combo.get_active_id()
        self._bootloader_module.SetZIPLSecureBoot(secure_boot)
