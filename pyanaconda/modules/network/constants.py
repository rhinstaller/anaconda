#
# Private constants for the network module.
#
# Copyright (C) 2018 Red Hat, Inc.
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
from enum import Enum, unique

from pyanaconda.core.constants import (
    FIREWALL_DEFAULT,
    FIREWALL_DISABLED,
    FIREWALL_ENABLED,
    FIREWALL_USE_SYSTEM_DEFAULTS,
)

NM_CONNECTION_UUID_LENGTH = 36
CONNECTION_ADDING_TIMEOUT = 5


@unique
class FirewallMode(Enum):
    """Firewall mode for the installed system."""

    DEFAULT = FIREWALL_DEFAULT
    DISABLED = FIREWALL_DISABLED
    ENABLED = FIREWALL_ENABLED
    USE_SYSTEM_DEFAULTS = FIREWALL_USE_SYSTEM_DEFAULTS


NM_CONNECTION_TYPE_WIFI = '802-11-wireless'
NM_CONNECTION_TYPE_ETHERNET = '802-3-ethernet'
NM_CONNECTION_TYPE_VLAN = 'vlan'
NM_CONNECTION_TYPE_BOND = 'bond'
NM_CONNECTION_TYPE_TEAM = 'team'
NM_CONNECTION_TYPE_BRIDGE = 'bridge'
NM_CONNECTION_TYPE_INFINIBAND = 'infiniband'
