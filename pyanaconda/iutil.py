#
# iutil.py - generic install utility functions
#
# Copyright (C) 1999, 2000, 2001, 2002, 2003, 2004, 2005, 2006, 2007
# Red Hat, Inc.  All rights reserved.
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
# Author(s): Erik Troan <ewt@redhat.com>
#

import glob
import os
import stat
import os.path
import errno
import subprocess
import unicodedata
import string
import types
from threading import Thread
from Queue import Queue, Empty

from pyanaconda.flags import flags
from pyanaconda.constants import DRACUT_SHUTDOWN_EJECT, ROOT_PATH, TRANSLATIONS_UPDATE_DIR, UNSUPPORTED_HW
from pyanaconda.regexes import PROXY_URL_PARSE

import logging
log = logging.getLogger("anaconda")
program_log = logging.getLogger("program")

from pyanaconda.anaconda_log import program_log_lock

def augmentEnv():
    env = os.environ.copy()
    env.update({"LC_ALL": "C",
                "ANA_INSTALL_PATH": ROOT_PATH
               })
    return env

def _run_program(argv, root='/', stdin=None, stdout=None, env_prune=None):
    """ Run an external program, log the output and return it to the caller
        @param argv The command to run and argument
        @param root The directory to chroot to before running command.
        @param stdin The file object to read stdin from.
        @param stdout Optional file object to write stdout and stderr to.
        @param env_prune environment variable to remove before execution
        @return The return code of the command and the output
    """
    if env_prune is None:
        env_prune = []

    def chroot():
        if root and root != '/':
            os.chroot(root)
            os.chdir("/")

    with program_log_lock:
        program_log.info("Running... %s", " ".join(argv))

        env = augmentEnv()
        for var in env_prune:
            env.pop(var, None)

        try:
            proc = subprocess.Popen(argv,
                                    stdin=stdin,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT,
                                    preexec_fn=chroot, cwd=root, env=env)

            out = proc.communicate()[0]
            if out:
                for line in out.splitlines():
                    program_log.info(line)
                    if stdout:
                        stdout.write(line)
                        stdout.write("\n")

        except OSError as e:
            program_log.error("Error running %s: %s", argv[0], e.strerror)
            raise

        program_log.debug("Return code: %d", proc.returncode)

    return (proc.returncode, out)

def execWithRedirect(command, argv, stdin=None, stdout=None,
                     root='/', env_prune=None):
    """ Run an external program and redirect the output to a file.
        @param command The command to run
        @param argv The argument list
        @param stdin The file object to read stdin from.
        @param stdout Optional file object to redirect stdout and stderr to.
        @param root The directory to chroot to before running command.
        @param env_prune environment variable to remove before execution
        @return The return code of the command
    """
    if flags.testing:
        log.info("not running command because we're testing: %s %s",
                 command, " ".join(argv))
        return 0

    argv = [command] + argv
    return _run_program(argv, stdin=stdin, stdout=stdout, root=root, env_prune=env_prune)[0]

def execWithCapture(command, argv, stdin=None, root='/'):
    """ Run an external program and capture standard out and err.
        @param command The command to run
        @param argv The argument list
        @param stdin The file object to read stdin from.
        @param root The directory to chroot to before running command.
        @return The output of the command
    """
    if flags.testing:
        log.info("not running command because we're testing: %s %s",
                 command, " ".join(argv))
        return ""

    argv = [command] + argv
    return _run_program(argv, stdin=stdin, root=root)[1]

