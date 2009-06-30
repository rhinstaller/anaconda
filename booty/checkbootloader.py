#!/usr/bin/python
#
# Check to see whether it looks like GRUB or LILO is the boot loader
# being used on the system.
#
# Jeremy Katz <katzj@redhat.com>
# Peter Jones <pjones@redhat.com>
#
# Copyright 2001,2005 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import os
import string

from util import getDiskPart
import iutil

grubConfigFile = "/etc/grub.conf"
liloConfigFile = "/etc/lilo.conf"
yabootConfigFile = "/etc/yaboot.conf"
siloConfigFile = "/etc/silo.conf"

def getRaidDisks(raidDevice, storage, raidLevel=None, stripPart=1):
    rc = []
    if raidLevel is not None:
        try:
            raidLevel = "raid%d" % (int(raidLevel),)
        except ValueError:
            pass

    try:
        f = open("/proc/mdstat", "r")
        lines = f.readlines()
        f.close()
    except:
        return rc
    
    for line in lines:
        fields = string.split(line, ' ')
        if fields[0] == raidDevice:
            if raidLevel is not None and fields[3] != raidLevel:
                continue
            for field in fields[4:]:
                if string.find(field, "[") == -1:
                    continue
                dev = string.split(field, '[')[0]
                if len(dev) == 0:
                    continue
                if stripPart:
                    disk = getDiskPart(dev, storage)[0]
                    rc.append(disk)
                else:
                    rc.append(dev)

    return rc
            

def getBootBlock(bootDev, instRoot, storage, seekBlocks=0):
    """Get the boot block from bootDev.  Return a 512 byte string."""
    block = " " * 512
    if bootDev is None:
        return block

    # get the devices in the raid device
    if bootDev[5:7] == "md":
        bootDevs = getRaidDisks(bootDev[5:], storage)
        bootDevs.sort()
    else:
        bootDevs = [ bootDev[5:] ]

    # FIXME: this is kind of a hack
    # look at all of the devs in the raid device until we can read the
    # boot block for one of them.  should do this better at some point
    # by looking at all of the drives properly
    for dev in bootDevs:
        try:
            fd = os.open("%s/dev/%s" % (instRoot, dev), os.O_RDONLY)
            if seekBlocks > 0:
                os.lseek(fd, seekBlocks * 512, 0)
            block = os.read(fd, 512)
            os.close(fd)
            return block
        except:
            pass
    return block

# takes a line like #boot=/dev/hda and returns /dev/hda
# also handles cases like quoted versions and other nonsense
def getBootDevString(line):
    dev = string.split(line, '=')[1]
    dev = string.strip(dev)
    dev = string.replace(dev, '"', '')
    dev = string.replace(dev, "'", "")
    return dev

def getBootDevList(line):
    devs = string.split(line, '=')[1]
    rets = []
    for dev in devs:
        dev = getBootDevString("=%s" % (dev,))
        rets.append(dev)
    return string.join(rets)

def getBootloaderTypeAndBoot(instRoot, storage):
    haveGrubConf = 1
    haveLiloConf = 1
    haveYabootConf = 1
    haveSiloConf = 1
    
    bootDev = None
    
    # make sure they have the config file, otherwise we definitely can't
    # use that bootloader
    if not os.access(instRoot + grubConfigFile, os.R_OK):
        haveGrubConf = 0
    if not os.access(instRoot + liloConfigFile, os.R_OK):
        haveLiloConf = 0
    if not os.access(instRoot + yabootConfigFile, os.R_OK):
        haveYabootConf = 0
    if not os.access(instRoot + siloConfigFile, os.R_OK):
        haveSiloConf = 0

    if haveGrubConf:
        bootDev = None
        for (fn, stanza) in [ ("/etc/sysconfig/grub", "boot="),
                              (grubConfigFile, "#boot=") ]:
            try:
                f = open(instRoot + fn, "r")
            except:
                continue
        
            # the following bits of code are straight from checkbootloader.py
            lines = f.readlines()
            f.close()
            for line in lines:
                if line.startswith(stanza):
                    bootDev = getBootDevString(line)
                    break
            if bootDev is not None:
                break

        if iutil.isEfi():
            return ("GRUB", bootDev)

        if bootDev is not None:
            block = getBootBlock(bootDev, instRoot, storage)
            # XXX I don't like this, but it's what the maintainer suggested :(
            if string.find(block, "GRUB") >= 0:
                return ("GRUB", bootDev)

    if haveLiloConf:
        f = open(instRoot + liloConfigFile, "r")
        lines = f.readlines()
        for line in lines:
            if line[0:5] == "boot=":
                bootDev = getBootDevString(line)
                break

        block = getBootBlock(bootDev, instRoot, storage)
        # this at least is well-defined
        if block[6:10] == "LILO":
            return ("LILO", bootDev)

    if haveYabootConf:
        f = open(instRoot + yabootConfigFile, "r")
        lines = f.readlines()
        for line in lines:
            if line[0:5] == "boot=":
                bootDev = getBootDevList(line)

        if bootDev:
                return ("YABOOT", bootDev)

    if haveSiloConf:
        bootDev = None
        # We've never done the /etc/sysconfig/silo thing, but maybe 
        # we should start...
        for (fn, stanza) in [ ("/etc/sysconfig/silo", "boot="),
                              (grubConfigFile, "#boot=") ]:
            try:
                f = open(instRoot + fn, "r")
            except:
                continue

            lines = f.readlines()
            f.close()
            for line in lines:
                if line.startswith(stanza):
                    bootDev = getBootDevString(line)
                    break
            if bootDev is not None:
                break

        if bootDev is not None:
            # XXX SILO sucks just like grub.
            if getDiskPart(bootDev, storage)[1] != 3:
                block = getBootBlock(bootDev, instRoot, storage, 1)
                if block[24:28] == "SILO":
                    return ("SILO", bootDev)

    return (None, None)
