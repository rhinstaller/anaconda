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

import os
import os.path
import re
import subprocess
from pathlib import Path
from random import SystemRandom as sr

from pyanaconda.core import util
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.i18n import _
from pyanaconda.core.path import make_directories, open_with_perm
from pyanaconda.core.regexes import (
    GROUPLIST_FANCY_PARSE,
    GROUPLIST_SIMPLE_VALID,
    NAME_VALID,
    PORTABLE_FS_CHARS,
)
from pyanaconda.core.string import strip_accents

try:
    # Use the standalone (not deprecated) package when available
    import crypt_r
except ImportError:
    # Fallback to the deprecated standard library module
    import crypt as crypt_r  # pylint: disable=deprecated-module

from pyanaconda.anaconda_loggers import get_module_logger

log = get_module_logger(__name__)


def crypt_password(password):
    """Crypt a password.

    Process a password with appropriate salted one-way algorithm.

    :param str password: password to be crypted
    :returns: crypted representation of the original password
    :rtype: str
    """
    # yescrypt is not supported by Python's crypt module,
    # so we need to generate the setting ourselves
    b64 = "./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    setting = "$y$j9T$" + "".join(sr().choice(b64) for _sc in range(24))

    # and try to compute the password hash using our yescrypt setting
    try:
        cryptpw = crypt_r.crypt(password, setting)

    # Fallback to sha512crypt, if yescrypt is not supported
    except OSError:
        log.info("yescrypt is not supported, falling back to sha512crypt")
        try:
            cryptpw = crypt_r.crypt(password, crypt_r.METHOD_SHA512)
        except OSError as exc:
            raise RuntimeError(_(
                "Unable to encrypt password: unsupported "
                "algorithm {}").format(crypt_r.METHOD_SHA512)
            ) from exc

    return cryptpw


def check_username(name):
    """Check if given username is valid.

    :param: user or group name to check
    :returns: a (success, translated-error-message) tuple
    :rtype: (bool, str or None)
    """

    # Check reserved names.
    reserved_names = [
        # passwd contents from setup.rpm
        "root",
        "bin",
        "daemon",
        "adm",
        "lp",
        "sync",
        "shutdown",
        "halt",
        "mail",
        "operator",
        "games",
        "ftp",
        "nobody",
        # from older version of the function
        "home",
        "system",
    ]
    if name in os.listdir("/") + reserved_names:
        return False, _("User name is reserved for system: %s") % name

    return is_valid_name(name)


def check_grouplist(group_list):
    """Check a group list for validity.

    :param str group_list: a string representation of a group list to be checked
    :returns: a (success, translated-error-message) tuple
    :rtype: (bool, str or None)
    """
    # Check empty list.
    if group_list == "":
        return True, None

    # Check the group names.
    for group_name in group_list.split(","):
        valid, message = check_groupname(group_name.strip())
        if not valid:
            return valid, message

    # Check the regexp to be sure
    if not GROUPLIST_SIMPLE_VALID.match(group_list):
        return False, _("Either a group name in the group list is invalid "
                        "or groups are not separated by a comma.")

    return True, None


def check_groupname(name):
    """Check if group name is valid.

    :param: group name to check
    :returns: a (success, translated-error-message) tuple
    :rtype: (bool, str or None)
    """
    return is_valid_name(name)


def is_valid_name(name):
    """Check if given name is valid for either a group or user.

    This method basically checks all the rules that are the same
    for both user and group names.

    There is a separate check_username() method, that adds some
    username specific checks on top of this.

    :param: user or group name to check
    :returns: a (success, translated-error-message) tuple
    :rtype: (bool, str or None)
    """

    # Check shadow-utils rules.
    if name.startswith("-"):
        return False, _("Name cannot start with '-' character.")

    if name in [".", ".."]:
        return False, _("Name '%s' is not allowed.") % name

    if name.isdigit():
        return False, _("Fully numeric name is not allowed.")

    # Final '$' allowed for Samba
    if name == "$":
        return False, _("Name '$' is not allowed.")

    if name.endswith("$"):
        sname = name[:-1]
    else:
        sname = name

    match = re.search(r'[^' + PORTABLE_FS_CHARS + r']', sname)

    if match:
        return False, _("Name cannot contain character: '%s'") % match.group()

    if len(name) > 32:
        return False, _("Name must be shorter than 33 characters.")

    # Check also with THE regexp to be sure
    if not NAME_VALID.match(name):
        return False, _("Name '%s' is invalid.") % name

    return True, None


