#
# Kickstart module for date and time settings.
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
from pyanaconda.dbus.constants import MODULE_USER_NAME, MODULE_USER_PATH
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.base import KickstartModule
from pyanaconda.modules.user.user_interface import UserInterface
from pyanaconda.modules.user.kickstart import UserKickstartSpecification

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class UserModule(KickstartModule):
    """The User module."""

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

    def publish(self):
        """Publish the module."""
        DBus.publish_object(UserInterface(self), MODULE_USER_PATH)
        DBus.register_service(MODULE_USER_NAME)

    @property
    def kickstart_specification(self):
        """Return the kickstart specification."""
        return UserKickstartSpecification

    def process_kickstart(self, data):
        """Process the kickstart data."""
        log.debug("Processing kickstart data...")
        # rootpw
        self.set_root_password(data.rootpw.password, crypted=data.rootpw.isCrypted)
        self.set_root_account_locked(data.rootpw.lock)
        self.set_rootpw_seen(data.rootpw.seen)

    def generate_kickstart(self):
        """Return the kickstart string."""
        log.debug("Generating kickstart data...")
        data = self.get_kickstart_handler()
        data.rootpw.password = self._root_password
        data.rootpw.isCrypted = self._root_password_is_crypted
        data.rootpw.lock = self.root_account_locked
        data.rootpw.seen = self.rootpw_seen
        return str(data)

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
