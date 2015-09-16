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

# Used for ascii_letters and digits constants
import string # pylint: disable=deprecated-module
import crypt
import random
import os
import os.path
import subprocess
from contextlib import contextmanager
from pyanaconda import iutil
import pwquality
from pyanaconda.iutil import strip_accents
from pyanaconda.iutil import open   # pylint: disable=redefined-builtin
from pyanaconda.constants import PASSWORD_MIN_LEN
from pyanaconda.errors import errorHandler, PasswordCryptError, ERROR_RAISE

import logging
log = logging.getLogger("anaconda")

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
        saltstr = saltstr + random.choice(string.ascii_letters +
                                          string.digits + './')

    cryptpw = crypt.crypt(password, saltstr)
    if cryptpw is None:
        exn = PasswordCryptError(algo=algo)
        if errorHandler.cb(exn) == ERROR_RAISE:
            raise exn

    return cryptpw

def validatePassword(pw, user="root", settings=None, minlen=None):
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
       :param int minlen: Minimum acceptable password length. If not passed,
                          use the default length from PASSWORD_MIN_LEN

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

    if minlen is not None:
        settings.minlen = minlen

    if valid:
        try:
            strength = settings.check(pw, None, user)
        except pwquality.PWQError as e:
            # Leave valid alone here: the password is weak but can still
            # be accepted.
            # PWQError values are built as a tuple of (int, str)
            message = e.args[1]

    return (valid, strength, message)

def guess_username(fullname):
    fullname = fullname.split()

    # use last name word (at the end in most of the western countries..)
    if len(fullname) > 0:
        username = fullname[-1].lower()
    else:
        username = u""

    # and prefix it with the first name initial
    if len(fullname) > 1:
        username = fullname[0][0].lower() + username

    username = strip_accents(username)
    return username

