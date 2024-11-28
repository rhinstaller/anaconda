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
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.i18n import _, C_
from pyanaconda.core.product import get_product_name, get_product_version
from pyanaconda.core.storage import get_supported_autopart_choices
from pyanaconda.ui.gui.utils import escape_markup, really_hide, really_show

import gi
gi.require_version("AnacondaWidgets", "3.4")
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, AnacondaWidgets

log = get_module_logger(__name__)

__all__ = ["Accordion", "CreateNewPage", "MountPointSelector", "Page", "UnknownPage"]

DATA_DEVICE = 0
SYSTEM_DEVICE = 1
SYSTEM_MOUNT_POINTS = [
    "/", "/boot", "/boot/efi", "/tmp", "/usr",
    "/var", "swap", "PPC PReP Boot", "BIOS Boot"
]


class MountPointSelector(AnacondaWidgets.MountpointSelector):
    """The mount point selector."""

    def __init__(self):
        super().__init__()
        self.root_name = ""

    @property
    def device_name(self):
        return self.get_property("name")

    @property
    def mount_point(self):
        return self.get_property("mountpoint")

    @property
    def mount_point_type(self):
        if not self.mount_point or self.mount_point in SYSTEM_MOUNT_POINTS:
            return SYSTEM_DEVICE
        else:
            return DATA_DEVICE


