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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from abc import ABCMeta

from dasbus.server.interface import dbus_interface
from dasbus.typing import *  # pylint: disable=wildcard-import
from pyanaconda.modules.common.base.base_template import ModuleInterfaceTemplate
from pyanaconda.modules.common.constants.interfaces import PAYLOAD_SOURCE


@dbus_interface(PAYLOAD_SOURCE.interface_name)
class PayloadSourceBaseInterface(ModuleInterfaceTemplate, metaclass=ABCMeta):
    """Base class for all the payload source module interfaces.

    This object contains API shared by all the sources. Everything in this object has
    to be implemented by a source to be used.
    """

    @property
    def Type(self) -> Str:
        """Get the type of this source.

        Possible values are:
         - LIVE_OS_IMAGE
        """
        return self.implementation.type.value

    @property
    def Description(self) -> Str:
        """Get a description of this source."""
        return self.implementation.description