class Users(object):
    def _getpwnam(self, user_name, root):
        """Like pwd.getpwnam, but is able to use a different root.

           Also just returns the pwd structure as a list, because of laziness.
        """
        with open(root + "/etc/passwd", "r") as f:
            for line in f:
                fields = line.split(":")
                if fields[0] == user_name:
                    return fields

        return None

    def _groupExists(self, group_name, root):
        """Returns whether a group with the given name already exists."""
        with open(root + "/etc/group", "r") as f:
            for line in f:
                if line.split(":")[0] == group_name:
                    return True

        return False

    @contextmanager
    def _ensureLoginDefs(self, root):
        """Runs a command after creating /etc/login.defs, if necessary.

           groupadd and useradd need login.defs to exist in the chroot, and if
           someone is doing a cloud image install or some kind of --nocore thing
           it may not. An empty one is ok, though. If it's missing, create it,
           run the command, then clean it up.
        """
        login_defs_path = root + '/etc/login.defs'
        if not os.path.exists(login_defs_path):
            open(login_defs_path, "w").close()
            login_defs_created = True
        else:
            login_defs_created = False

        yield

        if login_defs_created:
            os.unlink(login_defs_path)

    def createGroup(self, group_name, **kwargs):
        """Create a new user on the system with the given name.  Optional kwargs:

           :keyword int gid: The GID for the new user. If none is given, the next available one is used.
           :keyword str root: The directory of the system to create the new user in.
                          homedir will be interpreted relative to this. Defaults
                          to iutil.getSysroot().
        """
        root = kwargs.get("root", iutil.getSysroot())

        if self._groupExists(group_name, root):
            # If the group already exists, skip it
            return

        args = ["-R", root]
        if kwargs.get("gid") is not None:
            args.extend(["-g", str(kwargs["gid"])])

        args.append(group_name)
        with self._ensureLoginDefs(root):
            status = iutil.execWithRedirect("groupadd", args)

        if status == 4:
            raise ValueError("GID %s already exists" % kwargs.get("gid"))
        elif status == 9:
            raise ValueError("Group %s already exists" % group_name)
        elif status != 0:
            raise OSError("Unable to create group %s: status=%s" % (group_name, status))

    def createUser(self, user_name, *args, **kwargs):
        """Create a new user on the system with the given name.  Optional kwargs:

           :keyword str algo: The password algorithm to use in case isCrypted=True.
                              If none is given, the cryptPassword default is used.
           :keyword str gecos: The GECOS information (full name, office, phone, etc.).
                               Defaults to "".
           :keyword groups: A list of existing group names the user should be
                            added to.  Defaults to [].
           :type groups: list of str
           :keyword str homedir: The home directory for the new user.  Defaults to
                                 /home/<name>.
           :keyword bool isCrypted: Is the password kwargs already encrypted?  Defaults
                                    to False.
           :keyword bool lock: Is the new account locked by default?  Defaults to
                               False.
           :keyword str password: The password.  See isCrypted for how this is interpreted.
                                  If the password is "" then the account is created
                                  with a blank password. If None or False the account will
                                  be left in its initial state (locked)
           :keyword str root: The directory of the system to create the new user
                              in.  homedir will be interpreted relative to this.
                              Defaults to iutil.getSysroot().
           :keyword str shell: The shell for the new user.  If none is given, the
                               login.defs default is used.
           :keyword int uid: The UID for the new user.  If none is given, the next
                             available one is used.
           :keyword int gid: The GID for the new user.  If none is given, the next
                             available one is used.
        """

        root = kwargs.get("root", iutil.getSysroot())

        if self.checkUserExists(user_name, root):
            raise ValueError("User %s already exists" % user_name)

        args = ["-R", root]

        # If a specific gid is requested, create the user group with that GID.
        # Otherwise let useradd do it automatically.
        if kwargs.get("gid", None):
            self.createGroup(user_name, gid=kwargs['gid'], root=root)
            args.extend(['-g', str(kwargs['gid'])])
        else:
            args.append('-U')

        if kwargs.get("groups"):
            args.extend(['-G', ",".join(kwargs["groups"])])

        if kwargs.get("homedir"):
            homedir = kwargs["homedir"]
        else:
            homedir = "/home/" + user_name

        # useradd expects the parent directory tree to exist.
        parent_dir = iutil.parent_dir(root + homedir)

        # If root + homedir came out to "/", such as if we're creating the sshpw user,
        # parent_dir will be empty. Don't create that.
        if parent_dir:
            iutil.mkdirChain(parent_dir)

        args.extend(["-d", homedir])

        # Check whether the directory exists or if useradd should create it
        mk_homedir = not os.path.exists(root + homedir)
        if mk_homedir:
            args.append("-m")
        else:
            args.append("-M")

        if kwargs.get("shell"):
            args.extend(["-s", kwargs["shell"]])

        if kwargs.get("uid"):
            args.extend(["-u", str(kwargs["uid"])])

        if kwargs.get("gecos"):
            args.extend(["-c", kwargs["gecos"]])

        args.append(user_name)
        with self._ensureLoginDefs(root):
            status = iutil.execWithRedirect("useradd", args)

        if status == 4:
            raise ValueError("UID %s already exists" % kwargs.get("uid"))
        elif status == 6:
            raise ValueError("Invalid groups %s" % kwargs.get("groups", []))
        elif status == 9:
            raise ValueError("User %s already exists" % user_name)
        elif status != 0:
            raise OSError("Unable to create user %s: status=%s" % (user_name, status))

        if not mk_homedir:
            try:
                stats = os.stat(root + homedir)
                orig_uid = stats.st_uid
                orig_gid = stats.st_gid

                # Gett the UID and GID of the created user
                pwent = self._getpwnam(user_name, root)

                log.info("Home directory for the user %s already existed, "
                         "fixing the owner and SELinux context.", user_name)
                # home directory already existed, change owner of it properly
                iutil.chown_dir_tree(root + homedir,
                                     int(pwent[2]), int(pwent[3]),
                                     orig_uid, orig_gid)
                iutil.execWithRedirect("restorecon", ["-r", root + homedir])
            except OSError as e:
                log.critical("Unable to change owner of existing home directory: %s", e.strerror)
                raise

        pw = kwargs.get("password", False)
        crypted = kwargs.get("isCrypted", False)
        algo = kwargs.get("algo", None)
        lock = kwargs.get("lock", False)

        self.setUserPassword(user_name, pw, crypted, lock, algo, root)

    def checkUserExists(self, username, root=None):
        if self._getpwnam(username, root):
            return True

        return False

    def setUserPassword(self, username, password, isCrypted, lock, algo=None, root="/"):
        # Only set the password if it is a string, including the empty string.
        # Otherwise leave it alone (defaults to locked for new users) and reset sp_lstchg
        if password or password == "":
            if password == "":
                log.info("user account %s setup with no password", username)
            elif not isCrypted:
                password = cryptPassword(password, algo)

            if lock:
                password = "!" + password
                log.info("user account %s locked", username)

            proc = iutil.startProgram(["chpasswd", "-R", root, "-e"], stdin=subprocess.PIPE)
            proc.communicate(("%s:%s\n" % (username, password)).encode("utf-8"))
            if proc.returncode != 0:
                raise OSError("Unable to set password for new user: status=%s" % proc.returncode)

        # Reset sp_lstchg to an empty string. On systems with no rtc, this
        # field can be set to 0, which has a special meaning that the password
        # must be reset on the next login.
        iutil.execWithRedirect("chage", ["-R", root, "-d", "", username])

    def setRootPassword(self, password, isCrypted=False, isLocked=False, algo=None, root="/"):
        return self.setUserPassword("root", password, isCrypted, isLocked, algo, root)

    def setUserSshKey(self, username, key, **kwargs):
        root = kwargs.get("root", iutil.getSysroot())

        pwent = self._getpwnam(username, root)
        if not pwent:
            raise ValueError("setUserSshKey: user %s does not exist" % username)

        homedir = root + pwent[5]
        if not os.path.exists(homedir):
            log.error("setUserSshKey: home directory for %s does not exist", username)
            raise ValueError("setUserSshKey: home directory for %s does not exist" % username)

        uid = pwent[2]
        gid = pwent[3]

        sshdir = os.path.join(homedir, ".ssh")
        if not os.path.isdir(sshdir):
            os.mkdir(sshdir, 0o700)
            iutil.eintr_retry_call(os.chown, sshdir, int(uid), int(gid))

        authfile = os.path.join(sshdir, "authorized_keys")
        authfile_existed = os.path.exists(authfile)
        with iutil.open_with_perm(authfile, "a", 0o600) as f:
            f.write(key + "\n")

        # Only change ownership if we created it
        if not authfile_existed:
            iutil.eintr_retry_call(os.chown, authfile, int(uid), int(gid))
            iutil.execWithRedirect("restorecon", ["-r", sshdir])
