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
import tempfile
import os
import os.path
from pyanaconda import iutil
import pwquality
from pyanaconda.iutil import strip_accents
from pyanaconda import constants
from pyanaconda.errors import errorHandler, PasswordCryptError, ERROR_RAISE
from pyanaconda.regexes import USERNAME_VALID, PORTABLE_FS_CHARS
from pyanaconda.i18n import _
import re

import logging
log = logging.getLogger("anaconda")


def createLuserConf(instPath, algoname='sha512'):
    """ Writes a libuser.conf for instPath.

        This must be called before User() is instantiated the first time
        so that libuser.admin will use the temporary config file.
    """

    # If LIBUSER_CONF is not set, create a new temporary file
    if "LIBUSER_CONF" not in os.environ:
        (fp, fn) = tempfile.mkstemp(prefix="libuser.")
        log.info("created new libuser.conf at %s with instPath=\"%s\"", fn, instPath)
        fd = os.fdopen(fp, "w")
        # This is only ok if createLuserConf is first called before threads are started
        os.environ["LIBUSER_CONF"] = fn # pylint: disable=environment-modify
    else:
        fn = os.environ["LIBUSER_CONF"]
        log.info("Clearing libuser.conf at %s", fn)
        fd = open(fn, "w")

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

    # Import login.defs if installed
    if os.path.exists(os.path.normpath(instPath + "/etc/login.defs")):
        buf += """
[import]
login_defs = %(instPath)s/etc/login.defs
""" % {"instPath": instPath}


    fd.write(buf)
    fd.close()

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
    if algo not in salts:
        algo = 'sha512'

    cryptpw = iutil.encrypt_password(password, salts[algo], 16)
    if cryptpw is None:
        exn = PasswordCryptError(algo=algo)
        if errorHandler.cb(exn) == ERROR_RAISE:
            raise exn

    return cryptpw

class PwqualitySettingsCache(object):
    """Cache for libpwquality settings used for password validation.

    Libpwquality settings instantiation is probably not exactly cheap
    and we might need the settings for checking every password (even when
    it is being typed by the user) so it makes sense to cache the objects
    for reuse. As there might be multiple active policies for different
    passwords we need to be able to cache multiple policies based on
    minimum password length, as we don't input anything else to libpwquality
    than minimum password length and the password itself.
    """
    def __init__(self):
        self._pwq_settings = {}

    def get_settings_by_minlen(self, minlen):
        settings = self._pwq_settings.get(minlen)
        if settings is None:
            settings = pwquality.PWQSettings()
            settings.read_config()
            settings.minlen = minlen
            self._pwq_settings[minlen] = settings
        return settings

pwquality_settings_cache = PwqualitySettingsCache()

