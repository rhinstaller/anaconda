# vim: set fileencoding=utf-8
# Mountpoint selector accordion and page classes
#
# Copyright (C) 2012-2014 Red Hat, Inc.
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

from blivet.devicefactory import is_supported_device_type

from pyanaconda.i18n import _, C_
from pyanaconda.product import productName, productVersion
from pyanaconda.ui.gui.utils import escape_markup, really_hide, really_show
from pyanaconda.constants import DEFAULT_AUTOPART_TYPE
from pyanaconda.storage_utils import AUTOPART_CHOICES, AUTOPART_DEVICE_TYPES

import gi
gi.require_version("AnacondaWidgets", "3.0")
gi.require_version("Gtk", "3.0")

from gi.repository.AnacondaWidgets import MountpointSelector
from gi.repository import Gtk

__all__ = ["DATA_DEVICE", "SYSTEM_DEVICE",
           "newSelectorFromDevice", "updateSelectorFromDevice",
           "Accordion",
           "Page", "UnknownPage", "CreateNewPage"]

DATA_DEVICE = 0
SYSTEM_DEVICE = 1

def updateSelectorFromDevice(selector, device, mountpoint=""):
    """Create a MountpointSelector from a Device object template.  This
       method should be used whenever constructing a new selector, or when
       setting a bunch of attributes on an existing selector.  For just
       changing the name or size, it's probably fine to do it by hand.

       This method returns the selector created.

       If given a selector parameter, attributes will be set on that object
       instead of creating a new one.  The optional mountpoint parameter
       allows for specifying the mountpoint if it cannot be determined from
       the device (like for a Root specifying an existing installation).
    """
    if hasattr(device.format, "mountpoint") and device.format.mountpoint is not None:
        mp = device.format.mountpoint
    elif mountpoint:
        mp = mountpoint
    elif device.format.name:
        mp = device.format.name
    else:
        mp = _("Unknown")

    selector.props.name = device.name
    selector.props.size = str(device.size)
    selector.props.mountpoint = mp
    selector.device = device

def newSelectorFromDevice(device, mountpoint=""):
    selector = MountpointSelector(device.name, str(device.size))
    selector._root = None
    updateSelectorFromDevice(selector, device, mountpoint)

    return selector

# An Accordion is a box that goes on the left side of the custom partitioning spoke.  It
# stores multiple expanders which are here called Pages.  These Pages correspond to
# individual installed OSes on the system plus some special ones.  When one Page is
# expanded, all others are collapsed.
class Accordion(Gtk.Box):
    def __init__(self):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._expanders = []
        self._selectedPages = []

    def addPage(self, contents, cb):
        label = Gtk.Label(label="""<span size='large' weight='bold' fgcolor='black'>%s</span>""" %
                          escape_markup(contents.pageTitle), use_markup=True,
                          xalign=0, yalign=0.5, wrap=True)

        expander = Gtk.Expander()
        expander.set_label_widget(label)
        expander.add(contents)

        self.add(expander)
        self._expanders.append(expander)
        expander.connect("activate", self._onExpanded, cb)
        expander.show_all()

    def _find_by_title(self, title):
        for e in self._expanders:
            if e.get_child().pageTitle == title:
                return e

        return None

    @property
    def allPages(self):
        return [e.get_child() for e in self._expanders]

    @property
    def allSelectors(self):
        return [s for p in self.allPages for s in p.members]

    @property
    def allMembers(self):
        for page in self.allPages:
            for member in page.members:
                yield (page, member)

    @property
    def is_multiselection(self):
        return len(self._selectedPages) > 1

    @property
    def selectedPages(self):
        return self._selectedPages

    def expandPage(self, pageTitle):
        page = self._find_by_title(pageTitle)
        if not page:
            raise LookupError()

        if not page.get_expanded():
            page.emit("activate")

    def removePage(self, pageTitle):
        # First, remove the expander from the list of expanders we maintain.
        target = self._find_by_title(pageTitle)
        if not target:
            return

        self._expanders.remove(target)
        self._selectedPages.remove(target)

        # Then, remove it from the box.
        self.remove(target)

    def removeAllPages(self):
        for e in self._expanders:
            self.remove(e)

        self._expanders = []

    def _onExpanded(self, obj, cb=None):
        if cb:
            cb(obj.get_child())

