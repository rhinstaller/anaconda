#
# isys.py - installer utility functions and glue for C module
#
# Matt Wilson <msw@redhat.com>
# Erik Troan <ewt@redhat.com>
# Jeremy Katz <katzj@redhat.com>
#
# Copyright 2001 - 2007 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import _isys
import string
import os
import os.path
import socket
import stat
import posix
import sys
import kudzu
import iutil
import warnings
import resource
import re
import rhpl
import struct
import block

import logging
log = logging.getLogger("anaconda")
import warnings

mountCount = {}
raidCount = {}

MIN_RAM = _isys.MIN_RAM
MIN_GUI_RAM = _isys.MIN_GUI_RAM
EARLY_SWAP_RAM = _isys.EARLY_SWAP_RAM

## Get the amount of free space available under a directory path.
# @param path The directory path to check.
# @return The amount of free space available, in 
def pathSpaceAvailable(path):
    return _isys.devSpaceFree(path)

mdadmOutput = "/tmp/mdadmout"

## An error occured when running mdadm.
class MdadmError(Exception):
    ## The constructor.
    # @param args The arguments passed to the mdadm command.
    # @param name The the name of the RAID device used in the mdadm command.
    def __init__(self, args, name=None):
        self.args = args
        self.name = name
        self.log = self.getCmdOutput()

    ## Get the output of the last mdadm command run.
    # @return The formatted output of the mdadm command which caused an error.
    def getCmdOutput(self):
        f = open(mdadmOutput, "r")
        lines = reduce(lambda x,y: x + [string.strip(y),], f.readlines(), [])
        lines = string.join(reduce(lambda x,y: x + ["   %s" % (y,)], \
                                    lines, []), "\n")
        return lines

    def __str__(self):
        s = ""
        if not self.name is None:
            s = " for device %s" % (self.name,)
        command = "mdadm " + string.join(self.args, " ")
        return "'%s' failed%s\nLog:\n%s" % (command, s, self.log)

def _mdadm(*args):
    try:
        lines = iutil.execWithCapture("mdadm", args, stderr = mdadmOutput)
        lines = string.split(lines, '\n')
        lines = reduce(lambda x,y: x + [y.strip(),], lines, [])
        return lines
    except:
        raise MdadmError, args

def _getRaidInfo(drive):
    log.info("mdadm -E %s" % (drive,))
    try:
        lines = _mdadm("-E", drive)
    except MdadmError:
        ei = sys.exc_info()
        ei[1].name = drive
        raise ei[0], ei[1], ei[2]

    info = {
            'major': "-1",
            'minor': "-1",
            'uuid' : "",
            'level': -1,
            'nrDisks': -1,
            'totalDisks': -1,
            'mdMinor': -1,
        }

    for line in lines:
        vals = string.split(string.strip(line), ' : ')
        if len(vals) != 2:
            continue
        if vals[0] == "Version":
            vals = string.split(vals[1], ".")
            info['major'] = vals[0]
            info['minor'] = vals[1]
        elif vals[0] == "UUID":
            info['uuid'] = vals[1]
        elif vals[0] == "Raid Level":
            info['level'] = int(vals[1][4:])
        elif vals[0] == "Raid Devices":
            info['nrDisks'] = int(vals[1])
        elif vals[0] == "Total Devices":
            info['totalDisks'] = int(vals[1])
        elif vals[0] == "Preferred Minor":
            info['mdMinor'] = int(vals[1])
        else:
            continue

    if info['uuid'] == "":
        raise ValueError, info

    return info

def _stopRaid(mdDevice):
    log.info("mdadm --stop %s" % (mdDevice,))
    try:
        _mdadm("--stop", mdDevice)
    except MdadmError:
        ei = sys.exc_info()
        ei[1].name = mdDevice
        raise ei[0], ei[1], ei[2]

def raidstop(mdDevice):
    log.info("stopping raid device %s" %(mdDevice,))
    if raidCount.has_key (mdDevice):
        if raidCount[mdDevice] > 1:
            raidCount[mdDevice] = raidCount[mdDevice] - 1
            return
        del raidCount[mdDevice]

    devInode = "/dev/%s" % mdDevice

    makeDevInode(mdDevice, devInode)
    try:
        _stopRaid(devInode)
    except:
        pass

