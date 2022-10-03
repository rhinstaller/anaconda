#
# isys.py - installer utility functions and glue for C module
#
# Copyright (C) 2001-2013  Red Hat, Inc.
# All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
import time
import datetime
import zoneinfo
from pyanaconda.core.util import execWithRedirect

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


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
    execWithRedirect("date", ['--set=@{}'.format(epoch_seconds)])
