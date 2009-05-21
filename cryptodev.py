#
# cryptodev.py
#
# Copyright (C) 2008  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author(s): Dave Lehman <dlehman@redhat.com>
#

import os
import iutil

import logging
log = logging.getLogger("anaconda")

def isLuks(device):
    if not device.startswith("/"):
        device = "/dev/" + device
    rc = iutil.execWithRedirect("cryptsetup",
                                ["isLuks", device],
                                stdout = "/dev/null",
                                stderr = "/dev/null",
                                searchPath = 1)
    if rc:
        return False
    else:
        return True

def luksUUID(device):
    if not device.startswith("/"):
        device = "/dev/" + device

    if not isLuks(device):
        return None

    uuid = iutil.execWithCapture("cryptsetup", ["luksUUID", device])
    uuid = uuid.strip()
    return uuid

class LUKSDevice:
    """LUKSDevice represents an encrypted block device using LUKS/dm-crypt.
       It requires an underlying block device and a passphrase to become
       functional."""
    def __init__(self, device=None, passphrase=None, format=0):
        self._device = None
        self.passphrase = ""
        self.name = ""
        self.uuid = None
        self.nameLocked = False
        self.format = format
        self.preexist = not format
        self.packages = ["cryptsetup-luks"]
        self.scheme = "LUKS"

        self.setDevice(device)
        self.setPassphrase(passphrase)
        if self.getUUID():
            name = "%s-%s" % (self.scheme.lower(), self.uuid)
            self.setName(name, lock=True)

    def getScheme(self):
        """Returns the name of the encryption scheme used by the device."""
        if self.passphrase == "":
            return None
        return self.scheme

    def setDevice(self, device):
        if self._device == device:
            return

        self._device = device
        if device is not None:
            name = "%s-%s" % (self.scheme.lower(),
                              os.path.basename(device))
            self.setName(name)

    def getDevice(self, encrypted=0):
        if encrypted:
            dev = self._device
        else:
            dev = "mapper/%s" % (self.name,)

        return dev

    def getUUID(self):
        if self.format:
            # self.format means we're going to reformat but haven't yet
            # so we shouldn't act like there's anything worth seeing there
            return

        if not self.uuid:
            self.uuid = luksUUID(self.getDevice(encrypted=1))

        return self.uuid

    def setName(self, name, lock=False):
        """Set the name of the mapped device, eg: 'dmcrypt-sda3'"""
        if self.name == name:
            return

        if self.name and not self.getStatus():
            raise RuntimeError, "Cannot rename an active mapping."

        if self.nameLocked:
            log.debug("Failed to change locked mapping name: %s" % 
                      (self.name,))
            return

        self.name = name
        if lock and name:
            # don't allow anyone to lock the name as "" or None
            self.nameLocked = True

    def setPassphrase(self, passphrase):
        """Set the (plaintext) passphrase used to access the device."""
        self.passphrase = passphrase

    def crypttab(self):
        """Return a crypttab formatted line describing this mapping."""
        format = "%-23s %-15s %s\n"
        line = format % (self.name,
                         "UUID=%s" % (self.getUUID(),),
                         "none")
        return line

    def getStatus(self):
        """0 means active, 1 means inactive (or non-existent)"""
        if not self.name:
            return 1

        rc = iutil.execWithRedirect("cryptsetup",
                                    ["status", self.name],
                                    stdout = "/dev/null",
                                    stderr = "/dev/null",
                                    searchPath = 1)
        return rc

    def formatDevice(self, devPrefix="/dev"):
        """Write a LUKS header onto the device."""
        if not self.format:
            return

        if not self.getStatus():
            log.debug("refusing to format active mapping %s" % (self.name,))
            return 1

        if not self.passphrase:
            raise RuntimeError, "Cannot create mapping without a passphrase."

        device = self.getDevice(encrypted=1)
        if not device:
            raise ValueError, "Cannot open mapping without a device."

        # zero out the 1MB at the beginning and end of the device in the
        # hope that it will wipe any metadata from filesystems that
        # previously occupied this device
        log.debug("zeroing out beginning and end of %s..." % device)
        try:
            fd = os.open("%s/%s" % (devPrefix, device), os.O_RDWR)
            buf = '\0' * 1024 * 1024
            os.write(fd, buf)
            os.lseek(fd, -1024 * 1024, 2)
            os.write(fd, buf)
            os.close(fd)
        except Exception, e:
            log.error("error zeroing out %s/%s: %s" % (devPrefix, device, e))

        log.info("formatting %s as %s" % (device, self.getScheme()))
        p = os.pipe()
        os.write(p[1], "%s\n" % (self.passphrase,))
        os.close(p[1])

        rc = iutil.execWithRedirect("cryptsetup",
                                    ["-q", "luksFormat",
                                     "%s/%s" % (devPrefix, device)],
                                    stdin = p[0],
                                    stdout = "/dev/null",
                                    stderr = "/dev/tty5",
                                    searchPath = 1)
        self.format = 0
        return rc

    def openDevice(self, devPrefix="/dev/"):
        if not self.getStatus():
            # already mapped
            return 0

        if not self.passphrase:
            raise RuntimeError, "Cannot create mapping without a passphrase."

        device = self.getDevice(encrypted=1)
        if not device:
            raise ValueError, "Cannot open mapping without a device."

        uuid = self.getUUID()
        if not uuid:
            raise RuntimeError, "Device has no UUID."

        self.setName("%s-%s" % (self.scheme.lower(), uuid), lock=True)

        log.info("mapping %s device %s to %s" % (self.getScheme(),
                                                 device,
                                                 self.name))

        p = os.pipe()
        os.write(p[1], "%s\n" % (self.passphrase,))
        os.close(p[1])

        rc = iutil.execWithRedirect("cryptsetup",
                                    ["luksOpen",
                                     "%s/%s" % (devPrefix, device),
                                     self.name],
                                    stdin = p[0],
                                    stdout = "/dev/null",
                                    stderr = "/dev/tty5",
                                    searchPath = 1)
        return rc

    def closeDevice(self):
        if self.getStatus():
            # not mapped
            return 0

        log.info("unmapping %s device %s" % (self.getScheme(), self.name))
        rc = iutil.execWithRedirect("cryptsetup",
                                    ["luksClose", self.name],
                                    stdout = "/dev/null",
                                    stderr = "/dev/tty5",
                                    searchPath = 1)
        return rc

    def addPassphrase(self, newpass):
        if not newpass:
            return 1

        if newpass == self.passphrase:
            return 0

        p = os.pipe()
        os.write(p[1], "%s\n%s" % (self.passphrase, newpass))
        os.close(p[1])

        device = self.getDevice(encrypted=1)
        log.info("adding new passphrase to %s device %s" % (self.getScheme(),
                                                            device))
        rc = iutil.execWithRedirect("cryptsetup",
                                    ["-q",
                                     "luksAddKey",
                                     "/dev/%s" % (device,)],
                                    stdin = p[0],
                                    stdout = "/dev/null",
                                    stderr = "/dev/tty5",
                                    searchPath = 1)

        return rc

