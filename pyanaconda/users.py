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
import iutil
import pwquality
from pyanaconda.constants import ROOT_PATH

import logging
log = logging.getLogger("anaconda")

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

def createLuserConf(instPath, algoname='sha512'):
    """ Writes a libuser.conf for instPath.

        This must be called before User() is instantiated the first time
        so that libuser.admin will use the temporary config file.
    """
    createTmp = False
    try:
        fn = os.environ["LIBUSER_CONF"]
        if os.access(fn, os.F_OK):
            log.info("removing libuser.conf at %s" % (os.getenv("LIBUSER_CONF")))
            os.unlink(fn)
        log.info("created new libuser.conf at %s with instPath=\"%s\"" % \
                (fn,instPath))
        fd = open(fn, 'w')
    except (OSError, IOError, KeyError):
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

def getPassAlgo(authconfigStr):
    """ Reads the auth string and returns a string indicating our desired
        password encoding algorithm.
    """
    if authconfigStr.find("--enablemd5") != -1 or authconfigStr.find("--passalgo=md5") != -1:
        return 'md5'
    elif authconfigStr.find("--passalgo=sha256") != -1:
        return 'sha256'
    elif authconfigStr.find("--passalgo=sha512") != -1:
        return 'sha512'
    else:
        return None

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

def validatePassword(pw, confirm, minlen=6):
    # Do various steps to validate the password
    # Return an error string, or None for no errors
    # If inital checks pass, pwquality will be tested.  Raises
    # from pwquality will pass up to the calling code

    # if both pw and confirm are blank, password is disabled.
    if (pw and not confirm) or (confirm and not pw):
        error = _("You must enter your root password "
                  "and confirm it by typing it a second "
                  "time to continue.")
        return error

    if pw != confirm:
        error = _("The passwords you entered were "
                  "different.  Please try again.")
        return error

    legal = string.digits + string.ascii_letters + string.punctuation + " "
    for letter in pw:
        if letter not in legal:
            error = _("Requested password contains "
                      "non-ASCII characters, which are "
                      "not allowed.")
            return error

    if pw:
        settings = pwquality.PWQSettings()
        settings.read_config()
        settings.minlen = minlen
        settings.check(pw, None, "root")

    return None

class Users:
    def __init__ (self):
        self.admin = libuser.admin()

    def createGroup (self, group_name, **kwargs):
        """Create a new user on the system with the given name.  Optional kwargs:

           gid       -- The GID for the new user.  If none is given, the next
                        available one is used.
           root      -- The directory of the system to create the new user
                        in.  homedir will be interpreted relative to this.
                        Defaults to /mnt/sysimage.
        """

        childpid = os.fork()
        root = kwargs.get("root", "/mnt/sysimage")

        if not childpid:
            if not root in ["","/"]:
                os.chroot(root)
                del(os.environ["LIBUSER_CONF"])

            self.admin = libuser.admin()

            try:
                if self.admin.lookupGroupByName(group_name):
                    os._exit(1)

                groupEnt = self.admin.initGroup(group_name)

                if kwargs.get("gid", -1) >= 0:
                    groupEnt.set(libuser.GIDNUMBER, kwargs["gid"])

                self.admin.addGroup(groupEnt)
                os._exit(0)
            except Exception as e:
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

    def createUser (self, user_name, *args, **kwargs):
        """Create a new user on the system with the given name.  Optional kwargs:

           algo      -- The password algorithm to use in case isCrypted=True.
                        If none is given, the cryptPassword default is used.
           gecos     -- The GECOS information (full name, office, phone, etc.).
                        Defaults to "".
           groups    -- A list of existing group names the user should be
                        added to.  Defaults to [].
           homedir   -- The home directory for the new user.  Defaults to
                        /home/<name>.
           isCrypted -- Is the password kwargs already encrypted?  Defaults
                        to False.
           lock      -- Is the new account locked by default?  Defaults to
                        False.
           password  -- The password.  See isCrypted for how this is interpreted.
           root      -- The directory of the system to create the new user
                        in.  homedir will be interpreted relative to this.
                        Defaults to /mnt/sysimage.
           shell     -- The shell for the new user.  If none is given, the
                        libuser default is used.
           uid       -- The UID for the new user.  If none is given, the next
                        available one is used.
        """
        childpid = os.fork()
        root = kwargs.get("root", "/mnt/sysimage")

        if not childpid:
            if not root in ["","/"]:
                os.chroot(root)
                del(os.environ["LIBUSER_CONF"])

            self.admin = libuser.admin()

            try:
                if self.admin.lookupUserByName(user_name):
                    os._exit(1)

                userEnt = self.admin.initUser(user_name)
                groupEnt = self.admin.initGroup(user_name)

                grpLst = filter(lambda grp: grp,
                                map(lambda name: self.admin.lookupGroupByName(name), kwargs.get("groups", [])))
                userEnt.set(libuser.GIDNUMBER, [groupEnt.get(libuser.GIDNUMBER)[0]] +
                            map(lambda grp: grp.get(libuser.GIDNUMBER)[0], grpLst))

                if kwargs.get("homedir", False):
                    userEnt.set(libuser.HOMEDIRECTORY, kwargs["homedir"])
                else:
                    iutil.mkdirChain(root+'/home')
                    userEnt.set(libuser.HOMEDIRECTORY, "/home/" + user_name)

                if kwargs.get("shell", False):
                    userEnt.set(libuser.LOGINSHELL, kwargs["shell"])

                if kwargs.get("uid", -1) >= 0:
                    userEnt.set(libuser.UIDNUMBER, kwargs["uid"])

                if kwargs.get("gecos", False):
                    userEnt.set(libuser.GECOS, kwargs["gecos"])

                self.admin.addUser(userEnt, mkmailspool=kwargs.get("mkmailspool", True))
                self.admin.addGroup(groupEnt)

                if kwargs.get("password", False):
                    if kwargs.get("isCrypted", False):
                        password = kwargs["password"]
                    else:
                        password = cryptPassword(kwargs["password"], algo=kwargs.get("algo", None))

                    self.admin.setpassUser(userEnt, password, True)

                if kwargs.get("lock", False):
                    self.admin.lockUser(userEnt)

                # Add the user to all the groups they should be part of.
                grpLst.append(self.admin.lookupGroupByName(user_name))
                for grp in grpLst:
                    grp.add(libuser.MEMBERNAME, user_name)
                    self.admin.modifyGroup(grp)

                os._exit(0)
            except Exception as e:
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
            except Exception as e:
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

    def setUserPassword(self, username, password, isCrypted, lock, algo=None):
        user = self.admin.lookupUserByName(username)

        if isCrypted:
            self.admin.setpassUser(user, password, True)
        else:
            self.admin.setpassUser(user, cryptPassword(password, algo=algo), True)

        if lock:
            self.admin.lockUser(user)

        self.admin.modifyUser(user)

    def setRootPassword(self, password, isCrypted=False, isLocked=False, algo=None):
        return self.setUserPassword("root", password, isCrypted, isLocked, algo)