def _startRaid(mdDevice, mdMinor, uuid):
    log.info("mdadm -A --uuid=%s --super-minor=%s %s" % (uuid, mdMinor, mdDevice))
    try:
        _mdadm("-A", "--uuid=%s" % (uuid,), "--super-minor=%s" % (mdMinor,), \
                mdDevice)
    except MdadmError:
        ei = sys.exc_info()
        ei[1].name = mdDevice
        raise ei[0], ei[1], ei[2]

def raidstart(mdDevice, aMember):
    log.info("starting raid device %s" %(mdDevice,))
    if raidCount.has_key(mdDevice) and raidCount[mdDevice]:
	raidCount[mdDevice] = raidCount[mdDevice] + 1
	return

    raidCount[mdDevice] = 1

    mdInode = "/dev/%s" % mdDevice
    mbrInode = "/dev/%s" % aMember

    makeDevInode(mdDevice, mdInode)
    makeDevInode(aMember, mbrInode)

    minor = os.minor(os.stat(mdInode).st_rdev)
    try:
        info = _getRaidInfo(mbrInode)
        if info.has_key('mdMinor'):
            minor = info['mdMinor']
        _startRaid(mdInode, minor, info['uuid'])
    except:
        pass

## Remove the superblock from a RAID device.
# @param device The complete path to the RAID device name to wipe.
def wipeRaidSB(device):
    try:
        fd = os.open(device, os.O_WRONLY)
    except OSError, e:
        log.warning("error wiping raid device superblock for %s: %s", device, e)
        return

    try:
        _isys.wiperaidsb(fd)
    finally:
        os.close(fd)
    return

## Get the raw superblock from a RAID device.
# @param The basename of a RAID device to check.  This device node does not
#        need to exist to begin with.
# @return A RAID superblock in its raw on-disk format.
def raidsb(mdDevice):
    makeDevInode(mdDevice, "/dev/%s" % mdDevice)
    return raidsbFromDevice("/dev/%s" % mdDevice)

## Get the superblock from a RAID device.
# @param The full path to a RAID device name to check.  This device node must
#        already exist.
# @return A tuple of the contents of the RAID superblock, or ValueError on
#         error.
def raidsbFromDevice(device):
    try:
        info = _getRaidInfo(device)
        return (info['major'], info['minor'], info['uuid'], info['level'],
                info['nrDisks'], info['totalDisks'], info['mdMinor'])
    except:
        raise ValueError

def getRaidChunkFromDevice(device):
    fd = os.open(device, os.O_RDONLY)
    rc = 64
    try:
        rc = _isys.getraidchunk(fd)
    finally:
        os.close(fd)
    return rc

## Set up an already existing device node to be used as a loopback device.
# @param device The full path to a device node to set up as a loopback device.
# @param file The file to mount as loopback on device.
# @param readOnly Should this loopback device be used read-only?
def losetup(device, file, readOnly = 0):
    if readOnly:
	mode = os.O_RDONLY
    else:
	mode = os.O_RDWR
    targ = os.open(file, mode)
    loop = os.open(device, mode)
    try:
        _isys.losetup(loop, targ, file)
    finally:
        os.close(loop)
        os.close(targ)

def lochangefd(device, file):
    loop = os.open(device, os.O_RDONLY)
    targ = os.open(file, os.O_RDONLY)
    try:
        _isys.lochangefd(loop, targ)
    finally:
        os.close(loop)
        os.close(targ)

## Disable a previously setup loopback device.
# @param device The full path to an existing loopback device node.
def unlosetup(device):
    loop = os.open(device, os.O_RDONLY)
    try:
        _isys.unlosetup(loop)
    finally:
        os.close(loop)

def ddfile(file, megs, pw = None):
    buf = '\x00' * (1024 * 256)

    fd = os.open(file, os.O_RDWR | os.O_CREAT)

    total = megs * 4	    # we write out 1/4 of a meg each time through

    if pw:
	(fn, title, text) = pw
	win = fn(title, text, total - 1)

    for n in range(total):
	os.write(fd, buf)
	if pw:
	    win.set(n)

    if pw:
	win.pop()

    os.close(fd)

