# ostreepayload.py
# Deploy OSTree trees to target
#
# Copyright (C) 2012,2014,2021  Red Hat, Inc.
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
from dasbus.client.proxy import get_object_path

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.constants import PAYLOAD_TYPE_RPM_OSTREE, SOURCE_TYPE_FLATPAK
from pyanaconda.payload.migrated import MigratedDBusPayload
from pyanaconda.ui.lib.payload import create_source

log = get_module_logger(__name__)


class RPMOSTreePayload(MigratedDBusPayload):
    """ A RPMOSTreePayload deploys a tree (possibly with layered packages)
    onto the target system."""

    def set_from_opts(self, opts):
        """Add the flatpak source if available."""
        flatpak_source = create_source(SOURCE_TYPE_FLATPAK)

        if not flatpak_source.IsAvailable():
            log.debug("The flatpak source is not available.")
            return

        sources = self.proxy.Sources
        sources.append(get_object_path(flatpak_source))
        self.proxy.Sources = sources

    @property
    def type(self):
        """The DBus type of the payload."""
        return PAYLOAD_TYPE_RPM_OSTREE
