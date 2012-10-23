# Disk resizing dialog
#
# Copyright (C) 2012  Red Hat, Inc.
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

from __future__ import division

from gi.repository import Gtk

from pyanaconda.ui.gui import GUIObject
from pyanaconda.storage.size import Size

import gettext

_ = lambda x: gettext.ldgettext("anaconda", x)
P_ = lambda x, y, z: gettext.ldngettext("anaconda", x, y, z)

__all__ = ["ResizeDialog"]

DEVICE_ID_COL = 0
DESCRIPTION_COL = 1
FILESYSTEM_COL = 2
RECLAIMABLE_COL = 3
PERCENT_COL = 4
ACTION_COL = 5
EDITABLE_COL = 6

PRESERVE = _("Preserve")
SHRINK = _("Shrink")
DELETE = _("Delete")

def size_str(mb):
    if isinstance(mb, Size):
        spec = str(mb)
    else:
        spec = "%s mb" % mb

    return str(Size(spec=spec)).upper()

class ResizeDialog(GUIObject):
    builderObjects = ["actionStore", "diskStore", "resizeDialog"]
    mainWidgetName = "resizeDialog"
    uiFile = "spokes/lib/resize.glade"

    def __init__(self, data, storage, payload):
        GUIObject.__init__(self, data)
        self.storage = storage
        self.payload = payload

        self._actionStore = self.builder.get_object("actionStore")
        self._diskStore = self.builder.get_object("diskStore")

        self._view = self.builder.get_object("diskView")
        self._diskStore = self.builder.get_object("diskStore")
        self._reclaimable_label = self.builder.get_object("reclaimableSpaceLabel")
        self._selected_label = self.builder.get_object("selectedSpaceLabel")

        self._required_label = self.builder.get_object("requiredSpaceLabel")
        markup = self._required_label.get_label()
        self._required_label.set_markup(markup % size_str(self.payload.spaceRequired))

        self._reclaimDescLabel = self.builder.get_object("reclaimDescLabel")

        self._resizeButton = self.builder.get_object("resizeButton")

    def _description(self, part):
        # First, try to find the partition in some known Root.  If we find
        # it, return the mountpoint as the description.
        for root in self.storage.roots:
            for (mount, device) in root.mounts.iteritems():
                if device == part:
                    return "%s (%s)" % (mount, root.name)

        # Otherwise, fall back on increasingly vague information.
        if not part.isleaf:
            return self.storage.devicetree.getChildren(part)[0].name
        if getattr(part.format, "label", None):
            return part.format.label
        elif getattr(part.format, "name", None):
            return part.format.name
        else:
            return ""

    def populate(self, disks):
        totalDisks = 0
        totalReclaimableSpace = 0

        self._selectedReclaimableSpace = 0

        canShrinkSomething = False

        # Shouldn't have to do this outside of glade, but see:
        # https://bugzilla.gnome.org/show_bug.cgi?id=685003
        renderer = self.builder.get_object("actionRenderer")
        renderer.set_property("editable", True)

        for disk in disks:
            # First add the disk itself.
            itr = self._diskStore.append(None, [disk.id,
                                                "%s %s" % (size_str(disk.size), disk.description),
                                                "",
                                                "<span foreground='grey' style='italic'>%s total</span>",
                                                0,
                                                PRESERVE,
                                                False])

            diskReclaimableSpace = 0

            # Then add all its partitions.
            for dev in self.storage.devicetree.getChildren(disk):
                if dev.isExtended and disk.format.logicalPartitions:
                    continue

                # Devices that are not resizable are still deletable.
                if dev.resizable:
                    freeSize = dev.size - dev.minSize
                    canShrinkSomething = True
                else:
                    freeSize = dev.size

                self._diskStore.append(itr, [dev.id,
                                             self._description(dev),
                                             dev.format.type,
                                             _("%s of %s") % (size_str(freeSize), size_str(dev.size)),
                                             int((freeSize/dev.size) * 100),
                                             PRESERVE,
                                             True])
                diskReclaimableSpace += freeSize

            # And then go back and fill in the total reclaimable space for the
            # disk, now that we know what each partition has reclaimable.
            self._diskStore[itr][RECLAIMABLE_COL] = self._diskStore[itr][RECLAIMABLE_COL] % size_str(diskReclaimableSpace)
            self._diskStore[itr][PERCENT_COL] = int((diskReclaimableSpace/disk.size)*100)

            totalDisks += 1
            totalReclaimableSpace += diskReclaimableSpace

        self._update_labels(totalDisks, totalReclaimableSpace, 0)

        description = _("You don't have enough free space available for this installation.\n\n"
                        "You can remove existing filesystems you no longer need to free up space "
                        "for this installation.  Removing a filesystem will permanently delete all "
                        "of the data it contains.")

        if canShrinkSomething:
            description += "\n\n"
            description += _("There is also free space available in pre-existing filesystems.  "
                             "While it's risky and we recommend you back up your data first, you "
                             "can recover that free disk space and make it available for this "
                             "installation below.")

        self._reclaimDescLabel.set_text(description)

    def _update_labels(self, nDisks=None, totalReclaimable=None, selectedReclaimable=None):
        if nDisks is not None and totalReclaimable is not None:
            text = P_("<b>%s disk; %s reclaimable space</b> (in filesystems)",
                      "<b>%s disks; %s reclaimable space</b> (in filesystems)",
                      nDisks) % (nDisks, size_str(totalReclaimable))
            self._reclaimable_label.set_markup(text)

        if selectedReclaimable is not None:
            text = _("Total selected space to reclaim: <b>%s</b>") % size_str(selectedReclaimable)
            self._selected_label.set_markup(text)

    def refresh(self, disks):
        super(ResizeDialog, self).refresh()

        # clear out the store and repopulate it from the devicetree
        self._diskStore.clear()
        self.populate(disks)

        self._view.expand_all()

    def run(self):
        rc = self.window.run()
        self.window.destroy()
        return rc

    # Signal handlers.
    def _sumReclaimableSpace(self, model, path, itr, *args):
        (editable, action, ident) = model.get(itr, EDITABLE_COL, ACTION_COL, DEVICE_ID_COL)

        if not editable:
            return False

        device = self.storage.devicetree.getDeviceByID(ident)
        if action == PRESERVE:
            return False
        if action == SHRINK:
            if device.resizable:
                self._selectedReclaimableSpace += (device.size - device.minSize)
            else:
                self._selectedReclaimableSpace += device.size
        elif action == DELETE:
            self._selectedReclaimableSpace += device.size

        return False

    def on_action_changed(self, combo, path, itr, *args):
        diskItr = self._diskStore.get_iter_from_string(path)
        selectedRow = self._diskStore[diskItr]

        selectedAction = self._actionStore[itr][0]

        # Put the selected action into the store as well.
        selectedRow[ACTION_COL] = selectedAction

        # And then we're keeping a running tally of how much space the user
        # has selected to reclaim, so reflect that in the UI.
        self._selectedReclaimableSpace = 0
        self._diskStore.foreach(self._sumReclaimableSpace, None)
        self._update_labels(selectedReclaimable=self._selectedReclaimableSpace)

        got = Size(spec="%s MB" % self._selectedReclaimableSpace)
        need = self.payload.spaceRequired
        self._resizeButton.set_sensitive(got >= need)

    def _scheduleActions(self, model, path, itr, *args):
        (editable, action, ident) = model.get(itr, EDITABLE_COL, ACTION_COL, DEVICE_ID_COL)

        device = self.storage.devicetree.getDeviceByID(ident)

        if not editable:
            return False

        if action == PRESERVE:
            return False
        elif action == SHRINK:
            if device.resizable:
                self.storage.resizeDevice(device, device.minSize)
            else:
                self.storage.recursiveRemove(device)
        elif action == DELETE:
            self.storage.recursiveRemove(device)

        return False

    def on_resize_clicked(self, *args):
        self._diskStore.foreach(self._scheduleActions, None)
