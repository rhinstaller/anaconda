# User interface library functions for user handling
#
# Copyright (C) 2019  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.i18n import _
from pyanaconda.flags import flags
from pyanaconda.modules.common.structures.user import UserData

log = get_module_logger(__name__)


def get_root_configuration_status(users_module):
    """Get the status of the root configuration.

    :param users_module: a DBus proxy of the Users module
    :return: a translated message
    """
    if users_module.IsRootAccountLocked:
        return _("Root account is disabled")
    elif users_module.IsRootPasswordSet:
        return _("Root password is set")
    else:
        return _("Root password is not set")


def can_modify_root_configuration(users_module):
    """Is it allowed to modify the root configuration?

    :param users_module: a DBus proxy of the Users module
    :return: True or False
    """
    # Allow changes in the interactive mode.
    if not flags.automatedInstall:
        return True

    # Does the configuration allow changes?
    if conf.ui.can_change_root:
        return True

    # Allow changes if the root account isn't
    # already configured by the kickstart file.
    if users_module.CanChangeRootPassword:
        return True

    return False


def get_user_list(users_module, add_default=False, add_if_not_empty=False):
    """Get list of users from the Users DBus module.

    If add_default is True we will add an empty UserData instance as the first element
    of the list, so that the UIs don't have to handle that themselves.

    :param users_module: Users DBus module proxy
    :param bool add_default: if True add default user as first list element
    :returns: list of users from the Users DBus module
    :rtype: list
    """

    user_data_list = UserData.from_structure_list(users_module.Users)

    if add_default:
        # we only add default user to an empty list, to add default user to
        # a populated list the add_if_not_empty option needs to be used
        if not user_data_list or add_if_not_empty:
            data = UserData()
            data.set_admin_priviledges(True)
            user_data_list.insert(0, data)

    return user_data_list


def set_user_list(users_module, user_data_list, remove_unset=False):
    """Properly set the user list in the Users DBus module.

    Internally we are working with a list of UserData instances, while the SetUsers DBus API
    requires a list of DBus structures.

    Doing the conversion each time we need to set a new user list would be troublesome so
    this method takes a list of UserData instances, converts them to list of DBus structs
    and then forwards the list to the Users module.

    Also if remove_unset is True we will drop any UserData instances from the list before
    forwarding it to the Users DBus module. Missing name is used as an indicator that the
    given user has been unset by one of the UIs and should be discarded.

    :param users_module: Users DBus module proxy
    :param list user_data_list: list of user data objects
    :param bool remove_unset: remove all users without name from the list before setting it
    :type user_data_list: list of UserData instances
    """

    if remove_unset:
        user_data_list = [user for user in user_data_list if user.name]

    users_module.Users = UserData.to_structure_list(user_data_list)
