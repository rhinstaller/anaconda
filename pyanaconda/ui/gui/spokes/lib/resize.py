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


from collections import namedtuple

import gi
gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")

from gi.repository import Gdk, Gtk

from pyanaconda.core.i18n import _, C_, N_, P_
from pyanaconda.modules.common.constants.objects import DEVICE_TREE
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.ui.gui import GUIObject
from pyanaconda.ui.gui.utils import blockedHandler, escape_markup, timed_action
from pyanaconda.modules.storage.partitioning.automatic.utils import shrink_device, remove_device
from blivet.size import Size

__all__ = ["ResizeDialog"]

DEVICE_NAME_COL = 0
DESCRIPTION_COL = 1
FILESYSTEM_COL = 2
RECLAIMABLE_COL = 3
ACTION_COL = 4
EDITABLE_COL = 5
TYPE_COL = 6
TOOLTIP_COL = 7
RESIZE_TARGET_COL = 8

TY_NORMAL = 0
TY_FREE_SPACE = 1
TY_PROTECTED = 2

PartStoreRow = namedtuple("PartStoreRow", ["name", "desc", "fs", "reclaimable",
                                           "action", "editable", "ty",
                                           "tooltip", "target"])

PRESERVE = N_("Preserve")
SHRINK = N_("Shrink")
DELETE = N_("Delete")
NOTHING = ""


