import _isys

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
	
try:
    _isys.readmoduleinfo("/modules/module-info")
except IOError:
    _isys.readmoduleinfo("/boot/module-info")
