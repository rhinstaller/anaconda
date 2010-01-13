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
import iutil

from ..errors import *

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

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

def is_luks(device):
    cs = CryptSetup(yesDialog = askyes, logFunc = dolog)
    return cs.isLuks(device)

def luks_uuid(device):
    cs = CryptSetup(yesDialog = askyes, logFunc = dolog)
    return cs.luksUUID(device).strip()

def luks_status(name):
    """True means active, False means inactive (or non-existent)"""
    cs = CryptSetup(yesDialog = askyes, logFunc = dolog)
    return cs.luksStatus(name)!=0

def luks_format(device,
                passphrase=None, key_file=None,
                cipher=None, key_size=None):
    cs = CryptSetup(yesDialog = askyes, logFunc = dolog)
    key_file_unlink = False

    if passphrase:
        key_file = cs.prepare_passphrase_file(passphrase)
        key_file_unlink = True
    elif key_file and os.path.isfile(key_file):
        pass
    else:
        raise ValueError("luks_format requires either a passphrase or a key file")

    #None is not considered as default value and pycryptsetup doesn't accept it
    #so we need to filter out all Nones
    kwargs = {}
    kwargs["device"] = device
    if   cipher: kwargs["cipher"]  = cipher
    if key_file: kwargs["keyfile"] = key_file
    if key_size: kwargs["keysize"] = key_size

    rc = cs.luksFormat(**kwargs)
    if key_file_unlink: os.unlink(key_file)

    if rc:
        raise CryptoError("luks_format failed for '%s'" % device)

def luks_open(device, name, passphrase=None, key_file=None):
    cs = CryptSetup(yesDialog = askyes, logFunc = dolog)
    key_file_unlink = False

    if passphrase:
        key_file = cs.prepare_passphrase_file(passphrase)
        key_file_unlink = True
    elif key_file and os.path.isfile(key_file):
        pass
    else:
        raise ValueError("luks_open requires either a passphrase or a key file")

    rc = cs.luksOpen(device = device, name = name, keyfile = key_file)
    if key_file_unlink: os.unlink(key_file)
    if rc:
        raise CryptoError("luks_open failed for %s (%s)" % (device, name))

def luks_close(name):
    cs = CryptSetup(yesDialog = askyes, logFunc = dolog)
    rc = cs.luksClose(name)
    if rc:
        raise CryptoError("luks_close failed for %s" % name)

def luks_add_key(device,
                 new_passphrase=None, new_key_file=None,
                 passphrase=None, key_file=None):

    params = ["-q"]

    p = os.pipe()
    if passphrase:
        os.write(p[1], "%s\n" % passphrase)
    elif key_file and os.path.isfile(key_file):
        params.extend(["--key-file", key_file])
    else:
        raise CryptoError("luks_add_key requires either a passphrase or a key file")

    params.extend(["luksAddKey", device])

    if new_passphrase:
        os.write(p[1], "%s\n" % new_passphrase)
    elif new_key_file and os.path.isfile(new_key_file):
        params.append("%s" % new_key_file)
    else:
        raise CryptoError("luks_add_key requires either a passphrase or a key file to add")

    os.close(p[1])

    rc = iutil.execWithRedirect("cryptsetup", params,
                                stdin = p[0],
                                stdout = "/dev/tty5",
                                stderr = "/dev/tty5")

    os.close(p[0])
    if rc:
        raise CryptoError("luks add key failed with errcode %d" % (rc,))

def luks_remove_key(device,
                    del_passphrase=None, del_key_file=None,
                    passphrase=None, key_file=None):

    params = []

    p = os.pipe()
    if del_passphrase: #the first question is about the key we want to remove
        os.write(p[1], "%s\n" % del_passphrase)

    if passphrase:
        os.write(p[1], "%s\n" % passphrase)
    elif key_file and os.path.isfile(key_file):
        params.extend(["--key-file", key_file])
    else:
        raise CryptoError("luks_remove_key requires either a passphrase or a key file")

    params.extend(["luksRemoveKey", device])

    if del_passphrase:
        pass
    elif del_key_file and os.path.isfile(del_key_file):
        params.append("%s" % del_key_file)
    else:
        raise CryptoError("luks_remove_key requires either a passphrase or a key file to remove")

    os.close(p[1])

    rc = iutil.execWithRedirect("cryptsetup", params,
                                stdin = p[0],
                                stdout = "/dev/tty5",
                                stderr = "/dev/tty5")

    os.close(p[0])
    if rc:
        raise CryptoError("luks_remove_key failed with errcode %d" % (rc,))