## Mount a filesystem, similar to the mount system call.
# @param device The device to mount.  If bindMount is 1, this should be an
#               already mounted directory.  Otherwise, it should be a device
#               name.
# @param location The path to mount device on.
# @param fstype The filesystem type on device.  This can be disk filesystems
#               such as vfat or ext3, or pseudo filesystems such as proc or
#               selinuxfs.
# @param readOnly Should this filesystem be mounted readonly?
# @param bindMount Is this a bind mount?  (see the mount(8) man page)
# @param remount Are we mounting an already mounted filesystem?
# @return The return value from the mount system call.
def mount(device, location, fstype = "ext2", readOnly = 0, bindMount = 0, remount = 0):
    location = os.path.normpath(location)

    # We don't need to create device nodes for devices that start with '/'
    # (like '/usbdevfs') and also some special fake devices like 'proc'.
    # First try to make a device node and if that fails, assume we can
    # mount without making a device node.  If that still fails, the caller
    # will have to deal with the exception.
    # We note whether or not we created a node so we can clean up later.
    createdNode = 0
    if device and device != "none" and device[0] != "/":
	devName = "/tmp/%s" % device
	
	try:
	    makeDevInode (device, devName)
	    device = devName
	    createdNode = 1
	except SystemError:
	    pass

    if mountCount.has_key(location) and mountCount[location] > 0:
	mountCount[location] = mountCount[location] + 1
	return

    log.debug("isys.py:mount()- going to mount %s on %s" %(device, location))
    rc = _isys.mount(fstype, device, location, readOnly, bindMount, remount)

    if not rc:
	mountCount[location] = 1

    # did we create a node, if so remove
    if createdNode:
	os.unlink(device)

    return rc

## Unmount a filesystem, similar to the umount system call.
# @param what The directory to be unmounted.  This does not need to be the
#             absolute path.
# @param removeDir Should the mount point be removed after being unmounted?
# @return The return value from the umount system call.
def umount(what, removeDir = 1):
    what = os.path.normpath(what)

    if not os.path.isdir(what):
	raise ValueError, "isys.umount() can only umount by mount point"

    if mountCount.has_key(what) and mountCount[what] > 1:
	mountCount[what] = mountCount[what] - 1
	return

    rc = _isys.umount(what)

    if removeDir and os.path.isdir(what):
	os.rmdir(what)

    if not rc and mountCount.has_key(what):
	del mountCount[what]

    return rc

## Get the SMP status of the system.
# @return True if this is an SMP system, False otherwise.
def smpAvailable():
    return _isys.smpavailable()

htavailable = _isys.htavailable

## Disable swap.
# @param path The full path of the swap device to disable.
def swapoff (path):
    return _isys.swapoff (path)

## Enable swap.
# @param path The full path of the swap device to enable.
def swapon (path):
    return _isys.swapon (path)

## Load a keyboard layout for text mode installs.
# @param keymap The keyboard layout to load.  This must be one of the values
#               from rhpl.KeyboardModels.
def loadKeymap(keymap):
    return _isys.loadKeymap (keymap)

classMap = { "disk": kudzu.CLASS_HD,
             "cdrom": kudzu.CLASS_CDROM,
             "floppy": kudzu.CLASS_FLOPPY,
             "tape": kudzu.CLASS_TAPE }

cachedDrives = None

## Clear the drive dict cache.
# This method clears the drive dict cache.  If the drive state changes (by
# loading and unloading modules, attaching removable devices, etc.) then this
# function must be called before any of the *DriveDict or *DriveList functions.
# If not, those functions will return information that does not reflect the
# current machine state.
def flushDriveDict():
    global cachedDrives
    cachedDrives = None