def validatePassword(check_request):
    """Check the quality of a password.

       This function does this:
       - given a password and an optional parameters
       - it will tell if this password can be used at all (score >0)
       - how strong the password approximately is on a scale of 1-100
       - and, if the password is unusable, why it is unusable.

       This function uses libpwquality to check the password strength.
       Pwquality will raise a PWQError on a weak password but this function does
       not pass that forward.
       If the password fails the PWQSettings conditions, the score will be set to 0
       and the error message will contain the reason why the password is bad.

       :param check_request: a password check request wrapper
       :type check_request: a PasswordCheckRequest instance
       :returns: a password check result wrapper
       :rtype: a PasswordCheckResult instance

       The check_request has the following properties:

       * password - the password to be checked

       * username - the username for which the password is being set. If no
                    username is provided, "root" will be used. Use user=None
                    to disable the username check.

       * minimum_length - Minimum acceptable password length.
       * empty_ok - If the password can be empty.
       * pwquality_settings - an optional PWQSettings object
    """

    length_ok = False
    error_message = None
    pw_quality = 0
    if check_request.pwquality_settings:
        # the request supplies its own pwquality settings
        settings = check_request.pwquality_settings
    else:
        # use default settings for current minlen
        settings = pwquality_settings_cache.get_settings_by_minlen(check_request.minimum_length)

    try:
        # lets run the password through libpwquality
        pw_quality = settings.check(check_request.password, None, check_request.username)
    except pwquality.PWQError as e:
        # Leave valid alone here: the password is weak but can still
        # be accepted.
        # PWQError values are built as a tuple of (int, str)
        error_message = e.args[1]

    if check_request.empty_ok:
        # if we are OK with empty passwords, then empty passwords are also fine length wise
        length_ok = len(check_request.password) >= check_request.minimum_length or not check_request.password
    else:
        length_ok = len(check_request.password) >= check_request.minimum_length

    if not check_request.password:
        if check_request.empty_ok:
            pw_score = 1
        else:
            pw_score = 0
        status_text = _(constants.PASSWORD_STATUS_EMPTY)
    elif not length_ok:
        pw_score = 0
        status_text = _(constants.PASSWORD_STATUS_TOO_SHORT)
        # If the password is too short replace the libpwquality error
        # message with a generic "password is too short" message.
        # This is because the error messages returned by libpwquality
        # for short passwords don't make much sense.
        error_message = _(constants.PASSWORD_TOO_SHORT) % {"password": check_request.name_of_password}
    elif error_message:
        pw_score = 1
        status_text = _(constants.PASSWORD_STATUS_WEAK)
    elif pw_quality < 30:
        pw_score = 2
        status_text = _(constants.PASSWORD_STATUS_FAIR)
    elif pw_quality < 70:
        pw_score = 3
        status_text = _(constants.PASSWORD_STATUS_GOOD)
    else:
        pw_score = 4
        status_text = _(constants.PASSWORD_STATUS_STRONG)

    return PasswordCheckResult(check_request=check_request,
                               password_score=pw_score,
                               status_text=status_text,
                               password_quality=pw_quality,
                               error_message=error_message,
                               length_ok=length_ok)

def check_username(name):
    if name in os.listdir("/") + ["root", "home", "daemon", "system"]:
        return (False, _("User name is reserved for system: %s") % name)

    if name.startswith("-"):
        return (False, _("User name cannot start with '-' character"))

    # Final '$' allowed for Samba
    if name.endswith("$"):
        sname = name[:-1]
    else:
        sname = name
    match = re.search(r'[^' + PORTABLE_FS_CHARS + r']', sname)
    if match:
        return (False, _("User name cannot contain character: '%s'") % match.group())

    if len(name) > 32:
        return (False, _("User name must be shorter than 33 characters"))

    # Check also with THE regexp to be sure
    if not USERNAME_VALID.match(name):
        return (False, None)

    return (True, None)

def guess_username(fullname):
    fullname = fullname.split()

    # use last name word (at the end in most of the western countries..)
    if len(fullname) > 0:
        username = fullname[-1].decode("utf-8").lower()
    else:
        username = u""

    # and prefix it with the first name initial
    if len(fullname) > 1:
        username = fullname[0].decode("utf-8")[0].lower() + username

    username = strip_accents(username).encode("utf-8")
    return username