def execReadlines(command, argv, stdin=None, root='/', env_prune=None):
    """ Execute an external command and return the line output of the command
        in real-time.

        @param command The command to run
        @param argv The argument list
        @param stdin The file object to read stdin from.
        @param stdout Optional file object to redirect stdout and stderr to.
        @param stderr not used
        @param root The directory to chroot to before running command.
        @param env_prune environment variable to remove before execution

        Output from the file is not logged to program.log
        This returns a generator with the lines from the command until it has finished
    """
    if env_prune is None:
        env_prune = []

    # Return the lines from stdout via a Queue
    def queue_lines(out, queue):
        for line in iter(out.readline, b''):
            queue.put(line.strip())
        out.close()

    def chroot():
        if root and root != '/':
            os.chroot(root)
            os.chdir("/")

    argv = [command] + argv
    with program_log_lock:
        program_log.info("Running... %s", " ".join(argv))

    env = augmentEnv()
    for var in env_prune:
        env.pop(var, None)
    try:
        proc = subprocess.Popen(argv,
                                stdin=stdin,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT,
                                bufsize=1,
                                preexec_fn=chroot, cwd=root, env=env)
    except OSError as e:
        program_log.error("Error running %s: %s", argv[0], e.strerror)
        raise

    q = Queue()
    t = Thread(target=queue_lines, args=(proc.stdout, q))
    t.daemon = True # thread dies with the program
    t.start()

    while True:
        try:
            line = q.get(timeout=.1)
            yield line
            q.task_done()
        except Empty:
            if proc.poll() is not None:
                break
    q.join()


## Run a shell.
def execConsole():
    try:
        proc = subprocess.Popen(["/bin/sh"])
        proc.wait()
    except OSError as e:
        raise RuntimeError("Error running /bin/sh: " + e.strerror)

def getDirSize(directory):
    """ Get the size of a directory and all its subdirectories.
    @param dir The name of the directory to find the size of.
    @return The size of the directory in kilobytes.
    """
    def getSubdirSize(directory):
        # returns size in bytes
        try:
            mydev = os.lstat(directory)[stat.ST_DEV]
        except OSError as e:
            log.debug("failed to stat %s: %s", directory, e)
            return 0

        try:
            dirlist = os.listdir(directory)
        except OSError as e:
            log.debug("failed to listdir %s: %s", directory, e)
            return 0

        dsize = 0
        for f in dirlist:
            curpath = '%s/%s' % (directory, f)
            try:
                sinfo = os.lstat(curpath)
            except OSError as e:
                log.debug("failed to stat %s/%s: %s", directory, f, e)
                continue

            if stat.S_ISDIR(sinfo[stat.ST_MODE]):
                if os.path.ismount(curpath):
                    continue
                if mydev == sinfo[stat.ST_DEV]:
                    dsize += getSubdirSize(curpath)
            elif stat.S_ISREG(sinfo[stat.ST_MODE]):
                dsize += sinfo[stat.ST_SIZE]

        return dsize
    return getSubdirSize(directory)/1024

## Create a directory path.  Don't fail if the directory already exists.
# @param dir The directory path to create.
def mkdirChain(directory):
    try:
        os.makedirs(directory, 0755)
    except OSError as e:
        try:
            if e.errno == errno.EEXIST and stat.S_ISDIR(os.stat(directory).st_mode):
                return
        except OSError:
            pass

        log.error("could not create directory %s: %s", dir, e.strerror)

def get_active_console(dev="console"):
    '''Find the active console device.

    Some tty devices (/dev/console, /dev/tty0) aren't actual devices;
    they just redirect input and output to the real console device(s).

    These 'fake' ttys have an 'active' sysfs attribute, which lists the real
    console device(s). (If there's more than one, the *last* one in the list
    is the primary console.)
    '''
    # If there's an 'active' attribute, this is a fake console..
    while os.path.exists("/sys/class/tty/%s/active" % dev):
        # So read the name of the real, primary console out of the file.
        dev = open("/sys/class/tty/%s/active" % dev).read().split()[-1]
    return dev

def isConsoleOnVirtualTerminal(dev="console"):
    console = get_active_console(dev)          # e.g. 'tty1', 'ttyS0', 'hvc1'
    consoletype = console.rstrip('0123456789') # remove the number
    return consoletype == 'tty'

def strip_markup(text):
    if text.find("<") == -1:
        return text
    r = ""
    inTag = False
    for c in text:
        if c == ">" and inTag:
            inTag = False
            continue
        elif c == "<" and not inTag:
            inTag = True
            continue
        elif not inTag:
            r += c
    return r.encode("utf-8")

def reIPL(ipldev):
    try:
        rc = execWithRedirect("chreipl", ["node", "/dev/" + ipldev])
    except RuntimeError as e:
        rc = True
        log.info("Unable to set reIPL device to %s: %s",
                 ipldev, e)

    if rc:
        log.info("reIPL configuration failed")
    else:
        log.info("reIPL configuration successful")

