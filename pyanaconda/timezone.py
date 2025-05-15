#
# Copyright (C) 2012  Red Hat, Inc.
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

"""
Module providing functions for getting the list of timezones, writing timezone
configuration, valid timezones recognition etc.

"""

from collections import OrderedDict

import langtable
import pytz
from blivet import arch

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import util
from pyanaconda.core.constants import THREAD_STORAGE
from pyanaconda.flags import flags
from pyanaconda.modules.common.constants.objects import BOOTLOADER
from pyanaconda.modules.common.constants.services import STORAGE, TIMEZONE
from pyanaconda.modules.common.util import is_module_available
from pyanaconda.threading import threadMgr

log = get_module_logger(__name__)

# The following zones are not in pytz.common_timezones and
# Etc category in pytz.all_timezones includes some more,
# however confusing ones (like UCT, GMT+0, GMT-0,...)
ETC_ZONES = ['GMT+1', 'GMT+2', 'GMT+3', 'GMT+4', 'GMT+5', 'GMT+6', 'GMT+7',
             'GMT+8', 'GMT+9', 'GMT+10', 'GMT+11', 'GMT+12',
             'GMT-1', 'GMT-2', 'GMT-3', 'GMT-4', 'GMT-5', 'GMT-6', 'GMT-7',
             'GMT-8', 'GMT-9', 'GMT-10', 'GMT-11', 'GMT-12', 'GMT-13',
             'GMT-14', 'UTC', 'GMT']

NTP_PACKAGE = "chrony"
NTP_SERVICE = "chronyd"


def time_initialize(timezone_proxy):
    """
    Try to guess if RTC uses UTC time or not, set timezone.isUtc properly and
    set system time from RTC using the UTC guess.
    Guess is done by searching for bootable ntfs devices.

    :param timezone_proxy: DBus proxy of the timezone module
    """
    if arch.is_s390():
        # nothing to do on s390(x) were hwclock doesn't exist
        return

    if not timezone_proxy.IsUTC and not flags.automatedInstall:
        # if set in the kickstart, no magic needed here
        threadMgr.wait(THREAD_STORAGE)
        bootloader_proxy = STORAGE.get_proxy(BOOTLOADER)
        is_utc = not bootloader_proxy.DetectWindows()
        timezone_proxy.SetIsUTC(is_utc)

    cmd = "hwclock"
    args = ["--hctosys"]
    if timezone_proxy.IsUTC:
        args.append("--utc")
    else:
        args.append("--localtime")

    util.execWithRedirect(cmd, args)


def save_hw_clock(timezone_proxy=None):
    """
    Save system time to HW clock.

    :param timezone_proxy: DBus proxy of the timezone module

    """
    if arch.is_s390():
        return

    if not is_module_available(TIMEZONE):
        return

    if not timezone_proxy:
        timezone_proxy = TIMEZONE.get_proxy()

    cmd = "hwclock"
    args = ["--systohc"]
    if timezone_proxy.IsUTC:
        args.append("--utc")
    else:
        args.append("--local")

    util.execWithRedirect(cmd, args)


def get_preferred_timezone(territory):
    """
    Get the preferred timezone for a given territory. Note that this function
    simply returns the first timezone in the list of timezones for a given
    territory.

    :param territory: territory to get preferred timezone for
    :type territory: str
    :return: preferred timezone for the given territory or None if no found
    :rtype: str or None

    """

    timezones = langtable.list_timezones(territoryId=territory)
    if not timezones:
        return None

    return timezones[0]


def get_all_regions_and_timezones():
    """
    Get a dictionary mapping the regions to the list of their timezones.

    :rtype: dict

    """

    result = OrderedDict()

    for tz in pytz.common_timezones:
        parts = tz.split("/", 1)

        if len(parts) > 1:
            if parts[0] not in result:
                result[parts[0]] = set()
            result[parts[0]].add(parts[1])

    result["Etc"] = set(ETC_ZONES)
    return result


def is_valid_ui_timezone(timezone):
    """
    Check if a given string is a timezone specification offered by GUI.

    :type timezone: str
    :rtype: bool

    """

    etc_zones = ["Etc/" + zone for zone in ETC_ZONES]

    return timezone in pytz.common_timezones + etc_zones


def is_valid_timezone(timezone):
    """
    Check if a given string is a valid timezone specification.

    This includes also deprecated/backward timezones linked to other timezones
    in tz database (eg Japan -> Asia/Tokyo). Both the tzdata package (installed
    system) and TimezoneMap widget (installer GUI) should support them and be
    able link them to the correct timezone specification using the data from
    "backward" file.

    :type timezone: str
    :rtype: bool
    """

    return is_valid_ui_timezone(timezone) or timezone in pytz.all_timezones


def get_timezone(timezone):
    """
    Return a tzinfo object for a given timezone name.

    :param str timezone: the timezone name
    :rtype: datetime.tzinfo
    """

    return pytz.timezone(timezone)
