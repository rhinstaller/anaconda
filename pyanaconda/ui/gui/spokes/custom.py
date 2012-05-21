# Custom partitioning classes.
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

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)
N_ = lambda x: x
P_ = lambda x, y, z: gettext.ldngettext("anaconda", x, y, z)

from pyanaconda.product import productName, productVersion
from pyanaconda.storage.size import Size

from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.utils import setViewportBackground
from pyanaconda.ui.gui.categories.storage import StorageCategory

from gi.repository.AnacondaWidgets import MountpointSelector
from gi.repository import Gtk

__all__ = ["CustomPartitioningSpoke"]

DATA_DEVICE = 0
SYSTEM_DEVICE = 1

# An Accordion is a box that goes on the left side of the custom partitioning spoke.  It
# stores multiple expanders which are here called Pages.  These Pages correspond to
# individual installed OSes on the system plus some special ones.  When one Page is
# expanded, all others are collapsed.
class Accordion(Gtk.Box):
    def __init__(self):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._expanders = []

    def addPage(self, pageTitle, contents):
        label = Gtk.Label()
        label.set_markup("""<span size='large' weight='bold' fgcolor='black'>%s</span>""" % pageTitle)
        label.set_halign(Gtk.Align.START)
        label.set_line_wrap(True)

        expander = Gtk.Expander()
        expander.set_label_widget(label)
        expander.add(contents)
        expander.set_expanded(isinstance(contents, CreateNewPage))

        self.add(expander)
        self._expanders.append(expander)
        expander.connect("notify::expand", self._onExpanded)
        expander.show()

    def _onExpanded(self, obj, pspec):
        if not obj.get_expanded():
            return

        for expander in self._expanders:
            if expander is not obj:
                expander.set_expanded(False)

# A Page is a box that is stored in an Accordion.  It breaks down all the filesystems that
# comprise a single installed OS into two categories - Data filesystems and System filesystems.
# Each filesystem is described by a single MountpointSelector.
class Page(Gtk.Box):
    def __init__(self_):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=6)

        # Create the Data label and a box to store all its members in.
        self._dataBox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._dataBox.add(self._make_category_label(_("DATA")))
        self.add(self._dataBox)

        # Create the System label and a box to store all its members in.
        self._systemBox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._systemBox.add(self._make_category_label(_("SYSTEM")))
        self.add(self._systemBox)

        self._members = []

    def _make_category_label(self, name):
        label = Gtk.Label()
        label.set_markup("""<span fgcolor='dark grey' size='large' weight='bold'>%s</span>""" % name)
        label.set_halign(Gtk.Align.START)
        label.set_margin_left(24)
        return label

    def addDevice(self, device, ty):
        selector = MountpointSelector(device.name, device.size, device.mountpoint)
        selector.connect("button-release-event", self._onClicked)
        self._members.append(selector)

        if ty == DATA_DEVICE:
            self._dataBox.add(selector)
        else:
            self._systemBox.add(selector)

    def _onClicked(self, obj, event):
        for mem in self._members:
            mem._onClicked(mem == obj)

# This is a special Page that is displayed when no new installation has been automatically
# created, and shows the user how to go about doing that.  The intention is that an instance
# of this class will be packed into the Accordion first and then when the new installation
# is created, it will be removed and replaced with a Page for it.
class CreateNewPage(Page):
    def __init__(self):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=6)

        # Create a box where we store the "Here's how you create a new blah" info.
        self._createBox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._createBox.set_margin_left(16)

        label = Gtk.Label(_("You haven't created any mount points for your %s %s installation yet:") % (productName, productVersion))
        label.set_halign(Gtk.Align.START)
        label.set_line_wrap(True)
        self._createBox.add(label)

        self._createNewButton = Gtk.Button("")
        label = self._createNewButton.get_children()[0]
        label.set_line_wrap(True)
        label.set_use_markup(True)
        label.set_markup("""<span foreground='blue'><u>Click here to create them automatically.</u></span>""")

        self._createNewButton.set_halign(Gtk.Align.START)
        self._createNewButton.connect("clicked", self._onCreateClicked)
        self._createBox.add(self._createNewButton)

        label = Gtk.Label(_("Or, create new mount points below with the '+' icon."))
        label.set_halign(Gtk.Align.START)
        label.set_line_wrap(True)
        self._createBox.add(label)

        self.add(self._createBox)

    def _onCreateClicked(self, button):
        pass

