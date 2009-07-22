#
# isys.py - installer utility functions and glue for C module
#
# Matt Wilson <msw@redhat.com>
# Erik Troan <ewt@redhat.com>
# Jeremy Katz <katzj@redhat.com>
#
# Copyright 2001 - 2004 Red Hat, Inc.
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

mountCount = {}
raidCount = {}

MIN_RAM = _isys.MIN_RAM
MIN_GUI_RAM = _isys.MIN_GUI_RAM
EARLY_SWAP_RAM = _isys.EARLY_SWAP_RAM

def pathSpaceAvailable(path, fsystem = "ext2"):
    return _isys.devSpaceFree(path)

def spaceAvailable(device, fsystem = "ext2"):
    mount(device, "/mnt/space", fstype = fsystem)
    space = _isys.devSpaceFree("/mnt/space/.")
    umount("/mnt/space")
    return space

def fsSpaceAvailable(fsystem):
    return _isys.devSpaceFree(fsystem)

def raidstop(mdDevice):
    if raidCount.has_key (mdDevice):
        if raidCount[mdDevice] > 1:
            raidCount[mdDevice] = raidCount[mdDevice] - 1
            return
        del raidCount[mdDevice]

    devInode = "/dev/%s" % mdDevice

    makeDevInode(mdDevice, devInode)
    fd = os.open(devInode, os.O_RDONLY)

    try:
        _isys.raidstop(fd)
    except:
        pass
    os.close(fd)

def raidstart(mdDevice, aMember):
    if raidCount.has_key(mdDevice) and raidCount[mdDevice]:
	raidCount[mdDevice] = raidCount[mdDevice] + 1
	return

    raidCount[mdDevice] = 1

    mdInode = "/dev/%s" % mdDevice
    mbrInode = "/dev/%s" % aMember

    makeDevInode(mdDevice, mdInode)
    makeDevInode(aMember, mbrInode)
    fd = os.open(mdInode, os.O_RDONLY)

    try:
        _isys.raidstart(fd, mbrInode)
    except:
        pass
    os.close(fd)

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

def raidsb(mdDevice):
    makeDevInode(mdDevice, "/dev/%s" % mdDevice)
    return raidsbFromDevice("/dev/%s" % mdDevice)

def raidsbFromDevice(device):
    fd = os.open(device, os.O_RDONLY)
    rc = 0
    try:
        rc = _isys.getraidsb(fd)
    finally:
        os.close(fd)
    return rc

def getRaidChunkFromDevice(device):
    fd = os.open(device, os.O_RDONLY)
    rc = 64
    try:
        rc = _isys.getraidchunk(fd)
    finally:
        os.close(fd)
    return rc

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

def umount(what, removeDir = 1):
    what = os.path.normpath(what)

    if not os.path.isdir(what):
	raise ValueError, "isys.umount() can only umount by mount point"

    if mountCount.has_key(what) and mountCount[what] > 1:
	mountCount[what] = mountCount[what] - 1
	return

    rc = _isys.umount(what)

    if removeDir and os.path.isdir(what):
        try:
            os.rmdir(what)
        except:
            pass

    if not rc and mountCount.has_key(what):
	del mountCount[what]

    return rc

def smpAvailable():
    return _isys.smpavailable()

htavailable = _isys.htavailable

def chroot (path):
    warnings.warn("isys.chroot is deprecated.  Use os.chroot instead.",
                  DeprecationWarning, stacklevel=2)
    return os.chroot (path)

def checkBoot (path):
    return _isys.checkBoot (path)

def swapoff (path):
    return _isys.swapoff (path)

def swapon (path):
    return _isys.swapon (path)

def fbconProbe(path):
    return _isys.fbconprobe (path)

def loadFont():
    return _isys.loadFont ()

def loadKeymap(keymap):
    return _isys.loadKeymap (keymap)

classMap = { "disk": kudzu.CLASS_HD,
             "cdrom": kudzu.CLASS_CDROM,
             "floppy": kudzu.CLASS_FLOPPY,
             "tape": kudzu.CLASS_TAPE }

cachedDrives = None

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

                if not mediaPresent (device) or deviceIsReadOnly(device):
                    new[device] = dev
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

def hardDriveDict():
    return driveDict("disk")

def floppyDriveDict():
    return driveDict("floppy")

def cdromList():
    list = driveDict("cdrom").keys()
    list.sort()
    return list

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


def makeDevInode(name, fn=None):
    if fn:
        _isys.mkdevinode(name, fn)
        return fn
    path = '/dev/%s' % (name,)
    try:
        os.stat(path)
    except OSError:
        path = '/tmp/%s' % (name,)
        _isys.mkdevinode(name, path)
    return path

