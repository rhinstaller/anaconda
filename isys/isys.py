import _isys
import string

def mount(device, location, fstype = "ext2"):
    return _isys.mount(fstype, device, location)

def umount(what):
    return _isys.umount(what)

def smpAvailable():
    return _isys.smpavailable()

def probeDevices():
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

try:
    _isys.readmoduleinfo("/modules/module-info")
except IOError:
    _isys.readmoduleinfo("/boot/module-info")
