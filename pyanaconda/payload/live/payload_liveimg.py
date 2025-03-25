#
# Copyright (C) 2020  Red Hat, Inc.
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
from pyanaconda.core.constants import PAYLOAD_TYPE_LIVE_IMAGE
from pyanaconda.modules.common.structures.live_image import LiveImageConfigurationData
from pyanaconda.payload.migrated import MigratedDBusPayload

log = get_module_logger(__name__)

__all__ = ["LiveImagePayload"]


class LiveImagePayload(MigratedDBusPayload):
    """ Install using a live filesystem image from the network """

    def set_from_opts(self, opts):
        """Set the payload from the Anaconda cmdline options.

        :param opts: a namespace of options
        """
        source_proxy = self.get_source_proxy()
        source_data = LiveImageConfigurationData.from_structure(
            source_proxy.Configuration
        )

        if opts.proxy:
            source_data.proxy = opts.proxy

        if not conf.payload.verify_ssl:
            source_data.ssl_verification_enabled = conf.payload.verify_ssl

        source_proxy.Configuration = \
            LiveImageConfigurationData.to_structure(source_data)

    @property
    def type(self):
        """The DBus type of the payload."""
        return PAYLOAD_TYPE_LIVE_IMAGE
