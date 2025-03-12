#
# Utility functions for network module
#
# Copyright (C) 2019 Red Hat, Inc.
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

import glob
import os
from functools import wraps

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import util
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.regexes import IBFT_CONFIGURED_DEVICE_NAME

log = get_module_logger(__name__)


# TODO move somewhwere
# We duplicate this in dracut/parse-kickstart
def get_s390_settings(devname):
    cfg = {
        'SUBCHANNELS': '',
    }

    subchannels = []
    for symlink in sorted(glob.glob("/sys/class/net/%s/device/cdev[0-9]*" % devname)):
        subchannels.append(os.path.basename(os.readlink(symlink)))
    if not subchannels:
        return cfg
    cfg['SUBCHANNELS'] = ','.join(subchannels)

    return cfg


def prefix2netmask(prefix):
    """ Convert prefix (CIDR bits) to netmask """
    _bytes = []
    for _i in range(4):
        if prefix >= 8:
            _bytes.append(255)
            prefix -= 8
        else:
            _bytes.append(256 - 2 ** (8 - prefix))
            prefix = 0
    netmask = ".".join(str(byte) for byte in _bytes)
    return netmask


def netmask2prefix(netmask):
    """ Convert netmask to prefix (CIDR bits) """
    prefix = 0

    while prefix < 33:
        if (prefix2netmask(prefix) == netmask):
            return prefix

        prefix += 1

    return prefix


def get_default_route_iface(family="inet"):
    """Get the device having default route.

    :return: the name of the network device having default route
    """
    routes = util.execWithCapture("ip", ["-f", family, "route", "show"])
    if not routes:
        log.debug("Could not get default %s route device", family)
        return None

    for line in routes.split("\n"):
        if line.startswith("default"):
            parts = line.split()
            if len(parts) >= 5 and parts[3] == "dev":
                return parts[4]
            else:
                log.debug("Could not parse default %s route device", family)
                return None

    return None


def guard_by_system_configuration(return_value):
    def wrap(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            if not conf.system.can_configure_network:
                log.debug("Network configuration is disabled on this system.")
                return return_value
            else:
                return function(*args, **kwargs)
        return wrapped
    return wrap


def is_ibft_configured_device(iface):
    return IBFT_CONFIGURED_DEVICE_NAME.match(iface)


def is_nbft_device(iface):
    return iface.startswith("nbft")