def guess_username(fullname):
    """Guess username from full user name.

    :param str fullname: full user name
    :returns: guessed, hopefully suitable, username or empty string if no valid username can be generated
    :rtype: str
    """
    fullname = fullname.split()

    # use last name word (at the end in most of the western countries..)
    if len(fullname) > 0:
        username = fullname[-1].lower()
    else:
        username = ""

    # and prefix it with the first name initial
    if len(fullname) > 1:
        username = fullname[0][0].lower() + username

    username = strip_accents(username)

    # Validate the generated username - return empty string if invalid
    if username:
        is_valid, _ = is_valid_name(username)
        if not is_valid:
            return ""

    return username


def _getpwnam(user_name, root):
    """Like pwd.getpwnam, but is able to use a different root.

    Also just returns the pwd structure as a list, because of laziness.

    :param str user_name: user name
    :param str root: filesystem root for the operation
    """
    with open(root + "/etc/passwd", "r") as f:
        for line in f:
            fields = line.split(":")
            if fields[0] == user_name:
                return fields

    return None


def _getgrnam(group_name, root):
    """Like grp.getgrnam, but able to use a different root.

    Just returns the grp structure as a list, same reason as above.

    :param str group_name: group name
    :param str root: filesystem root for the operation
    """
    with open(root + "/etc/group", "r") as f:
        for line in f:
            fields = line.split(":")
            if fields[0] == group_name:
                return fields

    return None


def _getgrgid(gid, root):
    """Like grp.getgrgid, but able to use a different root.

    Just returns the fields as a list of strings.

    :param int git: group id
    :param str root: filesystem root for the operation
    """
    # Convert the probably-int GID to a string
    gid = str(gid)

    with open(root + "/etc/group", "r") as f:
        for line in f:
            fields = line.split(":")
            if fields[2] == gid:
                return fields

    return None


def create_group(group_name, gid=None, root=None):
    """Create a new user on the system with the given name.

    :param int gid: The GID for the new user. If none is given, the next available one is used.
    :param str root: The directory of the system to create the new user in.
                     homedir will be interpreted relative to this. Defaults
                     to conf.target.system_root.
    """
    if root is None:
        root = conf.target.system_root

    if _getgrnam(group_name, root):
        raise ValueError("Group %s already exists" % group_name)

    args = ["-R", root]
    if gid is not None:
        args.extend(["-g", str(gid)])

    args.append(group_name)
    status = util.execWithRedirect("groupadd", args)

    if status == 4:
        raise ValueError("GID %s already exists" % gid)
    elif status == 9:
        raise ValueError("Group %s already exists" % group_name)
    elif status != 0:
        raise OSError("Unable to create group %s: status=%s" % (group_name, status))


def _reown_homedir(root, homedir, username):
    """Home directory already existed, change owner of it properly.

    Change owner (uid and gid) of the files and directories under the given
    directory tree (recursively).

    :param str root: path to the system root (eg. /mnt/sysroot)
    :param str homedir: path to the user's home dir within root (eg. /home/tom)
    :param str username: name of the user (eg. tom)
    """
    try:
        # Get the UID and GID of user on previous system
        stats = os.stat(root + homedir)
        orig_uid = stats.st_uid
        orig_gid = stats.st_gid

        # Get the UID and GID of the created user on new system
        pwent = _getpwnam(username, root)
        uid = int(pwent[2])
        gid = int(pwent[3])

        # Change owner UID and GID where matching
        from_ids = "--from={}:{}".format(orig_uid, orig_gid)
        to_ids = "{}:{}".format(uid, gid)
        util.execWithRedirect("chown", ["--recursive", "--no-dereference",
                                        from_ids, to_ids, root + homedir])

        # Restore also SELinux contexts
        util.restorecon([homedir], root=root)

    except OSError as e:
        log.critical("Unable to change owner of existing home directory: %s", e.strerror)
        raise