def driveDict(klassArg):
    import parted
    global cachedDrives
    if cachedDrives is None:
        # FIXME: need to add dasd probing to kudzu
        devs = kudzu.probe(kudzu.CLASS_HD | kudzu.CLASS_CDROM | \
                           kudzu.CLASS_FLOPPY | kudzu.CLASS_TAPE,
                           kudzu.BUS_UNSPEC, kudzu.PROBE_SAFE)
        new = {}
        for dev in devs:
            device = dev.device
            if device is None: # none devices make no sense
                # kudzu is unable to determine the device for tape drives w/ 2.6
                if dev.deviceclass == classMap["tape"]:
                    tapedevs = filter(lambda d: d.startswith("st"), new.keys())
                    device = "st%d" % (len(tapedevs),)
                else:
                    continue

            if dev.deviceclass != classMap["disk"]:
                new[device] = dev
                continue
            try:
                devName = "/dev/%s" % (device,)
                makeDevInode(device, devName)

                if not mediaPresent (device):
                    new[device] = dev
                    continue

                # blacklist the device which the live image is running from
                # installing over that is almost certainly the wrong
                # thing to do.
                if os.path.exists("/dev/live") and \
                       stat.S_ISBLK(os.stat("/dev/live")[stat.ST_MODE]):
                    livetarget = os.path.realpath("/dev/live")
                    if livetarget.startswith(devName):
                        log.info("%s looks to be the live device; ignoring" % (device,))
                        continue

                if device.startswith("sd"):
                    peddev = parted.PedDevice.get(devName)
                    model = peddev.model

                    # blacklist *STMF on power5 iSeries boxes
                    if rhpl.getArch() == "ppc" and \
                            model.find("IBM *STMF KERNEL") != -1:
                        log.info("%s looks like STMF, ignoring" % (device,))
                        del peddev
                        continue

                    # blacklist PS3 flash 
                    if rhpl.getArch() == "ppc" and \
                            model.find("SCEI Flash-5") != -1:
                        log.info("%s looks like PS3 flash, ignoring" % \
                            (device,))
                        del peddev
                        continue

                    # blacklist DGC/EMC LUNs for which we have no ACL.
                    # We should be ignoring LUN_Z for all vendors, but I
                    # don't know how (if) other vendors encode this into
                    # the model info.
                    #
                    # XXX I need to work some SCC2 LUN mode page detection
                    # into libbdevid, and then this should use that instead.
                    # -- pjones
                    if str(peddev.model) == "DGC LUNZ":
                        log.info("%s looks like a LUN_Z device, ignoring" % \
                            (device,))
                        del peddev
                        continue

                    del peddev
                new[device] = dev
            except Exception, e:
                log.debug("exception checking disk blacklist on %s: %s" % \
                    (device, e))
        cachedDrives = new

    ret = {}
    for key,dev in cachedDrives.items():
        # XXX these devices should have deviceclass attributes.  Or they
        # should all be subclasses in a device tree and we should be able
        # to use isinstance on all of them.  Not both.
        if isinstance(dev, block.MultiPath) or isinstance(dev, block.RaidSet):
            if klassArg == "disk":
                ret[key] = dev
        elif dev.deviceclass == classMap[klassArg]:
            ret[key] = dev.desc
    return ret

## Get all the hard drives attached to the system.
# This method queries the drive dict cache for all hard drives.  If the cache
# is empty, this will cause all disk devices to be probed.  If the status of
# the devices has changed, flushDriveDict must be called first.
#
# @see flushDriveDict
# @see driveDict
# @return A dict of all the hard drive descriptions, keyed on device name.
def hardDriveDict():
    return driveDict("disk")

## Get all the floppy drives attached to the system.
# This method queries the drive dict cache for all floppy drives.  If the cache
# is empty, this will cause all disk devices to be probed.  If the status of
# the devices has changed, flushDriveDict must be run called first.
#
# @see flushDriveDict
# @see driveDict
# @return A dict of all the floppy drive descriptions, keyed on device name.
def floppyDriveDict():
    return driveDict("floppy")

## Get all CD/DVD drives attached to the system.
# This method queries the drive dict cache for all hard drives.  If the cache
# is empty, this will cause all disk devices to be probed.  If the status of
# the devices has changed, flushDriveDict must be called first.
#
# @see flushDriveDict
# @see driveDict
# @return A sorted list of all the CD/DVD drives, without any leading /dev/.
def cdromList():
    list = driveDict("cdrom").keys()
    list.sort()
    return list

## Get all tape drives attached to the system.
# This method queries the drive dict cache for all hard drives.  If the cache
# is empty, this will cause all disk devices to be probed.  If the status of
# the devices has changed, flushDriveDict must be called first.
#
# @see flushDriveDict
# @see driveDict
# @return A sorted list of all the tape drives, without any leading /dev/.
def tapeDriveList():
    list = driveDict("tape").keys()
    list.sort()
    return list

def getDasdPorts():
    return _isys.getDasdPorts()

def isUsableDasd(device):
    return _isys.isUsableDasd(device)

def isLdlDasd(device):
    return _isys.isLdlDasd(device)

