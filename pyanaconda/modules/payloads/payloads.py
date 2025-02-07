#
# Kickstart module for packaging.
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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.dbus import DBus
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.base import KickstartService
from pyanaconda.modules.common.constants.services import PAYLOADS
from pyanaconda.modules.common.containers import TaskContainer
from pyanaconda.modules.payloads.constants import PayloadType
from pyanaconda.modules.payloads.installation import (
    CopyDriverDisksFilesTask,
    PrepareSystemForInstallationTask,
)
from pyanaconda.modules.payloads.kickstart import PayloadKickstartSpecification
from pyanaconda.modules.payloads.payload.factory import PayloadFactory
from pyanaconda.modules.payloads.payloads_interface import PayloadsInterface
from pyanaconda.modules.payloads.source.factory import SourceFactory

log = get_module_logger(__name__)

__all__ = ["PayloadsService"]


class PayloadsService(KickstartService):
    """The Payload service."""

    def __init__(self):
        super().__init__()
        self._created_payloads = []
        self.created_payloads_changed = Signal()

        self._active_payload = None
        self.active_payload_changed = Signal()

    def publish(self):
        """Publish the module."""
        TaskContainer.set_namespace(PAYLOADS.namespace)
        DBus.publish_object(PAYLOADS.object_path, PayloadsInterface(self))
        DBus.register_service(PAYLOADS.service_name)

    @property
    def kickstart_specification(self):
        """Return the kickstart specification."""
        return PayloadKickstartSpecification

    @property
    def created_payloads(self):
        """List of all created payload modules."""
        return self._created_payloads

    def _add_created_payload(self, module):
        """Add a created payload module."""
        self._created_payloads.append(module)
        self.created_payloads_changed.emit(module)
        log.debug("Created the payload %s.", module.type)

    @property
    def active_payload(self):
        """The active payload.

        Payloads are handling the installation process.

        FIXME: Replace this solution by something extensible for multiple payload support.
               Could it be SetPayloads() and using this list to set order of payload installation?

        There are a few types of payloads e.g.: DNF, LiveImage...

        :return: a payload module or None
        """
        return self._active_payload

    def activate_payload(self, payload):
        """Activate the payload."""
        self._active_payload = payload

        if self._active_payload.needs_flatpak_side_payload():
            side_payload = self.create_payload(PayloadType.FLATPAK)
            self._active_payload.side_payload = side_payload
            log.debug("Created side payload %s.", side_payload.type)

        self.active_payload_changed.emit()
        log.debug("Activated the payload %s.", payload.type)

    def process_kickstart(self, data):
        """Process the kickstart data."""
        # Create a new payload module.
        payload_type = PayloadFactory.get_type_for_kickstart(data)

        if payload_type:
            payload_module = self.create_payload(payload_type)
            payload_module.process_kickstart(data)
            self.activate_payload(payload_module)

    def setup_kickstart(self, data):
        """Set up the kickstart data."""
        if self.active_payload:
            self.active_payload.setup_kickstart(data)

    def create_payload(self, payload_type):
        """Create payload based on the passed type.

        :param payload_type: type of the desirable payload
        :type payload_type: value of the payload.base.constants.PayloadType enum
        """
        payload = PayloadFactory.create_payload(payload_type)
        self._add_created_payload(payload)
        return payload

    def create_source(self, source_type):
        """Create source based on the passed type.

        :param source_type: type of the desirable source
        :type source_type: value of the payload.base.constants.SourceType enum
        """
        return SourceFactory.create_source(source_type)

    def is_network_required(self):
        """Do the sources require a network?

        :return: True or False
        """
        return bool(self.active_payload) and self.active_payload.is_network_required()

    def calculate_required_space(self):
        """Calculate space required for the installation.

        Calculate required space for the main payload and the side payload if exists.

        :return: required size in bytes
        :rtype: int
        """
        if not self.active_payload:
            return 0

        main_size = self.active_payload.calculate_required_space()
        side_size = 0


        if self.active_payload.side_payload:
            side_size = self.active_payload.side_payload.calculate_required_space()

        log.debug(
            "Main payload size: %s, side payload size: %s, total: %s",
            main_size,
            side_size,
            main_size + side_size,
        )

        return main_size + side_size

    def get_kernel_version_list(self):
        """Get the kernel versions list.

        The kernel version list doesn't have to be available
        before the payload installation.

        :return: a list of kernel versions
        :raises UnavailableValueError: if the list is not available
        """
        kernel_version_list = []

        if self.active_payload:
            kernel_version_list += self.active_payload.get_kernel_version_list()

        return kernel_version_list

    def install_with_tasks(self):
        """Return a list of installation tasks.

        Concatenate tasks of the main payload together with side payload of that payload.

        :return: list of tasks
        """
        if not self.active_payload:
            return []

        tasks = [
            PrepareSystemForInstallationTask(
                sysroot=conf.target.system_root
            )
        ]

        tasks += self.active_payload.install_with_tasks()

        if self.active_payload.side_payload:
            tasks += self.active_payload.side_payload.install_with_tasks()

        return tasks

    def post_install_with_tasks(self):
        """Return a list of post-installation tasks.

        Concatenate tasks of the main payload together with side payload of that payload.

        :return: a list of tasks
        """
        if not self.active_payload:
            return []

        tasks = [
            CopyDriverDisksFilesTask(
                sysroot=conf.target.system_root
            )
        ]

        tasks += self.active_payload.post_install_with_tasks()

        if self.active_payload.side_payload:
            tasks += self.active_payload.side_payload.post_install_with_tasks()

        return tasks

    def teardown_with_tasks(self):
        """Returns teardown tasks for this module.

        Concatenate tasks of the main payload together with side payload of that payload.

        :return: a list of tasks
        """
        if not self.active_payload:
            return []

        tasks = self.active_payload.tear_down_with_tasks()

        if self.active_payload.side_payload:
            tasks += self.active_payload.side_payload.tear_down_with_tasks()

        return tasks