class ResizeDialog(GUIObject):
    builderObjects = ["actionStore", "diskStore", "resizeDialog", "resizeAdjustment"]
    mainWidgetName = "resizeDialog"
    uiFile = "spokes/lib/resize.glade"

    def __init__(self, data, storage, payload):
        super().__init__(data)
        self.storage = storage
        self.payload = payload

        self._device_tree_proxy = STORAGE.get_proxy(DEVICE_TREE)

        # Get the required device size.
        required_space = self.payload.space_required.get_bytes()
        required_size = self._device_tree_proxy.GetRequiredDeviceSize(required_space)

        self._required_size = Size(required_size)
        self._initial_free_space = Size(0)
        self._selected_reclaimable_space = Size(0)

        self._disk_store = self.builder.get_object("diskStore")
        self._selection = self.builder.get_object("diskView-selection")
        self._view = self.builder.get_object("diskView")
        self._disk_store = self.builder.get_object("diskStore")
        self._reclaimable_label = self.builder.get_object("reclaimableSpaceLabel")
        self._selected_label = self.builder.get_object("selectedSpaceLabel")
        self._required_label = self.builder.get_object("requiredSpaceLabel")

        self._required_label.set_markup(
            _("Installation requires a total of <b>%s</b> for system data.")
            % escape_markup(str(self._required_size))
        )

        self._reclaim_desc_label = self.builder.get_object("reclaimDescLabel")
        self._resize_button = self.builder.get_object("resizeButton")
        self._preserve_button = self.builder.get_object("preserveButton")
        self._shrink_button = self.builder.get_object("shrinkButton")
        self._delete_button = self.builder.get_object("deleteButton")
        self._resize_slider = self.builder.get_object("resizeSlider")

    def _get_description(self, part):
        # First, try to find the partition in some known Root.  If we find
        # it, return the mountpoint as the description.
        for root in self.storage.roots:
            for (mount, device) in root.mounts.items():
                if device == part:
                    return "%s (%s)" % (mount, root.name)

        # Otherwise, fall back on increasingly vague information.
        if not part.isleaf:
            return part.children[0].name
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
        total_disks = 0
        total_reclaimable_space = Size(0)

        self._initial_free_space = Size(0)
        self._selected_reclaimable_space = Size(0)

        can_shrink_something = False

        for disk in disks:
            # First add the disk itself.
            if disk.partitioned and disk.format.supported:
                fstype = ""
                disk_reclaimable_space = Size(0)
            else:
                fstype = disk.format.name
                disk_reclaimable_space = disk.size

            itr = self._disk_store.append(None, [
                disk.name,
                "%s %s" % (disk.size.human_readable(max_places=1), disk.description),
                fstype,
                "<span foreground='grey' style='italic'>%s total</span>",
                _(PRESERVE),
                not disk.protected,
                TY_NORMAL,
                self._get_tooltip(disk),
                int(disk.size),
            ])

            if disk.partitioned and disk.format.supported:
                # Then add all its partitions.
                for dev in disk.children:
                    if dev.is_extended and disk.format.logical_partitions:
                        continue

                    # Devices that are not resizable are still deletable.
                    if dev.resizable:
                        free_size = dev.size - dev.min_size
                        resize_string = _("%(freeSize)s of %(devSize)s") % {
                            "freeSize": free_size.human_readable(max_places=1),
                            "devSize": dev.size.human_readable(max_places=1)
                        }
                        if not dev.protected:
                            can_shrink_something = True
                    else:
                        free_size = dev.size
                        resize_string = "<span foreground='grey'>%s</span>" % \
                            escape_markup(_("Not resizeable"))

                    if dev.protected:
                        ty = TY_PROTECTED
                    else:
                        ty = TY_NORMAL

                    self._disk_store.append(itr, [
                        dev.name,
                        self._get_description(dev),
                        dev.format.name,
                        resize_string,
                        _(PRESERVE),
                        not dev.protected,
                        ty,
                        self._get_tooltip(dev),
                        int(dev.size),
                    ])
                    disk_reclaimable_space += free_size

            # And then add another uneditable line that lists how much space is
            # already free in the disk.
            disk_free = self.storage.get_disk_free_space([disk])

            if disk_free >= Size("1MiB"):
                free_space_string = "<span foreground='grey' style='italic'>%s</span>" \
                                    % escape_markup(_("Free space"))

                disk_free_string = "<span foreground='grey' style='italic'>%s</span>" \
                                   % escape_markup(disk_free.human_readable(max_places=1))

                self._disk_store.append(itr, [
                    "",
                    free_space_string,
                    "",
                    disk_free_string,
                    NOTHING,
                    False,
                    TY_FREE_SPACE,
                    self._get_tooltip(disk),
                    disk_free,
                ])
                self._initial_free_space += disk_free

            # And then go back and fill in the total reclaimable space for the
            # disk, now that we know what each partition has reclaimable.
            self._disk_store[itr][RECLAIMABLE_COL] = \
                self._disk_store[itr][RECLAIMABLE_COL] % disk_reclaimable_space

            total_disks += 1
            total_reclaimable_space += disk_reclaimable_space

        self._update_labels(total_disks, total_reclaimable_space, 0)

        description = _(
            "You can remove existing file systems you no longer need to free up space for "
            "this installation.  Removing a file system will permanently delete all of the "
            "data it contains."
        )

        if can_shrink_something:
            description += "\n\n"
            description += _("There is also free space available in pre-existing file systems.  "
                             "While it's risky and we recommend you back up your data first, you "
                             "can recover that free disk space and make it available for this "
                             "installation below.")

        self._reclaim_desc_label.set_text(description)
        self._update_reclaim_button(Size(0))

    def _update_labels(self, num_disks=None, total_reclaimable=None, selected_reclaimable=None):
        if num_disks is not None and total_reclaimable is not None:
            text = P_(
                "<b>%(count)s disk; %(size)s reclaimable space</b> (in file systems)",
                "<b>%(count)s disks; %(size)s reclaimable space</b> (in file systems)",
                num_disks
            ) % {
                "count": escape_markup(str(num_disks)),
                "size": escape_markup(total_reclaimable)
            }

            self._reclaimable_label.set_markup(text)

        if selected_reclaimable is not None:
            text = _("Total selected space to reclaim: <b>%s</b>") \
                   % escape_markup(selected_reclaimable)

            self._selected_label.set_markup(text)

    def _setup_slider(self, device, value):
        """Set up the slider for the given device.

        Set up the slider for this device, pulling out any previously given
        shrink value as the default.  This also sets up the ticks on the
        slider and keyboard support.  Any devices that are not resizable
        will not have a slider displayed, so they do not need to be worried
        with here.

        :param device: The device
        :type device: PartitionDevice
        :param value: default value to set
        :type value: Size
        """
        # Convert the Sizes to ints
        min_size = int(device.min_size)
        size = int(device.size)
        default_value = int(value)

        # The slider needs to be keyboard-accessible.  We'll make small movements change in
        # 1% increments, and large movements in 5% increments.
        distance = size - min_size
        one_percent = int(distance / 100)
        five_percent = int(distance / 20)
        twenty_percent = int(distance / 5)

        with blockedHandler(self._resize_slider, self.on_resize_value_changed):
            self._resize_slider.set_range(min_size, size)

        self._resize_slider.set_value(default_value)

        adjustment = self.builder.get_object("resizeAdjustment")
        adjustment.configure(default_value, min_size, size, one_percent, five_percent, 0)

        # And then the slider needs a couple tick marks for easier navigation.
        self._resize_slider.clear_marks()
        for i in range(1, 5):
            self._resize_slider.add_mark(
                min_size + i * twenty_percent, Gtk.PositionType.BOTTOM, None
            )

        # Finally, add tick marks for the ends.
        self._resize_slider.add_mark(min_size, Gtk.PositionType.BOTTOM, str(device.min_size))
        self._resize_slider.add_mark(size, Gtk.PositionType.BOTTOM, str(device.size))

    def _update_action_buttons(self, row):
        obj = PartStoreRow(*row)
        device = self.storage.devicetree.get_device_by_name(obj.name)

        # Disks themselves may be editable in certain ways, but they are never
        # shrinkable.
        self._preserve_button.set_sensitive(obj.editable)
        self._shrink_button.set_sensitive(obj.editable and not device.is_disk)
        self._delete_button.set_sensitive(obj.editable)
        self._resize_slider.set_visible(False)

        if not obj.editable:
            return

        # If the selected filesystem does not support shrinking, make that
        # button insensitive.
        self._shrink_button.set_sensitive(device.resizable)

        if device.resizable:
            self._setup_slider(device, Size(obj.target))

        # Then, disable the button for whatever action is currently selected.
        # It doesn't make a lot of sense to allow clicking that.
        if obj.action == _(PRESERVE):
            self._preserve_button.set_sensitive(False)
        elif obj.action == _(SHRINK):
            self._shrink_button.set_sensitive(False)
            self._resize_slider.set_visible(True)
        elif obj.action == _(DELETE):
            self._delete_button.set_sensitive(False)

    def _update_reclaim_button(self, got):
        self._resize_button.set_sensitive(got + self._initial_free_space >= self._required_size)

    # pylint: disable=arguments-differ
    def refresh(self, disks):
        super().refresh()

        # clear out the store and repopulate it from the devicetree
        self._disk_store.clear()
        self.populate(disks)

        self._view.expand_all()

    def run(self):
        rc = self.window.run()
        self.window.destroy()
        return rc

    # Signal handlers.
    def on_key_pressed(self, window, event, *args):
        # Handle any keyboard events.  Right now this is just delete for
        # removing a partition, but it could include more later.
        if not event or event and event.type != Gdk.EventType.KEY_RELEASE:
            return

        if event.keyval == Gdk.KEY_Delete and self._delete_button.get_sensitive():
            self._delete_button.emit("clicked")

    def _sum_reclaimable_space(self, model, path, itr, *args):
        obj = PartStoreRow(*model[itr])

        if not obj.name:
            return False

        device = self.storage.devicetree.get_device_by_name(obj.name)
        if device.is_disk and device.partitioned and device.format.supported:
            return False

        if obj.action == _(PRESERVE):
            return False
        if obj.action == _(SHRINK):
            self._selected_reclaimable_space += device.size - Size(obj.target)
        elif obj.action == _(DELETE):
            self._selected_reclaimable_space += int(device.size)

        return False

    def on_preserve_clicked(self, button):
        itr = self._selection.get_selected()[1]
        self._on_action_changed(itr, PRESERVE)

    def on_shrink_clicked(self, button):
        itr = self._selection.get_selected()[1]
        self._on_action_changed(itr, SHRINK)

    def on_delete_clicked(self, button):
        itr = self._selection.get_selected()[1]
        self._on_action_changed(itr, DELETE)

    def _on_action_changed(self, itr, new_action):
        if not itr:
            return

        # Handle the row selected when a button was pressed.
        selected_row = self._disk_store[itr]
        selected_row[ACTION_COL] = _(new_action)

        # If that row is a disk header, we need to process all the partitions
        # it contains.
        device = self.storage.devicetree.get_device_by_name(selected_row[DEVICE_NAME_COL])
        if device.is_disk and device.partitioned and device.format.supported:
            part_itr = self._disk_store.iter_children(itr)

            while part_itr:
                # Immutable entries are those that we can't do anything to - like
                # the free space lines.  We just want to leave them in the display
                # for information, but you can't choose to preserve/delete/shrink
                # them.
                if self._disk_store[part_itr][TYPE_COL] in [TY_FREE_SPACE, TY_PROTECTED]:
                    part_itr = self._disk_store.iter_next(part_itr)
                    continue

                self._disk_store[part_itr][ACTION_COL] = _(new_action)

                # If the user marked a whole disk for deletion, they can't go in and
                # un-delete partitions under it.
                if new_action == DELETE:
                    self._disk_store[part_itr][EDITABLE_COL] = False
                elif new_action == PRESERVE:
                    part = self.storage.devicetree.get_device_by_name(
                        self._disk_store[part_itr][DEVICE_NAME_COL]
                    )
                    self._disk_store[part_itr][EDITABLE_COL] = not part.protected

                part_itr = self._disk_store.iter_next(part_itr)

        # And then we're keeping a running tally of how much space the user
        # has selected to reclaim, so reflect that in the UI.
        self._selected_reclaimable_space = Size(0)
        self._disk_store.foreach(self._sum_reclaimable_space, None)
        self._update_labels(selected_reclaimable=self._selected_reclaimable_space)
        self._update_reclaim_button(self._selected_reclaimable_space)
        self._update_action_buttons(selected_row)

    def _schedule_actions(self, model, path, itr, *args):
        obj = PartStoreRow(*model[itr])

        if not obj.name:
            return False

        if not obj.editable:
            return False

        if obj.action == _(PRESERVE):
            pass
        elif obj.action == _(SHRINK):
            device = self.storage.devicetree.get_device_by_name(obj.name)
            shrink_device(self.storage, device, Size(obj.target))
        elif obj.action == _(DELETE):
            device = self.storage.devicetree.get_device_by_name(obj.name)
            remove_device(self.storage, device)

        return False

    def on_resize_clicked(self, *args):
        self._disk_store.foreach(self._schedule_actions, None)

    def on_delete_all_clicked(self, button, *args):
        if button.get_label() == C_("GUI|Reclaim Dialog", "Delete _all"):
            action = DELETE
            button.set_label(C_("GUI|Reclaim Dialog", "Preserve _all"))
        else:
            action = PRESERVE
            button.set_label(C_("GUI|Reclaim Dialog", "Delete _all"))

        itr = self._disk_store.get_iter_first()
        while itr:
            obj = PartStoreRow(*self._disk_store[itr])
            if not obj.editable:
                itr = self._disk_store.iter_next(itr)
                continue

            device = self.storage.devicetree.get_device_by_name(obj.name)
            if device.is_disk:
                self._on_action_changed(itr, action)

            itr = self._disk_store.iter_next(itr)

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
        itr = selection.get_selected()[1]

        if not itr:
            return

        self._update_action_buttons(self._disk_store[itr])

    @timed_action(delay=200, threshold=500, busy_cursor=False)
    def on_resize_value_changed(self, rng):
        (model, itr) = self._selection.get_selected()

        old_delta = Size(rng.get_adjustment().get_upper()) - int(model[itr][RESIZE_TARGET_COL])
        self._selected_reclaimable_space -= old_delta

        # Update the target size in the store.
        model[itr][RESIZE_TARGET_COL] = Size(rng.get_value())

        # Update the "Total selected space" label.
        delta = Size(rng.get_adjustment().get_upper()) - int(rng.get_value())
        self._selected_reclaimable_space += delta
        self._update_labels(selected_reclaimable=self._selected_reclaimable_space)

        # And then the reclaim button, in case they've made enough space.
        self._update_reclaim_button(self._selected_reclaimable_space)

    def resize_slider_format(self, scale, value):
        # This makes the value displayed under the slider prettier than just a
        # single number.
        return str(Size(value))