# read /proc/dasd/devices and get a mapping between devs and the dasdnum
def getDasdDevPort():
    ret = {}
    f = open("/proc/dasd/devices", "r")
    lines = f.readlines()
    f.close()

    for line in lines:
        index = line.index("(")
        dasdnum = line[:index]

        start = line[index:].find("dasd")
        end = line[index + start:].find(":")
        dev = line[index + start:end + start + index].strip()

        ret[dev] = dasdnum

    return ret

# get active/ready state of a dasd device
# returns 0 if we're fine, 1 if not
def getDasdState(dev):
    devs = getDasdDevPort()
    if not devs.has_key(dev):
        log.warning("don't have %s in /dev/dasd/devices!" %(dev,))
        return 0

    f = open("/proc/dasd/devices", "r")
    lines = f.readlines()
    f.close()

    for line in lines:
        if not line.startswith(devs[dev]):
            continue
        # 2.6 seems to return basic
        if line.find(" basic") != -1:
            return 1
        # ... and newer 2.6 returns unformatted.  consistency!
        if line.find(" unformatted") != -1:
            return 1

    return 0

## Create a device node.
# This method creates a device node, optionally in a directory tree other than
# /dev.  Do not create device nodes in /tmp as we are trying to move away from
# using /tmp for anything other than temporary data.
#
# @param name The basename of the device node.
# @param fn An optional directory to create the new device node in.
# @return The path of the created device node.
def makeDevInode(name, fn=None):
    if fn:
        if fn.startswith("/tmp"):
            warnings.warn("device node created in /tmp", stacklevel=2)
        if os.path.exists(fn):
            return fn
        _isys.mkdevinode(name, fn)
        return fn
    path = '/dev/%s' % (name,)
    try:
        os.stat(path)
    except OSError:
        path = '/dev/%s' % (name,)
        _isys.mkdevinode(name, path)
    return path

## Calculate the broadcast address of a network.
# @param ip An IPv4 address as a string.
# @param nm A corresponding netmask as a string.
# @return A tuple of network address and broadcast address strings.
def inet_calcNetBroad (ip, nm):
    (ipaddr,) = struct.unpack('I', socket.inet_pton(socket.AF_INET, ip))
    ipaddr = socket.ntohl(ipaddr)

    (nmaddr,) = struct.unpack('I', socket.inet_pton(socket.AF_INET, nm))
    nmaddr = socket.ntohl(nmaddr)

    netaddr = ipaddr & nmaddr
    bcaddr = netaddr | (~nmaddr)

    nw = socket.inet_ntop(socket.AF_INET, struct.pack('!I', netaddr))
    bc = socket.inet_ntop(socket.AF_INET, struct.pack('!I', bcaddr))

    return (nw, bc)

def doProbeBiosDisks():
    if rhpl.getArch() not in ("i386", "x86_64"):
        return None
    return _isys.biosDiskProbe()

def doGetBiosDisk(mbrSig):
    return _isys.getbiosdisk(mbrSig)

handleSegv = _isys.handleSegv

biosdisks = {}
for d in range(80, 80 + 15):
    disk = doGetBiosDisk("%d" %(d,))
    #print "biosdisk of %s is %s" %(d, disk)
    if disk is not None:
        biosdisks[disk] = d

def compareDrives(first, second):
    if biosdisks.has_key(first) and biosdisks.has_key(second):
        one = biosdisks[first]
        two = biosdisks[second]
        if (one < two):
            return -1
        elif (one > two):
            return 1

    if first.startswith("hd"):
        type1 = 0
    elif first.startswith("sd"):
        type1 = 1
    elif first.startswith("xvd"):
        type1 = -1
    else:
        type1 = 2

    if second.startswith("hd"):
        type2 = 0
    elif second.startswith("sd"):
	type2 = 1
    elif second.startswith("xvd"):
        type2 = -1
    else:
	type2 = 2

    if (type1 < type2):
	return -1
    elif (type1 > type2):
	return 1
    else:
	len1 = len(first)
	len2 = len(second)

	if (len1 < len2):
	    return -1
	elif (len1 > len2):
	    return 1
	else:
	    if (first < second):
		return -1
	    elif (first > second):
		return 1

    return 0

