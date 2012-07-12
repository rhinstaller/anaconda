from __future__ import print_function

import sys
import os
import fnmatch
from ctypes import *


# XXX this one may need some tweaking...
def find_library(name, somajor=0):
    env = os.environ.get("LD_LIBRARY_PATH")
    common = ["/lib64", "/lib"]

    if env:
        libdirs = env.split(":") + common
    else:
        libdirs = common

    libdirs = filter(os.path.isdir, libdirs)

    for dir in libdirs:
        files = fnmatch.filter(os.listdir(dir), "lib%s.so.%d" % (name, somajor))
        files = [os.path.join(dir, file) for file in files]

        if files:
            break

    if files:
        return files[0]
    else:
        return None

# find the udev library
name = "udev"
somajor = 1
libudev = find_library(name=name, somajor=somajor)

if not libudev or not os.path.exists(libudev):
    raise ImportError, "No library named %s.%d" % (name, somajor)

# load the udev library
libudev = CDLL(libudev)


# create aliases for needed functions and set the return types where needed
libudev_udev_new = libudev.udev_new
libudev_udev_new.argtypes = []
libudev_udev_new.restype = c_void_p
libudev_udev_unref = libudev.udev_unref
libudev_udev_unref.argtypes = [ c_void_p ]

libudev_udev_device_new_from_syspath = libudev.udev_device_new_from_syspath
libudev_udev_device_new_from_syspath.restype = c_void_p
libudev_udev_device_new_from_syspath.argtypes = [ c_void_p, c_char_p ]
libudev_udev_device_unref = libudev.udev_device_unref
libudev_udev_device_unref.argtypes = [ c_void_p ]

libudev_udev_device_get_syspath = libudev.udev_device_get_syspath
libudev_udev_device_get_syspath.restype = c_char_p
libudev_udev_device_get_syspath.argtypes = [ c_void_p ]
libudev_udev_device_get_sysname = libudev.udev_device_get_sysname
libudev_udev_device_get_sysname.restype = c_char_p
libudev_udev_device_get_sysname.argtypes = [ c_void_p ]
libudev_udev_device_get_devpath = libudev.udev_device_get_devpath
libudev_udev_device_get_devpath.restype = c_char_p
libudev_udev_device_get_devpath.argtypes = [ c_void_p ]
libudev_udev_device_get_devtype = libudev.udev_device_get_devtype
libudev_udev_device_get_devtype.restype = c_char_p
libudev_udev_device_get_devtype.argtypes = [ c_void_p ]
libudev_udev_device_get_devnode = libudev.udev_device_get_devnode
libudev_udev_device_get_devnode.restype = c_char_p
libudev_udev_device_get_devnode.argtypes = [ c_void_p ]
libudev_udev_device_get_subsystem = libudev.udev_device_get_subsystem
libudev_udev_device_get_subsystem.restype = c_char_p
libudev_udev_device_get_subsystem.argtypes = [ c_void_p ]
libudev_udev_device_get_sysnum = libudev.udev_device_get_sysnum
libudev_udev_device_get_sysnum.restype = c_char_p
libudev_udev_device_get_sysnum.argtypes = [ c_void_p ]

libudev_udev_device_get_properties_list_entry = libudev.udev_device_get_properties_list_entry
libudev_udev_device_get_properties_list_entry.restype = c_void_p
libudev_udev_device_get_properties_list_entry.argtypes = [ c_void_p ]
libudev_udev_list_entry_get_next = libudev.udev_list_entry_get_next
libudev_udev_list_entry_get_next.restype = c_void_p
libudev_udev_list_entry_get_next.argtypes = [ c_void_p ]

libudev_udev_list_entry_get_name = libudev.udev_list_entry_get_name
libudev_udev_list_entry_get_name.restype = c_char_p
libudev_udev_list_entry_get_name.argtypes = [ c_void_p ]
libudev_udev_list_entry_get_value = libudev.udev_list_entry_get_value
libudev_udev_list_entry_get_value.restype = c_char_p
libudev_udev_list_entry_get_value.argtypes = [ c_void_p ]

libudev_udev_enumerate_new = libudev.udev_enumerate_new
libudev_udev_enumerate_new.restype = c_void_p
libudev_udev_enumerate_new.argtypes = [ c_void_p ]
libudev_udev_enumerate_unref = libudev.udev_enumerate_unref
libudev_udev_enumerate_unref.argtypes = [ c_void_p ]

