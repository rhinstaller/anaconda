#
# User module.
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
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.base import KickstartBaseModule

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class UserModule(KickstartBaseModule):
    """The user module."""

    def __init__(self):
        super().__init__()

        self.name_changed = Signal()
        self._name = ""

    # pylint: disable=arguments-differ
    def process_kickstart(self, data, user_data=None):
        """Process the kickstart data."""
        if not user_data:
            return

        self.set_name(user_data.name)

    def setup_kickstart(self, data):
        """Setup the kickstart data."""
        user_data = data.UserData()
        user_data.name = self.name

        data.user.userList.append(user_data)
        return data

    @property
    def name(self):
        """Name of the user."""
        return self._name

    def set_name(self, name):
        """Set a name of the user.

        :param name: a name
        """
        self._name = name
        self.name_changed.emit()
        log.debug("User name is set to '%s'.", name)