def compareNetDevices(first, second):
    try:
        trimmed_first = int(first.lstrip(string.letters))
        trimmed_second = int(second.lstrip(string.letters))
    except:
        return 0

    if trimmed_first < trimmed_second:
        return -1
    elif trimmed_first > trimmed_second:
        return 1
    else:
        return 0

# called from anaconda (basically rescue mode only) to configure an interface
# when we have collected all of the configuration information from the user
def configNetDevice(device, gateway):
    devname = device.get('device')
    ipv4 = device.get('ipaddr')
    netmask = device.get('netmask')
    ipv6 = device.get('ipv6addr')
    prefix = device.get('ipv6prefix')

    return _isys.confignetdevice(devname, ipv4, netmask, ipv6, prefix, gateway)

def resetResolv():
    return _isys.resetresolv()

def setResolvRetry(count):
    return _isys.setresretry(count)

# called from anaconda to run DHCP (that's DHCP, DHCPv6, or auto neighbor
# discovery) on a particular interface
def dhcpNetDevice(device):
    # returns None on failure, "" if no nameserver is found, nameserver IP
    # otherwise
    devname = device.get('device')
    v4 = 0
    v6 = 0
    v4method = ''
    v6method = ''
    klass = device.get('dhcpclass')

    if device.get('useipv4'):
        v4 = 1
        if device.get('bootproto') == 'dhcp':
            v4method = 'dhcp'
        else:
            v4method = 'manual'

    if device.get('useipv6'):
        v6 = 1
        if device.get('ipv6_autoconf') == 'yes':
            v6method = 'auto'
        elif device.get('ipv6_autoconf') == 'no' and device.get('bootproto') == 'dhcp':
            v6method = 'dhcp'
        else:
            v6method = 'manual'

    if klass is None:
        klass = ''

    return _isys.dhcpnetdevice(devname, v4, v4method, v6, v6method, klass)

def _readXFSLabel_int(device):
    try:
        fd = os.open(device, os.O_RDONLY)
    except:
        return None

    try:
        buf = os.read(fd, 128)
        os.close(fd)
    except OSError, e:
        log.debug("error reading xfs label on %s: %s" %(device, e))
        try:
            os.close(fd)
        except:
            pass
        return None

    xfslabel = None
    if len(buf) == 128 and buf[0:4] == "XFSB":
        xfslabel = string.rstrip(buf[108:120],"\0x00")

    return xfslabel

def readXFSLabel(device, makeDevNode = 1):
    if makeDevNode:
        makeDevInode(device, "/tmp/disk")
	label = _readXFSLabel_int("/tmp/disk")
	os.unlink("/tmp/disk")
    else:
        label = _readXFSLabel_int(device)
    return label

def _readJFSLabel_int(device):
    jfslabel = None
    try:
        fd = os.open(device, os.O_RDONLY)
    except:
        return jfslabel

    try:
        os.lseek(fd, 32768, 0)
        buf = os.read(fd, 180)
        os.close(fd)
    except OSError, e:
        log.debug("error reading jfs label on %s: %s" %(device, e))
        try:
            os.close(fd)
        except:
            pass
        return jfslabel

    if (len(buf) == 180 and buf[0:4] == "JFS1"):
        jfslabel = string.rstrip(buf[152:168],"\0x00")

    return jfslabel

def readJFSLabel(device, makeDevNode = 1):
    if makeDevNode:
        makeDevInode(device, "/tmp/disk")
	label = _readJFSLabel_int("/tmp/disk")
	os.unlink("/tmp/disk")
    else:
        label = _readJFSLabel_int(device)
    return label

def _readSwapLabel_int(device):
    label = None
    try:
        fd = os.open(device, os.O_RDONLY)
    except:
        return label

    pagesize = resource.getpagesize()
    try:
        buf = os.read(fd, pagesize)
        os.close(fd)
    except OSError, e:
        log.debug("error reading swap label on %s: %s" %(device, e))
        try:
            os.close(fd)
        except:
            pass
        return label

    if ((len(buf) == pagesize) and (buf[pagesize - 10:] == "SWAPSPACE2")):
        label = string.rstrip(buf[1052:1068], "\0x00")
    return label

def readSwapLabel(device, makeDevNode = 1):
    if makeDevNode:
        makeDevInode(device, "/tmp/disk")
        label = _readSwapLabel_int("/tmp/disk")
        os.unlink("/tmp/disk")
    else:
        label = _readSwapLabel_int(device)
    return label

