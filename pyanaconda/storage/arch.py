#
# arch.py
#
# Copyright (C) 1999, 2000, 2001, 2002, 2003, 2004, 2005, 2006, 2007, 2013
# Red Hat, Inc.  All rights reserved.
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
# Author(s): Jeremy Katz <katzj@redhat.com>
#            Paul Nasrat <pnasrat@redhat.com>
#            Peter Jones <pjones@redhat.com>
#            Chris Lumens <clumens@redhat.com>
#            Will Woods <wwoods@redhat.com>
#            Dennis Gilmore <dgilmore@ausil.us>
#            David Marlin <dmarlin@redhat.com>
#

import os

from .flags import flags

## Get the SPARC machine variety type.
# @return The SPARC machine type, or 0 if not SPARC.
def getSparcMachine():
    if not isSparc():
        return 0

    machine = None


    f = open('/proc/cpuinfo', 'r')
    lines = f.readlines()
    f.close()
    for line in lines:
        if line.find('type') != -1:
            machine = line.split(':')[1].strip()
            return machine

    return None

## Get the PPC machine variety type.
# @return The PPC machine type, or 0 if not PPC.
def getPPCMachine():
    if not isPPC():
        return 0

    ppcMachine = None
    machine = None
    platform = None

    # ppc machine hash
    ppcType = { 'Mac'      : 'PMac',
                'Book'     : 'PMac',
                'CHRP IBM' : 'pSeries',
                'Pegasos'  : 'Pegasos',
                'Efika'    : 'Efika',
                'iSeries'  : 'iSeries',
                'pSeries'  : 'pSeries',
                'PReP'     : 'PReP',
                'CHRP'     : 'pSeries',
                'Amiga'    : 'APUS',
                'Gemini'   : 'Gemini',
                'Shiner'   : 'ANS',
                'BRIQ'     : 'BRIQ',
                'Teron'    : 'Teron',
                'AmigaOne' : 'Teron',
                'Maple'    : 'pSeries',
                'Cell'     : 'pSeries',
                'Momentum' : 'pSeries',
                'PS3'      : 'PS3',
                'PowerNV'  : 'pSeries'
                }

    f = open('/proc/cpuinfo', 'r')
    lines = f.readlines()
    f.close()
    for line in lines:
        if line.find('machine') != -1:
            machine = line.split(':')[1]
        elif line.find('platform') != -1:
            platform = line.split(':')[1]

    for part in (machine, platform):
        if ppcMachine is None and part is not None:
            for type in ppcType.items():
                if part.find(type[0]) != -1:
                    ppcMachine = type[1]

    if ppcMachine is None:
        log.warning("Unable to find PowerPC machine type")
    elif ppcMachine == 0:
        log.warning("Unknown PowerPC machine type: %s" %(ppcMachine,))

    return ppcMachine

## Get the powermac machine ID.
# @return The powermac machine id, or 0 if not PPC.
def getPPCMacID():
    machine = None

    if not isPPC():
        return 0
    if getPPCMachine() != "PMac":
        return 0

    f = open('/proc/cpuinfo', 'r')
    lines = f.readlines()
    f.close()
    for line in lines:
      if line.find('machine') != -1:
        machine = line.split(':')[1]
        machine = machine.strip()
        return machine

    log.warning("No Power Mac machine id")
    return 0

## Get the powermac generation.
# @return The powermac generation, or 0 if not powermac.
def getPPCMacGen():
    # XXX: should NuBus be here?
    pmacGen = ['OldWorld', 'NewWorld', 'NuBus']

    if not isPPC():
        return 0
    if getPPCMachine() != "PMac":
        return 0

    f = open('/proc/cpuinfo', 'r')
    lines = f.readlines()
    f.close()
    gen = None
    for line in lines:
      if line.find('pmac-generation') != -1:
        gen = line.split(':')[1]
        break

    if gen is None:
        log.warning("Unable to find pmac-generation")

    for _type in pmacGen:
      if _type in gen:
          return type

    log.warning("Unknown Power Mac generation: %s" %(gen,))
    return 0

## Determine if the hardware is an iBook or PowerBook
# @return 1 if so, 0 otherwise.
def getPPCMacBook():
    if not isPPC():
        return 0
    if getPPCMachine() != "PMac":
        return 0

    f = open('/proc/cpuinfo', 'r')
    buf = f.read()
    f.close()
    return 'book' in buf.lower()

## Get the ARM processor variety.
# @return The ARM processor variety type, or 0 if not ARM.
def getARMMachine():
    if not isARM():
        return 0

    if flags.arm_platform:
        return flags.arm_platform

    armMachine = os.uname()[2].rpartition('.' )[2]

    if armMachine.startswith('arm'):
        return None
    else:
        return armMachine


cell = None
## Determine if the hardware is the Cell platform.
# @return True if so, False otherwise.
def isCell():
    global cell
    if cell is not None:
        return cell

    cell = False
    if not isPPC():
        return cell

    f = open('/proc/cpuinfo', 'r')
    lines = f.readlines()
    f.close()

    for line in lines:
      if 'Cell' in line:
          cell = True

    return cell

mactel = None
## Determine if the hardware is an Intel-based Apple Mac.
# @return True if so, False otherwise.
def isMactel():
    global mactel
    if mactel is not None:
        return mactel

    if not isX86():
        mactel = False
    elif not os.path.isfile(DMI_CHASSIS_VENDOR):
        mactel = False
    else:
        buf = open(DMI_CHASSIS_VENDOR).read()
        mactel = ("apple" in buf.lower())
    return mactel

efi = None
## Determine if the hardware supports EFI.
# @return True if so, False otherwise.
def isEfi():
    global efi
    if efi is not None:
        return efi

    efi = False
    # XXX need to make sure efivars is loaded...
    if os.path.exists("/sys/firmware/efi"):
        efi = True

    return efi

# Architecture checking functions

def isX86(bits=None):
    arch = os.uname()[4]

    # x86 platforms include:
    #     i*86
    #     athlon*
    #     x86_64
    #     amd*
    #     ia32e
    if bits is None:
        if (arch.startswith('i') and arch.endswith('86')) or \
           arch.startswith('athlon') or arch.startswith('amd') or \
           arch == 'x86_64' or arch == 'ia32e':
            return True
    elif bits == 32:
        if arch.startswith('i') and arch.endswith('86'):
            return True
    elif bits == 64:
        if arch.startswith('athlon') or arch.startswith('amd') or \
           arch == 'x86_64' or arch == 'ia32e':
            return True

    return False

def isPPC(bits=None):
    arch = os.uname()[4]

    if bits is None:
        if arch == 'ppc' or arch == 'ppc64':
            return True
    elif bits == 32:
        if arch == 'ppc':
            return True
    elif bits == 64:
        if arch == 'ppc64':
            return True

    return False

def isS390():
    return os.uname()[4].startswith('s390')

def isIA64():
    return os.uname()[4] == 'ia64'

def isAlpha():
    return os.uname()[4].startswith('alpha')

def isSparc():
    return os.uname()[4].startswith('sparc')

def isARM():
    return os.uname()[4].startswith('arm')

def getArch():
    if isX86(bits=32):
        return 'i386'
    elif isX86(bits=64):
        return 'x86_64'
    elif isPPC(bits=32):
        return 'ppc'
    elif isPPC(bits=64):
        return 'ppc64'
    elif isAlpha():
        return 'alpha'
    elif isSparc():
        return 'sparc'
    elif isARM():
        return 'arm'
    else:
        return os.uname()[4]
