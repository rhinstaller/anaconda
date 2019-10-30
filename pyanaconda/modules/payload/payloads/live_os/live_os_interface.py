#
# DBus interface for Live payload.
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
from pyanaconda.dbus.interface import dbus_interface, dbus_signal
from pyanaconda.dbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.modules.common.constants.objects import LIVE_OS_HANDLER
from pyanaconda.modules.common.containers import TaskContainer
from pyanaconda.modules.payload.payloads.payload_base_interface import PayloadBaseInterface


@dbus_interface(LIVE_OS_HANDLER.interface_name)
class LiveOSHandlerInterface(PayloadBaseInterface):
    """DBus interface for Live OS payload module."""

    def connect_signals(self):
        super().connect_signals()
        self.implementation.kernel_version_list_changed.connect(self.KernelVersionListChanged)

    def SetUpSourcesWithTask(self) -> ObjPath:
        """Set up installation source."""
        return TaskContainer.to_object_path(
            self.implementation.set_up_sources_with_task()
        )

    def TearDownSourcesWithTask(self) -> ObjPath:
        """Tear down installation sources."""
        return TaskContainer.to_object_path(
            self.implementation.tear_down_sources_with_task()
        )

    def PreInstallWithTask(self) -> ObjPath:
        """Prepare installation source for the installation."""
        return TaskContainer.to_object_path(
            self.implementation.pre_install_with_task()
        )

    def InstallWithTask(self) -> ObjPath:
        """Install the payload.

        * Copy the payload.
        * Create rescue images
        """
        return TaskContainer.to_object_path(
            self.implementation.install_with_task()
        )

    def PostInstallWithTasks(self) -> List[ObjPath]:
        """Do post installation tasks.

        * [NO] check installation requirements were applied (Payload)
        """
        return TaskContainer.to_object_path_list(
            self.implementation.post_install_with_tasks()
        )

    def UpdateKernelVersionList(self):
        """Update the list of kernel versions."""
        self.implementation.update_kernel_version_list()

    def GetKernelVersionList(self) -> List[Str]:
        """Get the kernel versions list."""
        return self.implementation.kernel_version_list

    @dbus_signal
    def KernelVersionListChanged(self, kernel_version_list: List[Str]):
        """Signal kernel version list change."""
        pass