# A Page is a box that is stored in an Accordion.  It breaks down all the filesystems that
# comprise a single installed OS into two categories - Data filesystems and System filesystems.
# Each filesystem is described by a single MountpointSelector.
class Page(Gtk.Box):
    def __init__(self, title):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=6)

        # Create the Data label and a box to store all its members in.
        self._dataBox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._dataLabel = self._make_category_label(_("DATA"))
        really_hide(self._dataLabel)
        self._dataBox.add(self._dataLabel)
        self._dataBox.connect("add", self._onSelectorAdded, self._dataLabel)
        self._dataBox.connect("remove", self._onSelectorRemoved, self._dataLabel)
        self.add(self._dataBox)

        # Create the System label and a box to store all its members in.
        self._systemBox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._systemLabel = self._make_category_label(_("SYSTEM"))
        really_hide(self._systemLabel)
        self._systemBox.add(self._systemLabel)
        self._systemBox.connect("add", self._onSelectorAdded, self._systemLabel)
        self._systemBox.connect("remove", self._onSelectorRemoved, self._systemLabel)
        self.add(self._systemBox)

        self.members = []
        self.pageTitle = title

    def _make_category_label(self, name):
        label = Gtk.Label()
        label.set_markup("""<span fgcolor='dark grey' size='large' weight='bold'>%s</span>""" %
                escape_markup(name))
        label.set_halign(Gtk.Align.START)
        label.set_margin_left(24)
        return label

    def addSelector(self, device, cb, mountpoint=""):
        selector = newSelectorFromDevice(device, mountpoint=mountpoint)
        selector.connect("button-press-event", self._onSelectorClicked, cb)
        selector.connect("key-release-event", self._onSelectorClicked, cb)
        selector.connect("focus-in-event", self._onSelectorFocusIn, cb)
        selector.set_margin_bottom(6)
        self.members.append(selector)

        # pylint: disable=no-member
        if self._mountpointType(selector.props.mountpoint) == DATA_DEVICE:
            self._dataBox.add(selector)
        else:
            self._systemBox.add(selector)

        return selector

    def removeSelector(self, selector):
        if self._mountpointType(selector.props.mountpoint) == DATA_DEVICE:
            self._dataBox.remove(selector)
        else:
            self._systemBox.remove(selector)

        self.members.remove(selector)

    def _mountpointType(self, mountpoint):
        if not mountpoint or mountpoint in ["/", "/boot", "/boot/efi", "/tmp", "/usr", "/var",
                                            "swap", "PPC PReP Boot", "BIOS Boot"]:
            return SYSTEM_DEVICE
        else:
            return DATA_DEVICE

    def _onSelectorClicked(self, selector, event, cb):
        gi.require_version("Gdk", "3.0")
        from gi.repository import Gdk

        if event:
            if not event.type in [Gdk.EventType.BUTTON_PRESS, Gdk.EventType.KEY_RELEASE, Gdk.EventType.FOCUS_CHANGE]:
                return

            if event.type == Gdk.EventType.KEY_RELEASE and \
               event.keyval not in [Gdk.KEY_space, Gdk.KEY_Return, Gdk.KEY_ISO_Enter, Gdk.KEY_KP_Enter, Gdk.KEY_KP_Space]:
                return

            state = event.get_state()
            accordion = self.get_ancestor(Accordion)
            if state & Gdk.ModifierType.CONTROL_MASK:
                if selector in accordion._selectedPages:
                    # Unselect actual item and return
                    accordion._selectedPages.remove(selector)
                    selector.set_chosen(False)
                    return
                else:
                    accordion._selectedPages.append(selector)
            elif not accordion._selectedPages:
                accordion._selectedPages.append(selector)

        # Then, this callback will set up the right hand side of the screen to
        # show the details for the newly selected object.
        cb(selector)

    def _onSelectorFocusIn(self, selector, event, cb):
        # could be simple lambda, but this way it looks more similar to the
        # _onSelectorClicked
        cb(selector)

    def _onSelectorAdded(self, container, widget, label):
        really_show(label)

    def _onSelectorRemoved(self, container, widget, label):
        # This runs before widget is removed from container, so if it's the last
        # item then the container will still not be empty.
        if len(container.get_children()) == 1:
            really_hide(label)

