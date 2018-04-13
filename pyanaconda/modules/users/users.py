#
# Kickstart module for the users module.
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
from pyanaconda.dbus import DBus
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.base import KickstartModule
from pyanaconda.modules.common.constants.services import USERS
from pyanaconda.modules.users.user import UserModule, UserInterface
from pyanaconda.modules.users.kickstart import UsersKickstartSpecification
from pyanaconda.modules.users.users_interface import UsersInterface

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class UsersModule(KickstartModule):
    """The Users module."""

    def __init__(self):
        super().__init__()
        self.rootpw_seen_changed = Signal()
        self._rootpw_seen = False

        self.root_password_is_set_changed = Signal()
        self._root_password_is_set = False
        self._root_password = ""
        self._root_password_is_crypted = False

        self.root_account_locked_changed = Signal()
        self._root_account_locked = False

        self.users_changed = Signal()
        self._users = {}

    def publish(self):
        """Publish the module."""
        DBus.publish_object(USERS.object_path, UsersInterface(self))
        DBus.register_service(USERS.service_name)

    @property
    def kickstart_specification(self):
        """Return the kickstart specification."""
        return UsersKickstartSpecification

    def process_kickstart(self, data):
        """Process the kickstart data."""
        log.debug("Processing kickstart data...")
        self.set_root_password(data.rootpw.password, crypted=data.rootpw.isCrypted)
        self.set_root_account_locked(data.rootpw.lock)
        self.set_rootpw_seen(data.rootpw.seen)

        for user_data in data.user.userList:
            user = self._create_user_instance()
            user.process_kickstart(data, user_data)
            self._publish_user_instance(user)

    def generate_kickstart(self):
        """Return the kickstart string."""
        log.debug("Generating kickstart data...")
        data = self.get_kickstart_handler()
        data.rootpw.password = self._root_password
        data.rootpw.isCrypted = self._root_password_is_crypted
        data.rootpw.lock = self.root_account_locked
        data.rootpw.seen = self.rootpw_seen

        for user in self.users.values():
            user.setup_kickstart(data)

        return str(data)

    @property
    def users(self):
        """Dictionary of users and their object paths."""
        return self._users

    @property
    def object_paths_of_users(self):
        """List of users object paths."""
        return list(self._users.keys())

    def create_user(self):
        """Create and publish a new UserModule.

        :return: an object path of the module
        """
        user_instance = self._create_user_instance()
        object_path = self._publish_user_instance(user_instance)
        return object_path

    def _create_user_instance(self):
        """Create a new instance of the user.

        :return: an instance of UserModule
        """
        user_instance = UserModule()
        log.debug("Created a new user instance.")
        return user_instance

    def _publish_user_instance(self, user_instance):
        """Publish the user instance on DBus.

        :param user_instance: an instance of UserModule
        """
        # Publish the DBus object.
        publishable = UserInterface(user_instance)
        object_path = UserInterface.get_object_path(USERS.namespace)
        DBus.publish_object(object_path, publishable)

        # Update the module.
        self.users[object_path] = user_instance
        self.users_changed.emit()

        log.debug("Published a user at '%s'.", object_path)
        return object_path

    @property
    def rootpw_seen(self):
        return self._rootpw_seen

    def set_rootpw_seen(self, rootpw_seen):
        self._rootpw_seen = rootpw_seen
        self.rootpw_seen_changed.emit()
        log.debug("Root password considered seen in kickstart: %s.", rootpw_seen)

    @property
    def root_password(self):
        """The root password.

        :returns: root password (might be crypted)
        :rtype: str
        """
        return self._root_password

    @property
    def root_password_is_crypted(self):
        """Is the root password crypted ?

        :returns: if root password is crypted
        :rtype: bool
        """
        return self._root_password_is_crypted

    def set_root_password(self, root_password, crypted):
        """Set the crypted root password.

        :param str root_password: root password
        :param bool crypted: if the root password is crypted
        """
        self._root_password = root_password
        self._root_password_is_crypted = crypted
        self.root_password_is_set_changed.emit()
        log.debug("Root password set.")

    def clear_root_password(self):
        """Clear any set root password."""
        self._root_password = ""
        self._root_password_is_crypted = False
        self.root_password_is_set_changed.emit()
        log.debug("Root password cleared.")

    @property
    def root_password_is_set(self):
        """Is the root password set ?"""
        return bool(self._root_password)

    def set_root_account_locked(self, locked):
        """Lock or unlock the root account.

        :param bool locked: True id the account should be locked, False otherwise.
        """
        self._root_account_locked = locked
        self.root_account_locked_changed.emit()
        if locked:
            log.debug("Root account has been locked.")
        else:
            log.debug("Root account has been unlocked.")

    @property
    def root_account_locked(self):
        """Is the root account locked ?"""
        return self._root_account_locked
