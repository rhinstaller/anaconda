#
# Copyright (C) 2020  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
from dasbus.client.observer import DBusObserver, DBusObserverError

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.constants import RHSM_SERVICE_TIMEOUT
from pyanaconda.modules.common.constants.services import RHSM

log = get_module_logger(__name__)


class RHSMObserver(DBusObserver):
    """Observer of the systemd unit backed RHSM DBus service."""

    def __init__(self, startup_check_method, timeout=RHSM_SERVICE_TIMEOUT):
        """Creates a RHSM service observer.

        The observer will wait (up to a timeout) for the task starting the RHSM service
        to finish and then provide access to the corresponding RHSM DBus API.

        The waiting is only expected to happen at Anaconda startup, once the RHSM
        startup task has finished running no further waiting is expected.

        :param startup_check_method: a blocking method that waits for RHSM
                                     startup to finish up to a given timeout
                                     and then returns a boolean value corresponding
                                     to True if startup was successful or False
                                     otherwise
        :param float timeout: how long to wait for RHSM service to start in seconds
        """
        super().__init__(RHSM.message_bus, RHSM.service_name)
        self._startup_check_method = startup_check_method
        self._timeout = timeout

    def get_proxy(self, object_identifier):
        """Returns a proxy of the given RHSM object identifier.

        :param object_identifier: RHSM DBus API object identifier
        :type object_identifier: DBusObjectIdentifier instance
        :raises: DBusObserverError if the given proxy can't be returned
        """
        # first check if the DBus API seems to be up
        if not self.is_service_available and not self._startup_check_method(self._timeout):
            raise DBusObserverError("The RHSM DBus API is not available.")

        # get a proxy of a specific DBus interface
        return RHSM.get_proxy(object_identifier, interface_name=object_identifier)
