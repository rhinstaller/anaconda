# Mountpoint selector accordion and page classes
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

from pyanaconda.product import productName, productVersion

from gi.repository.AnacondaWidgets import MountpointSelector
from gi.repository import Gtk

__all__ = ["DATA_DEVICE", "SYSTEM_DEVICE",
           "Accordion",
           "Page", "UnknownPage", "CreateNewPage"]

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

    def addPage(self, contents, cb=None):
        label = Gtk.Label()
        label.set_markup("""<span size='large' weight='bold' fgcolor='black'>%s</span>""" % contents.pageTitle)
        label.set_alignment(0, 0.5)
        label.set_line_wrap(True)

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
        return [s for p in self.allPages for s in getattr(p, "_members", [])]

    def currentPage(self):
        for e in self._expanders:
            if e.get_expanded():
                return e.get_child()

        return None

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

        # Then, remove it from the box.
        self.remove(target)

    def removeAllPages(self):
        for e in self._expanders:
            self.remove(e)

        self._expanders = []

    def _onExpanded(self, obj, cb=None):
        # Set all other expanders to closed, but don't do anything to the
        # expander this method was called on.  It's already been handled by
        # the default activate signal handler.
        for expander in self._expanders:
            if expander == obj:
                continue

            expander.set_expanded(False)

        if cb:
            cb(obj.get_child())

# A Page is a box that is stored in an Accordion.  It breaks down all the filesystems that
# comprise a single installed OS into two categories - Data filesystems and System filesystems.
# Each filesystem is described by a single MountpointSelector.
class Page(Gtk.Box):
    def __init__(self):
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
        self.pageTitle = ""

    def _make_category_label(self, name):
        label = Gtk.Label()
        label.set_markup("""<span fgcolor='dark grey' size='large' weight='bold'>%s</span>""" % name)
        label.set_halign(Gtk.Align.START)
        label.set_margin_left(24)
        return label

    def addDevice(self, name, size, mountpoint, cb):
        selector = MountpointSelector(name, str(size).upper(), mountpoint or "")
        selector.connect("button-press-event", self._onSelectorClicked, cb)
        selector.connect("key-release-event", self._onSelectorClicked, cb)
        #selector.connect("focus-in-event", self._onSelectorClicked, cb)
        self._members.append(selector)

        selector._device = None
        selector._root = None

        if self._mountpointType(mountpoint) == DATA_DEVICE:
            self._dataBox.add(selector)
        else:
            self._systemBox.add(selector)

        return selector

    def removeSelector(self, selector):
        if self._mountpointType(selector.props.mountpoint) == DATA_DEVICE:
            self._dataBox.remove(selector)
        else:
            self._systemBox.remove(selector)

        self._members.remove(selector)

    def _mountpointType(self, mountpoint):
        if not mountpoint:
            # This catches things like swap.
            return SYSTEM_DEVICE
        elif mountpoint in ["/", "/boot", "/boot/efi", "/tmp", "/usr", "/var",
                            "biosboot", "prepboot"]:
            return SYSTEM_DEVICE
        else:
            return DATA_DEVICE

    def _onSelectorClicked(self, selector, event, cb):
        from gi.repository import Gdk

        if event and not event.type in [Gdk.EventType.BUTTON_PRESS, Gdk.EventType.KEY_RELEASE, Gdk.EventType.FOCUS_CHANGE]:
            return

        if event and event.type == Gdk.EventType.KEY_RELEASE and \
           event.keyval not in [Gdk.KEY_space, Gdk.KEY_Return, Gdk.KEY_ISO_Enter, Gdk.KEY_KP_Enter, Gdk.KEY_KP_Space]:
              return

        # Then, this callback will set up the right hand side of the screen to
        # show the details for the newly selected object.
        cb(selector)

class UnknownPage(Page):
    def __init__(self):
        # For this type of page, there's only one place to store members.
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._members = []
        self.pageTitle = ""

    def addDevice(self, name, size, mountpoint, cb):
        selector = MountpointSelector(name, str(size).upper(), mountpoint or "")
        selector.connect("button-press-event", self._onSelectorClicked, cb)
        selector.connect("key-release-event", self._onSelectorClicked, cb)
        #selector.connect("focus-in-event", self._onSelectorClicked, cb)

        selector._device = None
        selector._root = None

        self._members.append(selector)
        self.add(selector)

        return selector

    def removeSelector(self, selector):
        self.remove(selector)
        self._members.remove(selector)

# This is a special Page that is displayed when no new installation has been automatically
# created, and shows the user how to go about doing that.  The intention is that an instance
# of this class will be packed into the Accordion first and then when the new installation
# is created, it will be removed and replaced with a Page for it.
class CreateNewPage(Page):
    def __init__(self, cb):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.pageTitle = ""

        # Create a box where we store the "Here's how you create a new blah" info.
        self._createBox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._createBox.set_margin_left(16)

        label = Gtk.Label(_("You haven't created any mount points for your %s %s installation yet:") % (productName, productVersion))
        label.set_alignment(0, 0.5)
        label.set_line_wrap(True)
        self._createBox.add(label)

        self._createNewButton = Gtk.LinkButton("", label=_("Click here to create them automatically."))
        label = self._createNewButton.get_children()[0]
        label.set_line_wrap(True)

        self._createNewButton.set_has_tooltip(False)
        self._createNewButton.set_halign(Gtk.Align.START)
        self._createNewButton.connect("clicked", cb)
        self._createNewButton.connect("activate-link", lambda *args: Gtk.true())
        self._createBox.add(self._createNewButton)

        label = Gtk.Label(_("Or, create new mount points below with the '+' icon."))
        label.set_alignment(0, 0.5)
        label.set_line_wrap(True)
        self._createBox.add(label)

        self.add(self._createBox)