class CustomPartitioningSpoke(NormalSpoke):
    builderObjects = ["customStorageWindow",
                      "partitionStore",
                      "addImage", "removeImage", "settingsImage"]
    mainWidgetName = "customStorageWindow"
    uiFile = "spokes/custom.ui"

    category = StorageCategory
    title = N_("MANUAL PARTITIONING")

    def apply(self):
        pass

    @property
    def indirect(self):
        return True

    def _addCategory(self, store, name):
        return store.append(None, ["""<span size="large" weight="bold" fgcolor="grey">%s</span>""" % name, ""])

    def _addPartition(self, store, itr, device):
        name = self._partitionName(device)
        size = Size(spec=str(device.size) + " MB")

        return store.append(itr, ["""<span size="large" weight="bold">%s</span>\n<span size="small" fgcolor="grey">%s</span>""" % (name, device.format.__dict__.get("mountpoint", "")), size.humanReadable()])

    def _grabObjects(self):
        self._configureBox = self.builder.get_object("configureBox")
        self._availableSpaceLabel = self.builder.get_object("availableSpaceLabel")
        self._totalSpaceLabel = self.builder.get_object("totalSpaceLabel")

        self._summaryButton = self.builder.get_object("summary_button")

        self._viewport = self.builder.get_object("partitionsViewport")
        self._partitionsNotebook = self.builder.get_object("partitionsNotebook")

    def initialize(self):
        NormalSpoke.initialize(self)

        self._grabObjects()
        setViewportBackground(self.builder.get_object("availableSpaceViewport"), "#db3279")
        setViewportBackground(self.builder.get_object("totalSpaceViewport"), "#60605b")
        setViewportBackground(self._viewport)

        self._accordion = Accordion()

        page = CreateNewPage()
        self._accordion.addPage(_("New %s %s Install") % (productName, productVersion), page)
        self._viewport.add(self._accordion)

        self._partitionsNotebook.set_current_page(0)
        label = self.builder.get_object("whenCreateLabel")
        label.set_text(label.get_text() % (productName, productVersion))

    def _partitionName(self, device):
        # If there's a mountpoint, we can probably just use that.
        if hasattr(device.format, "mountpoint") and device.format.mountpoint:
            if device.format.mountpoint == "/":
                return "Root"
            elif device.format.mountpoint.count("/") == 1:
                return device.format.mountpoint[1:].capitalize()
        else:
            # Otherwise, try to use the name of whatever format the request is.
            return device.format.name

    def _isSystemPartition(self, mountpoint):
        if mountpoint and mountpoint in ["/", "/boot"]:
            return True
        elif not mountpoint:
            return True
        else:
            return False

    def _currentFreeSpace(self):
        """Add up all the free space on selected disks and return it as a Size."""
        totalFree = 0

        freeDisks = self.storage.getFreeSpace(disks=[d for d in self.storage.devicetree.devices if d.name in self.data.clearpart.drives])
        for tup in freeDisks.values():
            for chunk in tup:
                totalFree += chunk

        return Size(totalFree).convertTo("GB")

    def _currentTotalSpace(self):
        """Add up the sizes of all selected disks and return it as a Size."""
        totalSpace = 0

        disks = [d for d in self.storage.devicetree.devices if d.name in self.data.clearpart.drives]
        for disk in disks:
            totalSpace += disk.size

        return Size(spec="%s MB" % totalSpace).convertTo("GB")

    def refresh(self):
        NormalSpoke.refresh(self)

        self._availableSpaceLabel.set_text("%.2f GB" % self._currentFreeSpace())
        self._totalSpaceLabel.set_text("%.2f GB" % self._currentTotalSpace())

        summaryLabel = self._summaryButton.get_children()[0]
        count = len(self.data.clearpart.drives)
        summary = P_("%d storage device selected",
                     "%d storage devices selected",
                     count) % count

        summaryLabel.set_use_markup(True)
        summaryLabel.set_markup("<span foreground='blue'><u>%s</u></span>" % summary)

    def on_back_clicked(self, button):
        self.skipTo = "StorageSpoke"
        NormalSpoke.on_back_clicked(self, button)

    # Use the default back action here, since the finish button takes the user
    # to the install summary screen.
    def on_finish_clicked(self, button):
        NormalSpoke.on_back_clicked(self, button)

    def on_add_clicked(self, button):
        pass

    def on_remove_clicked(self, button):
        pass

    def on_summary_clicked(self, button):
        pass

    def on_configure_clicked(self, button):
        pass
