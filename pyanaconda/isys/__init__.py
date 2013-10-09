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
# Author(s): Matt Wilson <msw@redhat.com>
#            Erik Troan <ewt@redhat.com>
#            Jeremy Katz <katzj@redhat.com>
#

try:
    from pyanaconda import _isys
except ImportError:
    # We're running in some sort of testing mode, in which case we can fix
    # up PYTHONPATH and just do this basic import.
    import _isys

import os
import os.path
import socket
import stat
import posix
import sys
from pyanaconda import iutil
import blivet.arch
import re
import struct
import dbus
import time
import datetime

import logging
log = logging.getLogger("anaconda")

if blivet.arch.getArch() in ("ppc64"):
    MIN_RAM = 768 * 1024
    GUI_INSTALL_EXTRA_RAM = 512 * 1024
else:
    MIN_RAM = 512 * 1024
    GUI_INSTALL_EXTRA_RAM = 0

MIN_GUI_RAM = MIN_RAM + GUI_INSTALL_EXTRA_RAM
EARLY_SWAP_RAM = 896 * 1024

## Get the amount of free space available under a directory path.
# @param path The directory path to check.
# @return The amount of free space available, in 
def pathSpaceAvailable(path):
    return _isys.devSpaceFree(path)

def resetResolv():
    return _isys.resetresolv()

def modulesWithPaths():
    mods = []
    for modline in open("/proc/modules", "r"):
        modName = modline.split(" ", 1)[0]
        modInfo = iutil.execWithCapture("modinfo",
                ["-F", "filename", modName]).splitlines()
        modPaths = [ line.strip() for line in modInfo if line!="" ]
        mods.extend(modPaths)
    return mods

def isPseudoTTY (fd):
    return _isys.isPseudoTTY (fd)

## Flush filesystem buffers.
def sync ():
    return _isys.sync ()

## Determine if a file is an ISO image or not.
# @param file The full path to a file to check.
# @return True if ISO image, False otherwise.
def isIsoImage(path):
    return _isys.isisoimage(path)

isPAE = None
def isPaeAvailable():
    global isPAE
    if isPAE is not None:
        return isPAE

    isPAE = False
    if not blivet.arch.isX86():
        return isPAE

    f = open("/proc/cpuinfo", "r")
    lines = f.readlines()
    f.close()

    for line in lines:
        if line.startswith("flags") and line.find("pae") != -1:
            isPAE = True
            break

    return isPAE

def isLpaeAvailable():
    with open("/proc/cpuinfo", "r") as fobj:
        for line in fobj:
            if line.startswith("Features") and "lpae" in line.split():
                return True

    return False

def getAnacondaVersion():
    return _isys.getAnacondaVersion()

def set_system_time(secs):
    """
    Set system time to time given as a number of seconds since the Epoch.

    :param secs: a number of seconds since the Epoch to set system time to
    :type secs: int

    """

    _isys.set_system_time(secs)
    log.info("System time set to %s", time.ctime(secs))

def set_system_date_time(year=None, month=None, day=None, hour=None, minute=None,
                         second=None, utc=False):
    """
    Set system date and time given by the parameters as numbers. If some
    parameter is missing or None, the current system date/time field is used
    instead (i.e. the value is not changed by this function).

    :type year, month, ..., second: int
    :param utc: wheter the other parameters specify UTC or local time
    :type utc: bool

    """

    # get the right values
    local = 0 if utc else 1
    now = datetime.datetime.now()
    year = year or now.year
    month = month or now.month
    day = day or now.day
    hour = hour or now.hour
    minute = minute or now.minute
    second = second or now.second

    # struct fields -> year, month, day, hour, minute, second, week_day, year_day, local
    time_struct = time.struct_time((year, month, day, hour, minute, second, 0, 0, local))
    set_system_time(int(time.mktime(time_struct)))

auditDaemon = _isys.auditdaemon

handleSegv = _isys.handleSegv

printObject = _isys.printObject
bind_textdomain_codeset = _isys.bind_textdomain_codeset
isVioConsole = _isys.isVioConsole
initLog = _isys.initLog
total_memory = _isys.total_memory
