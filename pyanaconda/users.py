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
from pyanaconda import iutil
import pwquality
from pyanaconda.iutil import strip_accents
from pyanaconda.i18n import _
from pyanaconda.constants import PASSWORD_MIN_LEN

import logging
log = logging.getLogger("anaconda")

def createLuserConf(instPath, algoname='sha512'):
    """ Writes a libuser.conf for instPath.

        This must be called before User() is instantiated the first time
        so that libuser.admin will use the temporary config file.
    """
    createTmp = False
    try:
        fn = os.environ["LIBUSER_CONF"]
        if os.access(fn, os.F_OK):
            log.info("removing libuser.conf at %s", os.getenv("LIBUSER_CONF"))
            os.unlink(fn)
        log.info("created new libuser.conf at %s with instPath=\"%s\"", fn, instPath)
        fd = open(fn, 'w')
    except (OSError, IOError, KeyError):
        createTmp = True

    if createTmp:
        (fp, fn) = tempfile.mkstemp(prefix="libuser.")
        log.info("created new libuser.conf at %s with instPath=\"%s\"", fn, instPath)
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

    for _i in range(saltlen):
        saltstr = saltstr + random.choice (string.letters +
                                           string.digits + './')

    return crypt.crypt (password, saltstr)

def validatePassword(pw, user="root", settings=None):
    """Check the quality of a password.

       This function does three things: given a password and an optional
       username, it will tell if this password can be used at all, how
       strong the password is on a scale of 1-100, and, if the password is
       unusable, why it is unusuable.

       This function uses libpwquality to check the password strength.
       pwquality will raise a PWQError on a weak password, which, honestly,
       is kind of dumb behavior. A weak password isn't exceptional, it's what
       we're asking about! Anyway, this function does not raise PWQError. If
       the password fails the PWQSettings conditions, the first member of the
       return tuple will be False and the second member of the tuple will be 0.

       :param pw: the password to check
       :type pw: string

       :param user: the username for which the password is being set. If no
                    username is provided, "root" will be used. Use user=None
                    to disable the username check.
       :type user: string

       :param settings: an optional PWQSettings object
       :type settings: pwquality.PWQSettings

       :returns: A tuple containing (bool(valid), int(score), str(message))
       :rtype: tuple
    """

    valid = True
    message = None
    strength = 0

    if settings is None:
        # Generate a default PWQSettings once and save it as a member of this function
        if not hasattr(validatePassword, "pwqsettings"):
            validatePassword.pwqsettings = pwquality.PWQSettings()
            validatePassword.pwqsettings.read_config()
            validatePassword.pwqsettings.minlen = PASSWORD_MIN_LEN
        settings = validatePassword.pwqsettings

    legal = string.digits + string.ascii_letters + string.punctuation + " "
    for letter in pw:
        if letter not in legal:
            message = _("Requested password contains "
                      "non-ASCII characters, which are "
                      "not allowed.")
            valid = False
            break

    if valid:
        try:
            strength = settings.check(pw, None, user)
        except pwquality.PWQError as e:
            # Leave valid alone here: the password is weak but can still
            # be accepted.
            # PWQError values are built as a tuple of (int, str)
            message = e[1]

    return (valid, strength, message)

