# The class for timezone validation.
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

from pyanaconda.i18n import N_, _
from pyanaconda.timezone import is_valid_timezone
from pyanaconda.ui.common import check_environment_firstboot
from pyanaconda.ui.validators import BaseValidator
from pyanaconda.ui.validators.network import NetworkValidator

log = logging.getLogger("anaconda")

__all__ = ["TimeValidator"]


class TimeValidator(BaseValidator):
    """A class to check the timezone."""

    title = N_("Timezone validation")
    depends_on = [NetworkValidator]

    @classmethod
    def should_create(cls, config):
        return check_environment_firstboot(config.data)

    def __init__(self, config):
        super(TimeValidator, self).__init__(config)
        self._data = config.data

    def _is_valid(self):
        return self._data.timezone.timezone and is_valid_timezone(self._data.timezone.timezone)

    def _get_validation_error(self):
        if not self._data.timezone.timezone:
            return _("The timezone is not set.")
        else:
            return _("The timezone is not valid.")