def resetRpmDb():
    for rpmfile in glob.glob("%s/var/lib/rpm/__db.*" % ROOT_PATH):
        try:
            os.unlink(rpmfile)
        except OSError as e:
            log.debug("error %s removing file: %s", e, rpmfile)

def parseNfsUrl(nfsurl):
    options = ''
    host = ''
    path = ''
    if nfsurl:
        s = nfsurl.split(":")
        s.pop(0)
        if len(s) >= 3:
            (options, host, path) = s[:3]
        elif len(s) == 2:
            (host, path) = s
        else:
            host = s[0]

    return (options, host, path)

def add_po_path(module, directory):
    """ Looks to see what translations are under a given path and tells
    the gettext module to use that path as the base dir """
    for d in os.listdir(directory):
        if not os.path.isdir("%s/%s" %(directory,d)):
            continue
        if not os.path.exists("%s/%s/LC_MESSAGES" %(directory,d)):
            continue
        for basename in os.listdir("%s/%s/LC_MESSAGES" %(directory,d)):
            if not basename.endswith(".mo"):
                continue
            log.info("setting %s as translation source for %s", directory, basename[:-3])
            module.bindtextdomain(basename[:-3], directory)

def setup_translations(module):
    if os.path.isdir(TRANSLATIONS_UPDATE_DIR):
        add_po_path(module, TRANSLATIONS_UPDATE_DIR)
    module.textdomain("anaconda")

def fork_orphan():
    """Forks an orphan.

    Returns 1 in the parent and 0 in the orphaned child.
    """
    intermediate = os.fork()
    if not intermediate:
        if os.fork():
            # the intermediate child dies
            os._exit(0)
        return 0
    # the original process waits for the intermediate child
    os.waitpid(intermediate, 0)
    return 1

def _run_systemctl(command, service):
    """
    Runs 'systemctl command service.service'

    :return: exit status of the systemctl

    """

    service_name = service + ".service"
    ret = execWithRedirect("systemctl", [command, service_name])

    return ret

def start_service(service):
    return _run_systemctl("start", service)

def stop_service(service):
    return _run_systemctl("stop", service)

def restart_service(service):
    return _run_systemctl("restart", service)

def service_running(service):
    ret = _run_systemctl("status", service)

    return ret == 0

def dracut_eject(device):
    """
    Use dracut shutdown hook to eject media after the system is shutdown.
    This is needed because we are running from the squashfs.img on the media
    so ejecting too early will crash the installer.
    """
    if not device:
        return

    try:
        if not os.path.exists(DRACUT_SHUTDOWN_EJECT):
            mkdirChain(os.path.dirname(DRACUT_SHUTDOWN_EJECT))
            f = open(DRACUT_SHUTDOWN_EJECT, "w")
            f.write("#!/bin/sh\n")
            f.write("# Created by Anaconda\n")
        else:
            f = open(DRACUT_SHUTDOWN_EJECT, "a")

        f.write("eject %s\n" % (device,))
        f.close()
        os.chmod(DRACUT_SHUTDOWN_EJECT, 0755)
        log.info("Wrote dracut shutdown eject hook for %s", device)
    except (IOError, OSError) as e:
        log.error("Error writing dracut shutdown eject hook for %s: %s", device, e)

def vtActivate(num):
    """
    Try to switch to tty number $num.

    :type num: int
    :return: whether the switch was successful or not
    :rtype: bool

    """

    try:
        ret = execWithRedirect("chvt", [str(num)])
    except OSError as oserr:
        ret = -1
        log.error("Failed to run chvt: %s", oserr.strerror)

    if ret != 0:
        log.error("Failed to switch to tty%d", num)

    return ret == 0

class ProxyStringError(Exception):
    pass