def guess_username(fullname):
    fullname = fullname.split()

    # use last name word (at the end in most of the western countries..)
    if len(fullname) > 0:
        username = fullname[-1].decode("utf-8").lower()
    else:
        username = u""

    # and prefix it with the first name inital
    if len(fullname) > 1:
        username = fullname[0].decode("utf-8")[0].lower() + username

    username = strip_accents(username).encode("utf-8")
    return username

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
                os.chdir("/")
                del(os.environ["LIBUSER_CONF"])

            self.admin = libuser.admin()

            if self.admin.lookupGroupByName(group_name):
                log.error("Group %s already exists, not creating.", group_name)
                os._exit(1)

            groupEnt = self.admin.initGroup(group_name)

            if kwargs.get("gid", -1) >= 0:
                groupEnt.set(libuser.GIDNUMBER, kwargs["gid"])

            try:
                self.admin.addGroup(groupEnt)
            except RuntimeError as e:
                log.critical("Error when creating new group: %s", e)
                os._exit(1)

            os._exit(0)

        try:
            status = os.waitpid(childpid, 0)[1]
        except OSError as e:
            log.critical("exception from waitpid while creating a group: %s %s", e.errno, e.strerror)
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
                        If the password is "" then the account is created
                        with a blank password. If None or False the account will
                        be left in its initial state (locked)
           root      -- The directory of the system to create the new user
                        in.  homedir will be interpreted relative to this.
                        Defaults to /mnt/sysimage.
           shell     -- The shell for the new user.  If none is given, the
                        libuser default is used.
           uid       -- The UID for the new user.  If none is given, the next
                        available one is used.
           gid       -- The GID for the new user.  If none is given, the next
                        available one is used.
        """
        childpid = os.fork()
        root = kwargs.get("root", "/mnt/sysimage")

        if not childpid:
            if not root in ["","/"]:
                os.chroot(root)
                os.chdir("/")
                del(os.environ["LIBUSER_CONF"])

            self.admin = libuser.admin()

            if self.admin.lookupUserByName(user_name):
                log.error("User %s already exists, not creating.", user_name)
                os._exit(1)

            userEnt = self.admin.initUser(user_name)
            groupEnt = self.admin.initGroup(user_name)

            if kwargs.get("gid", -1) >= 0:
                groupEnt.set(libuser.GIDNUMBER, kwargs["gid"])

            grpLst = filter(lambda grp: grp,
                            map(self.admin.lookupGroupByName, kwargs.get("groups", [])))
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

            # need to create home directory for the user or does it already exist?
            # userEnt.get returns lists (usually with a single item)
            mk_homedir = not os.path.exists(userEnt.get(libuser.HOMEDIRECTORY)[0])

            try:
                self.admin.addUser(userEnt, mkmailspool=kwargs.get("mkmailspool", True),
                                   mkhomedir=mk_homedir)
            except RuntimeError as e:
                log.critical("Error when creating new user: %s", e)
                os._exit(1)

            try:
                self.admin.addGroup(groupEnt)
            except RuntimeError as e:
                log.critical("Error when creating new group: %s", e)
                os._exit(1)

            if not mk_homedir:
                try:
                    stats = os.stat(userEnt.get(libuser.HOMEDIRECTORY)[0])
                    orig_uid = stats.st_uid
                    orig_gid = stats.st_gid

                    log.info("Home directory for the user %s already existed, "
                             "fixing the owner.", user_name)
                    # home directory already existed, change owner of it properly
                    iutil.chown_dir_tree(userEnt.get(libuser.HOMEDIRECTORY)[0],
                                         userEnt.get(libuser.UIDNUMBER)[0],
                                         groupEnt.get(libuser.GIDNUMBER)[0],
                                         orig_uid, orig_gid)
                except OSError as e:
                    log.critical("Unable to change owner of existing home directory: %s",
                            os.strerror)
                    os._exit(1)

            pw = kwargs.get("password", False)
            try:
                if pw:
                    if kwargs.get("isCrypted", False):
                        password = kwargs["password"]
                    else:
                        password = cryptPassword(kwargs["password"], algo=kwargs.get("algo", None))
                    self.admin.setpassUser(userEnt, password, True)
                    userEnt.set(libuser.SHADOWLASTCHANGE, "")
                    self.admin.modifyUser(userEnt)
                elif pw == "":
                    # Setup the account with *NO* password
                    self.admin.unlockUser(userEnt)
                    log.info("user account %s setup with no password", user_name)

                if kwargs.get("lock", False):
                    self.admin.lockUser(userEnt)
                    log.info("user account %s locked", user_name)
            # setpassUser raises SystemError on failure, while unlockUser and lockUser
            # raise RuntimeError
            except (RuntimeError, SystemError) as e:
                log.critical("Unable to set password for new user: %s", e)
                os._exit(1)

            # Add the user to all the groups they should be part of.
            grpLst.append(self.admin.lookupGroupByName(user_name))
            try:
                for grp in grpLst:
                    grp.add(libuser.MEMBERNAME, user_name)
                    self.admin.modifyGroup(grp)
            except RuntimeError as e:
                log.critical("Unable to add user to groups: %s", e)
                os._exit(1)

            os._exit(0)

        try:
            status = os.waitpid(childpid, 0)[1]
        except OSError as e:
            log.critical("exception from waitpid while creating a user: %s %s", e.errno, e.strerror)
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
                os.chdir("/")
                del(os.environ["LIBUSER_CONF"])

            self.admin = libuser.admin()

            if self.admin.lookupUserByName(username):
                os._exit(0)
            else:
                os._exit(1)

        try:
            status = os.waitpid(childpid, 0)[1]
        except OSError as e:
            log.critical("exception from waitpid while creating a user: %s %s", e.errno, e.strerror)
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

        user.set(libuser.SHADOWLASTCHANGE, "")
        self.admin.modifyUser(user)

    def setRootPassword(self, password, isCrypted=False, isLocked=False, algo=None):
        return self.setUserPassword("root", password, isCrypted, isLocked, algo)
