import _isys

def mount(device, location, fstype = "ext2"):
    return _isys.mount(fstype, device, location)
