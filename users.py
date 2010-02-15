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
    createTmp = False
    try:
        fn = os.environ["LIBUSER_CONF"]
        if os.access(fn, os.F_OK):
            log.info("removing libuser.conf at %s" % (os.getenv("LIBUSER_CONF")))
            os.unlink(fn)
        log.info("created new libuser.conf at %s with instPath=\"%s\"" % \
                (fn,instPath))
        fd = open(fn, 'w')
    except:
        createTmp = True

    if createTmp:
        (fp, fn) = tempfile.mkstemp(prefix="libuser.")
        log.info("created new libuser.conf at %s with instPath=\"%s\"" % \
                (fn,instPath))
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

    return fn

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
    def __init__ (self, anaconda):
        self.anaconda = anaconda
        self.admin = libuser.admin()
        self.rootPassword = { "isCrypted": False, "password": "", "lock": False }

    def createGroup (self, name=None, gid=None, root="/mnt/sysimage"):
        childpid = os.fork()

        if not childpid:
            if not root in ["","/"]:
                os.chroot(root)
                del(os.environ["LIBUSER_CONF"])

            self.admin = libuser.admin()

            try:
                if self.admin.lookupGroupByName(name):
                    os._exit(1)

                groupEnt = self.admin.initGroup(name)

                if gid >= 0:
                    groupEnt.set(libuser.GIDNUMBER, gid)

                self.admin.addGroup(groupEnt)
                os._exit(0)
            except Exception, e:
                log.critical("Error when creating new group: %s" % str(e))
                os._exit(1)

        try:
            (pid, status) = os.waitpid(childpid, 0)
        except OSError as e:
            log.critical("exception from waitpid while creating a group: %s %s" % (e.errno, e.strerror))
            return False

        if os.WIFEXITED(status) and (os.WEXITSTATUS(status) == 0):
            return True
        else:
            return False

    def createUser (self, name=None, password=None, isCrypted=False, groups=[],
                    homedir=None, shell=None, uid=None, algo=None, lock=False,
                    root="/mnt/sysimage", gecos=None):
        childpid = os.fork()

        if not childpid:
            if not root in ["","/"]:
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

                if gecos:
                    userEnt.set(libuser.GECOS, gecos)

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
        except OSError as e:
            log.critical("exception from waitpid while creating a user: %s %s" % (e.errno, e.strerror))
            return False

        if os.WIFEXITED(status) and (os.WEXITSTATUS(status) == 0):
            return True
        else:
            return False

    def checkUserExists(self, username, root="/mnt/sysimage"):
        childpid = os.fork()

        if not childpid:
            if not root in ["","/"]:
                os.chroot(root)
                del(os.environ["LIBUSER_CONF"])

            self.admin = libuser.admin()

            try:
                if self.admin.lookupUserByName(username):
                    os._exit(0)
            except Exception, e:
                log.critical("Error when searching for user: %s" % str(e))
            os._exit(1)

        try:
            (pid, status) = os.waitpid(childpid, 0)
        except OSError as e:
            log.critical("exception from waitpid while creating a user: %s %s" % (e.errno, e.strerror))
            return False

        if os.WIFEXITED(status) and (os.WEXITSTATUS(status) == 0):
            return True
        else:
            return False

    # Reads the auth string and returns a string indicating our desired
    # password encoding algorithm.
    def getPassAlgo(self):
        if self.anaconda.security.auth.find("--enablemd5") != -1 or \
           self.anaconda.security.auth.find("--passalgo=md5") != -1:
            return 'md5'
        elif self.anaconda.security.auth.find("--passalgo=sha256") != -1:
            return 'sha256'
        elif self.anaconda.security.auth.find("--passalgo=sha512") != -1:
            return 'sha512'
        else:
            return None

    def setUserPassword(self, username, password, isCrypted, lock, algo=None):
        user = self.admin.lookupUserByName(username)

        if isCrypted:
            self.admin.setpassUser(user, password, True)
        else:
            self.admin.setpassUser(user, cryptPassword(password, algo=algo), True)

        if lock:
            self.admin.lockUser(user)

        self.admin.modifyUser(user)

    def setRootPassword(self, algo=None):
        return self.setUserPassword("root", self.rootPassword["password"],
                                    self.rootPassword["isCrypted"],
                                    self.rootPassword["lock"], algo)

    def write(self, instPath):
        # make sure crypt_style in libuser.conf matches the salt we're using
        createLuserConf(instPath, algoname=self.getPassAlgo())

        # User should already exist, just without a password.
        self.setRootPassword(algo=self.getPassAlgo())

        if self.anaconda.ksdata:
            for gd in self.anaconda.ksdata.group.groupList:
                if not self.createGroup(name=gd.name,
                                        gid=gd.gid,
                                        root=instPath):
                    log.error("Group %s already exists, not creating." % gd.name)

            for ud in self.anaconda.ksdata.user.userList:
                if not self.createUser(name=ud.name,
                                       password=ud.password,
                                       isCrypted=ud.isCrypted,
                                       groups=ud.groups,
                                       homedir=ud.homedir,
                                       shell=ud.shell,
                                       uid=ud.uid,
                                       algo=self.getPassAlgo(),
                                       lock=ud.lock,
                                       root=instPath,
                                       gecos=ud.gecos):
                    log.error("User %s already exists, not creating." % ud.name)

    def writeKS(self, f):
        if self.rootPassword["isCrypted"]:
            args = " --iscrypted %s" % self.rootPassword["password"]
        else:
            args = " --iscrypted %s" % cryptPassword(self.rootPassword["password"], algo=self.getPassAlgo())

        if self.rootPassword["lock"]:
            args += " --lock"

        f.write("rootpw %s\n" % args)
