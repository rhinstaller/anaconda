#
# The RPM OSTree source module.
#
# Copyright (C) 2023 Red Hat, Inc.
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
from pyanaconda.core.i18n import _
from pyanaconda.modules.common.structures.rpm_ostree import (
    RPMOSTreeContainerConfigurationData,
)
from pyanaconda.modules.payloads.constants import SourceType
from pyanaconda.modules.payloads.source.rpm_ostree.rpm_ostree import (
    RPMOSTreeSourceModule,
)
from pyanaconda.modules.payloads.source.rpm_ostree_container.rpm_ostree_container_interface import (
    RPMOSTreeContainerSourceInterface,
)

log = get_module_logger(__name__)

__all__ = ["RPMOSTreeContainerSourceModule"]


class RPMOSTreeContainerSourceModule(RPMOSTreeSourceModule):
    """The RPM OSTree from container source module."""

    def __init__(self):
        super().__init__()
        self._configuration = RPMOSTreeContainerConfigurationData()

    @property
    def type(self):
        """Get type of this source."""
        return SourceType.RPM_OSTREE_CONTAINER

    @property
    def description(self):
        """Get description of this source."""
        return _("RPM OSTree Container")

    def for_publication(self):
        """Return a DBus representation."""
        return RPMOSTreeContainerSourceInterface(self)

    @property
    def network_required(self):
        """Does the source require a network?

        :return: True or False
        """
        # the 'registry' transport value will most probably require network settings
        # other transport ways shouldn't require that
        if self._configuration.transport == "registry":
            return True

        return False

    def process_kickstart(self, data):
        """Process the kickstart data."""
        configuration = RPMOSTreeContainerConfigurationData()

        configuration.stateroot = data.ostreecontainer.stateroot or ""
        configuration.url = data.ostreecontainer.url or ""
        configuration.remote = data.ostreecontainer.remote or ""
        configuration.transport = data.ostreecontainer.transport or ""
        configuration.signature_verification_enabled = not data.ostreecontainer.noSignatureVerification

        self.set_configuration(configuration)

    def setup_kickstart(self, data):
        """Setup the kickstart data."""
        data.ostreecontainer.stateroot = self.configuration.stateroot
        data.ostreecontainer.remote = self.configuration.remote
        data.ostreecontainer.transport = self.configuration.transport
        data.ostreecontainer.url = self.configuration.url
        data.ostreecontainer.noSignatureVerification = not self.configuration.signature_verification_enabled
        data.ostreecontainer.seen = True

    def __repr__(self):
        """Return a string representation of the source."""
        return "Source(type='{}', stateroot='{}', transport='{}', url='{}')".format(
            self.type.value,
            self.configuration.stateroot,
            self.configuration.transport,
            self.configuration.url
        )
