import kudzu
import _isys
import string
import os

def spaceAvailable(device, fsystem = "ext2"):
    makeDevInode(device, "/tmp/spaceDev")
    mount("/tmp/spaceDev", "/mnt/space", fstype = fsystem)
    space = _isys.devSpaceFree("/mnt/space/.")
    umount("/mnt/space")
    os.rmdir("/mnt/space")
    os.remove("/tmp/spaceDev")
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

def losetup(device, file):
    loop = os.open(device, os.O_RDONLY)
    targ = os.open(file, os.O_RDWR)
    _isys.losetup(loop, targ, file)
    os.close(loop)
    os.close(targ)

def unlosetup(device):
    loop = os.open(device, os.O_RDONLY)
    _isys.unlosetup(loop)
    os.close(loop)

def ddfile(file, megs):
    fd = os.open(file, os.O_RDWR | os.O_CREAT)
    _isys.ddfile(fd, megs)
    os.close(fd)

def mount(device, location, fstype = "ext2"):
    return _isys.mount(fstype, device, location)

def umount(what):
    return _isys.umount(what)

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
        if klass <= 191:
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

def pumpNetDevice(device):
    # returns None on failure, "" if no nameserver is found, nameserver IP
    # otherwise
    return _isys.pumpnetdevice(device)
