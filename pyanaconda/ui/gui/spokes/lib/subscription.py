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
