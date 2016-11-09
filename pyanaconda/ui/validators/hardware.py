# The class for hardware validation.
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
from pyanaconda.iutil import is_unsupported_hw
from pyanaconda.product import productName
from pyanaconda.ui.validators import BaseValidator

log = logging.getLogger("anaconda")

__all__ = ["HardwareValidator"]


class HardwareValidator(BaseValidator):
    """A class to check that the hardware is supported."""

    title = N_("Hardware validation")

    def __init__(self, config):
        super(HardwareValidator, self).__init__(config)
        self._data = config.data

    def _is_valid(self):
        # Is the hardware supported?
        # pylint: disable=no-member
        return not productName.startswith("Red Hat ") \
               or not is_unsupported_hw() \
               or self._data.unsupportedhardware.unsupported_hardware

    def _get_validation_error(self):
        return _("This hardware (or a combination thereof) is not "
                 "supported by Red Hat. For more information on "
                 "supported hardware, please refer to "
                 "http://www.redhat.com/hardware.")
