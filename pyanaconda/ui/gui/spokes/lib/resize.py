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
N_ = lambda x: x
P_ = lambda x, y, z: gettext.ldngettext("anaconda", x, y, z)

__all__ = ["ResizeDialog"]

DEVICE_ID_COL = 0
DESCRIPTION_COL = 1
FILESYSTEM_COL = 2
RECLAIMABLE_COL = 3
PERCENT_COL = 4
ACTION_COL = 5
EDITABLE_COL = 6
TOOLTIP_COL = 7

PRESERVE = N_("Preserve")
SHRINK = N_("Shrink")
DELETE = N_("Delete")

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

        self._preserveButton = self.builder.get_object("preserveButton")
#        self._shrinkButton = self.builder.get_object("shrinkButton")
        self._deleteButton = self.builder.get_object("deleteButton")

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

        for disk in disks:
            # First add the disk itself.
            if disk.partitioned:
                editable = False
                percent = 0
                fstype = ""
                diskReclaimableSpace = 0
            else:
                editable = not disk.protected
                percent = 100
                fstype = disk.format.type
                diskReclaimableSpace = disk.size

            itr = self._diskStore.append(None, [disk.id,
                                                "%s %s" % (size_str(disk.size), disk.description),
                                                fstype,
                                                "<span foreground='grey' style='italic'>%s total</span>",
                                                percent,
                                                _(PRESERVE),
                                                editable,
                                                _("Whole disks are not editable.")])

            if disk.partitioned:
                # Then add all its partitions.
                for dev in self.storage.devicetree.getChildren(disk):
                    if dev.isExtended and disk.format.logicalPartitions:
                        continue

                    # Devices that are not resizable are still deletable.
                    if dev.resizable:
                        freeSize = dev.size - dev.minSize
                        if not dev.protected:
                            canShrinkSomething = True
                    else:
                        freeSize = dev.size

                    if dev.protected:
                        tooltip = _("This device contains the installation source.")
                    else:
                        tooltip = None

                    self._diskStore.append(itr, [dev.id,
                                                 self._description(dev),
                                                 dev.format.type,
                                                 _("%s of %s") % (size_str(freeSize), size_str(dev.size)),
                                                 int((freeSize/dev.size) * 100),
                                                 _(PRESERVE),
                                                 not dev.protected,
                                                 tooltip])
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

#        if canShrinkSomething:
#            description += "\n\n"
#            description += _("There is also free space available in pre-existing filesystems.  "
#                             "While it's risky and we recommend you back up your data first, you "
#                             "can recover that free disk space and make it available for this "
#                             "installation below.")

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

    def _update_buttons(self, row):
        # If this is a disk header, it's not editable, so make all the
        # buttons insensitive.
        self._preserveButton.set_sensitive(row[EDITABLE_COL])
#        self._shrinkButton.set_sensitive(row[EDITABLE_COL])
        self._deleteButton.set_sensitive(row[EDITABLE_COL])

        if not row[EDITABLE_COL]:
            return

        # If the selected filesystem does not support shrinking, make that
        # button insensitive.
        device = self.storage.devicetree.getDeviceByID(row[DEVICE_ID_COL])
#        self._shrinkButton.set_sensitive(device.resizable)

        # Then, disable the button for whatever action is currently selected.
        # It doesn't make a lot of sense to allow clicking that.
        if row[ACTION_COL] == _(PRESERVE):
            self._preserveButton.set_sensitive(False)
#        elif row[ACTION_COL] == _(SHRINK):
#            self._shrinkButton.set_sensitive(False)
        elif row[ACTION_COL] == _(DELETE):
            self._deleteButton.set_sensitive(False)

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
        if action == _(PRESERVE):
            return False
        if action == _(SHRINK):
            if device.resizable:
                self._selectedReclaimableSpace += (device.size - device.minSize)
            else:
                self._selectedReclaimableSpace += device.size
        elif action == _(DELETE):
            self._selectedReclaimableSpace += device.size

        return False

    def on_preserve_clicked(self, button):
        self._actionChanged(PRESERVE)

    def on_shrink_clicked(self, button):
        self._actionChanged(SHRINK)

    def on_delete_clicked(self, button):
        self._actionChanged(DELETE)

    def _actionChanged(self, newAction):
        selection = self.builder.get_object("diskView-selection")
        (model, itr) = selection.get_selected()

        if not itr:
            return

        selectedRow = self._diskStore[itr]

        # Put the selected action into the store as well.
        selectedRow[ACTION_COL] = _(newAction)

        # And then we're keeping a running tally of how much space the user
        # has selected to reclaim, so reflect that in the UI.
        self._selectedReclaimableSpace = 0
        self._diskStore.foreach(self._sumReclaimableSpace, None)
        self._update_labels(selectedReclaimable=self._selectedReclaimableSpace)

        got = Size(spec="%s MB" % self._selectedReclaimableSpace)
        need = self.payload.spaceRequired
        self._resizeButton.set_sensitive(got >= need)

        self._update_buttons(selectedRow)

    def _scheduleActions(self, model, path, itr, *args):
        (editable, action, ident) = model.get(itr, EDITABLE_COL, ACTION_COL, DEVICE_ID_COL)

        device = self.storage.devicetree.getDeviceByID(ident)

        if not editable:
            return False

        if action == _(PRESERVE):
            return False
        elif action == _(SHRINK):
            if device.resizable:
                self.storage.resizeDevice(device, device.minSize)
            else:
                self.storage.recursiveRemove(device)
        elif action == _(DELETE):
            self.storage.recursiveRemove(device)

        return False

    def on_resize_clicked(self, *args):
        self._diskStore.foreach(self._scheduleActions, None)

    def on_row_clicked(self, view, path, column):
        # This handles when the user clicks on a row in the view.  We use it
        # only for expanding/collapsing disk headers.
        if view.row_expanded(path):
            view.collapse_row(path)
        else:
            view.expand_row(path, True)

    def on_selection_changed(self, selection):
        # This handles when the selection changes.  It's very similar to what
        # on_row_clicked above does, but this handler only deals with changes in
        # selection.  Thus, clicking on a disk header to collapse it and then
        # immediately clicking on it again to expand it would not work when
        # dealt with here.
        (model, itr) = selection.get_selected()

        if not itr:
            return

        self._update_buttons(self._diskStore[itr])