def makedev(major, minor):
    warnings.warn("isys.makedev is deprecated.  Use os.makedev instead.",
                  DeprecationWarning, stacklevel=2)
    return os.makedev(major, minor)

def mknod(pathname, mode, dev):
    warnings.warn("isys.mknod is deprecated.  Use os.mknod instead.",
                  DeprecationWarning, stacklevel=2)
    return os.mknod(pathname, mode, dev)

def inet_calcNetBroad (ip, nm):
    (ipaddr,) = struct.unpack('!I', socket.inet_pton(socket.AF_INET, ip))
    ipaddr = socket.ntohl(ipaddr)

    (nmaddr,) = struct.unpack('!I', socket.inet_pton(socket.AF_INET, nm))
    nmaddr = socket.ntohl(nmaddr)

    netaddr = ipaddr & nmaddr
    bcaddr = netaddr | (~nmaddr)
    nw = socket.inet_ntop(socket.AF_INET, struct.pack('I', netaddr))
    bc = socket.inet_ntop(socket.AF_INET, struct.pack('I', bcaddr))

    return (nw, bc)

def getopt(*args):
    warnings.warn("isys.getopt is deprecated.  Use optparse instead.",
                  DeprecationWarning, stacklevel=2)
    return apply(_isys.getopt, args)

def doProbeBiosDisks():
    return _isys.biosDiskProbe()

def doGetBiosDisk(mbrSig):
    if rhpl.getArch() not in ("i386", "x86_64"):    
        return None
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
    elif (first.startswith("vd") or first.startswith("xvd")):
        type1 = -1
    else:
        type1 = 2

    if second.startswith("hd"):
        type2 = 0
    elif second.startswith("sd"):
	type2 = 1
    elif (second.startswith("vd") or second.startswith("xvd")):
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
    trimmed_first = float(first.lstrip(string.letters))
    trimmed_second = float(second.lstrip(string.letters))

    if trimmed_first < trimmed_second:
        return -1
    elif trimmed_first > trimmed_second:
        return 1
    else:
        return 0


def configNetDevice(device, ip, netmask, gw):
    return _isys.confignetdevice(device, ip, netmask, gw)

def resetResolv():
    return _isys.resetresolv()

def setResolvRetry(count):
    return _isys.setresretry(count)

def dhcpNetDevice(device, dhcpclass=None):
    # returns None on failure, "" if no nameserver is found, nameserver IP
    # otherwise
    return _isys.dhcpnetdevice(device, dhcpclass)

def readXFSLabel_int(device):
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
	label = readXFSLabel_int("/tmp/disk")
	os.unlink("/tmp/disk")
    else:
        label = readXFSLabel_int(device)
    return label

def readJFSLabel_int(device):
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
	label = readJFSLabel_int("/tmp/disk")
	os.unlink("/tmp/disk")
    else:
        label = readJFSLabel_int(device)
    return label

def readSwapLabel_int(device):
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
        label = readSwapLabel_int("/tmp/disk")
        os.unlink("/tmp/disk")
    else:
        label = readSwapLabel_int(device)
    return label

def readExt2Label(device, makeDevNode = 1):
    if makeDevNode:
        makeDevInode(device, "/tmp/disk")
        label = _isys.e2fslabel("/tmp/disk")
        os.unlink("/tmp/disk")
    else:
        label = _isys.e2fslabel(device)
    return label

def _readFATLabel(device):
    label = iutil.execWithCapture("dosfslabel", [device], stderr="/dev/tty5")
    label = label.strip()
    if len(label) == 0:
        return None
    return label

def readFATLabel(device, makeDevNode = 1):
    if not rhpl.getArch() == "ia64":
        return None
    if makeDevNode:
        makeDevInode(device, "/tmp/disk")
        label = _readFATLabel("/tmp/disk")
        os.unlink("/tmp/disk")
    else:
        label = _readFATLabel(device)
    return label

def readReiserFSLabel_int(device):
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
	label = readReiserFSLabel_int("/tmp/disk")
        os.unlink("/tmp/disk")
    else:
        label = readReiserFSLabel_int(device)
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
    if label is None:
        label = readFATLabel(device, makeDevNode)
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