def readExt2Label(device, makeDevNode = 1):
    if makeDevNode:
        makeDevInode(device, "/tmp/disk")
        label = _isys.e2fslabel("/tmp/disk");
        os.unlink("/tmp/disk")
    else:
        label = _isys.e2fslabel(device)
    return label

def _readReiserFSLabel_int(device):
    label = None

    try:
        fd = os.open(device, os.O_RDONLY)
    except OSError, e:
        log.debug("error opening device %s: %s" % (device, e))
        return label

    # valid block sizes in reiserfs are 512 - 8192, powers of 2
    # we put 4096 first, since it's the default
    # reiserfs superblock occupies either the 2nd or 16th block
    for blksize in (4096, 512, 1024, 2048, 8192):
        for start in (blksize, (blksize*16)):
            try:
                os.lseek(fd, start, 0)
                # read 120 bytes to get s_magic and s_label
                buf = os.read(fd, 120)

                # see if this block is the superblock
                # this reads reiserfs_super_block_v1.s_magic as defined
                # in include/reiserfs_fs.h in the reiserfsprogs source
                m = string.rstrip(buf[52:61], "\0x00")
                if m == "ReIsErFs" or m == "ReIsEr2Fs" or m == "ReIsEr3Fs":
                    # this reads reiserfs_super_block.s_label as
                    # defined in include/reiserfs_fs.h
                    label = string.rstrip(buf[100:116], "\0x00")
                    os.close(fd)
                    return label
            except OSError, e:
                # [Error 22] probably means we're trying to read an
                # extended partition. 
                log.debug("error reading reiserfs label on %s: %s" %(device, e))

                try:
                    os.close(fd)
                except:
                    pass

                return label

    os.close(fd)
    return label

def readReiserFSLabel(device, makeDevNode = 1):
    if makeDevNode:
        makeDevInode(device, "/tmp/disk")
	label = _readReiserFSLabel_int("/tmp/disk")
        os.unlink("/tmp/disk")
    else:
        label = _readReiserFSLabel_int(device)
    return label

def readFSLabel(device, makeDevNode = 1):
    label = readExt2Label(device, makeDevNode)
    if label is None:
        label = readSwapLabel(device, makeDevNode)
    if label is None:
        label = readXFSLabel(device, makeDevNode)
    if label is None:
        label = readJFSLabel(device, makeDevNode)
    if label is None:
        label = readReiserFSLabel(device, makeDevNode)
    return label

def ext2Clobber(device, makeDevNode = 1):
    _isys.e2fsclobber(device)

def ext2IsDirty(device):
    makeDevInode(device, "/tmp/disk")
    label = _isys.e2dirty("/tmp/disk");
    os.unlink("/tmp/disk")
    return label

def ext2HasJournal(device, makeDevNode = 1):
    if makeDevNode:
        makeDevInode(device, "/tmp/disk")
        hasjournal = _isys.e2hasjournal("/tmp/disk");
        os.unlink("/tmp/disk")
    else:
        hasjournal = _isys.e2hasjournal(device);
    return hasjournal

def ejectCdrom(device, makeDevice = 1):
    if makeDevice:
        makeDevInode(device, "/tmp/cdrom")
        fd = os.open("/tmp/cdrom", os.O_RDONLY|os.O_NONBLOCK)
    else:
        fd = os.open(device, os.O_RDONLY|os.O_NONBLOCK)

    # this is a best effort
    try:
	_isys.ejectcdrom(fd)
    except SystemError, e:
        log.warning("error ejecting cdrom (%s): %s" %(device, e))
	pass

    os.close(fd)

    if makeDevice:
        os.unlink("/tmp/cdrom")

def driveUsesModule(device, modules):
    """Returns true if a drive is using a prticular module.  Only works
       for SCSI devices right now."""

    if not isinstance(modules, ().__class__) and not \
            isinstance(modules, [].__class__):
        modules = [modules]

    if device[:2] == "hd":
        return False
    rc = False
    if os.access("/tmp/scsidisks", os.R_OK):
        sdlist=open("/tmp/scsidisks", "r")
        sdlines = sdlist.readlines()
        sdlist.close()
        for l in sdlines:
            try:
                # each line has format of:  <device>  <module>
                (sddev, sdmod) = string.split(l)

                if sddev == device:
                    if sdmod in modules:
                        rc = True
                        break
            except:
                    pass
    return rc

