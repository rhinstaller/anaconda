# Disk resizing dialog
#
# Copyright (C) 2012-2013  Red Hat, Inc.
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

from pyanaconda.i18n import _, N_, P_
from pyanaconda.ui.lib.disks import size_str
from pyanaconda.ui.gui import GUIObject
from blivet.size import Size

__all__ = ["ResizeDialog"]

DEVICE_ID_COL = 0
DESCRIPTION_COL = 1
FILESYSTEM_COL = 2
RECLAIMABLE_COL = 3
ACTION_COL = 4
EDITABLE_COL = 5
TOOLTIP_COL = 6
RESIZE_TARGET_COL = 7
NAME_COL = 8

PRESERVE = N_("Preserve")
SHRINK = N_("Shrink")
DELETE = N_("Delete")

class ResizeDialog(GUIObject):
    builderObjects = ["actionStore", "diskStore", "resizeDialog", "resizeAdjustment"]
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
        self._shrinkButton = self.builder.get_object("shrinkButton")
        self._deleteButton = self.builder.get_object("deleteButton")
        self._resizeSlider = self.builder.get_object("resizeSlider")

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

    def _get_tooltip(self, device):
        if device.protected:
            return _("This device contains the installation source.")
        else:
            return None

    def populate(self, disks):
        totalDisks = 0
        totalReclaimableSpace = 0

        self._initialFreeSpace = Size(0)
        self._selectedReclaimableSpace = 0

        canShrinkSomething = False

        free_space = self.storage.getFreeSpace(disks=disks)

        for disk in disks:
            # First add the disk itself.
            editable = not disk.protected

            if disk.partitioned:
                fstype = ""
                diskReclaimableSpace = 0
            else:
                fstype = disk.format.type
                diskReclaimableSpace = disk.size

            itr = self._diskStore.append(None, [disk.id,
                                                "%s %s" % (size_str(disk.size), disk.description),
                                                fstype,
                                                "<span foreground='grey' style='italic'>%s total</span>",
                                                _(PRESERVE),
                                                editable,
                                                self._get_tooltip(disk),
                                                disk.size,
                                                disk.name])

            if disk.partitioned:
                # Then add all its partitions.
                for dev in self.storage.devicetree.getChildren(disk):
                    if dev.isExtended and disk.format.logicalPartitions:
                        continue

                    # Devices that are not resizable are still deletable.
                    if dev.resizable:
                        freeSize = dev.size - dev.minSize
                        resizeString = _("%(freeSize)s of %(devSize)s") \
                                       % {"freeSize": size_str(freeSize), "devSize": size_str(dev.size)}
                        if not dev.protected:
                            canShrinkSomething = True
                    else:
                        freeSize = dev.size
                        resizeString = "<span foreground='grey'>%s</span>" % _("Not resizeable")

                    self._diskStore.append(itr, [dev.id,
                                                 self._description(dev),
                                                 dev.format.type,
                                                 resizeString,
                                                 _(PRESERVE),
                                                 not dev.protected,
                                                 self._get_tooltip(dev),
                                                 dev.size,
                                                 dev.name])
                    diskReclaimableSpace += freeSize

            # And then add another uneditable line that lists how much space is
            # already free in the disk.
            diskFree = free_space[disk.name][0]
            converted = diskFree.convertTo(spec="mb")
            if int(converted):
                self._diskStore.append(itr, [disk.id,
                                             _("""<span foreground='grey' style='italic'>Free space</span>"""),
                                             "",
                                             "<span foreground='grey' style='italic'>%s</span>" % size_str(diskFree),
                                             _(PRESERVE),
                                             False,
                                             self._get_tooltip(disk),
                                             float(converted),
                                             ""])
                self._initialFreeSpace += diskFree

            # And then go back and fill in the total reclaimable space for the
            # disk, now that we know what each partition has reclaimable.
            self._diskStore[itr][RECLAIMABLE_COL] = self._diskStore[itr][RECLAIMABLE_COL] % size_str(diskReclaimableSpace)

            totalDisks += 1
            totalReclaimableSpace += diskReclaimableSpace

        self._update_labels(totalDisks, totalReclaimableSpace, 0)

        description = _("You can remove existing filesystems you no longer need to free up space "
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

    def _setup_slider(self, device, value):
        """Set up the slider for this device, pulling out any previously given
           shrink value as the default.  This also sets up the ticks on the
           slider and keyboard support.  Any devices that are not resizable
           will not have a slider displayed, so they do not need to be worried
           with here.
        """
        self._resizeSlider.set_range(device.minSize, device.size)
        self._resizeSlider.set_value(value)

        # The slider needs to be keyboard-accessible.  We'll make small movements change in
        # 1% increments, and large movements in 5% increments.
        distance = device.size - device.minSize
        onePercent = distance*0.01
        fivePercent = distance*0.05
        twentyPercent = distance*0.2

        adjustment = self.builder.get_object("resizeAdjustment")
        adjustment.configure(value, device.minSize, device.size, onePercent, fivePercent, 0)

        # And then the slider needs a couple tick marks for easier navigation.
        self._resizeSlider.clear_marks()
        for i in range(1, 5):
            self._resizeSlider.add_mark(device.minSize + i*twentyPercent, Gtk.PositionType.BOTTOM, None)

        # Finally, add tick marks for the ends.
        self._resizeSlider.add_mark(device.minSize, Gtk.PositionType.BOTTOM, size_str(device.minSize))
        self._resizeSlider.add_mark(device.size, Gtk.PositionType.BOTTOM, size_str(device.size))

    def _update_action_buttons(self, row):
        device = self.storage.devicetree.getDeviceByID(row[DEVICE_ID_COL])

        # Disks themselves may be editable in certain ways, but they are never
        # shrinkable.
        self._preserveButton.set_sensitive(row[EDITABLE_COL])
        self._shrinkButton.set_sensitive(row[EDITABLE_COL] and not device.isDisk)
        self._deleteButton.set_sensitive(row[EDITABLE_COL])
        self._resizeSlider.set_visible(False)

        if not row[EDITABLE_COL]:
            return

        # If the selected filesystem does not support shrinking, make that
        # button insensitive.
        self._shrinkButton.set_sensitive(device.resizable)

        self._setup_slider(device, row[RESIZE_TARGET_COL])

        # Then, disable the button for whatever action is currently selected.
        # It doesn't make a lot of sense to allow clicking that.
        if row[ACTION_COL] == _(PRESERVE):
            self._preserveButton.set_sensitive(False)
        elif row[ACTION_COL] == _(SHRINK):
            self._shrinkButton.set_sensitive(False)
            self._resizeSlider.set_visible(True)
        elif row[ACTION_COL] == _(DELETE):
            self._deleteButton.set_sensitive(False)

    def _update_reclaim_button(self, got):
        # The reclaim button is sensitive if two conditions are met:
        # (1) There's enough available space (existing free/unpartitioned space,
        #     shrink space, etc.) on all disks.
        # (2) At least one destructive action has been chosen.  We can detect
        #     this by checking whether got is non-zero.
        need = self.payload.spaceRequired
        self._resizeButton.set_sensitive(got+self._initialFreeSpace >= need and got > Size(0))

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
        (editable, action, ident, targetSize) = model.get(itr, EDITABLE_COL, ACTION_COL, DEVICE_ID_COL, RESIZE_TARGET_COL)

        if not editable:
            return False

        device = self.storage.devicetree.getDeviceByID(ident)
        if action == _(PRESERVE):
            return False
        if action == _(SHRINK):
            self._selectedReclaimableSpace += device.size - targetSize
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

        # Handle the row selected when a button was pressed.
        selectedRow = self._diskStore[itr]
        selectedRow[ACTION_COL] = _(newAction)

        # If that row is a disk header, we need to process all the partitions
        # it contains.
        device = self.storage.devicetree.getDeviceByID(selectedRow[DEVICE_ID_COL])
        if device.isDisk and device.partitioned:
            partItr = model.iter_children(itr)
            while partItr:
                self._diskStore[partItr][ACTION_COL] = _(newAction)

                # If the user marked a whole disk for deletion, they can't go in and
                # un-delete partitions under it.
                if newAction == DELETE:
                    self._diskStore[partItr][EDITABLE_COL] = False
                elif newAction == PRESERVE:
                    part = self.storage.devicetree.getDeviceByID(self._diskStore[partItr][DEVICE_ID_COL])
                    self._diskStore[partItr][EDITABLE_COL] = not part.protected

                partItr = model.iter_next(partItr)

        # And then we're keeping a running tally of how much space the user
        # has selected to reclaim, so reflect that in the UI.
        self._selectedReclaimableSpace = 0
        self._diskStore.foreach(self._sumReclaimableSpace, None)
        self._update_labels(selectedReclaimable=self._selectedReclaimableSpace)

        self._update_reclaim_button(Size(spec="%s MB" % self._selectedReclaimableSpace))
        self._update_action_buttons(selectedRow)

    def _scheduleActions(self, model, path, itr, *args):
        (editable, action, ident, target) = model.get(itr, EDITABLE_COL, ACTION_COL, DEVICE_ID_COL, RESIZE_TARGET_COL)

        device = self.storage.devicetree.getDeviceByID(ident)

        if not editable:
            return False

        if action == _(PRESERVE):
            return False
        elif action == _(SHRINK):
            if device.resizable:
                self.storage.resizeDevice(device, target)
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

        self._update_action_buttons(self._diskStore[itr])

    def on_resize_value_changed(self, rng):
        selection = self.builder.get_object("diskView-selection")
        (model, itr) = selection.get_selected()

        # Update the target size in the store.
        model[itr][RESIZE_TARGET_COL] = rng.get_value()

        # Update the "Total selected space" label.
        delta = rng.get_adjustment().get_upper()-rng.get_value()
        self._update_labels(selectedReclaimable=self._selectedReclaimableSpace+delta)

        # And then the reclaim button, in case they've made enough space.
        newTotal = self._selectedReclaimableSpace + delta
        self._update_reclaim_button(Size(spec="%s MB" % newTotal))

    def resize_slider_format(self, scale, value):
        # This makes the value displayed under the slider prettier than just a
        # single number.
        return size_str(value)
