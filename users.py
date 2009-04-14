#
# users.py:  Code for creating user accounts and setting the root password
#
# Copyright (C) 2006, 2007, 2008 Red Hat, Inc.  All rights reserved.
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
# Author(s): Chris Lumens <clumens@redhat.com>
#

import libuser
import string
import crypt
import random
import tempfile
import os
import os.path

import logging
log = logging.getLogger("anaconda")

def createLuserConf(instPath, algoname='sha512'):
    """Writes a libuser.conf for instPath."""
    if os.getenv("LIBUSER_CONF") and \
       os.access(os.environ["LIBUSER_CONF"], os.R_OK):
        fn = os.environ["LIBUSER_CONF"]
        fd = open(fn, 'w')
    else:
        (fp, fn) = tempfile.mkstemp(prefix="libuser.")
        fd = os.fdopen(fp, 'w')

    buf = """
[defaults]
skeleton = %(instPath)s/etc/skel
mailspooldir = %(instPath)s/var/mail
crypt_style = %(algo)s
modules = files shadow
create_modules = files shadow
[files]
directory = %(instPath)s/etc
[shadow]
directory = %(instPath)s/etc
""" % {"instPath": instPath, "algo": algoname}

    fd.write(buf)
    fd.close()
    os.environ["LIBUSER_CONF"] = fn

# These are explained in crypt/crypt-entry.c in glibc's code.  The prefixes
# we use for the different crypt salts:
#     $1$    MD5
#     $5$    SHA256
#     $6$    SHA512
def cryptPassword(password, algo=None):
    salts = {'md5': '$1$', 'sha256': '$5$', 'sha512': '$6$'}
    saltlen = 2

    if algo is None:
        algo = 'sha512'

    if algo == 'md5' or algo == 'sha256' or algo == 'sha512':
        saltlen = 16

    saltstr = salts[algo]

    for i in range(saltlen):
        saltstr = saltstr + random.choice (string.letters +
                                           string.digits + './')

    return crypt.crypt (password, saltstr)

class Users:
    def __init__ (self):
        self.admin = libuser.admin()

    def createUser (self, name=None, password=None, isCrypted=False, groups=[],
                    homedir=None, shell=None, uid=None, algo=None, lock=False,
                    root="/mnt/sysimage"):
        childpid = os.fork()

        if not childpid:
            os.chroot(root)

            del(os.environ["LIBUSER_CONF"])
            self.admin = libuser.admin()

            try:
                if self.admin.lookupUserByName(name):
                    os._exit(1)

                userEnt = self.admin.initUser(name)
                groupEnt = self.admin.initGroup(name)

                grpLst = filter(lambda grp: grp,
                                map(lambda name: self.admin.lookupGroupByName(name), groups))
                userEnt.set(libuser.GIDNUMBER, [groupEnt.get(libuser.GIDNUMBER)[0]] +
                            map(lambda grp: grp.get(libuser.GIDNUMBER)[0], grpLst))

                if not homedir:
                    homedir = "/home/" + name

                userEnt.set(libuser.HOMEDIRECTORY, homedir)

                if shell:
                    userEnt.set(libuser.LOGINSHELL, shell)

                if uid >= 0:
                    userEnt.set(libuser.UIDNUMBER, uid)

                self.admin.addUser(userEnt)
                self.admin.addGroup(groupEnt)

                if password:
                    if isCrypted:
                        self.admin.setpassUser(userEnt, password, True)
                    else:
                        self.admin.setpassUser(userEnt,
                                            cryptPassword(password, algo=algo),
                                            True)

                if lock:
                    self.admin.lockUser(userEnt)

                # Add the user to all the groups they should be part of.
                grpLst.append(self.admin.lookupGroupByName(name))
                for grp in grpLst:
                    grp.add(libuser.MEMBERNAME, name)
                    self.admin.modifyGroup(grp)

                os._exit(0)
            except Exception, e:
                log.critical("Error when creating new user: %s" % str(e))
                os._exit(1)

        try:
            (pid, status) = os.waitpid(childpid, 0)
        except OSError, (num, msg):
            log.critical("exception from waitpid while creating a user: %s %s" % (num, msg))
            return False

        if os.WIFEXITED(status) and (os.WEXITSTATUS(status) == 0):
            return True
        else:
            return False

    def setRootPassword(self, password, isCrypted, lock, algo=None):
        rootUser = self.admin.lookupUserByName("root")

        if isCrypted:
            self.admin.setpassUser(rootUser, password, True)
        else:
            self.admin.setpassUser(rootUser, cryptPassword(password, algo=algo), True)

        if lock:
            self.admin.lockUser(rootUser)

        self.admin.modifyUser(rootUser)