def create_user(username, password=False, is_crypted=False, lock=False,
                homedir=None, uid=None, gid=None, groups=None, shell=None, gecos="",
                root=None):
    """Create a new user on the system with the given name.

    :param str username: The username for the new user to be created.
    :param str password: The password. See is_crypted for how this is interpreted.
                         If the password is "" then the account is created
                         with a blank password. If None or False the account will
                         be left in its initial state (locked)
    :param bool is_crypted: Is the password already encrypted? Defaults to False.
    :param bool lock: Is the new account locked by default?
                      Defaults to False.
    :param str homedir: The home directory for the new user.
                        Defaults to /home/<name>.
    :param int uid: The UID for the new user.
                    If none is given, the next available one is used.
    :param int gid: The GID for the new user.
                    If none is given, the next available one is used.
    :param groups: A list of group names the user should be added to.
                   Each group name can contain an optional GID in parenthesis,
                   such as "groupName(5000)".
                   Defaults to [].
    :type groups: list of str
    :param str shell: The shell for the new user.
                      If none is given, the login.defs default is used.
    :param str gecos: The GECOS information (full name, office, phone, etc.).
                      Defaults to "".
    :param str root: The directory of the system to create the new user in.
                     The homedir option will be interpreted relative to this.
                     Defaults to conf.target.system_root.
    """

    # resolve the optional arguments that need a default that can't be
    # reasonably set in the function signature
    if not homedir:
        homedir = "/home/" + username

    if groups is None:
        groups = []

    if root is None:
        root = conf.target.system_root

    if check_user_exists(username, root):
        raise ValueError("User %s already exists" % username)

    args = ["-R", root]

    # Split the groups argument into a list of (username, gid or None) tuples
    # the gid, if any, is a string since that makes things simpler
    group_gids = [GROUPLIST_FANCY_PARSE.match(group).groups() for group in groups]

    # If a specific gid is requested:
    #   - check if a group already exists with that GID. i.e., the user's
    #     GID should refer to a system group, such as users. If so, just set
    #     the GID.
    #   - check if a new group is requested with that GID. If so, set the GID
    #     and let the block below create the actual group.
    #   - if neither of those are true, create a new user group with the requested
    #     GID
    # otherwise use -U to create a new user group with the next available GID.
    if gid:
        if not _getgrgid(gid, root) and not any(one_gid[1] == str(gid) for one_gid in group_gids):
            create_group(username, gid=gid, root=root)

        args.extend(['-g', str(gid)])
    else:
        args.append('-U')

    # If any requested groups do not exist, create them.
    group_list = []
    for group_name, group_id in group_gids:
        existing_group = _getgrnam(group_name, root)

        # Check for a bad GID request
        if group_id and existing_group and group_id != existing_group[2]:
            raise ValueError("Group %s already exists with GID %s" % (group_name, group_id))

        # Otherwise, create the group if it does not already exist
        if not existing_group:
            create_group(group_name, gid=group_id, root=root)
        group_list.append(group_name)

    if group_list:
        args.extend(['-G', ",".join(group_list)])

    # useradd expects the parent directory tree to exist.
    parent_dir = Path(root + homedir).resolve().parent

    # If root + homedir came out to "/", such as if we're creating the sshpw user,
    # parent_dir will be empty. Don't create that.
    if parent_dir != Path("/"):
        make_directories(str(parent_dir))

    args.extend(["-d", homedir])

    # Check whether the directory exists or if useradd should create it
    mk_homedir = not os.path.exists(root + homedir)
    if mk_homedir:
        args.append("-m")
    else:
        args.append("-M")

    if shell:
        args.extend(["-s", shell])

    if uid:
        args.extend(["-u", str(uid)])

    if gecos:
        args.extend(["-c", gecos])

    args.append(username)
    status = util.execWithRedirect("useradd", args)

    if status == 4:
        raise ValueError("UID %s already exists" % uid)
    elif status == 6:
        raise ValueError("Invalid groups %s" % groups)
    elif status == 9:
        raise ValueError("User %s already exists" % username)
    elif status != 0:
        raise OSError("Unable to create user %s: status=%s" % (username, status))

    if not mk_homedir:
        log.info("Home directory for the user %s already existed, "
                 "fixing the owner and SELinux context.", username)
        _reown_homedir(root, homedir, username)

    set_user_password(username, password, is_crypted, lock, root)


