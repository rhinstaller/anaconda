import kudzu
import _isys
import string
import os
import os.path

mountCount = {}

def spaceAvailable(device, fsystem = "ext2"):
    mount(device, "/mnt/space", fstype = fsystem)
    space = _isys.devSpaceFree("/mnt/space/.")
    umount("/mnt/space")
    return space

def raidstop(mdDevice):
    makeDevInode(mdDevice, "/tmp/md")
    fd = os.open("/tmp/md", os.O_RDONLY)
    os.remove("/tmp/md")
    _isys.raidstop(fd)
    os.close(fd)

def raidstart(mdDevice, aMember):
    makeDevInode(mdDevice, "/tmp/md")
    makeDevInode(aMember, "/tmp/member")
    fd = os.open("/tmp/md", os.O_RDONLY)
    os.remove("/tmp/md")
    _isys.raidstart(fd, "/tmp/member")
    os.close(fd)
    os.remove("/tmp/member")

def raidsb(mdDevice):
    makeDevInode(mdDevice, "/tmp/md")
    fd = os.open("/tmp/md", os.O_RDONLY)
    rc = _isys.getraidsb(fd)
    os.close(fd)
    return rc

def losetup(device, file, readonly = 0):
    if readonly:
	mode = os.O_RDONLY
    else:
	mode = os.O_RDWR
    targ = os.open(file, mode)
    loop = os.open(device, mode)
    _isys.losetup(loop, targ, file)
    os.close(loop)
    os.close(targ)

def lochangefd(device, file):
    loop = os.open(device, os.O_RDONLY)
    targ = os.open(file, os.O_RDONLY)
    _isys.lochangefd(loop, targ)
    os.close(loop)
    os.close(targ)

def unlosetup(device):
    loop = os.open(device, os.O_RDONLY)
    _isys.unlosetup(loop)
    os.close(loop)

def ddfile(file, megs, pw = None):
    fd = os.open("/dev/zero", os.O_RDONLY);
    buf = os.read(fd, 1024 * 256)
    os.close(fd)

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

def mount(device, location, fstype = "ext2", readOnly = 0):
    location = os.path.normpath(location)

    if device != "/proc":
	devName = "/tmp/%s" % device
	makeDevInode(device, devName)
	device = devName

    if mountCount.has_key(location) and mountCount[location] > 0:
	mountCount[location] = mountCount[location] + 1
	return

    rc = _isys.mount(fstype, device, location, readOnly)

    if not rc:
	mountCount[location] = 1

    if device != "/proc":
	os.unlink(device)

    return rc

def umount(what, removeDir = 1):
    what = os.path.normpath(what)

    if not os.path.isdir(what):
	raise ValueError, "isys.umount() can only umount by mount point"

    if mountCount.has_key(what) and mountCount[what] > 1:
	mountCount[what] = mountCount - 1
	return

    rc = _isys.umount(what)

    if removeDir and os.path.isdir(what):
	os.rmdir(what)

    if not rc and mountCount.has_key(what):
	del mountCount[what]

    return rc

def smpAvailable():
    return _isys.smpavailable()

def chroot (path):
    return _isys.chroot (path)

def checkBoot (path):
    return _isys.checkBoot (path)

def swapoff (path):
    return _isys.swapoff (path)

def swapon (path):
    return _isys.swapon (path)

def fbconProbe(path):
    return _isys.fbconprobe (path)

def loadFont(font):
    return _isys.loadFont (font)

def loadKeymap(keymap):
    return _isys.loadKeymap (keymap)

def probePciDevices():
    # probes all probeable buses and returns a list of 
    # ( driver, major, minor, description, args ) tuples, where args is a
    # list of (argName, argDescrip) tuples
    devices = _isys.pciprobe()
    if (not devices): return None

    result = []
    for dev in devices:
	info = _isys.findmoduleinfo(dev)
	if not info:
	    raise KeyError, "module " + dev + " is not in the module list"
	result.append(info)

    return result

def driveDict(klassArg):
    p = _isys.ProbedList()
    p.updateIde()
    p.updateScsi()

    dict = {}
    for (klass, dev, descr) in p:
	if (klass == klassArg):
	    dict[dev] = descr
    return dict

def hardDriveDict():
    return driveDict("disk")

def floppyDriveDict():
    return driveDict("floppy")