class UnknownPage(Page):
    def __init__(self, title):
        # For this type of page, there's only one place to store members.
        # pylint: disable=super-init-not-called,non-parent-init-called
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.members = []
        self.pageTitle = title

    def addSelector(self, device, cb, mountpoint=""):
        selector = newSelectorFromDevice(device, mountpoint=mountpoint)
        selector.connect("button-press-event", self._onSelectorClicked, cb)
        selector.connect("key-release-event", self._onSelectorClicked, cb)

        self.members.append(selector)
        self.add(selector)

        return selector

    def removeSelector(self, selector):
        self.remove(selector)
        self.members.remove(selector)

# This is a special Page that is displayed when no new installation has been automatically
# created, and shows the user how to go about doing that.  The intention is that an instance
# of this class will be packed into the Accordion first and then when the new installation
# is created, it will be removed and replaced with a Page for it.
class CreateNewPage(Page):
    def __init__(self, title, createClickedCB, autopartTypeChangedCB, partitionsToReuse=True):
        # pylint: disable=super-init-not-called,non-parent-init-called
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.members = []
        self.pageTitle = title

        # Create a box where we store the "Here's how you create a new blah" info.
        self._createBox = Gtk.Grid()
        self._createBox.set_row_spacing(6)
        self._createBox.set_column_spacing(6)
        self._createBox.set_margin_left(16)

        label = Gtk.Label(label=_("You haven't created any mount points for your "
                            "%(product)s %(version)s installation yet.  "
                            "You can:") % {"product" : productName, "version" : productVersion},
                            wrap=True, xalign=0, yalign=0.5)
        self._createBox.attach(label, 0, 0, 2, 1)

        dot = Gtk.Label(label="•", xalign=0.5, yalign=0.4, hexpand=False)
        self._createBox.attach(dot, 0, 1, 1, 1)

        self._createNewButton = Gtk.LinkButton(uri="",
                label=C_("GUI|Custom Partitioning|Autopart Page", "_Click here to create them automatically."))
        label = self._createNewButton.get_children()[0]
        label.set_alignment(0, 0.5)
        label.set_hexpand(True)
        label.set_line_wrap(True)
        label.set_use_underline(True)

        # Create this now to pass into the callback.  It will be populated later
        # on in this method.
        store = Gtk.ListStore(str, int)
        combo = Gtk.ComboBox(model=store)
        cellrendr = Gtk.CellRendererText()
        combo.pack_start(cellrendr, True)
        combo.add_attribute(cellrendr, "text", 0)
        combo.connect("changed", autopartTypeChangedCB)

        self._createNewButton.set_has_tooltip(False)
        self._createNewButton.set_halign(Gtk.Align.START)
        self._createNewButton.connect("clicked", createClickedCB, combo)
        self._createNewButton.connect("activate-link", lambda *args: Gtk.true())
        self._createBox.attach(self._createNewButton, 1, 1, 1, 1)

        dot = Gtk.Label(label="•", xalign=0.5, yalign=0, hexpand=False)
        self._createBox.attach(dot, 0, 2, 1, 1)

        label = Gtk.Label(label=_("Create new mount points by clicking the '+' button."),
                          xalign=0, yalign=0.5, hexpand=True, wrap=True)
        self._createBox.attach(label, 1, 2, 1, 1)

        if partitionsToReuse:
            dot = Gtk.Label(label="•", xalign=0.5, yalign=0, hexpand=False)
            self._createBox.attach(dot, 0, 3, 1, 1)

            label = Gtk.Label(label=_("Or, assign new mount points to existing "
                                      "partitions after selecting them below."),
                              xalign=0, yalign=0.5, hexpand=True, wrap=True)
            self._createBox.attach(label, 1, 3, 1, 1)

        label = Gtk.Label(label=C_("GUI|Custom Partitioning|Autopart Page", "_New mount points will use the following partitioning scheme:"),
                          xalign=0, yalign=0.5, wrap=True, use_underline=True)
        self._createBox.attach(label, 0, 4, 2, 1)
        label.set_mnemonic_widget(combo)

        autopart_choices = (c for c in AUTOPART_CHOICES if is_supported_device_type(AUTOPART_DEVICE_TYPES[c[1]]))
        default = None
        for name, code in autopart_choices:
            itr = store.append([_(name), code])
            if code == DEFAULT_AUTOPART_TYPE:
                default = itr

        combo.set_margin_left(18)
        combo.set_margin_right(18)
        combo.set_hexpand(False)
        combo.set_active_iter(default or store.get_iter_first())

        self._createBox.attach(combo, 0, 5, 2, 1)

        self.add(self._createBox)