def deviceIsReadOnly(device):
    if not device.startswith("/dev/"):
        return _isys.deviceIsReadOnly("/dev/" + device)
    else:
        return _isys.deviceIsReadOnly(device)

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
    def convertDmToSd(minor):
        slaves = []
        slavepath = "/sys/block/dm-%d/slaves" % (minor,)
        if os.path.isdir(slavepath):
            slaves = os.listdir(slavepath)
        return slaves

    # ewww.  just ewww.
    if re.search("mapper/mpath[0-9]*",device) is not None:
        mpath = '/dev/'+ device
        if os.path.exists(mpath):
            minor = os.minor(os.stat(mpath).st_rdev)
            sddisk = convertDmToSd(minor)
            if len(sddisk) > 0:
                device = sddisk[0]

    if not os.path.islink("/sys/block/%s/device" %(device,)):
        return False
    target = os.readlink("/sys/block/%s/device" %(device,))
    if re.search("/platform/host[0-9]*/session[0-9]*/target[0-9]*:[0-9]*:[0-9]*/[0-9]*:[0-9]*:[0-9]*:[0-9]*", target) is not None:
        return True
    return False

def vtActivate (num):
    if rhpl.getArch() == "s390":
        return
    _isys.vtActivate (num)

def isPsudoTTY (fd):
    return _isys.isPsudoTTY (fd)

def sync ():
    return _isys.sync ()

def isIsoImage(file):
    return _isys.isisoimage(file)

def fbinfo():
    return _isys.fbinfo()

def cdRwList():
    if not os.access("/proc/sys/dev/cdrom/info", os.R_OK): return []

    f = open("/proc/sys/dev/cdrom/info", "r")
    lines = f.readlines()
    f.close()

    driveList = []
    finalDict = {}

    for line in lines:
	line = string.split(line, ':', 1)

	if (line and line[0] == "drive name"):
	    line = string.split(line[1])
	    # no CDROM drives
	    if not line:  return []

	    for device in line:
		if device[0:2] == 'sr':
		    device = "scd" + device[2:]
		driveList.append(device)
	elif ((line and line[0] == "Can write CD-R") or
	      (line and line[0] == "Can write CD-RW")):
	    line = string.split(line[1])
	    field = 0
	    for ability in line:
		if ability == "1":
		    finalDict[driveList[field]] = 1
		field = field + 1

    l = finalDict.keys()
    l.sort()
    return l

def ideCdRwList():
    newList = []
    for dev in cdRwList():
	if dev[0:2] == 'hd': newList.append(dev)

    return newList

def getLinkStatus(dev):
    return _isys.getLinkStatus(dev)

def getMacAddress(dev):
    return _isys.getMacAddress(dev)

def isWireless(dev):
    return _isys.isWireless(dev)

def getIPAddress(dev):
    return _isys.getIPAddress(dev)

def resetFileContext(fn, instroot = '/'):
    return _isys.resetFileContext(fn, instroot)

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

            if start >= 0x100000000L:
                isPAE = True
                break

        f.close()
    except:
        pass

    return isPAE

def getMpathModel(drive):
    info = "Unknown Multipath Device"
    fulldev = "/dev/%s" % (drive,)

    # get minor number
    if os.path.exists(fulldev):
        minor = os.minor(os.stat(fulldev).st_rdev)
    else:
        return info.strip()

    # get slaves
    slaves = []
    slavepath = "/sys/block/dm-%d/slaves" % (minor,)
    if os.path.isdir(slavepath):
        slaves = os.listdir(slavepath)
    else:
        return info.strip()

    # collect "vendor", "model" and "wwid" from a slave
    vendor = ""
    model = ""
    wwid = ""
    for slave in slaves:
        # get "vendor"
        sarg = "/sys/block/%s/device/vendor" % (slave,)
        f = open(sarg, "r")
        vendor = f.readline().strip()
        f.close()

        # get "model"
        sarg = "/sys/block/%s/device/model" % (slave,)
        f = open(sarg, "r")
        model = f.readline().strip()
        f.close()

        # get "wwid"
        sarg = "/block/%s" % (slave,)
        output = iutil.execWithCapture("scsi_id", ["-g", "-u", "-s", sarg],
                                       stderr = "/dev/tty5")
        # may be an EMC device, try special option
        if output == "":
            output = iutil.execWithCapture("scsi_id",
                                    ["-g", "-u", "-ppre-spc3-83", "-s", sarg],
                                    stderr = "/dev/tty5")
        if output != "":
            for line in output.split("\n"):
                if line == '':
                    continue
                wwid = line

        # This loop is enough only the first slave
        break

    if vendor != "" and model != "" and wwid != "":
        info = vendor + "," + model + "," + wwid

    return info.strip()

auditDaemon = _isys.auditdaemon

handleSegv = _isys.handleSegv

printObject = _isys.printObject
bind_textdomain_codeset = _isys.bind_textdomain_codeset
isVioConsole = _isys.isVioConsole

