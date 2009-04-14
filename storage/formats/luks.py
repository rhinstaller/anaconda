# luks.py
# Device format classes for anaconda's storage configuration module.
#
# Copyright (C) 2009  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Dave Lehman <dlehman@redhat.com>
#



import os

from iutil import log_method_call
from ..errors import *
from ..devicelibs import crypto
from . import DeviceFormat, register_device_format

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("storage")


class LUKS(DeviceFormat):
    """ A LUKS device. """
    _type = "luks"
    _name = "LUKS"
    _udevTypes = ["crypto_LUKS"]
    _formattable = True                 # can be formatted
    _supported = False                  # is supported
    _linuxNative = True                 # for clearpart
    _packages = ["cryptsetup-luks"]     # required packages

    def __init__(self, *args, **kwargs):
        """ Create a LUKS instance.

            Keyword Arguments:

                device -- the path to the underlying device
                name -- the name of the mapped device
                uuid -- this device's UUID
                passphrase -- device passphrase (string)
                key_file -- path to a file containing a key (string)
                cipher -- cipher mode string
                key_size -- key size in bits
                exists -- indicates whether this is an existing format
        """
        log_method_call(self, *args, **kwargs)
        DeviceFormat.__init__(self, *args, **kwargs)
        self.cipher = kwargs.get("cipher")
        self.key_size = kwargs.get("key_size")
        self.mapName = kwargs.get("name")

        if not self.exists and not self.cipher:
            self.cipher = "aes-xts-plain"
            if not self.key_size:
                # default to the max (512 bits) for aes-xts
                self.key_size = 512

        # FIXME: these should both be lists, but managing them will be a pain
        self.__passphrase = kwargs.get("passphrase")
        self._key_file = kwargs.get("key_file")

        if not self.mapName and self.exists and self.uuid:
            self.mapName = "luks-%s" % self.uuid
        elif not self.mapName and self.device:
            self.mapName = "luks-%s" % os.path.basename(self.device)

    def _setPassphrase(self, passphrase):
        """ Set the passphrase used to access this device. """
        self.__passphrase = passphrase

    passphrase = property(fset=_setPassphrase)

    @property
    def hasKey(self):
        return (self.__passphrase or
                (self._key_file and os.access(self._key_file, os.R_OK)))

    @property
    def configured(self):
        """ To be ready we need a key or passphrase and a map name. """
        return self.hasKey and self.mapName

    @property
    def status(self):
        if not self.exists or not self.mapName:
            return False
        return os.path.exists("/dev/mapper/%s" % self.mapName)

    def probe(self):
        """ Probe for any missing information about this format.

            cipher mode, key size
        """
        raise NotImplementedError("probe method not defined for LUKS")

    def setup(self, *args, **kwargs):
        """ Open, or set up, the format. """
        log_method_call(self, device=self.device, mapName=self.mapName,
                        type=self.type, status=self.status)
        if not self.configured:
            raise LUKSError("luks device not configured")

        if self.status:
            return

        DeviceFormat.setup(self, *args, **kwargs)
        crypto.luks_open(self.device, self.mapName,
                       passphrase=self.__passphrase,
                       key_file=self._key_file)

    def teardown(self, *args, **kwargs):
        """ Close, or tear down, the format. """
        log_method_call(self, device=self.device,
                        type=self.type, status=self.status)
        if not self.exists:
            raise LUKSError("format has not been created")

        if self.status:
            log.debug("unmapping %s" % self.mapName)
            crypto.luks_close(self.mapName)

    def create(self, *args, **kwargs):
        """ Create the format. """
        log_method_call(self, device=self.device,
                        type=self.type, status=self.status)
        if not self.hasKey:
            raise LUKSError("luks device has no key/passphrase")

        DeviceFormat.create(self, *args, **kwargs)
        crypto.luks_format(self.device,
                         passphrase=self.__passphrase,
                         key_file=self._key_file,
                         cipher=self.cipher,
                         key_size=self.key_size)

        self.uuid = crypto.luks_uuid(self.device)
        self.exists = True
        self.mapName = "luks-%s" % self.uuid
        self.notifyKernel()

    def destroy(self, *args, **kwargs):
        """ Create the format. """
        log_method_call(self, device=self.device,
                        type=self.type, status=self.status)
        self.teardown()
        DeviceFormat.destroy(self, *args, **kwargs)

    @property
    def keyFile(self):
        """ Path to key file to be used in /etc/crypttab """
        return self._key_file

    def addKeyFromFile(self, keyfile):
        """ Add a new key from a file.

            Add the contents of the specified key file to an available key
            slot in the LUKS header.
        """
        log_method_call(self, device=self.device,
                        type=self.type, status=self.status, file=keyfile)
        if not self.exists:
            raise LUKSError("format has not been created")

        crypto.luks_add_key(self.device,
                          passphrase=self.__passphrase,
                          key_file=self._key_file,
                          new_key_file=keyfile)

    def addPassphrase(self, passphrase):
        """ Add a new passphrase.

            Add the specified passphrase to an available key slot in the
            LUKS header.
        """
        log_method_call(self, device=self.device,
                        type=self.type, status=self.status)
        if not self.exists:
            raise LUKSError("format has not been created")

        crypto.luks_add_key(self.device,
                          passphrase=self.__passphrase,
                          key_file=self._key_file,
                          new_passphrase=passphrase)

    def removeKeyFromFile(self, keyfile):
        """ Remove a key contained in a file.

            Remove key contained in the specified key file from the LUKS
            header.
        """
        log_method_call(self, device=self.device,
                        type=self.type, status=self.status, file=keyfile)
        if not self.exists:
            raise LUKSError("format has not been created")

        crypto.luks_remove_key(self.device,
                             passphrase=self.__passphrase,
                             key_file=self._key_file,
                             del_key_file=keyfile)


    def removePassphrase(self, passphrase):
        """ Remove the specified passphrase from the LUKS header. """
        log_method_call(self, device=self.device,
                        type=self.type, status=self.status)
        if not self.exists:
            raise LUKSError("format has not been created")

        crypto.luks_remove_key(self.device,
                             passphrase=self.__passphrase,
                             key_file=self._key_file,
                             del_passphrase=passphrase)


register_device_format(LUKS)