## Check if a removable media drive (CD, USB key, etc.) has media present.
# @param device The basename of the device node.
# @return True if media is present in device, False otherwise.
def mediaPresent(device):
    try:
        fd = os.open("/dev/%s" % device, os.O_RDONLY)
    except OSError, (errno, strerror):
        # error 123 = No medium found
        if errno == 123:
            return False
        else:
            return True
    else:
        os.close(fd)
        return True

def driveIsIscsi(device):
    # ewww.  just ewww.
    if not os.path.islink("/sys/block/%s/device" %(device,)):
        return False
    target = os.readlink("/sys/block/%s/device" %(device,))
    if re.search("/platform/host[0-9]*/session[0-9]*/target[0-9]*:[0-9]*:[0-9]*/[0-9]*:[0-9]*:[0-9]*:[0-9]*", target) is not None:
        return True
    return False

def vtActivate (num):
    _isys.vtActivate (num)

def isPsudoTTY (fd):
    return _isys.isPsudoTTY (fd)

## Flush filesystem buffers.
def sync ():
    return _isys.sync ()

## Determine if a file is an ISO image or not.
# @param file The full path to a file to check.
# @return True if ISO image, False otherwise.
def isIsoImage(file):
    return _isys.isisoimage(file)

def fbinfo():
    return _isys.fbinfo()

## Determine whether a network device has a link present or not.
# @param dev The network device to check.
# @return True if there is a link, False if not or if dev is in an unknown
#         state.
def getLinkStatus(dev):
    if dev == '' or dev is None:
        return False

    # getLinkStatus returns 1 for link, 0 for no link, -1 for unknown state
    if _isys.getLinkStatus(dev) == 1:
        return True
    else:
        return False

## Get the MAC address for a network device.
# @param dev The network device to check.
# @return The MAC address for dev as a string, or None on error.
def getMacAddress(dev):
    return _isys.getMacAddress(dev)

## Determine if a network device is a wireless device.
# @param dev The network device to check.
# @return True if dev is a wireless network device, False otherwise.
def isWireless(dev):
    return _isys.isWireless(dev)

## Get the IP address for a network device.
# @param dev The network device to check.
# @see netlink_interfaces_ip2str
# @return The IPv4 address for dev, or None on error.
def getIPAddress(dev):
    return _isys.getIPAddress(dev)

## Get the correct context for a file from loaded policy.
# @param fn The filename to query.
def matchPathContext(fn):
    return _isys.matchPathContext(fn)

## Set the SELinux file context of a file
# @param fn The filename to fix.
# @param con The context to use.
# @param instroot An optional root filesystem to look under for fn.
def setFileContext(fn, con, instroot = '/'):
    if con is not None and os.access("%s/%s" % (instroot, fn), os.F_OK):
        return (_isys.setFileContext(fn, con, instroot) != 0)
    return False

## Restore the SELinux file context of a file to its default.
# @param fn The filename to fix.
# @param instroot An optional root filesystem to look under for fn.
def resetFileContext(fn, instroot = '/'):
    con = matchPathContext(fn)
    if con:
        return setFileContext(fn, con, instroot)
    return False

def prefix2netmask(prefix):
    return _isys.prefix2netmask(prefix)

def netmask2prefix (netmask):
    prefix = 0

    while prefix < 33:
        if (prefix2netmask(prefix) == netmask):
            return prefix

        prefix += 1

    return prefix

isPAE = None
def isPaeAvailable():
    global isPAE
    if isPAE is not None:
        return isPAE

    isPAE = False
    if rhpl.getArch() not in ("i386", "x86_64"):
        return isPAE

    try:
        f = open("/proc/iomem", "r")
        lines = f.readlines()
        for line in lines:
            if line[0].isspace():
                continue
            start = line.split(' ')[0].split('-')[0]
            start = long(start, 16)

            if start > 0x100000000L:
                isPAE = True
                break

        f.close()
    except:
        pass

    return isPAE

auditDaemon = _isys.auditdaemon

handleSegv = _isys.handleSegv

printObject = _isys.printObject
bind_textdomain_codeset = _isys.bind_textdomain_codeset
isVioConsole = _isys.isVioConsole
