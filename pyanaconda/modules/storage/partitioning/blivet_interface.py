#
# DBus interface for the Blivet partitioning module.
#
# Copyright (C) 2019 Red Hat, Inc.
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
import pickle

from blivetgui.communication.server import BlivetUtilsServer

from pyanaconda.dbus.interface import dbus_interface
from pyanaconda.dbus.typing import *  # pylint: disable=wildcard-import
from pyanaconda.modules.common.constants.objects import BLIVET_PARTITIONING
from pyanaconda.modules.storage.partitioning.base_interface import PartitioningInterface


@dbus_interface(BLIVET_PARTITIONING.interface_name)
class BlivetPartitioningInterface(PartitioningInterface):
    """DBus interface for the Blivet partitioning module."""

    def __init__(self, implementation):
        """Initialize the interface."""
        super().__init__(implementation)
        self._request_handler = BlivetRequestHandler()

    def SendRequest(self, data: List[Byte]) -> List[Byte]:
        """Send a request to the storage handler.

        :param data: a request data in bytes
        :return: a reply data in bytes
        """
        return self._request_handler.get_reply(bytes(data), self.implementation.storage_handler)


class BlivetRequestHandler(BlivetUtilsServer):
    """The request handler for the Blivet."""

    def __init__(self):  # pylint: disable=super-init-not-called
        self._data = None
        self._result = None

    def get_reply(self, request, utils):
        """Get a reply to a request."""
        self.blivet_utils = utils
        self._data = request

        # Handle the request.
        self.handle()

        # Return the reply.
        return self._result

    def handle(self):
        """Handle a message."""
        msg = self._recv_msg()
        unpickled_msg = pickle.loads(msg)

        if unpickled_msg[0] == "call":
            self._call_utils_method(unpickled_msg)
        elif unpickled_msg[0] == "param":
            self._get_param(unpickled_msg)
        elif unpickled_msg[0] == "method":
            self._call_method(unpickled_msg)
        elif unpickled_msg[0] == "next":
            self._get_next(unpickled_msg)
        elif unpickled_msg[0] == "key":
            self._get_key(unpickled_msg)

    def _recv_msg(self):
        """Receive a message from a client."""
        return self._data

    def _send(self, data):
        """Send a message to a client."""
        self._result = data