class Accordion(Gtk.Box):
    """ An Accordion is a box that goes on the left side of the custom partitioning spoke.
        It stores multiple expanders which are here called Pages.  These Pages correspond to
        individual installed OSes on the system plus some special ones.  When one Page is
        expanded, all others are collapsed.
    """
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._expanders = []
        self._active_selectors = []
        self._current_selector = None
        self._last_selected = None

    def find_page_by_title(self, title):
        for e in self._expanders:
            if e.get_child().page_title == title:
                return e.get_child()

        return None

    def _on_expanded(self, obj, cb=None):
        # Get the content of the expander.
        child = obj.get_child()

        if child:
            # The expander is not expanded yet.
            is_expanded = not obj.get_expanded()
            # Show or hide the child.
            # We need to set this manually because of a gtk bug:
            # https://bugzilla.gnome.org/show_bug.cgi?id=776937
            child.set_visible(is_expanded)

        if cb:
            cb(child)

    def _activate_selector(self, selector, activate, show_arrow):
        selector.set_chosen(activate)
        selector.props.show_arrow = show_arrow
        selector.get_page().mark_selection(selector)

    def add_page(self, contents, cb):
        label = Gtk.Label(label="""<span size='large' weight='bold' fgcolor='black'>%s</span>""" %
                          escape_markup(contents.page_title), use_markup=True,
                          xalign=0, yalign=0.5, wrap=True)

        expander = Gtk.Expander()
        expander.set_label_widget(label)
        expander.add(contents)

        self.add(expander)
        self._expanders.append(expander)
        expander.connect("activate", self._on_expanded, cb)
        expander.show_all()

    def unselect(self):
        """ Unselect all items and clear current_selector.
        """
        for s in self._active_selectors:
            self._activate_selector(s, False, False)
        self._active_selectors.clear()
        self._current_selector = None
        log.debug("Unselecting all items.")

    def select(self, selector):
        """ Select one item. Remove selection from all other items
            and clear ``current_selector`` if set. Add new selector and
            append it to selected items. Also select the new item.

            :param selector: Selector which we want to select.
        """
        self.unselect()
        self._active_selectors.append(selector)
        self._current_selector = selector
        self._last_selected = selector
        self._activate_selector(selector, activate=True, show_arrow=True)
        log.debug("Select device: %s", selector.device_name)

    def _select_with_shift(self, clicked_selector):
        # No items selected, only select this one
        if not self._last_selected or self._last_selected is clicked_selector:
            self.select(clicked_selector)
            return

        select_items = []
        start_selection = False
        for s in self.all_selectors:
            if s is clicked_selector or s is self._last_selected:
                if start_selection:
                    select_items.append(s) # append last item too
                    break
                else:
                    start_selection = True
            if start_selection:
                select_items.append(s)

        self.unselect()
        self.append_selection(select_items)

    def append_selection(self, selectors):
        """ Append new selectors to the actual selection. This takes
            list of selectors.
            If more than 1 item is selected remove the ``current_selector``.
            No current selection is allowed in multiselection.

            :param list selectors: List of selectors which will be
            appended to current selection.
        """
        if not selectors:
            return

        # If multiselection is already active it will be active even after the new selection.
        multiselection = ((self.is_multiselection or len(selectors) > 1) or
                          # Multiselection will be active also when there is one item already
                          # selected and it's not the same which is in selectors array
                          (self._current_selector and self._current_selector not in selectors))

        # Hide arrow from current selected item if there will be multiselection.
        if not self.is_multiselection and multiselection and self._current_selector:
            self._current_selector.props.show_arrow = False

        for s in selectors:
            self._active_selectors.append(s)
            if multiselection:
                self._activate_selector(s, activate=True, show_arrow=False)
            else:
                self._activate_selector(s, activate=True, show_arrow=True)
            log.debug("Append device %s to the selection.", s.device_name)

        if len(selectors) == 1:
            self._last_selected = selectors[-1]

        if multiselection:
            self._current_selector = None
        else:
            self._current_selector = self._active_selectors[0]
        log.debug("Selected items %s; added items %s",
                  len(self._active_selectors), len(selectors))

    def remove_selection(self, selectors):
        """ Remove :param:`selectors` from current selection. If only
            one item is selected after this operation it's set as
            ``current_selector``.
            Items which are not selected are ignored.

            :param list selectors: List of selectors which will be
            removed from current selection.
        """
        for s in selectors:
            if s in self._active_selectors:
                self._activate_selector(s, activate=False, show_arrow=False)
                self._active_selectors.remove(s)
                log.debug("Device %s is removed from the selection.", s)

        if len(self._active_selectors) == 1:
            self._current_selector = self._active_selectors[0]
            self._current_selector.props.show_arrow = True
        else:
            self._current_selector = None
        log.debug("Selected items %s; removed items %s",
                  len(self._active_selectors), len(selectors))

    @property
    def current_selector(self):
        return self._current_selector

    @property
    def all_pages(self):
        return [e.get_child() for e in self._expanders]

    @property
    def all_selectors(self):
        return [s for p in self.all_pages for s in p.members]

    @property
    def is_multiselection(self):
        return len(self._active_selectors) > 1

    @property
    def is_current_selected(self):
        if self.current_selector:
            return True
        return False

    @property
    def selected_items(self):
        return self._active_selectors

    def page_for_selector(self, selector):
        """ Return page for given selector. """
        for page in self.all_pages:
            for s in page.members:
                if s is selector:
                    return page

    def get_expanded_pages(self):
        """Return titles of expanded pages."""
        return [page.page_title for page in self.all_pages if page.get_parent().get_expanded()]

    def expand_pages(self, page_titles):
        for page_title in page_titles:
            page = self.find_page_by_title(page_title)
            if page:
                expander = page.get_parent()
                if not expander:
                    raise LookupError()

                if not expander.get_expanded():
                    expander.emit("activate")

    def remove_page(self, page_title):
        # First, remove the expander from the list of expanders we maintain.
        target = self.find_page_by_title(page_title)
        if not target:
            return

        self._expanders.remove(target.get_parent())
        for s in target.members:
            if s in self._active_selectors:
                self._active_selectors.remove(s)

        # Then, remove it from the box.
        self.remove(target.get_parent())

    def remove_all_pages(self):
        for e in self._expanders:
            self.remove(e)

        self._expanders = []
        self._active_selectors = []
        self._current_selector = None

    def clear_current_selector(self):
        """ If current selector is selected, deselect it
        """
        if self._current_selector:
            if self._current_selector in self._active_selectors:
                self._active_selectors.remove(self._current_selector)
            self._activate_selector(self._current_selector, activate=False, show_arrow=False)
            self._current_selector = None

    def process_event(self, selector, event, cb):
        """ Process events from selectors and select items as result.
            Call cb after selection is done with old selector and new selector
            as arguments.

            :param selector: Clicked selector
            :param event: Gtk event object
            :param cb: Callback which will be called after selection is done.
            This callback is setup in :meth:`Page.add_selector` method.
        """
        gi.require_version("Gdk", "3.0")
        from gi.repository import Gdk

        old_selector = self.current_selector

        if event:
            if event.type not in [Gdk.EventType.BUTTON_PRESS, Gdk.EventType.KEY_RELEASE,
                                  Gdk.EventType.FOCUS_CHANGE]:
                return

            if event.type == Gdk.EventType.KEY_RELEASE and \
               event.keyval not in [Gdk.KEY_space, Gdk.KEY_Return, Gdk.KEY_ISO_Enter, Gdk.KEY_KP_Enter, Gdk.KEY_KP_Space]:
                return

            # deal with multiselection
            state = event.get_state()
            if state & Gdk.ModifierType.CONTROL_MASK: # holding CTRL
                if selector in self._active_selectors:
                    self.remove_selection([selector])
                else:
                    self.append_selection([selector])
            elif state & Gdk.ModifierType.SHIFT_MASK: # holding SHIFT
                self._select_with_shift(selector)
            else:
                self.select(selector)

        # Then, this callback will set up the right hand side of the screen to
        # show the details for the newly selected object.
        cb(old_selector, selector)


