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
from pyanaconda.modules.common.constants.services import SUBSCRIPTION
from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.common.util import is_module_available

log = get_module_logger(__name__)

__all__ = ["SetUpCDNSourceTask"]


class SetUpCDNSourceTask(Task):
    """Task to set up the CDN source."""

    @property
    def name(self):
        """Name of the task."""
        return "Set up the CDN source"

    def run(self):
        """Run the task."""
        log.debug("Validating the CDN source.")

        if not is_module_available(SUBSCRIPTION):
            raise SourceSetupError(_(
                "Red Hat CDN is unavailable for this installation."
            ))

        subscription_proxy = SUBSCRIPTION.get_proxy()
        if not subscription_proxy.IsSubscriptionAttached:
            raise SourceSetupError(_(
                "To access the Red Hat CDN, a valid Red Hat subscription is required."
            ))
