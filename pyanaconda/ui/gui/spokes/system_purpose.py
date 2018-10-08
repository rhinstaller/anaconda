# system purpose spoke class
#
# Copyright (C) 2018 Red Hat, Inc.
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
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Pango", "1.0")

from gi.repository import Gtk, Pango

from pyanaconda.core.i18n import _, CN_
from pyanaconda.modules.common.constants.services import SUBSCRIPTION

from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.utils import escape_markup
from pyanaconda.ui.categories.system import SystemCategory
from pyanaconda.ui.communication import hubQ

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

__all__ = ["SystemPurposeSpoke"]


class SystemPurposeSpoke(NormalSpoke):
    """
       .. inheritance-diagram:: SystemPurposeSpoke
          :parts: 3
    """
    builderObjects = ["system_purpose_window"]

    mainWidgetName = "system_purpose_window"
    uiFile = "spokes/system_purpose.glade"
    help_id = "SystemPurposeSpoke"

    category = SystemCategory

    icon = "dialog-question-symbolic"
    title = CN_("GUI|Spoke", "_System Purpose")

    def __init__(self, *args):
        NormalSpoke.__init__(self, *args)

        # connect to the subscription DBUS module API
        self._subscription_module = SUBSCRIPTION.get_observer()
        self._subscription_module.connect()

        # record if the spoke has been visited by the user at least once
        self._spoke_visited = False

        # Add three invisible radio buttons so that we can show list boxes
        # with no radio buttons ticked
        self._fakeRoleButton = Gtk.RadioButton(group=None)
        self._fakeRoleButton.set_active(True)
        self._fakeSLAButton = Gtk.RadioButton(group=None)
        self._fakeSLAButton.set_active(True)
        self._fakeUsageButton = Gtk.RadioButton(group=None)
        self._fakeUsageButton.set_active(True)

    def initialize(self):
        NormalSpoke.initialize(self)
        self.initialize_start()
        # get object references from the builders
        self._role_list_box = self.builder.get_object("role_list_box")
        self._sla_list_box = self.builder.get_object("sla_list_box")
        self._usage_list_box = self.builder.get_object("usage_list_box")

        # Connect viewport scrolling with listbox focus events
        role_viewport = self.builder.get_object("role_viewport")
        sla_viewport = self.builder.get_object("sla_viewport")
        usage_viewport = self.builder.get_object("usage_viewport")
        self._role_list_box.set_focus_vadjustment(Gtk.Scrollable.get_vadjustment(role_viewport))
        self._sla_list_box.set_focus_vadjustment(Gtk.Scrollable.get_vadjustment(sla_viewport))
        self._usage_list_box.set_focus_vadjustment(Gtk.Scrollable.get_vadjustment(usage_viewport))

        # set list view states state based on valid system purpose fields and values from kickstart (if any)

        # role
        self._fill_listbox(self._role_list_box,
                           self._fakeRoleButton,
                           self.on_role_toggled,
                           self._subscription_module.proxy.Role,
                           self._subscription_module.proxy.ValidRoles)
        # SLA
        self._fill_listbox(self._sla_list_box,
                           self._fakeSLAButton,
                           self.on_sla_toggled,
                           self._subscription_module.proxy.SLA,
                           self._subscription_module.proxy.ValidSLAs)
        # usage
        self._fill_listbox(self._usage_list_box,
                           self._fakeUsageButton,
                           self.on_usage_toggled,
                           self._subscription_module.proxy.Usage,
                           self._subscription_module.proxy.ValidUsageTypes)

        # Send ready signal to main event loop
        hubQ.send_ready(self.__class__.__name__, False)

        # report that we are done
        self.initialize_done()

    def _fill_listbox(self, listbox, radio_button_group, clicked_callback, user_provided_value, valid_values):
        """Fill the given list box with data based on current value & valid values.

        Please note that it is possible that the list box will be empty if no
        list of valid values are available and the user has not supplied any value
        via kickstart or the DBUS API.

        :param listbox: the listbox to fill
        :param radio_button_group: radio button group for the list box
        :param callable clicked_callback: called when a radio button in the list box is clicked
        :param user_provided_value: the value provided by the user (if any)
        :type user_provided_value: str or None
        :param list valid_values: list of known valid values
        """
        preselected_value_list = self._handle_user_provided_value(user_provided_value,
                                                                  valid_values)

        for value, display_string, preselected in preselected_value_list:
            radio_button = Gtk.RadioButton(group=radio_button_group)
            radio_button.set_active(preselected)
            self._add_row(listbox, value, display_string, radio_button, clicked_callback)

    def _add_row(self, listbox, original_value, name, button, clicked_callback):
        """Add a row to a listbox on the system purpose screen."""
        row = Gtk.ListBoxRow()
        # attach custom original value to the row
        # - that way we can access the original value corresponding to
        #   the display value when the row is clicked
        row.original_value = original_value
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        button.set_valign(Gtk.Align.CENTER)
        button.set_margin_start(6)
        button.connect("toggled", clicked_callback, row)
        box.add(button)

        label = Gtk.Label(label='<span size="large">{}</span>'.format(escape_markup(name)),
                          use_markup=True, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR,
                          hexpand=True, xalign=0, yalign=0.5)
        label.set_margin_top(8)
        label.set_margin_bottom(8)
        box.add(label)

        row.add(box)
        listbox.insert(row, -1)

    def _handle_user_provided_value(self, user_provided_value, valid_values):
        """Handle user provided value (if any) based on list of valid values.

        There are three possible outcomes:
        - the value matches one of the valid values, so we preselect the valid value
        - the value does not match a valid value, so we append a custom value
          to the list and preselect it
        - the user provided value is not available (empty string), no matching will be done
          and no value will be preselected

        :param str user_provided_value: a value provided by user
        :param list valid_values: a list of valid values
        :returns: list of values with one value preselected
        :rtype: list of (str, str, bool) tuples in (<value>, <display string>, <is_preselected>) format
        """
        preselected_value_list = []
        value_matched = False
        for valid_value in valid_values:
            preselect = False
            if user_provided_value and not value_matched:
                if user_provided_value == valid_value:
                    preselect = True
                    value_matched = True
            preselected_value_list.append((valid_value, valid_value, preselect))
        # check if the user provided value matched a valid value
        if user_provided_value and not value_matched:
            # user provided value did not match any valid value,
            # add it as a custom value to the list and preselect it
            other_value_string = _("Other ({})").format(user_provided_value)
            preselected_value_list.append((user_provided_value, other_value_string, True))
        return preselected_value_list

    # Signal handlers
    def on_row_activated(self, listbox, row):
        """Activated if any row is clicked.

        Make sure to activate the corresponding radio button on the row that was clicked.
        """
        box = row.get_children()[0]
        button = box.get_children()[0]
        button.set_active(True)

    def on_role_toggled(self, radio, row):
        # If the radio button toggled to inactive, don't reactivate the row
        if radio.get_active():
            self._subscription_module.proxy.SetRole(row.original_value)
            row.activate()

    def on_sla_toggled(self, radio, row):
        # If the radio button toggled to inactive, don't reactivate the row
        if radio.get_active():
            self._subscription_module.proxy.SetSLA(row.original_value)
            row.activate()

    def on_usage_toggled(self, radio, row):
        # If the radio button toggled to inactive, don't reactivate the row
        if radio.get_active():
            self._subscription_module.proxy.SetUsage(row.original_value)
            row.activate()

    def refresh(self):
        # we can now consider the spoke as visited
        self._spoke_visited = True

    @property
    def system_purpose_set(self):
        """Was something in the spoke set via kickstart or by the user ?"""
        return self._subscription_module.proxy.IsSystemPurposeSet

    @property
    def status(self):
        if self.system_purpose_set:
            return _("System purpose has been set.")
        else:
            if self._spoke_visited:
                # visited but nothing selected
                return _("No purpose declared.")
            else:
                # not yet visited & nothing in kickstart
                return _("None selected.")

    @property
    def mandatory(self):
        return False

    def apply(self):
        # Send ready signal to main event loop
        hubQ.send_ready(self.__class__.__name__, False)

    @property
    def completed(self):
        # the system purpose spoke is not mandatory & even default values are considered valid
        return True

    @property
    def sensitive(self):
        # the system purpose spoke should be always accessible
        return True
