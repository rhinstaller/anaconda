# The class for installation source validation.
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

from pyanaconda.constants import THREAD_PAYLOAD, THREAD_CHECK_SOFTWARE
from pyanaconda.flags import flags
from pyanaconda.i18n import N_, _
from pyanaconda.packaging import PackagePayload, payloadMgr
from pyanaconda.threads import threadMgr
from pyanaconda.ui.validators import BaseValidator
from pyanaconda.ui.validators.network import NetworkValidator

log = logging.getLogger("anaconda")

__all__ = ["SourceValidator"]


class SourceValidator(BaseValidator):
    """A class to check the installation source."""

    title = N_("Installation source validation")
    depends_on = [NetworkValidator]

    def __init__(self, config):
        super(SourceValidator, self).__init__(config)
        self._data = config.data
        self._payload = config.payload
        self._storage = config.storage

        # error flags
        self._payload_error = False

    def should_validate(self):
        return isinstance(self._payload, PackagePayload)

    def setup(self):
        # Setup the listener.
        payloadMgr.addListener(payloadMgr.STATE_ERROR, self._payload_error_occurred)

    def ready(self):
        return (not threadMgr.get(THREAD_PAYLOAD) and
                not threadMgr.get(THREAD_CHECK_SOFTWARE))

    def _is_valid(self):
        # If there is no base repo, return false.
        if flags.automatedInstall and self.ready() and not self._payload.baseRepo:
            return False
        # Otherwise check the source.
        return not self.errors and self.ready() and (self._data.method.method or self._payload.baseRepo)

    def _get_validation_error(self):
        return _("Error setting up software source.")

    def _payload_error_occurred(self):
        """Process the payloadMgr.STATE_ERROR event."""
        self._payload_error = True
        self._report_error(payloadMgr.error)
