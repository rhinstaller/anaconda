#
# DBus interface for payload Live OS image source.
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
from dasbus.server.interface import dbus_interface
from dasbus.server.property import emits_properties_changed
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.modules.common.constants.interfaces import PAYLOAD_SOURCE_LIVE_OS
from pyanaconda.modules.common.containers import TaskContainer
from pyanaconda.modules.payloads.source.source_base_interface import (
    PayloadSourceBaseInterface,
)


@dbus_interface(PAYLOAD_SOURCE_LIVE_OS.interface_name)
class LiveOSSourceInterface(PayloadSourceBaseInterface):
    """Interface for the payload Live OS image source."""

    def connect_signals(self):
        super().connect_signals()
        self.watch_property("ImagePath", self.implementation.image_path_changed)

    @property
    def ImagePath(self) -> Str:
        """Get the path to the Live OS base image.

        This image will be used as the installation.
        """
        return self.implementation.image_path

    @ImagePath.setter
    @emits_properties_changed
    def ImagePath(self, image_path: Str):
        """Set the path to the Live OS base image.

        This image will be used as the installation source.
        """
        self.implementation.set_image_path(image_path)

    def DetectImageWithTask(self) -> ObjPath:
        """Detect a Live OS image with a task.

        Detect an image and set the image path of the source.

        :return: an path to the DBus task
        """
        return TaskContainer.to_object_path(
            self.implementation.detect_image_with_task()
        )
