#
# Base object of all payload sources.
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
from abc import ABCMeta, abstractmethod

from pyanaconda.core.signal import Signal
from pyanaconda.dbus.publishable import Publishable
from pyanaconda.modules.common.base import KickstartBaseModule


class PayloadSourceBase(KickstartBaseModule, Publishable, metaclass=ABCMeta):
    """Base class for all the payload source modules.

    This object contains API shared by all the sources. Everything in this object has
    to be implemented by a source to be used.
    """

    def __init__(self):
        super().__init__()
        self._is_ready = False
        self.is_ready_changed = Signal()

    @property
    def is_ready(self):
        """This source is ready for the installation to start.

        This method will not be part of the public API. There is no need for others than the
        payload owner to see the status of the source.

        :rtype: bool
        """
        return self._is_ready

    def _set_is_ready(self, value):
        """Set if the source is ready to be used for the installation process.

        :param value: True if the source is ready
        :type value: bool
        """
        self._is_ready = value
        self.is_ready_changed.emit()

    @abstractmethod
    def set_up_with_tasks(self):
        """Prepare this payload source.

        Do everything it requires to be able to use this source for installation.

        This method will not be part of the public API. Having this private only will prevent race
        conditions and there is no real use outside of payload.

        :return: list of tasks to prepare this source
        :rtype: list[task]
        """
        pass

    @abstractmethod
    def tear_down_with_tasks(self):
        """Tear down this payload source.

        Cleanup everything done by the setup method.

        This method will not be part of the public API. Having this private only will prevent race
        conditions and there is no real use outside of payload.

        :return: list of tasks to tear down this source
        :rtype: list[task]
        """
        pass