class BasePage(Gtk.Box):
    """ Base class for all Pages. It implements most methods which is used
        all kind of Page classes.

        .. NOTE::

            You should not instantiate this class. Please create a subclass
            and use the subclass instead.
    """
    def __init__(self, title):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.members = []
        self.page_title = title
        self._selected_members = set()
        self._data_box = None
        self._system_box = None

    @property
    def selected_members(self):
        return self._selected_members

    def _get_accordion(self):
        return self.get_ancestor(Accordion)

    def _make_category_label(self, name):
        label = Gtk.Label()
        label.set_markup("""<span fgcolor='dark grey' size='large' weight='bold'>%s</span>""" %
                escape_markup(name))
        label.set_halign(Gtk.Align.START)
        label.set_margin_start(24)
        return label

    def mark_selection(self, selector):
        if selector.get_chosen():
            self._selected_members.add(selector)
        else:
            self._selected_members.discard(selector)

    def add_selector(self, selector, cb):
        accordion = self._get_accordion()
        selector.set_page(self)
        selector.connect("button-press-event", accordion.process_event, cb)
        selector.connect("key-release-event", accordion.process_event, cb)
        selector.connect("focus-in-event", self._on_selector_focus_in, cb)
        selector.set_margin_bottom(6)
        self.members.append(selector)

        # pylint: disable=no-member
        if selector.mount_point_type == DATA_DEVICE:
            self._data_box.add(selector)
        else:
            self._system_box.add(selector)

    def _on_selector_focus_in(self, selector, event, cb):
        accordion = self._get_accordion()
        cb(accordion.current_selector, selector)

    def _on_selector_added(self, container, widget, label):
        really_show(label)

    def _on_selector_removed(self, container, widget, label):
        # This runs before widget is removed from container, so if it's the last
        # item then the container will still not be empty.
        if len(container.get_children()) == 1:
            really_hide(label)


class Page(BasePage):
    """ A Page is a box that is stored in an Accordion.  It breaks down all the filesystems that
        comprise a single installed OS into two categories - Data filesystems and System filesystems.
        Each filesystem is described by a single MountpointSelector.
    """
    def __init__(self, title):
        super().__init__(title)

        # Create the Data label and a box to store all its members in.
        self._data_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._data_label = self._make_category_label(_("DATA"))
        really_hide(self._data_label)
        self._data_box.add(self._data_label)
        self._data_box.connect("add", self._on_selector_added, self._data_label)
        self._data_box.connect("remove", self._on_selector_removed, self._data_label)
        self.add(self._data_box)

        # Create the System label and a box to store all its members in.
        self._system_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._system_label = self._make_category_label(_("SYSTEM"))
        really_hide(self._system_label)
        self._system_box.add(self._system_label)
        self._system_box.connect("add", self._on_selector_added, self._system_label)
        self._system_box.connect("remove", self._on_selector_removed, self._system_label)
        self.add(self._system_box)