class PasswordCheckRequest(object):
    """A wrapper for a password check request.

    This in general means the password to be checked as well as its validation criteria
    such as minimum length, if it can be empty, etc.
    """

    def __init__(self, password,
                 username='root',
                 minimum_length=None,
                 empty_ok=False,
                 pwquality_settings=None,
                 name_of_password=None
                 ):

        # use default minimal password lenght
        # if it is not set
        if minimum_length is None:
            minimum_length = constants.PASSWORD_MIN_LEN
        # just use "password" if no password name is specified
        if name_of_password is None:
            name_of_password = _(constants.NAME_OF_PASSWORD)

        self._password = password
        self._username = username
        self._minimum_length = minimum_length
        self._empty_ok = empty_ok
        self._pwquality_settings = pwquality_settings
        self._name_of_password = name_of_password

    @property
    def password(self):
        """Password string to be checked.

        :returns: password string for the check
        :rtype: str
        """
        return self._password

    @property
    def username(self):
        """The username for which the password is being set.

        If no username is provided, "root" will be used.
        Use username=None to disable the username check.

        :returns: username corresponding to the password
        :rtype: str or None
        """
        return self._username

    @property
    def minimum_length(self):
        """Minimum password length.

        If not set the Anaconda-wide default is used (6 characters).

        :returns: minimum password length
        :rtype: int
        """
        return self._minimum_length

    @property
    def empty_ok(self):
        """Reports if an empty password is considered acceptable.

        By default empty passwords are not considered acceptable.

        :returns: if empty passwords are acceptable
        :rtype: bool
        """
        return self._empty_ok

    @property
    def pwquality_settings(self):
        """Settings for libpwquality (if any).

        :returns: libpwquality settings
        :rtype: pwquality settings object or None
        """
        return self._pwquality_settings

    @property
    def name_of_password(self):
        """Specifies how should the password be called in error messages.

        In some cases we are checking a "password", but at other times it
        might be a "passphrase", etc.

        :returns: name of the password
        :rtype: str
        """
        return self._name_of_password


class PasswordCheckResult(object):
    """A wrapper for results for a password check."""

    def __init__(self,
                 check_request,
                 password_score,
                 status_text,
                 password_quality,
                 error_message,
                 length_ok):
        self._check_request = check_request
        self._password_score = password_score
        self._status_text = status_text
        self._password_quality = password_quality
        self._error_message = error_message
        self._length_ok = length_ok

    @property
    def check_request(self):
        """The check request used to generate this check result object.

        Can be used to get the password text and checking parameters
        for this password check result.

        :returns: the password check request that triggered this password check result
        :rtype: a PasswordCheckRequest instance
        """

        return self._check_request

    @property
    def password_score(self):
        """A high-level integer score indicating password quality.

        Goes from 0 (invalid password) to 4 (valid & very strong password).
        Mainly used to drive the password quality indicator in the GUI.
        """
        return self._password_score

    @property
    def status_text(self):
        """A short overall status message describing the password.

        Generally something like "Good.", "Too short.", "Empty.", etc.

        :rtype: short status message
        :rtype: str
        """
        return self._status_text

    @property
    def password_quality(self):
        """More fine grained integer indicator describing password strength.

        This basically exports the quality score assigned by libpwquality to the password,
        which goes from 0 (unacceptable password) to 100 (strong password).

        Note of caution though about using the password quality value - it is intended
        mainly for on-line password strength hints, not for long-term stability,
        even just because password dictionary updates and other peculiarities of password
        strength judging.

        :returns: password quality value as reported by libpwquality
        :rtype: int
        """
        return self._password_quality

    @property
    def error_message(self):
        """Option error message describing white the password is bad in detail.

        Mostly direct error output from libpwquality supplied when libpwquality
        rejects the password. There is currently only non-pwquality error message
        which is returned when the password is too short, overriding error messages
        from libpwquality which become confusing in such a case.

        :returns: why the password is bad (provided it is bad) or None
        :rtype: str or None
        """
        return self._error_message

    @property
    def length_ok(self):
        """Reports if the password is long enough.

        :returns: if the password is long enough
        :rtype: bool
        """
        return self._length_ok


