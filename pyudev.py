from __future__ import print_function

import sys
import os
import fnmatch
from ctypes import *


# XXX this one may need some tweaking...
def find_library(name, somajor=0):
    env = os.environ.get("LD_LIBRARY_PATH")

    if env:
        libdirs = env.split(":")
    else:
        libdirs = ["/lib64", "/lib"]

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
libudev = find_library(name="udev", somajor=0)

if not libudev or not os.path.exists(libudev):
    raise ImportError, "No library named %s" % libudev

# load the udev library
libudev = CDLL(libudev)


# create aliases for needed functions and set the return types where needed
libudev_udev_new = libudev.udev_new
libudev_udev_unref = libudev.udev_unref

libudev_udev_device_new_from_syspath = libudev.udev_device_new_from_syspath
libudev_udev_device_unref = libudev.udev_device_unref

libudev_udev_device_get_syspath = libudev.udev_device_get_syspath
libudev_udev_device_get_sysname = libudev.udev_device_get_sysname
libudev_udev_device_get_syspath.restype = c_char_p
libudev_udev_device_get_sysname.restype = c_char_p

libudev_udev_device_get_properties_list_entry = libudev.udev_device_get_properties_list_entry
libudev_udev_list_entry_get_next = libudev.udev_list_entry_get_next

libudev_udev_list_entry_get_name = libudev.udev_list_entry_get_name
libudev_udev_list_entry_get_value = libudev.udev_list_entry_get_value
libudev_udev_list_entry_get_name.restype = c_char_p
libudev_udev_list_entry_get_value.restype = c_char_p

libudev_udev_enumerate_new = libudev.udev_enumerate_new
libudev_udev_enumerate_unref = libudev.udev_enumerate_unref

libudev_udev_enumerate_add_match_subsystem = libudev.udev_enumerate_add_match_subsystem
libudev_udev_enumerate_scan_devices = libudev.udev_enumerate_scan_devices
libudev_udev_enumerate_get_list_entry = libudev.udev_enumerate_get_list_entry


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

        # get the first property entry
        property_entry = libudev_udev_device_get_properties_list_entry(udev_device)

        while property_entry:
            name = libudev_udev_list_entry_get_name(property_entry)
            value = libudev_udev_list_entry_get_value(property_entry)

            # XXX we have to split some of the values into a list,
            # the libudev is not so smart :(
            fields = value.split()

            if len(fields) > 1:
                value = [fields[0]]

                for item in fields[1:]:
                    (key, sep, val) = item.partition("=")
                    if sep:
                        value.append(val)
                    else:
                        value.append(key)

                if len(value) == 1:
                    value = value[0]

            self[name] = value

            # get next property entry
            property_entry = libudev_udev_list_entry_get_next(property_entry)

        # set additional properties
        libudev.udev_device_get_devpath.restype = c_char_p
        self.devpath = libudev.udev_device_get_devpath(udev_device)

        libudev.udev_device_get_subsystem.restype = c_char_p
        self.subsystem = libudev.udev_device_get_subsystem(udev_device)

        libudev.udev_device_get_devtype.restype = c_char_p
        self.devtype = libudev.udev_device_get_devtype(udev_device)

        libudev.udev_device_get_sysnum.restype = c_char_p
        self.sysnum = libudev.udev_device_get_sysnum(udev_device)

        libudev.udev_device_get_devnode.restype = c_char_p
        self.devnode = libudev.udev_device_get_devnode(udev_device)

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