def cdromList():
    list = driveDict("cdrom").keys()
    list.sort()
    return list

def moduleListByType(type):
    return _isys.modulelist(type)

def makeDevInode(name, fn):
    return _isys.mkdevinode(name, fn)

def inet_ntoa (addr):
    return "%d.%d.%d.%d" % ((addr >> 24) & 0x000000ff,
                            (addr >> 16) & 0x000000ff,
                            (addr >> 8) & 0x000000ff,
                            addr & 0x000000ff)
    
def inet_aton (addr):
    quad = string.splitfields (addr, ".")
    try: 
        rc = ((string.atoi (quad[0]) << 24) +
              (string.atoi (quad[1]) << 16) +
              (string.atoi (quad[2]) << 8) +
              string.atoi (quad[3]))
    except IndexError:
        raise ValueError
    return rc

def inet_calcNetmask (ip):
    if isinstance (ip, type (0)):
        addr = inet_ntoa (ip)
    else:
        addr = ip
    quad = string.splitfields (addr, ".")
    if len (quad) > 0:
        klass = string.atoi (quad[0])
        if klass <= 127:
            mask = "255.0.0.0";
        elif klass <= 191:
            mask = "255.255.0.0";
        else:
            mask = "255.255.255.0";
    return mask
    
def inet_calcNetBroad (ip, nm):
    if isinstance (ip, type ("")):
        ipaddr = inet_aton (ip)
    else:
        ipaddr = ip

    if isinstance (nm, type ("")):
        nmaddr = inet_aton (nm)
    else:
        nmaddr = nm

    netaddr = ipaddr & nmaddr
    bcaddr = netaddr | (~nmaddr);
            
    return (inet_ntoa (netaddr), inet_ntoa (bcaddr))

def inet_calcGateway (bc):
    if isinstance (bc, type ("")):
        bcaddr = inet_aton (bc)
    else:
        bcaddr = ip

    return inet_ntoa (bcaddr - 1)

def inet_calcNS (net):
    if isinstance (net, type ("")):
        netaddr = inet_aton (net)
    else:
        netaddr = net

    return inet_ntoa (netaddr + 1)

def parseArgv(str):
    return _isys.poptParseArgv(str)

def getopt(*args):
    return apply(_isys.getopt, args)

def compareDrives(first, second):
    type1 = first[0:3]
    type2 = second[0:3]

    if type1 == "hda":
	type1 = 0
    elif type1 == "sda":
	type1 = 1
    else:
	type1 = 2

    if type2 == "hda":
	type2 = 0
    elif type2 == "sda":
	type2 = 1
    else:
	type2 = 2

    if (type1 < type2):
	return -1
    elif (type1 > type2):
	return 1
    elif first < second:
	return -1
    elif first > second:
	return 1

    return 0

def configNetDevice(device, ip, netmask, gw):
    return _isys.confignetdevice(device, ip, netmask, gw)

def resetResolv():
    return _isys.resetresolv()

def setResolvRetry(count):
    return _isys.setresretry(count)

def pumpNetDevice(device):
    # returns None on failure, "" if no nameserver is found, nameserver IP
    # otherwise
    return _isys.pumpnetdevice(device)

def readExt2Label(device):
    makeDevInode(device, "/tmp/disk")
    label = _isys.e2fslabel("/tmp/disk");
    os.unlink("/tmp/disk")
    return label

def ext2IsDirty(device):
    makeDevInode(device, "/tmp/disk")
    label = _isys.e2dirty("/tmp/disk");
    os.unlink("/tmp/disk")
    return label

def ejectCdrom(device):
    makeDevInode(device, "/tmp/cdrom")
    fd = os.open("/tmp/cdrom", os.O_RDONLY)

    # this is a best effort
    try:
	_isys.ejectcdrom(fd)
    except SystemError:
	pass

    os.close(fd)
    os.unlink("/tmp/cdrom")

def driveIsRemovable(device):
    # assume ide if starts with 'hd', and we don't have to create
    # device beforehand since it just reads /proc/ide
    from log import log

    if device[:2] == "hd":
        rc = (_isys.isIdeRemovable("/dev/"+device) == 1)
    else:
        makeDevInode(device, "/tmp/disk")
        rc = (_isys.isScsiRemovable("/tmp/disk") == 1)
        os.unlink("/tmp/disk")

    return rc

def vtActivate (num):
    _isys.vtActivate (num)