class ProxyString(object):
    """ Handle a proxy url
    """
    def __init__(self, url=None, protocol="http://", host=None, port="3128",
                 username=None, password=None):
        """ Initialize with either url
        ([protocol://][username[:password]@]host[:port]) or pass host and
        optionally:

        protocol    http, https, ftp
        host        hostname without protocol
        port        port number (defaults to 3128)
        username    username
        password    password

        The str() of the object is the full proxy url

        ProxyString.url is the full url including username:password@
        ProxyString.noauth_url is the url without username:password@
        """
        self.url = url
        self.protocol = protocol
        self.host = host
        self.port = str(port)
        self.username = username
        self.password = password
        self.proxy_auth = ""
        self.noauth_url = None

        if url:
            self.parse_url()
        elif not host:
            raise ProxyStringError("No host url")
        else:
            self.parse_components()

    def parse_url(self):
        """ Parse the proxy url into its component pieces
        """
        # NOTE: If this changes, update tests/regex/proxy.py
        #
        # proxy=[protocol://][username[:password]@]host[:port][path]
        # groups
        # 1 = protocol
        # 2 = username:password@
        # 3 = username
        # 4 = password
        # 5 = hostname
        # 6 = port
        # 7 = extra
        m = PROXY_URL_PARSE.match(self.url)
        if not m:
            raise ProxyStringError("malformed url, cannot parse it.")

        # If no protocol was given default to http.
        if m.group(1):
            self.protocol = m.group(1)
        else:
            self.protocol = "http://"

        if m.group(3):
            self.username = m.group(3)

        if m.group(4):
            # Skip the leading colon
            self.password = m.group(4)[1:]

        if m.group(5):
            self.host = m.group(5)
            if m.group(6):
                # Skip the leading colon
                self.port = m.group(6)[1:]
        else:
            raise ProxyStringError("url has no host component")

        self.parse_components()

    def parse_components(self):
        """ Parse the components of a proxy url into url and noauth_url
        """
        if self.username or self.password:
            self.proxy_auth = "%s:%s@" % (self.username or "",
                                          self.password or "")

        self.url = self.protocol + self.proxy_auth + self.host + ":" + self.port
        self.noauth_url = self.protocol + self.host + ":" + self.port

    @property
    def dict(self):
        """ return a dict of all the elements of the proxy string
        url, noauth_url, protocol, host, port, username, password
        """
        components = ["url", "noauth_url", "protocol", "host", "port",
                      "username", "password"]
        return dict((k, getattr(self, k)) for k in components)

    def __str__(self):
        return self.url

def getdeepattr(obj, name):
    """This behaves as the standard getattr, but supports
       composite (containing dots) attribute names.

       As an example:

       >>> import os
       >>> from os.path import split
       >>> getdeepattr(os, "path.split") == split
       True
    """

    for attr in name.split("."):
        obj = getattr(obj, attr)
    return obj

def setdeepattr(obj, name, value):
    """This behaves as the standard setattr, but supports
       composite (containing dots) attribute names.

       As an example:

       >>> class O:
       >>>   pass
       >>> a = O()
       >>> a.b = O()
       >>> a.b.c = O()
       >>> setdeepattr(a, "b.c.d", True)
       >>> a.b.c.d
       True
    """
    path = name.split(".")
    for attr in path[:-1]:
        obj = getattr(obj, attr)
    return setattr(obj, path[-1], value)

def strip_accents(s):
    """This function takes arbitrary unicode string
    and returns it with all the diacritics removed.

    :param s: arbitrary string
    :type s: unicode

    :return: s with diacritics removed
    :rtype: unicode

    """
    return ''.join((c for c in unicodedata.normalize('NFD', s)
                      if unicodedata.category(c) != 'Mn'))

def cmp_obj_attrs(obj1, obj2, attr_list):
    """ Compare attributes of 2 objects for changes

        Missing attrs are considered a mismatch

        :param obj1: First object to compare
        :type obj1: Any object
        :param obj2: Second object to compare
        :type obj2: Any object
        :param attr_list: List of attributes to compare
        :type attr_list: list or tuple of strings
        :returns: True if the attrs all match
        :rtype: bool
    """
    for attr in attr_list:
        if hasattr(obj1, attr) and hasattr(obj2, attr):
            if getattr(obj1, attr) != getattr(obj2, attr):
                return False
        else:
            return False
    return True

