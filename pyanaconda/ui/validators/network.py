# The class for network validation.
#
# Copyright (C) 2016  Red Hat, Inc.
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
# Author(s):  Vendula Poncova <vponcova@redhat.com>
#
import logging

from pyanaconda import network
from pyanaconda import nm
from pyanaconda.constants import ANACONDA_ENVIRON
from pyanaconda.flags import can_touch_runtime_system, flags
from pyanaconda.i18n import N_
from pyanaconda.ui.common import check_environment_firstboot
from pyanaconda.ui.validators import BaseValidator
from pyanaconda.ui.validators.hardware import HardwareValidator

log = logging.getLogger("anaconda")

__all__ = ["NetworkValidator"]


class NetworkValidator(BaseValidator):
    """A class for network configuration validation."""

    title = N_("Network validation")
    depends_on = [HardwareValidator]

    @classmethod
    def should_create(cls, config):
        return check_environment_firstboot(config.data)

    def __init__(self, config):
        super(NetworkValidator, self).__init__(config)
        self._data = config.data
        self._payload = config.payload
        self._default_hostname = self._data.network.hostname

    def setup(self):
        """Set up the validator."""
        if not self._data.network.seen:
            hostname = self._data.network.hostname
            self._update_network_data()
            self._update_hostname_data(self._default_hostname, hostname)

    def _is_mandatory(self):
        """Is the validation mandatory?"""
        # The network validation should be mandatory only if it is running
        # during the installation and if the installation source requires network.
        return ANACONDA_ENVIRON in flags.environs and self._payload.needsNetwork

    def _is_valid(self):
        """Is the configuration valid?

        Do an additional check if we're installing from CD/DVD, since a network
        connection should not be required in this case.
        """
        return (not can_touch_runtime_system("require network connection")
                or nm.nm_activated_devices())

    def _get_validation_error(self):
        return network.status_message()

    def _update_network_data(self):
        """Update network data."""
        self._data.network.network = []

        for i, name in enumerate(nm.nm_devices()):
            if network.is_ibft_configured_device(name):
                continue
            nd = network.ksdata_from_ifcfg(name)
            if not nd:
                continue
            if name in nm.nm_activated_devices():
                nd.activate = True
            else:
                # First network command defaults to --activate so we must
                # use --no-activate explicitly to prevent the default.
                if i == 0:
                    nd.activate = False
            self._data.network.network.append(nd)

    def _update_hostname_data(self, default_hostname, hostname):
        """Check the host name and update data.

        :param hostname: the host name
        :return: the valid host name from parameter or the default one
        """
        (valid, error) = network.sanityCheckHostname(hostname)

        if not valid:
            hostname = default_hostname
            log.error("Host name is not valid: %s", error)

        network.update_hostname_data(self._data, hostname)
        return hostname
