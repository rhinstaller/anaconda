import _isys

def mount(device, location, fstype = "ext2"):
    return _isys.mount(fstype, device, location)

def umount(what):
    return _isys.umount(what)

def smpAvailable():
    return _isys.smpavailable()
