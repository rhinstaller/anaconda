#
# crypto.py
#
# Copyright (C) 2009  Red Hat, Inc.  All rights reserved.
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
#            Martin Sivak <msivak@redhat.com>
#

import os
from pycryptsetup import CryptSetup
from pyanaconda import iutil

from ..errors import *

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

LUKS_METADATA_SIZE = 2.0    # MB

# Keep the character set size a power of two to make sure all characters are
# equally likely
GENERATED_PASSPHRASE_CHARSET = ("0123456789"
                                "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                                "abcdefghijklmnopqrstuvwxyz"
                                "./")
# 20 chars * 6 bits per char = 120 "bits of security"
GENERATED_PASSPHRASE_LENGTH = 20

def generateBackupPassphrase():
    rnd = os.urandom(GENERATED_PASSPHRASE_LENGTH)
    cs = GENERATED_PASSPHRASE_CHARSET
    raw = "".join([cs[ord(c) % len(cs)] for c in rnd])

    # Make the result easier to read
    parts = []
    for i in xrange(0, len(raw), 5):
        parts.append(raw[i : i + 5])
    return "-".join(parts)

def askyes(question):
    return True

def dolog(priority, text):
    pass

def askpassphrase(text):
    return None

def is_luks(device):
    cs = CryptSetup(device=device, yesDialog = askyes, logFunc = dolog, passwordDialog = askpassphrase)
    return cs.isLuks()

def luks_uuid(device):
    cs = CryptSetup(device=device, yesDialog = askyes, logFunc = dolog, passwordDialog = askpassphrase)
    return cs.luksUUID()

def luks_status(name):
    """True means active, False means inactive (or non-existent)"""
    cs = CryptSetup(name=name, yesDialog = askyes, logFunc = dolog, passwordDialog = askpassphrase)
    return cs.status()

def luks_format(device,
                passphrase=None,
                cipher=None, key_size=None, key_file=None):
    if not passphrase:
        raise ValueError("luks_format requires passphrase")

    cs = CryptSetup(device=device, yesDialog = askyes, logFunc = dolog, passwordDialog = askpassphrase)

    #None is not considered as default value and pycryptsetup doesn't accept it
    #so we need to filter out all Nones
    kwargs = {}

    # Split cipher designator to cipher name and cipher mode
    cipherType = None
    cipherMode = None
    if cipher:
        cparts = cipher.split("-")
        cipherType = "".join(cparts[0:1])
        cipherMode = "-".join(cparts[1:])
    
    if cipherType: kwargs["cipher"]  = cipherType
    if cipherMode: kwargs["cipherMode"]  = cipherMode
    if   key_size: kwargs["keysize"]  = key_size

    rc = cs.luksFormat(**kwargs)
    if rc:
        raise CryptoError("luks_format failed for '%s'" % device)

    # activate first keyslot
    cs.addKeyByVolumeKey(newPassphrase = passphrase)
    if rc:
        raise CryptoError("luks_add_key_by_volume_key failed for '%s'" % device)


def luks_open(device, name, passphrase=None, key_file=None):
    if not passphrase:
        raise ValueError("luks_format requires passphrase")

    cs = CryptSetup(device=device, yesDialog = askyes, logFunc = dolog, passwordDialog = askpassphrase)

    rc = cs.activate(passphrase = passphrase, name = name)
    if rc<0:
        raise CryptoError("luks_open failed for %s (%s) with errno %d" % (device, name, rc))

def luks_close(name):
    cs = CryptSetup(name=name, yesDialog = askyes, logFunc = dolog, passwordDialog = askpassphrase)
    rc = cs.deactivate()

    if rc:
        raise CryptoError("luks_close failed for %s" % name)

def luks_add_key(device,
                 new_passphrase=None,
                 passphrase=None, key_file=None):

    if not passphrase:
        raise ValueError("luks_add_key requires passphrase")

    cs = CryptSetup(device=device, yesDialog = askyes, logFunc = dolog, passwordDialog = askpassphrase)
    rc = cs.addKeyByPassphrase(passphrase = passphrase, newPassphrase = new_passphrase)
    
    if rc<0:
        raise CryptoError("luks add key failed with errcode %d" % (rc,))

def luks_remove_key(device,
                    del_passphrase=None,
                    passphrase=None, key_file=None):

    if not passphrase:
        raise ValueError("luks_remove_key requires passphrase")

    cs = CryptSetup(device=device, yesDialog = askyes, logFunc = dolog, passwordDialog = askpassphrase)
    rc = cs.removePassphrase(passphrase = passphrase)
    
    if rc:
        raise CryptoError("luks remove key failed with errcode %d" % (rc,))