def check_user_exists(username, root=None):
    """Check a user exists.

    :param str username: username to check
    :param str root: target system sysroot path
    """
    if root is None:
        root = conf.target.system_root

    if _getpwnam(username, root):
        return True

    return False


def set_user_password(username, password, is_crypted, lock, root="/"):
    """Set user password.

    :param str username: username of the user
    :param str password: user password
    :param bool is_crypted: is the password already crypted ?
    :param bool lock: should the password for this username be locked ?
    :param str root: target system sysroot path
    """

    # Only set the password if it is a string, including the empty string.
    # Otherwise leave it alone (defaults to locked for new users) and reset sp_lstchg
    if password or password == "":
        if password == "":
            log.info("user account %s setup with no password", username)
        elif not is_crypted:
            password = crypt_password(password)

        if lock:
            password = "!" + password
            log.info("user account %s locked", username)

        proc = util.startProgram(["chpasswd", "-R", root, "-e"], stdin=subprocess.PIPE)
        proc.communicate(("%s:%s\n" % (username, password)).encode("utf-8"))
        if proc.returncode != 0:
            raise OSError("Unable to set password for new user: status=%s" % proc.returncode)

    # Reset sp_lstchg to an empty string. On systems with no rtc, this
    # field can be set to 0, which has a special meaning that the password
    # must be reset on the next login.
    util.execWithRedirect("chage", ["-R", root, "-d", "", username])


def set_root_password(password, is_crypted=False, lock=False, root="/"):
    """Set root password.

    :param str password: root password
    :param bool is_crypted: is the password already crypted ?
    :param bool lock: should the root password be locked ?
    :param str root: target system sysroot path
    """
    return set_user_password("root", password, is_crypted, lock, root)


def set_user_ssh_key(username, key, root=None):
    """Set an SSH key for a given username.

    :param str username: a username
    :param str key: the SSH key to set
    :param str root: target system sysroot path
    """
    if root is None:
        root = conf.target.system_root

    pwent = _getpwnam(username, root)
    if not pwent:
        raise ValueError("set_user_ssh_key: user %s does not exist" % username)

    homedir = root + pwent[5]
    if not os.path.exists(homedir):
        log.error("set_user_ssh_key: home directory for %s does not exist", username)
        raise ValueError("set_user_ssh_key: home directory for %s does not exist" % username)

    uid = pwent[2]
    gid = pwent[3]

    sshdir = os.path.join(homedir, ".ssh")
    if not os.path.isdir(sshdir):
        os.mkdir(sshdir, 0o700)
        os.chown(sshdir, int(uid), int(gid))

    authfile = os.path.join(sshdir, "authorized_keys")
    authfile_existed = os.path.exists(authfile)
    with open_with_perm(authfile, "a", 0o600) as f:
        f.write(key + "\n")

    # Only change ownership if we created it
    if not authfile_existed:
        os.chown(authfile, int(uid), int(gid))
        util.restorecon([sshdir.removeprefix(root)], root=root)