class Users:
    def __init__(self):
        self.admin = libuser.admin()

    def _prepareChroot(self, root):
        # Unfortunately libuser doesn't have an API to operate on a
        # chroot, so we hack it here by forking a child and calling
        # chroot() in that child's context.

        childpid = os.fork()
        if not childpid:
            if not root in ["","/"]:
                os.chroot(root)
                os.chdir("/")
                # This is ok because it's after a fork
                del(os.environ["LIBUSER_CONF"]) # pylint: disable=environment-modify

            self.admin = libuser.admin()

        return childpid

    def _finishChroot(self, childpid):
        assert childpid > 0
        try:
            status = iutil.eintr_retry_call(os.waitpid, childpid, 0)[1]
        except OSError as e:
            log.critical("exception from waitpid: %s %s", e.errno, e.strerror)
            return False

        if os.WIFEXITED(status) and (os.WEXITSTATUS(status) == 0):
            return True
        else:
            return False

    def createGroup (self, group_name, **kwargs):
        """Create a new user on the system with the given name.  Optional kwargs:

           gid       -- The GID for the new user.  If none is given, the next
                        available one is used.
           root      -- The directory of the system to create the new user
                        in.  homedir will be interpreted relative to this.
                        Defaults to /mnt/sysimage.
        """

        childpid = self._prepareChroot(kwargs.get("root", iutil.getSysroot()))
        if childpid == 0:
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
        else:
            return self._finishChroot(childpid)

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
        childpid = self._prepareChroot(kwargs.get("root", iutil.getSysroot()))
        if childpid == 0:
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

            homedir = kwargs.get("homedir", None)
            if not homedir:
                homedir = "/home/" + user_name
            # libuser expects the parent directory tree to exist.
            parent_dir = iutil.parent_dir(homedir)
            if parent_dir:
                iutil.mkdirChain(parent_dir)
            userEnt.set(libuser.HOMEDIRECTORY, homedir)

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
                             "fixing the owner and SELinux context.", user_name)
                    # home directory already existed, change owner of it properly
                    iutil.chown_dir_tree(userEnt.get(libuser.HOMEDIRECTORY)[0],
                                         userEnt.get(libuser.UIDNUMBER)[0],
                                         groupEnt.get(libuser.GIDNUMBER)[0],
                                         orig_uid, orig_gid)
                    iutil.execWithRedirect("restorecon",
                                           ["-r", userEnt.get(libuser.HOMEDIRECTORY)[0]])
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
        else:
            return self._finishChroot(childpid)

    def checkUserExists(self, username, root=None):
        childpid = self._prepareChroot(root)

        if childpid == 0:
            if self.admin.lookupUserByName(username):
                os._exit(0)
            else:
                os._exit(1)
        else:
            return self._finishChroot(childpid)

    def setUserPassword(self, username, password, isCrypted, lock, algo=None):
        user = self.admin.lookupUserByName(username)

        if isCrypted:
            self.admin.setpassUser(user, password, True)
        else:
            self.admin.setpassUser(user, cryptPassword(password, algo=algo), True)

        if lock:
            self.admin.lockUser(user)

        user.set(libuser.SHADOWLASTCHANGE, "")
        return self.admin.modifyUser(user)

    def setRootPassword(self, password, isCrypted=False, isLocked=False, algo=None):
        return self.setUserPassword("root", password, isCrypted, isLocked, algo)

    def setUserSshKey(self, username, key, **kwargs):
        childpid = self._prepareChroot(kwargs.get("root", iutil.getSysroot()))

        if childpid == 0:
            user = self.admin.lookupUserByName(username)
            if not user:
                log.error("setUserSshKey: user %s does not exist", username)
                os._exit(1)

            homedir = user.get(libuser.HOMEDIRECTORY)[0]
            if not os.path.exists(homedir):
                log.error("setUserSshKey: home directory for %s does not exist", username)
                os._exit(1)

            sshdir = os.path.join(homedir, ".ssh")
            if not os.path.isdir(sshdir):
                os.mkdir(sshdir, 0o700)
                iutil.eintr_retry_call(os.chown, sshdir, user.get(libuser.UIDNUMBER)[0], user.get(libuser.GIDNUMBER)[0])

            authfile = os.path.join(sshdir, "authorized_keys")
            authfile_existed = os.path.exists(authfile)
            with open(authfile, "a") as f:
                f.write(key + "\n")

            # Only change mode and ownership if we created it
            if not authfile_existed:
                iutil.eintr_retry_call(os.chmod, authfile, 0o600)
                iutil.eintr_retry_call(os.chown, authfile, user.get(libuser.UIDNUMBER)[0], user.get(libuser.GIDNUMBER)[0])
                iutil.execWithRedirect("restorecon", ["-r", sshdir])
            os._exit(0)
        else:
            return self._finishChroot(childpid)
