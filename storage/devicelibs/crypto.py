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
#

import os

import iutil
from ..errors import *

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

def is_luks(device):
    rc = iutil.execWithRedirect("cryptsetup",
                                ["isLuks", device],
                                stdout = "/dev/tty5",
                                stderr = "/dev/tty5",
                                searchPath = 1)
    if rc:
        return False
    else:
        return True

def luks_uuid(device):
    uuid = iutil.execWithCapture("cryptsetup",
                                 ["luksUUID", device],
                                 stderr="/dev/tty5")
    return uuid.strip()

def luks_status(name):
    """0 means active, 1 means inactive (or non-existent)"""
    rc = iutil.execWithRedirect("cryptsetup",
                                ["status", name],
                                stdout = "/dev/tty5",
                                stderr = "/dev/tty5",
                                searchPath = 1)
    return rc

def luks_format(device,
                passphrase=None, key_file=None,
                cipher=None, key_size=None):
    p = os.pipe()
    argv = ["-q"]
    os.close(p[1])

    if cipher:
        argv.extend(["--cipher", cipher])

    if key_size:
        argv.append("--key-size=%d" % key_size)

    argv.extend(["luksFormat", device])
        
    if passphrase:
        os.write(p[1], "%s\n" % passphrase)
    elif key_file and os.path.isfile(key_file):
        argv.append(key_file)
    else:
        raise ValueError("luks_format requires either a passphrase or a key file")

    rc = iutil.execWithRedirect("cryptsetup",
                                argv,
                                stdin = p[0],
                                stdout = "/dev/tty5",
                                stderr = "/dev/tty5",
                                searchPath = 1)

    os.close(p[0])
    if rc:
        raise CryptoError("luks_format failed for '%s'" % device)

def luks_open(device, name, passphrase=None, key_file=None):
    p = os.pipe()
    if passphrase:
        os.write(p[1], "%s\n" % passphrase)
        argv = ["luksOpen", device, name]
    elif key_file and os.path.isfile(key_file):
        argv = ["luksOpen", "--key-file", key_file, device, name]
    else:
        raise ValueError("luks_open requires either a passphrase or a key file")

    os.close(p[1])
    rc = iutil.execWithRedirect("cryptsetup",
                                argv,
                                stdin = p[0],
                                stdout = "/dev/tty5",
                                stderr = "/dev/tty5",
                                searchPath = 1)

    os.close(p[0])
    if rc:
        raise CryptoError("luks_open failed for %s (%s)" % (device, name))

def luks_close(name):
    rc = iutil.execWithRedirect("cryptsetup",
                                ["luksClose", name],
                                stdout = "/dev/tty5",
                                stderr = "/dev/tty5",
                                searchPath = 1)

    if rc:
        raise CryptoError("luks_close failed for %s" % name)

def luks_add_key(device,
                 new_passphrase=None, new_key_file=None,
                 passphrase=None, key_file=None):
    p = os.pipe()
    if passphrase:
        os.write(p[1], "%s\n" % passphrase)
        key_spec = ""
    elif key_file and os.path.isfile(key_file):
        key_spec = "--key-file %s" % key_file
    else:
        raise ValueError("luks_add_key requires either a passphrase or a key file")

    if new_passphrase:
        os.write(p[1], "%s\n" % new_passphrase)
        new_key_spec = ""
    elif new_key_file and os.path.isfile(new_key_file):
        new_key_spec = "%s" % new_key_file
    else:
        raise ValueError("luks_add_key requires either a passphrase or a key file to add")

    os.close(p[1])

    rc = iutil.execWithRedirect("cryptsetup",
                                ["-q",
                                 key_spec,
                                 "luksAddKey",
                                 device,
                                 new_key_spec],
                                stdin = p[0],
                                stdout = "/dev/tty5",
                                stderr = "/dev/tty5",
                                searchPath = 1)

    os.close(p[0])
    if rc:
        raise CryptoError("luks add key failed")

def luks_remove_key(device,
                    del_passphrase=None, del_key_file=None,
                    passphrase=None, key_file=None):
    p = os.pipe()
    if passphrase:
        os.write(p[1], "%s\n" % passphrase)
        key_spec = ""
    elif key_file and os.path.isfile(key_file):
        key_spec = "--key-file %s" % key_file
    else:
        raise ValueError("luks_remove_key requires either a passphrase or a key file")

    if del_passphrase:
        os.write(p[1], "%s\n" % del_passphrase)
        del_key_spec = ""
    elif del_key_file and os.path.isfile(del_key_file):
        del_key_spec = "%s" % del_key_file
    else:
        raise ValueError("luks_remove_key requires either a passphrase or a key file to remove")

    os.close(p[1])

    rc = iutil.execWithRedirect("cryptsetup",
                                ["-q",
                                 key_spec,
                                 "luksRemoveKey",
                                 device,
                                 del_key_spec],
                                stdin = p[0],
                                stdout = "/dev/tty5",
                                stderr = "/dev/tty5",
                                searchPath = 1)

    os.close(p[0])
    if rc:
        raise CryptoError("luks_remove_key failed")


