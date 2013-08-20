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
# Red Hat Author(s): Vratislav Podzimek <vpodzime@redhat.com>
#

"""
Module providing functions for getting the list of timezones, writing timezone
configuration, valid timezones recognition etc.

"""

import os
import pytz
import langtable
from collections import OrderedDict

from pyanaconda import iutil
from pyanaconda.constants import THREAD_STORAGE
from pyanaconda.flags import flags
from pyanaconda.threads import threadMgr
from blivet import arch

import logging
log = logging.getLogger("anaconda")

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

class TimezoneConfigError(Exception):
    """Exception class for timezone configuration related problems"""
    pass

def time_initialize(timezone, storage, bootloader):
    """
    Try to guess if RTC uses UTC time or not, set timezone.isUtc properly and
    set system time from RTC using the UTC guess.
    Guess is done by searching for bootable ntfs devices.

    :param timezone: ksdata.timezone object
    :param storage: blivet.Blivet instance
    :param bootloader: bootloader.Bootloader instance

    """

    if arch.isS390():
        # nothing to do on s390 where hwclock doesn't exist
        return

    if not timezone.isUtc and not flags.automatedInstall:
        # if set in the kickstart, no magic needed here
        threadMgr.wait(THREAD_STORAGE)
        ntfs_devs = filter(lambda dev: dev.format.name == "ntfs",
                           storage.devices)

        timezone.isUtc = not bootloader.has_windows(ntfs_devs)

    cmd = "hwclock"
    args = ["--hctosys"]
    if timezone.isUtc:
        args.append("--utc")
    else:
        args.append("--localtime")

    iutil.execWithRedirect(cmd, args)

def write_timezone_config(timezone, root):
    """
    Write timezone configuration for the system specified by root.

    :param timezone: ksdata.timezone object
    :param root: path to the root
    :raise: TimezoneConfigError

    """

    # we want to create a relative symlink
    tz_file = "/usr/share/zoneinfo/" + timezone.timezone
    rooted_tz_file = os.path.normpath(root + tz_file)
    relative_path = os.path.normpath("../" + tz_file)
    link_path = os.path.normpath(root + "/etc/localtime")

    if not os.access(rooted_tz_file, os.R_OK):
        log.error("Timezone to be linked (%s) doesn't exist", rooted_tz_file)
    else:
        try:
            # os.symlink fails if link_path exists, so try to remove it first
            os.remove(link_path)
        except OSError:
            pass

        try:
            os.symlink(relative_path, link_path)
        except OSError as oserr:
            log.error("Error when symlinking timezone (from %s): %s",
                      rooted_tz_file, oserr.strerror)

    try:
        fobj = open(os.path.normpath(root + "/etc/adjtime"), "r")
        lines = fobj.readlines()
        fobj.close()
    except IOError:
        lines = [ "0.0 0 0.0\n", "0\n" ]

    try:
        with open(os.path.normpath(root + "/etc/adjtime"), "w") as fobj:
            fobj.write(lines[0])
            fobj.write(lines[1])
            if timezone.isUtc:
                fobj.write("UTC\n")
            else:
                fobj.write("LOCAL\n")
    except IOError as ioerr:
        msg = "Error while writing /etc/adjtime file: %s" % ioerr.strerror
        raise TimezoneConfigError(msg)

def save_hw_clock(timezone):
    """
    Save system time to HW clock.

    :param timezone: ksdata.timezone object

    """

    if arch.isS390():
        return

    cmd = "hwclock"
    args = ["--systohc"]
    if timezone.isUtc:
        args.append("--utc")
    else:
        args.append("--local")

    iutil.execWithRedirect(cmd, args)


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

def is_valid_timezone(timezone):
    """
    Check if a given string is an existing timezone.

    :type timezone: str
    :rtype: bool

    """

    etc_zones = ["Etc/" + zone for zone in ETC_ZONES]

    return timezone in pytz.common_timezones + etc_zones