class UnknownPage(BasePage):

    def add_selector(self, selector, cb):
        accordion = self._get_accordion()
        selector.set_page(self)
        selector.connect("button-press-event", accordion.process_event, cb)
        selector.connect("key-release-event", accordion.process_event, cb)
        self.members.append(selector)
        self.add(selector)


class CreateNewPage(BasePage):
    """ This is a special Page that is displayed when no new installation
        has been automatically created, and shows the user how to go about
        doing that.  The intention is that an instance of this class will be
        packed into the Accordion first and then when the new installation
        is created, it will be removed and replaced with a Page for it.
    """
    def __init__(self, title, create_clicked_cb, autopart_type_changed_cb,
                 encrypted_changed_cb, default_scheme, default_encryption,
                 partitions_to_reuse=True):
        super().__init__(title)

        # Create a box where we store the "Here's how you create a new blah" info.
        self._createBox = Gtk.Grid()
        self._createBox.set_row_spacing(6)
        self._createBox.set_column_spacing(6)
        self._createBox.set_margin_start(16)

        label = Gtk.Label(label=_("You haven't created any mount points for your "
                            "%(product)s %(version)s installation yet.  "
                            "You can:") % {"product" : get_product_name(),
                                           "version" : get_product_version()},
                            wrap=True, xalign=0, yalign=0.5)
        self._createBox.attach(label, 0, 0, 2, 1)

        dot = Gtk.Label(label="•", xalign=0.5, yalign=0.4, hexpand=False)
        self._createBox.attach(dot, 0, 1, 1, 1)

        self._createNewButton = Gtk.LinkButton(uri="",
                label=C_("GUI|Custom Partitioning|Autopart Page", "_Click here to create them automatically."))
        label = self._createNewButton.get_children()[0]
        label.set_xalign(0)
        label.set_yalign(0.5)
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
        combo.connect("changed", autopart_type_changed_cb)

        self._createNewButton.set_has_tooltip(False)
        self._createNewButton.set_halign(Gtk.Align.START)
        self._createNewButton.connect("clicked", create_clicked_cb, combo)
        self._createNewButton.connect("activate-link", lambda *args: Gtk.true())
        self._createBox.attach(self._createNewButton, 1, 1, 1, 1)

        dot = Gtk.Label(label="•", xalign=0.5, yalign=0, hexpand=False)
        self._createBox.attach(dot, 0, 2, 1, 1)

        label = Gtk.Label(label=_("Create new mount points by clicking the '+' button."),
                          xalign=0, yalign=0.5, hexpand=True, wrap=True)
        self._createBox.attach(label, 1, 2, 1, 1)

        if partitions_to_reuse:
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

        default = None
        for name, code in get_supported_autopart_choices():
            itr = store.append([_(name), code])
            if code == default_scheme:
                default = itr

        combo.set_margin_start(18)
        combo.set_margin_end(18)
        combo.set_hexpand(False)
        combo.set_active_iter(default or store.get_iter_first())
        self._createBox.attach(combo, 0, 5, 2, 1)

        label = Gtk.Label(
            label=C_(
                "GUI|Custom Partitioning|Autopart Page",
                "_Encrypt automatically created mount points by default:"
            ),
            xalign=0,
            yalign=0.5,
            wrap=True,
            use_underline=True
        )
        self._createBox.attach(label, 0, 6, 2, 1)

        checkbox = Gtk.CheckButton(label=C_("GUI|Custom Partitioning|Autopart Page", "Encrypt my data."))
        checkbox.connect("toggled", encrypted_changed_cb)
        checkbox.set_active(default_encryption)
        checkbox.set_margin_start(18)
        checkbox.set_margin_end(18)
        checkbox.set_hexpand(False)

        label.set_mnemonic_widget(checkbox)
        self._createBox.attach(checkbox, 0, 7, 2, 1)

        self.add(self._createBox)
