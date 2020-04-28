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
import os.path
from abc import ABC, ABCMeta, abstractmethod

from dasbus.server.publishable import Publishable

from pyanaconda.modules.common.base import KickstartBaseModule
from pyanaconda.modules.payloads.constants import SourceState
from pyanaconda.modules.payloads.source.mount_tasks import TearDownMountTask
from pyanaconda.modules.payloads.source.utils import MountPointGenerator
from pyanaconda.anaconda_loggers import get_module_logger

log = get_module_logger(__name__)


class PayloadSourceBase(KickstartBaseModule, Publishable, metaclass=ABCMeta):
    """Base class for all the payload source modules.

    This object contains API shared by all the sources. Everything in this object has
    to be implemented by a source to be used.
    """

    def __repr__(self):
        """Print sources in a nicer way."""
        # FIXME: Every source should implement it's repr and this should be removed.
        # See https://docs.python.org/3/library/functions.html#repr for reasons why.
        return "Source({})".format(self.type.value)

    @property
    @abstractmethod
    def type(self):
        """Get type of this source object.

        :return: type of this source
        :type: value of payload.base.constants.SourceType
        """
        pass

    @abstractmethod
    def get_state(self):
        """Get state of this source.

        This method will not be part of the public API. There is no need for others than the
        payload owner to see the status of the source. It is also not really useful, in time when
        user gets the ready state the state could be different because of the DBus parallelism.
        In general we should not share state.

        :return: one of the supported state of SourceState enum
        :rtype: pyanaconda.modules.payloads.constants.SourceState enum value
        """
        pass

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


class MountingSourceBase(PayloadSourceBase, ABC):
    """Base class for sources that use mounting.

    Implements some common functionality, most notably generation of mount point paths.
    """
    # pylint: disable=abstract-method

    def __init__(self):
        super().__init__()
        self._mount_point = MountPointGenerator.generate_mount_point(self.type.value.lower())

    def get_state(self):
        """This source is ready for the installation to start.

        :return: one of the supported state of SourceState enum
        :rtype: pyanaconda.modules.payloads.constants.SourceState enum value
        """
        res = os.path.ismount(self._mount_point)
        return SourceState.from_bool(res)

    @property
    def mount_point(self):
        """Where the source will be mounted.

        :return: path to the mount point
        :rtype: str
        """
        return self._mount_point

    def tear_down_with_tasks(self):
        """Tear down the installation source.

        :return: list of tasks required for the source clean-up
        :rtype: [TearDownMountTask]
        """
        task = TearDownMountTask(self._mount_point)
        return [task]
