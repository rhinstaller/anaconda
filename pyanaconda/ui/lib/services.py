#
# Copyright (C) 2021  Red Hat, Inc.
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
from pyanaconda.core.constants import SETUP_ON_BOOT_RECONFIG
from pyanaconda.modules.common.constants.services import SERVICES
from pyanaconda.modules.common.util import is_module_available

log = get_module_logger(__name__)


def is_reconfiguration_mode():
    """Check if we are running in Initial Setup reconfig mode.

    :return: True or False
    """
    if not is_module_available(SERVICES):
        return False

    services_module = SERVICES.get_proxy()
    return services_module.SetupOnBoot == SETUP_ON_BOOT_RECONFIG