def dir_tree_map(root, func, files=True, dirs=True):
    """
    Apply the given function to all files and directories in the directory tree
    under the given root directory.

    :param root: root of the directory tree the function should be mapped to
    :type root: str
    :param func: a function taking the directory/file path
    :type func: path -> None
    :param files: whether to apply the function to the files in the dir. tree
    :type files: bool
    :param dirs: whether to apply the function to the directories in the dir. tree
    :type dirs: bool

    TODO: allow using globs and thus more trees?

    """

    for (dir_ent, _dir_items, file_items) in os.walk(root):
        if dirs:
            # try to call the function on the directory entry
            try:
                func(dir_ent)
            except OSError:
                pass

        if files:
            # try to call the function on the files in the directory entry
            for file_ent in (os.path.join(dir_ent, f) for f in file_items):
                try:
                    func(file_ent)
                except OSError:
                    pass

        # directories under the directory entry will appear as directory entries
        # in the loop

def chown_dir_tree(root, uid, gid, from_uid_only=None, from_gid_only=None):
    """
    Change owner (uid and gid) of the files and directories under the given
    directory tree (recursively).

    :param root: root of the directory tree that should be chown'ed
    :type root: str
    :param uid: UID that should be set as the owner
    :type uid: int
    :param gid: GID that should be set as the owner
    :type gid: int
    :param from_uid_only: if given, the owner is changed only for the files and
                          directories owned by that UID
    :type from_uid_only: int or None
    :param from_gid_only: if given, the owner is changed only for the files and
                          directories owned by that GID
    :type from_gid_only: int or None

    """

    def conditional_chown(path, uid, gid, from_uid=None, from_gid=None):
        stats = os.stat(path)
        if (from_uid and stats.st_uid != from_uid) or \
                (from_gid and stats.st_gid != from_gid):
            # owner UID or GID not matching, do nothing
            return

        # UID and GID matching or not required
        os.chown(path, uid, gid)

    if not from_uid_only and not from_gid_only:
        # the easy way
        dir_tree_map(root, lambda path: os.chown(path, uid, gid))
    else:
        # conditional chown
        dir_tree_map(root, lambda path: conditional_chown(path, uid, gid,
                                                          from_uid_only,
                                                          from_gid_only))

def is_unsupported_hw():
    """ Check to see if the hardware is supported or not.

        :returns:   True if this is unsupported hardware, False otherwise
        :rtype:     bool
    """
    try:
        tainted = long(open("/proc/sys/kernel/tainted").read())
    except (IOError, ValueError):
        tainted = 0L

    status = bool(tainted & UNSUPPORTED_HW)
    if status:
        log.debug("Installing on Unsupported Hardware")
    return status

# Define translations between ASCII uppercase and lowercase for
# locale-independent string conversions. The tables are 256-byte string used
# with string.translate. If string.translate is used with a unicode string,
# even if the string contains only 7-bit characters, string.translate will
# raise a UnicodeDecodeError.
_ASCIIupper_table = string.maketrans(string.ascii_lowercase, string.ascii_uppercase)
_ASCIIlower_table = string.maketrans(string.ascii_uppercase, string.ascii_lowercase)

def _toASCII(s):
    """Convert a unicode string to ASCII"""
    if type(s) == types.UnicodeType:
        # Decompose the string using the NFK decomposition, which in addition
        # to the canonical decomposition replaces characters based on
        # compatibility equivalence (e.g., ROMAN NUMERAL ONE has its own code
        # point but it's really just a capital I), so that we can keep as much
        # of the ASCII part of the string as possible.
        s = unicodedata.normalize('NKFD', s).encode('ascii', 'ignore')
    elif type(s) != types.StringType:
        s = ''
    return s

def upperASCII(s):
    """Convert a string to uppercase using only ASCII character definitions.

    The returned string will contain only ASCII characters. This function is
    locale-independent.
    """
    return string.translate(_toASCII(s), _ASCIIupper_table)

def lowerASCII(s):
    """Convert a string to lowercase using only ASCII character definitions.

    The returned string will contain only ASCII characters. This function is
    locale-independent.
    """
    return string.translate(_toASCII(s), _ASCIIlower_table)

def upcase_first_letter(text):
    """
    Helper function that upcases the first letter of the string. Python's
    standard string.capitalize() not only upcases the first letter but also
    lowercases all the others. string.title() capitalizes all words in the
    string.

    :type text: either a str or unicode object
    :return: the given text with the first letter upcased
    :rtype: str or unicode (depends on the input)

    """

    if not text:
        # cannot change anything
        return text
    elif len(text) == 1:
        return text.upper()
    else:
        return text[0].upper() + text[1:]
