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

class LUKSDevice:
    """LUKSDevice represents an encrypted block device using LUKS/dm-crypt.
       It requires an underlying block device and a passphrase to become
       functional."""
    def __init__(self, device=None, passphrase=None, format=0):
        self._device = None
        self.passphrase = ""
        self.name = ""
        self.nameLocked = False
        self.format = format
        self.preexist = not format
        self.packages = ["cryptsetup-luks"]
        self.scheme = "LUKS"

        self.setDevice(device)
        self.setPassphrase(passphrase)

    def getScheme(self):
        """Returns the name of the encryption scheme used by the device."""
        if self.passphrase == "":
            return None
        return self.scheme

    def setDevice(self, device):
        self._device = device
        if device is not None:
            name = "%s-%s" % (self.getScheme().lower(),
                              os.path.basename(device))
            self.setName(name)

    def getDevice(self, encrypted=0):
        if encrypted:
            dev = self._device
        else:
            dev = "mapper/%s" % (self.name,)

        return dev

    def setName(self, name, lock=False):
        """Set the name of the mapped device, eg: 'dmcrypt-sda3'"""
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
                         "/dev/%s" % (self.getDevice(encrypted=1),),
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

    def formatDevice(self):
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

        log.info("formatting %s as %s" % (device, self.getScheme()))
        p = os.pipe()
        os.write(p[1], "%s\n" % (self.passphrase,))
        os.close(p[1])

        rc = iutil.execWithRedirect("cryptsetup",
                                    ["-q", "luksFormat",
                                     "/dev/%s" % (device,)],
                                    stdin = p[0],
                                    stdout = "/dev/null",
                                    stderr = "/dev/tty5",
                                    searchPath = 1)
        self.format = 0
        return rc

    def openDevice(self):
        if not self.getStatus():
            # already mapped
            return

        if not self.passphrase:
            raise RuntimeError, "Cannot create mapping without a passphrase."

        device = self.getDevice(encrypted=1)
        if not device:
            raise ValueError, "Cannot open mapping without a device."

        log.info("mapping %s device %s to %s" % (self.getScheme(),
                                                 device,
                                                 self.name))

        p = os.pipe()
        os.write(p[1], "%s\n" % (self.passphrase,))
        os.close(p[1])

        rc = iutil.execWithRedirect("cryptsetup",
                                    ["luksOpen",
                                     "/dev/%s" % (device,),
                                     self.name],
                                    stdin = p[0],
                                    stdout = "/dev/null",
                                    stderr = "/dev/tty5",
                                    searchPath = 1)
        return rc

    def closeDevice(self):
        log.info("unmapping %s device %s" % (self.getScheme(), self.name))
        rc = iutil.execWithRedirect("cryptsetup",
                                    ["luksClose", self.name],
                                    stdout = "/dev/null",
                                    stderr = "/dev/tty5",
                                    searchPath = 1)
        return rc


