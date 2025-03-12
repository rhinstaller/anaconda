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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

"""
Module providing functions for getting the list of timezones, writing timezone
configuration, valid timezones recognition etc.

"""

import datetime
import time
import zoneinfo
from collections import OrderedDict
from functools import cache

import langtable
from blivet import arch

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.constants import THREAD_STORAGE
from pyanaconda.core.threads import thread_manager
from pyanaconda.core.util import execWithRedirect
from pyanaconda.flags import flags
from pyanaconda.modules.common.constants.objects import BOOTLOADER
from pyanaconda.modules.common.constants.services import STORAGE

log = get_module_logger(__name__)

# The Etc category in zoneinfo.available_timezones() includes some more,
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
        thread_manager.wait(THREAD_STORAGE)
        bootloader_proxy = STORAGE.get_proxy(BOOTLOADER)
        timezone_proxy.IsUTC = not bootloader_proxy.DetectWindows()

    cmd = "hwclock"
    args = ["--hctosys"]
    if timezone_proxy.IsUTC:
        args.append("--utc")
    else:
        args.append("--localtime")

    execWithRedirect(cmd, args)


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


@cache
def all_timezones():
    """
    Get all timezones, but with the Etc zones reduced. Cached.

    :rtype: set

    """
    etc_zones = {"Etc/" + zone for zone in ETC_ZONES}
    return zoneinfo.available_timezones() | etc_zones


def get_all_regions_and_timezones():
    """
    Get a dictionary mapping the regions to the list of their timezones.

    :rtype: dict
    """
    result = OrderedDict()

    for tz in sorted(all_timezones()):
        region, city = parse_timezone(tz)

        if region and city:
            result.setdefault(region, set())
            result[region].add(city)

    return result


def parse_timezone(timezone):
    """Parse the specified timezone.

    Return empty strings if the timezone cannot be parsed.

    :return: a region and a city
    :rtype: a tuple of strings
    """
    try:
        region, city = timezone.split("/", 1)

        if region and city:
            return region, city

    except ValueError:
        pass

    log.debug("Invalid timezone: %s", timezone)
    return "", ""


def is_valid_timezone(timezone):
    """
    Check if a given string is an existing timezone.

    :type timezone: str
    :rtype: bool

    """

    return timezone in all_timezones()


def get_timezone(timezone):
    """
    Return a tzinfo object for a given timezone name.

    :param str timezone: the timezone name
    :rtype: datetime.tzinfo
    """

    return zoneinfo.ZoneInfo(timezone)


def set_system_date_time(year=None, month=None, day=None, hour=None, minute=None,
                         tz=None):
    """Set system date and time given by the parameters.

    If some parameter is missing or None, the current system date/time field is used instead
    (i.e. the value is not changed by this function).

    :param int|None year: year to set
    :param int|None month: month to set
    :param int|None day: day to set
    :param int|None hour: hour to set
    :param int|None minute: minute to set
    :param str tz: time zone of the requested time
    """
    utc = zoneinfo.ZoneInfo(key='UTC')
    # If no timezone is set, use UTC
    if not tz:
        tz = utc
    else:
        tz = zoneinfo.ZoneInfo(key=tz)

    time.tzset()

    # get the right values
    now = datetime.datetime.now(tz)
    year = year if year is not None else now.year
    month = month if month is not None else now.month
    day = day if day is not None else now.day
    hour = hour if hour is not None else now.hour
    minute = minute if minute is not None else now.minute
    second = now.second

    set_date = datetime.datetime(year, month, day, hour, minute, second, tzinfo=tz)
    epoch_seconds = int(set_date.timestamp())

    log.info("Setting system time to %s UTC", time.asctime(time.gmtime(epoch_seconds)))
    execWithRedirect("/usr/bin/date", ['--set=@{}'.format(epoch_seconds)])
