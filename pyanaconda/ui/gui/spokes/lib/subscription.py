# Helper methods for the Subscription spoke.
#
# Copyright (C) 2020  Red Hat, Inc.
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

from collections import namedtuple

from pyanaconda.core.i18n import _

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


TextComboBoxItem = namedtuple("TextComboBoxItem", ["value", "display_string", "is_preselected"])

def handle_user_provided_value(user_provided_value, valid_values):
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
    :rtype: list of TextComboBoxItem tuples
    """
    preselected_value_list = []
    value_matched = False
    for valid_value in valid_values:
        preselect = False
        if user_provided_value and not value_matched:
            if user_provided_value == valid_value:
                preselect = True
                value_matched = True
        item = TextComboBoxItem(value=valid_value,
                                display_string=valid_value,
                                is_preselected=preselect)
        preselected_value_list.append(item)
    # check if the user provided value matched a valid value
    if user_provided_value and not value_matched:
        # user provided value did not match any valid value,
        # add it as a custom value to the list and preselect it
        other_value_string = _("Other ({})").format(user_provided_value)
        item = TextComboBoxItem(value=user_provided_value,
                                display_string=other_value_string,
                                is_preselected=True)
        preselected_value_list.append(item)
    return preselected_value_list


def fill_combobox(combobox, user_provided_value, valid_values):
    """Fill the given ComboBoxText instance with data based on current value & valid values.

    Please note that it is possible that the list box will be empty if no
    list of valid values are available and the user has not supplied any value
    via kickstart or the DBUS API.

    NOTE: Removes any existing values from the GTK ComboBoxText instance before
          filling it.

    :param combobox: the combobox to fill
    :param user_provided_value: the value provided by the user (if any)
    :type user_provided_value: str or None
    :param list valid_values: list of known valid values
    """
    preselected_value_list = handle_user_provided_value(user_provided_value,
                                                        valid_values)
    # make sure the combo box is empty
    combobox.remove_all()

    # add the "Not Specified" option as the first item
    # - otherwise the user would not be able to unselect option clicked previously
    #   or selected via kickstart
    # - set the active id to this value by default

    active_id = ""
    combobox.append("", _("Not Specified"))

    if preselected_value_list:
        for value, display_string, preselected in preselected_value_list:
            combobox.append(value, display_string)
            # the value has been preselected, set the active id accordingly
            if preselected:
                active_id = value

    # set the active id (what item should be selected in the combobox)
    combobox.set_active_id(active_id)


def add_attached_subscription_delegate(listbox, subscription, delegate_index):
    """Add delegate representing an attached subscription to the listbox.

    :param listbox: a listbox to add the delegate to
    :type listbox: GTK ListBox
    :param subscription: a subscription attached to the system
    :type: AttachedSubscription instance
    :param int delegate_index: index of the delegate in the listbox
    """
    log.debug("Subscription GUI: adding subscription to listbox: %s", subscription.name)
    # if we are not the first delegate, we should pre-pend a spacer, so that the
    # actual delegates are nicely delimited
    if delegate_index != 0:
        row = Gtk.ListBoxRow()
        row.set_name("subscriptions_listbox_row_spacer")
        row.set_margin_top(4)
        listbox.insert(row, -1)

    # construct delegate
    row = Gtk.ListBoxRow()
    # set a name so that the ListBoxRow instance can be styled via CSS
    row.set_name("subscriptions_listbox_row")

    main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    main_vbox.set_margin_top(12)
    main_vbox.set_margin_bottom(12)

    # ruff: noqa: UP032
    name_label = Gtk.Label(label='<span size="x-large">{}</span>'.format(subscription.name),
                           use_markup=True, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR,
                           hexpand=True, xalign=0, yalign=0.5)
    name_label.set_margin_start(12)
    name_label.set_margin_bottom(12)

    # create the first details grid
    details_grid_1 = Gtk.Grid()
    details_grid_1.set_column_spacing(12)
    details_grid_1.set_row_spacing(12)

    # first column
    service_level_label = Gtk.Label(label="<b>{}</b>".format(_("Service level")),
                                    use_markup=True, xalign=0)
    service_level_status_label = Gtk.Label(label=subscription.service_level)
    sku_label = Gtk.Label(label="<b>{}</b>".format(_("SKU")),
                          use_markup=True, xalign=0)
    sku_status_label = Gtk.Label(label=subscription.sku, xalign=0)
    contract_label = Gtk.Label(label="<b>{}</b>".format(_("Contract")),
                               use_markup=True, xalign=0)
    contract_status_label = Gtk.Label(label=subscription.contract, xalign=0)

    # add first column to the grid
    details_grid_1.attach(service_level_label, 0, 0, 1, 1)
    details_grid_1.attach(service_level_status_label, 1, 0, 1, 1)
    details_grid_1.attach(sku_label, 0, 1, 1, 1)
    details_grid_1.attach(sku_status_label, 1, 1, 1, 1)
    details_grid_1.attach(contract_label, 0, 2, 1, 1)
    details_grid_1.attach(contract_status_label, 1, 2, 1, 1)

    # second column
    start_date_label = Gtk.Label(label="<b>{}</b>".format(_("Start date")),
                                 use_markup=True, xalign=0)
    start_date_status_label = Gtk.Label(label=subscription.start_date, xalign=0)
    end_date_label = Gtk.Label(label="<b>{}</b>".format(_("End date")),
                               use_markup=True, xalign=0)
    end_date_status_label = Gtk.Label(label=subscription.end_date, xalign=0)
    entitlements_label = Gtk.Label(label="<b>{}</b>".format(_("Entitlements")),
                                   use_markup=True, xalign=0)
    entitlement_string = _("{} consumed").format(subscription.consumed_entitlement_count)
    entitlements_status_label = Gtk.Label(label=entitlement_string, xalign=0)

    # create the second details grid
    details_grid_2 = Gtk.Grid()
    details_grid_2.set_column_spacing(12)
    details_grid_2.set_row_spacing(12)

    # add second column to the grid
    details_grid_2.attach(start_date_label, 0, 0, 1, 1)
    details_grid_2.attach(start_date_status_label, 1, 0, 1, 1)
    details_grid_2.attach(end_date_label, 0, 1, 1, 1)
    details_grid_2.attach(end_date_status_label, 1, 1, 1, 1)
    details_grid_2.attach(entitlements_label, 0, 2, 1, 1)
    details_grid_2.attach(entitlements_status_label, 1, 2, 1, 1)

    details_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
    details_hbox.pack_start(details_grid_1, True, True, 12)
    details_hbox.pack_start(details_grid_2, True, True, 0)

    main_vbox.pack_start(name_label, True, True, 0)
    main_vbox.pack_start(details_hbox, True, True, 0)

    row.add(main_vbox)

    # append delegate to listbox
    listbox.insert(row, -1)


def populate_attached_subscriptions_listbox(listbox, attached_subscriptions):
    """Populate the attached subscriptions listbox with delegates.

    Unfortunately it does not seem to be possible to create delegate templates
    that could be reused for each data item in the listbox via Glade, so
    we need to construct them imperatively via Python GTK API.

    :param listbox: listbox to populate
    :type listbox: GTK ListBox
    :param attached_subscriptions: list of AttachedSubscription instances
    """
    log.debug("Subscription GUI: populating attached subscriptions listbox")

    # start by making sure the listbox is empty
    for child in listbox.get_children():
        listbox.remove(child)
        del(child)

    # add one delegate per attached subscription
    delegate_index = 0
    for subscription in attached_subscriptions:
        add_attached_subscription_delegate(listbox, subscription, delegate_index)
        delegate_index = delegate_index + 1

    # Make sure the delegates are actually visible after the listbox has been cleared.
    # Without show_all() nothing would be visible past first clear.
    listbox.show_all()

    log.debug("Subscription GUI: attached subscriptions listbox has been populated")
