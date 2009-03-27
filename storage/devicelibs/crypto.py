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
    cs = CryptSetup(yesDialog = askyes, logFunc = dolog)
    return cs.addKey(device, new_passphrase, new_key_file, passphrase, key_file)


def luks_remove_key(device,
                    del_passphrase=None, del_key_file=None,
                    passphrase=None, key_file=None):
    cs = CryptSetup(yesDialog = askyes, logFunc = dolog)
    return cs.removeKey(device, del_passphrase, del_key_file, passphrase, key_file)


