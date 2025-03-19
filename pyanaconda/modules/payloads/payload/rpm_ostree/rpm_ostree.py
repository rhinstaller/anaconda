#
# Kickstart module for the RPM OSTree payload.
#
# Copyright (C) 2020 Red Hat, Inc.
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
from pyanaconda.modules.payloads.constants import PayloadType, SourceType
from pyanaconda.modules.payloads.payload.payload_base import PayloadBase
from pyanaconda.modules.payloads.payload.rpm_ostree.rpm_ostree_interface import RPMOSTreeInterface
from pyanaconda.modules.payloads.source.factory import SourceFactory

log = get_module_logger(__name__)


class RPMOSTreeModule(PayloadBase):
    """The RPM OSTree payload module."""

    def for_publication(self):
        """Get the interface used to publish this source."""
        return RPMOSTreeInterface(self)

    @property
    def type(self):
        """Get type of this payload.

        :return: value of the payload.base.constants.PayloadType enum
        """
        return PayloadType.RPM_OSTREE

    @property
    def supported_source_types(self):
        """Get list of sources supported by the RPM OSTree module."""
        return [
            SourceType.RPM_OSTREE,
            SourceType.RPM_OSTREE_CONTAINER,
        ]

    def process_kickstart(self, data):
        """Process the kickstart data."""
        source_type = SourceFactory.get_rpm_ostree_type_for_kickstart(data)

        if source_type is None:
            return

        source = SourceFactory.create_source(source_type)
        source.process_kickstart(data)
        self.add_source(source)

    def setup_kickstart(self, data):
        """Setup the kickstart data."""
        for source in self.sources:
            source.setup_kickstart(data)

    def pre_install_with_tasks(self):
        """Execute preparation steps.

        :return: list of tasks
        """
        # TODO: Implement this method
        pass

    def install_with_tasks(self):
        """Install the payload.

        :return: list of tasks
        """
        # TODO: Implement this method
        pass

    def post_install_with_tasks(self):
        """Execute post installation steps.

        :return: list of tasks
        """
        # TODO: Implement this method
        pass
