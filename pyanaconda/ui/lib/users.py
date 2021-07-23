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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pyanaconda.flags import flags
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.i18n import N_, _
from pyanaconda.ui.lib.services import is_reconfiguration_mode
from pyanaconda.modules.common.structures.user import UserData

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


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
            user_data_list.insert(0, UserData())

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

    users_module.SetUsers(UserData.to_structure_list(user_data_list))


def check_setting_root_password_is_mandatory(users_module):
    """Check if setting the root password is mandatory.

    Root password is by default considered mandatory only
    if no admin-level user has been configured yet.

    If root_password_must_be_set is set to True in the Anaconda config file,
    root password must be set, regardless of an admin user existing or not.

    :param users_module: Users DBus module proxy
    :return: True if setting root password is mandatory, False otherwise
    :rtype: bool
    """
    if conf.ui.root_password_must_be_set:
        return not users_module.IsRootPasswordSet
    else:
        return not users_module.CheckAdminUserExists()


def check_root_password_entry_is_complete(users_module):
    """Check if root password configuration can be considered complete.

    :param users_module: Users DBus module proxy
    :return: True if root password entry is complete, False otherwise
    :rtype: bool
    """
    # Completion conditions:
    # - password is set
    # - or this is automated installation and password is locked
    # - is root_password_must_be_set is True in the config file,
    #   password must be set even for an automated installation
    return bool(
        users_module.IsRootPasswordSet or
        (users_module.IsRootAccountLocked and
         flags.automatedInstall
         and not conf.ui.root_password_must_be_set)
    )


def get_root_password_status_message(users_module):
    """Get status message for the root password spoke.

    Both GUI and TUI have the same status message, so it makes sense
    to have it defined in a single place.

    :param users_module: Users DBus module proxy
    :return: root password spoke status message
    :rtype: str
    """
    if users_module.IsRootAccountLocked:
        # reconfig mode currently allows re-enabling a locked root account if
        # user sets a new root password
        if is_reconfiguration_mode():
            return _("Disabled, set password to enable.")
        # the root_password_must_be_set config file option overrides even
        # locked account
        elif conf.ui.root_password_must_be_set:
            return _("Root password is not set")
        else:
            return _("Root account is disabled.")
    elif users_module.IsRootPasswordSet:
        return _("Root password is set")
    else:
        return _("Root password is not set")