libudev_udev_enumerate_add_match_subsystem = libudev.udev_enumerate_add_match_subsystem
libudev_udev_enumerate_add_match_subsystem.restype = c_int
libudev_udev_enumerate_add_match_subsystem.argtypes = [ c_void_p, c_char_p ]
libudev_udev_enumerate_scan_devices = libudev.udev_enumerate_scan_devices
libudev_udev_enumerate_scan_devices.restype = c_int
libudev_udev_enumerate_scan_devices.argtypes = [ c_void_p ]
libudev_udev_enumerate_get_list_entry = libudev.udev_enumerate_get_list_entry
libudev_udev_enumerate_get_list_entry.restype = c_void_p
libudev_udev_enumerate_get_list_entry.argtypes = [ c_void_p ]

libudev_udev_device_get_devlinks_list_entry = libudev.udev_device_get_devlinks_list_entry
libudev_udev_device_get_devlinks_list_entry.restype = c_void_p
libudev_udev_device_get_devlinks_list_entry.argtypes = [ c_void_p ]


class UdevDevice(dict):

    def __init__(self, udev, sysfs_path):
        dict.__init__(self)

        # create new udev device from syspath
        udev_device = libudev_udev_device_new_from_syspath(udev, sysfs_path)
        if not udev_device:
            # device does not exist
            return

        # set syspath and sysname properties
        self.syspath = libudev_udev_device_get_syspath(udev_device)
        self.sysname = libudev_udev_device_get_sysname(udev_device)

        # get the devlinks list
        devlinks = []
        devlinks_entry = libudev_udev_device_get_devlinks_list_entry(udev_device)

        while devlinks_entry:
            path = libudev_udev_list_entry_get_name(devlinks_entry)
            devlinks.append(path)

            devlinks_entry = libudev_udev_list_entry_get_next(devlinks_entry)

        # add devlinks list to the dictionary
        self["symlinks"] = devlinks

        # get the first property entry
        property_entry = libudev_udev_device_get_properties_list_entry(udev_device)

        while property_entry:
            name = libudev_udev_list_entry_get_name(property_entry)
            value = libudev_udev_list_entry_get_value(property_entry)

            # lvm outputs values for multiple lvs in one line
            # we want to split them and make a list
            # if the first lv's value is empty we end up with a value starting
            # with name=, prepend a space that our split does the right thing
            if value.startswith("%s=" % name):
                value = " " + value

            if value.count(" %s=" % name):
                value = value.split(" %s=" % name)

            self[name] = value

            # get next property entry
            property_entry = libudev_udev_list_entry_get_next(property_entry)

        # set additional properties
        self.devpath = libudev_udev_device_get_devpath(udev_device)
        self.subsystem = libudev_udev_device_get_subsystem(udev_device)
        self.devtype = libudev_udev_device_get_devtype(udev_device)
        self.sysnum = libudev_udev_device_get_sysnum(udev_device)
        self.devnode = libudev_udev_device_get_devnode(udev_device)

        # cleanup
        libudev_udev_device_unref(udev_device)


class Udev(object):

    def __init__(self):
        self.udev = libudev_udev_new()

    def create_device(self, sysfs_path):
        return UdevDevice(self.udev, sysfs_path)

    def enumerate_devices(self, subsystem=None):
        enumerate = libudev_udev_enumerate_new(self.udev)

        # add the match subsystem
        if subsystem is not None:
            rc = libudev_udev_enumerate_add_match_subsystem(enumerate, subsystem)
            if not rc == 0:
                print("error: unable to add the match subsystem", file=sys.stderr)
                libudev_udev_enumerate_unref(enumerate)
                return []

        # scan the devices
        rc = libudev_udev_enumerate_scan_devices(enumerate)
        if not rc == 0:
            print("error: unable to enumerate the devices", file=sys.stderr)
            libudev_udev_enumerate_unref(enumerate)
            return []

        # create the list of sysfs paths
        sysfs_paths = []

        # get the first list entry
        list_entry = libudev_udev_enumerate_get_list_entry(enumerate)

        while list_entry:
            sysfs_path = libudev_udev_list_entry_get_name(list_entry)
            sysfs_paths.append(sysfs_path)

            # get next list entry
            list_entry = libudev_udev_list_entry_get_next(list_entry)

        # cleanup
        libudev_udev_enumerate_unref(enumerate)

        return sysfs_paths

    def scan_devices(self, sysfs_paths=None):
        if sysfs_paths is None:
            sysfs_paths = self.enumerate_devices()

        for sysfs_path in sysfs_paths:
            device = self.create_device(sysfs_path)

            if device:
                yield device

    def unref(self):
        libudev_udev_unref(self.udev)
        self.udev = None
