#
# util.py - generic install utility functions
#
# Copyright (C) 1999-2014
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

import glob
import os
import os.path
import subprocess
import unicodedata
# Used for ascii_lowercase, ascii_uppercase constants
import string  # pylint: disable=deprecated-module
import tempfile
import re
import gettext
import signal
import sys
import imp
import types
import inspect
import functools

import requests
from requests_file import FileAdapter
from requests_ftp import FTPAdapter

from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.flags import flags
from pyanaconda.core.process_watchers import WatchProcesses
from pyanaconda.core.constants import DRACUT_SHUTDOWN_EJECT, TRANSLATIONS_UPDATE_DIR, \
    IPMI_ABORTED, X_TIMEOUT, TAINT_HARDWARE_UNSUPPORTED, TAINT_SUPPORT_REMOVED, \
    WARNING_HARDWARE_UNSUPPORTED, WARNING_SUPPORT_REMOVED
from pyanaconda.errors import RemovedModuleError

from pyanaconda.anaconda_logging import program_log_lock
from pyanaconda.anaconda_loggers import get_module_logger, get_program_logger
log = get_module_logger(__name__)
program_log = get_program_logger()

from pykickstart.constants import KS_SCRIPT_ONERROR

_child_env = {}


def setenv(name, value):
    """ Set an environment variable to be used by child processes.

        This method does not modify os.environ for the running process, which
        is not thread-safe. If setenv has already been called for a particular
        variable name, the old value is overwritten.

        :param str name: The name of the environment variable
        :param str value: The value of the environment variable
    """

    _child_env[name] = value


def augmentEnv():
    env = os.environ.copy()
    env.update({"ANA_INSTALL_PATH": conf.target.system_root})
    env.update(_child_env)
    return env


def set_system_root(path):
    """Change the OS root path.

    The path defined by conf.target.system_root will be bind mounted at the given
    path, so conf.target.system_root can be used to access the root of the new OS.

    We always call it after the root device is mounted at conf.target.physical_root
    to set the physical root as the current system root.

    Then, it can be used by Payload subclasses which install operating systems to
    non-default roots.

    If the given path is None, then conf.target.system_root is only unmounted.

    :param path: the new OS root path or None
    """
    sysroot = conf.target.system_root

    if sysroot == path:
        return

    # Unmount the mount point if necessary.
    rc = execWithRedirect("findmnt", ["-rn", sysroot])

    if rc == 0:
        execWithRedirect("mount", ["--make-rprivate", sysroot])
        execWithRedirect("umount", ["--recursive", sysroot])

    if not path:
        return

    # Create a directory for the mount point.
    if not os.path.exists(sysroot):
        mkdirChain(sysroot)

    # Mount the mount point.
    rc = execWithRedirect("mount", ["--rbind", path, sysroot])

    if rc != 0:
        raise OSError("Failed to mount sysroot to {}.".format(path))


def startProgram(argv, root='/', stdin=None, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                 env_prune=None, env_add=None, reset_handlers=True, reset_lang=True, **kwargs):
    """ Start an external program and return the Popen object.

        The root and reset_handlers arguments are handled by passing a
        preexec_fn argument to subprocess.Popen, but an additional preexec_fn
        can still be specified and will be run. The user preexec_fn will be run
        last.

        :param argv: The command to run and argument
        :param root: The directory to chroot to before running command.
        :param stdin: The file object to read stdin from.
        :param stdout: The file object to write stdout to.
        :param stderr: The file object to write stderr to.
        :param env_prune: environment variables to remove before execution
        :param env_add: environment variables to add before execution
        :param reset_handlers: whether to reset to SIG_DFL any signal handlers set to SIG_IGN
        :param reset_lang: whether to set the locale of the child process to C
        :param kwargs: Additional parameters to pass to subprocess.Popen
        :return: A Popen object for the running command.
    """
    if env_prune is None:
        env_prune = []

    # Transparently redirect callers requesting root=_root_path to the
    # configured system root.
    target_root = root
    if target_root == conf.target.physical_root:
        target_root = conf.target.system_root

    # Check for and save a preexec_fn argument
    preexec_fn = kwargs.pop("preexec_fn", None)

    # Map reset_handlers to the restore_signals Popen argument.
    # restore_signals handles SIGPIPE, and preexec below handles any additional
    # signals ignored by anaconda.
    restore_signals = reset_handlers

    def preexec():
        # If a target root was specificed, chroot into it
        if target_root and target_root != '/':
            os.chroot(target_root)
            os.chdir("/")

        # Signal handlers set to SIG_IGN persist across exec. Reset
        # these to SIG_DFL if requested. In particular this will include the
        # SIGPIPE handler set by python.
        if reset_handlers:
            for signum in range(1, signal.NSIG):
                if signal.getsignal(signum) == signal.SIG_IGN:
                    signal.signal(signum, signal.SIG_DFL)

        # If the user specified an additional preexec_fn argument, run it
        if preexec_fn is not None:
            preexec_fn()

    with program_log_lock:
        if target_root != '/':
            program_log.info("Running in chroot '%s'... %s", target_root, " ".join(argv))
        else:
            program_log.info("Running... %s", " ".join(argv))

    env = augmentEnv()
    for var in env_prune:
        env.pop(var, None)

    if reset_lang:
        env.update({"LC_ALL": "C"})

    if env_add:
        env.update(env_add)

    # pylint: disable=subprocess-popen-preexec-fn
    return subprocess.Popen(argv,
                            stdin=stdin,
                            stdout=stdout,
                            stderr=stderr,
                            close_fds=True,
                            restore_signals=restore_signals,
                            preexec_fn=preexec, cwd=root, env=env, **kwargs)


class X11Status:
    """Status of Xorg launch.

    Values of an instance can be modified from the handler functions.
    """
    def __init__(self):
        self.started = False
        self.timed_out = False

    def needs_waiting(self):
        return not (self.started or self.timed_out)


def startX(argv, output_redirect=None, timeout=X_TIMEOUT):
    """ Start X and return once X is ready to accept connections.

        X11, if SIGUSR1 is set to SIG_IGN, will send SIGUSR1 to the parent
        process once it is ready to accept client connections. This method
        sets that up and waits for the signal or bombs out if nothing happens
        for a minute. The process will also be added to the list of watched
        processes.

        :param argv: The command line to run, as a list
        :param output_redirect: file or file descriptor to redirect stdout and stderr to
        :param timeout: Number of seconds to timing out.
    """
    x11_status = X11Status()

    # Handle successful start before timeout
    def sigusr1_success_handler(num, frame):
        log.debug("X server has signalled a successful start.")
        x11_status.started = True

    # Fail after, let's say a minute, in case something weird happens
    # and we don't receive SIGUSR1
    def sigalrm_handler(num, frame):
        # Check that it didn't make it under the wire
        if x11_status.started:
            return
        x11_status.timed_out = True
        log.error("Timeout trying to start %s", argv[0])

    # Handle delayed start after timeout
    def sigusr1_too_late_handler(num, frame):
        if x11_status.timed_out:
            log.debug("SIGUSR1 received after X server timeout. Switching back to tty1. "
                      "SIGUSR1 now again initiates test of exception reporting.")
            signal.signal(signal.SIGUSR1, old_sigusr1_handler)

    # preexec_fn to add the SIGUSR1 handler in the child we are starting
    # see man page XServer(1), section "signals"
    def sigusr1_preexec():
        signal.signal(signal.SIGUSR1, signal.SIG_IGN)

    try:
        old_sigusr1_handler = signal.signal(signal.SIGUSR1, sigusr1_success_handler)
        old_sigalrm_handler = signal.signal(signal.SIGALRM, sigalrm_handler)

        # Start the timer
        log.debug("Setting timeout %s seconds for starting X.", timeout)
        signal.alarm(timeout)

        childproc = startProgram(argv, stdout=output_redirect, stderr=output_redirect,
                                 preexec_fn=sigusr1_preexec)
        WatchProcesses.watch_process(childproc, argv[0])

        # Wait for SIGUSR1 or SIGALRM
        while x11_status.needs_waiting():
            signal.pause()

    finally:
        # Stop the timer
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_sigalrm_handler)

        # Handle outcome of X start attempt
        if x11_status.started:
            signal.signal(signal.SIGUSR1, old_sigusr1_handler)
        elif x11_status.timed_out:
            signal.signal(signal.SIGUSR1, sigusr1_too_late_handler)
            # Kill Xorg because from now on we will not use it. It will exit only after sending
            # the signal, but at least we don't have to track that.
            WatchProcesses.unwatch_process(childproc)
            childproc.terminate()
            log.debug("Exception handler test suspended to prevent accidental activation by "
                      "delayed Xorg start. Next SIGUSR1 will be handled as delayed Xorg start.")
            # Raise an exception to notify the caller that things went wrong. This affects
            # particularly pyanaconda.display.do_startup_x11_actions(), where the window manager
            # is started immediately after this. The WM would just wait forever.
            raise TimeoutError("Timeout trying to start %s" % argv[0])


def _run_program(argv, root='/', stdin=None, stdout=None, env_prune=None, log_output=True,
                 binary_output=False, filter_stderr=False):
    """ Run an external program, log the output and return it to the caller

        NOTE/WARNING: UnicodeDecodeError will be raised if the output of the of the
                      external command can't be decoded as UTF-8.

        :param argv: The command to run and argument
        :param root: The directory to chroot to before running command.
        :param stdin: The file object to read stdin from.
        :param stdout: Optional file object to write the output to.
        :param env_prune: environment variable to remove before execution
        :param log_output: whether to log the output of command
        :param binary_output: whether to treat the output of command as binary data
        :param filter_stderr: whether to exclude the contents of stderr from the returned output
        :return: The return code of the command and the output
    """
    try:
        if filter_stderr:
            stderr = subprocess.PIPE
        else:
            stderr = subprocess.STDOUT

        proc = startProgram(argv, root=root, stdin=stdin, stdout=subprocess.PIPE, stderr=stderr,
                            env_prune=env_prune)

        (output_string, err_string) = proc.communicate()
        if not binary_output:
            output_string = output_string.decode("utf-8")
            if output_string and output_string[-1] != "\n":
                output_string = output_string + "\n"

        if log_output:
            with program_log_lock:
                if binary_output:
                    # try to decode as utf-8 and replace all undecodable data by
                    # "safe" printable representations when logging binary output
                    decoded_output_lines = output_string.decode("utf-8", "replace")
                else:
                    # output_string should already be a Unicode string
                    decoded_output_lines = output_string.splitlines(True)

                for line in decoded_output_lines:
                    program_log.info(line.strip())

        if stdout:
            stdout.write(output_string)

        # If stderr was filtered, log it separately
        if filter_stderr and err_string and log_output:
            # try to decode as utf-8 and replace all undecodable data by
            # "safe" printable representations when logging binary output
            decoded_err_string = err_string.decode("utf-8", "replace")
            err_lines = decoded_err_string.splitlines(True)

            with program_log_lock:
                for line in err_lines:
                    program_log.info(line.strip())

    except OSError as e:
        with program_log_lock:
            program_log.error("Error running %s: %s", argv[0], e.strerror)
        raise

    with program_log_lock:
        program_log.debug("Return code: %d", proc.returncode)

    return (proc.returncode, output_string)


def execInSysroot(command, argv, stdin=None, root=None):
    """ Run an external program in the target root.
        :param command: The command to run
        :param argv: The argument list
        :param stdin: The file object to read stdin from.
        :param root: The directory to chroot to before running the command.
        :return: The return code of the command
    """
    if root is None:
        root = conf.target.system_root

    return execWithRedirect(command, argv, stdin=stdin, root=root)


def execWithRedirect(command, argv, stdin=None, stdout=None,
                     root='/', env_prune=None, log_output=True, binary_output=False):
    """ Run an external program and redirect the output to a file.

        :param command: The command to run
        :param argv: The argument list
        :param stdin: The file object to read stdin from.
        :param stdout: Optional file object to redirect stdout and stderr to.
        :param root: The directory to chroot to before running command.
        :param env_prune: environment variable to remove before execution
        :param log_output: whether to log the output of command
        :param binary_output: whether to treat the output of command as binary data
        :return: The return code of the command
    """
    argv = [command] + argv
    return _run_program(argv, stdin=stdin, stdout=stdout, root=root, env_prune=env_prune,
                        log_output=log_output, binary_output=binary_output)[0]


def execWithCapture(command, argv, stdin=None, root='/', log_output=True, filter_stderr=False):
    """ Run an external program and capture standard out and err.

        :param command: The command to run
        :param argv: The argument list
        :param stdin: The file object to read stdin from.
        :param root: The directory to chroot to before running command.
        :param log_output: Whether to log the output of command
        :param filter_stderr: Whether stderr should be excluded from the returned output
        :return: The output of the command
    """
    argv = [command] + argv
    return _run_program(argv, stdin=stdin, root=root, log_output=log_output,
                        filter_stderr=filter_stderr)[1]


def execWithCaptureBinary(command, argv, stdin=None, root='/', log_output=False, filter_stderr=False):
    """ Run an external program and capture standard out and err as binary data.
        The binary data output is not logged by default but logging can be enabled.

        :param command: The command to run
        :param argv: The argument list
        :param stdin: The file object to read stdin from.
        :param root: The directory to chroot to before running command.
        :param log_output: Whether to log the binary output of the command
        :param filter_stderr: Whether stderr should be excluded from the returned output
        :return: The output of the command
    """
    argv = [command] + argv
    return _run_program(argv, stdin=stdin, root=root, log_output=log_output,
                        filter_stderr=filter_stderr, binary_output=True)[1]


def execReadlines(command, argv, stdin=None, root='/', env_prune=None, filter_stderr=False):
    """ Execute an external command and return the line output of the command
        in real-time.

        This method assumes that there is a reasonably low delay between the
        end of output and the process exiting. If the child process closes
        stdout and then keeps on truckin' there will be problems.

        NOTE/WARNING: UnicodeDecodeError will be raised if the output of the
                      external command can't be decoded as UTF-8.

        :param command: The command to run
        :param argv: The argument list
        :param stdin: The file object to read stdin from.
        :param stdout: Optional file object to redirect stdout and stderr to.
        :param root: The directory to chroot to before running command.
        :param env_prune: environment variable to remove before execution
        :param filter_stderr: Whether stderr should be excluded from the returned output

        Output from the file is not logged to program.log
        This returns an iterator with the lines from the command until it has finished
    """

    class ExecLineReader(object):
        """Iterator class for returning lines from a process and cleaning
           up the process when the output is no longer needed.
        """

        def __init__(self, proc, argv):
            self._proc = proc
            self._argv = argv

        def __iter__(self):
            return self

        def __del__(self):
            # See if the process is still running
            if self._proc.poll() is None:
                # Stop the process and ignore any problems that might arise
                try:
                    self._proc.terminate()
                except OSError:
                    pass

        def __next__(self):
            # Read the next line, blocking if a line is not yet available
            line = self._proc.stdout.readline().decode("utf-8")
            if line == '':
                # Output finished, wait for the process to end
                self._proc.communicate()

                # Check for successful exit
                if self._proc.returncode < 0:
                    raise OSError("process '%s' was killed by signal %s" %
                                  (self._argv, -self._proc.returncode))
                elif self._proc.returncode > 0:
                    raise OSError("process '%s' exited with status %s" %
                                  (self._argv, self._proc.returncode))
                raise StopIteration

            return line.strip()

    argv = [command] + argv

    if filter_stderr:
        stderr = subprocess.DEVNULL
    else:
        stderr = subprocess.STDOUT

    try:
        proc = startProgram(argv, root=root, stdin=stdin, stderr=stderr, env_prune=env_prune, bufsize=1)
    except OSError as e:
        with program_log_lock:
            program_log.error("Error running %s: %s", argv[0], e.strerror)
        raise

    return ExecLineReader(proc, argv)


## Run a shell.
def execConsole():
    try:
        proc = startProgram(["/bin/sh"], stdout=None, stderr=None, reset_lang=False)
        proc.wait()
    except OSError as e:
        raise RuntimeError("Error running /bin/sh: " + e.strerror)


## Create a directory path.  Don't fail if the directory already exists.
def mkdirChain(directory):
    """ Make a directory and all of its parents. Don't fail if part or
        of it already exists.

        :param str directory: The directory path to create
    """

    os.makedirs(directory, 0o755, exist_ok=True)


def get_active_console(dev="console"):
    """Find the active console device.

    Some tty devices (/dev/console, /dev/tty0) aren't actual devices;
    they just redirect input and output to the real console device(s).

    These 'fake' ttys have an 'active' sysfs attribute, which lists the real
    console device(s). (If there's more than one, the *last* one in the list
    is the primary console.)
    """
    # If there's an 'active' attribute, this is a fake console..
    while os.path.exists("/sys/class/tty/%s/active" % dev):
        # So read the name of the real, primary console out of the file.
        console_path = "/sys/class/tty/%s/active" % dev
        active = open(console_path, "rt").read()
        if active.split():
            # the active attribute seems to be pointing to another console
            dev = active.split()[-1]
        else:
            # At least some consoles on PPC have the "active" attribute, but it is empty.
            # (see rhbz#1569045 for more details)
            log.warning("%s is empty while console name is expected", console_path)
            # We can't continue to a next console if active is empty, so set dev to ""
            # and break the search loop.
            dev = ""
            break
    return dev


def isConsoleOnVirtualTerminal(dev="console"):
    console = get_active_console(dev)           # e.g. 'tty1', 'ttyS0', 'hvc1'
    consoletype = console.rstrip('0123456789')  # remove the number
    return consoletype == 'tty'


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
    for rpmfile in glob.glob("%s/var/lib/rpm/__db.*" % conf.target.system_root):
        try:
            os.unlink(rpmfile)
        except OSError as e:
            log.debug("error %s removing file: %s", e, rpmfile)


def add_po_path(directory):
    """ Looks to see what translations are under a given path and tells
    the gettext module to use that path as the base dir """
    for d in os.listdir(directory):
        if not os.path.isdir("%s/%s" % (directory, d)):
            continue
        if not os.path.exists("%s/%s/LC_MESSAGES" % (directory, d)):
            continue
        for basename in os.listdir("%s/%s/LC_MESSAGES" % (directory, d)):
            if not basename.endswith(".mo"):
                continue
            log.info("setting %s as translation source for %s", directory, basename[:-3])
            gettext.bindtextdomain(basename[:-3], directory)


def setup_translations():
    if os.path.isdir(TRANSLATIONS_UPDATE_DIR):
        add_po_path(TRANSLATIONS_UPDATE_DIR)
    gettext.textdomain("anaconda")


def _run_systemctl(command, service, root="/"):
    """
    Runs 'systemctl command service.service'

    :return: exit status of the systemctl

    """

    args = [command, service]
    if root != "/":
        args += ["--root", root]

    ret = execWithRedirect("systemctl", args)

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


def is_service_installed(service, root=None):
    """Is a systemd service installed in the sysroot?

    :param str service: name of the service to check
    :param str root: path to the sysroot or None to use default sysroot path
    """
    if root is None:
        root = conf.target.system_root

    if not service.endswith(".service"):
        service += ".service"

    args = ["list-unit-files", service, "--no-legend"]

    if root != "/":
        args += ["--root", root]

    unit_file = execWithCapture("systemctl", args)

    return bool(unit_file)


def enable_service(service, root=None):
    """ Enable a systemd service in the sysroot.

    :param str service: name of the service to enable
    :param str root: path to the sysroot or None to use default sysroot path
    """
    if root is None:
        root = conf.target.system_root

    ret = _run_systemctl("enable", service, root=root)

    if ret != 0:
        raise ValueError("Error enabling service %s: %s" % (service, ret))


def disable_service(service, root=None):
    """ Disable a systemd service in the sysroot.

    :param str service: name of the service to enable
    :param str root: path to the sysroot or None to use default sysroot path
    """
    if root is None:
        root = conf.target.system_root

    # we ignore the error so we can disable services even if they don't
    # exist, because that's effectively disabled
    ret = _run_systemctl("disable", service, root=root)

    if ret != 0:
        log.warning("Disabling %s failed. It probably doesn't exist", service)


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
            f = open_with_perm(DRACUT_SHUTDOWN_EJECT, "w", 0o755)
            f.write("#!/bin/sh\n")
            f.write("# Created by Anaconda\n")
        else:
            f = open(DRACUT_SHUTDOWN_EJECT, "a")

        f.write("eject %s\n" % (device,))
        f.close()
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


def strip_accents(s):
    """This function takes arbitrary unicode string
    and returns it with all the diacritics removed.

    :param s: arbitrary string
    :type s: str

    :return: s with diacritics removed
    :rtype: str

    """
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                   if unicodedata.category(c) != 'Mn')


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


def get_kernel_taint(flag):
    """Get a value of a kernel taint.

    :param flag: a kernel taint flag
    :return: False if the value of taint is 0, otherwise True
    """
    try:
        tainted = int(open("/proc/sys/kernel/tainted").read())
    except (IOError, ValueError):
        tainted = 0

    return bool(tainted & (1 << flag))


def find_hardware_with_removed_support():
    """Find hardware with removed support.

    :return: a list of hardware specifications
    """
    pattern = "Warning: (.*) - Support for this device has been removed in this major release."
    hardware = []

    for line in execReadlines("journalctl", ["-b", "-k", "-g", pattern, "-o", "cat"]):
        matched = re.match(pattern, line)

        if matched:
            hardware.append(matched.group(1))

    return hardware


def detect_unsupported_hardware():
    """Detect unsupported hardware.

    :return: a list of warnings
    """
    warnings = []  # pylint: disable=redefined-outer-name

    if flags.automatedInstall or not conf.target.is_hardware:
        log.info("Skipping detection of unsupported hardware.")
        return []

    # Check TAINT_HARDWARE_UNSUPPORTED
    if not conf.system.can_detect_unsupported_hardware:
        log.debug("This system doesn't support TAINT_HARDWARE_UNSUPPORTED.")
    elif get_kernel_taint(TAINT_HARDWARE_UNSUPPORTED):
        warnings.append(WARNING_HARDWARE_UNSUPPORTED)

    # Check TAINT_SUPPORT_REMOVED
    if not conf.system.can_detect_support_removed:
        log.debug("This system doesn't support TAINT_SUPPORT_REMOVED.")
    elif get_kernel_taint(TAINT_SUPPORT_REMOVED):
        warning = WARNING_SUPPORT_REMOVED
        hardware = find_hardware_with_removed_support()

        if hardware:
            warning += "\n\n" + "\n".join(hardware)

        warnings.append(warning)

    # Log all warnings.
    for msg in warnings:
        log.warning(msg)

    return warnings


def ensure_str(str_or_bytes, keep_none=True):
    """
    Returns a str instance for given string or ``None`` if requested to keep it.

    :param str_or_bytes: string to be kept or converted to str type
    :type str_or_bytes: str or bytes
    :param bool keep_none: whether to keep None as it is or raise ValueError if
                           ``None`` is passed
    :raises ValueError: if applied on an object not being of type bytes nor str
                        (nor NoneType if ``keep_none`` is ``False``)
    """

    if keep_none and str_or_bytes is None:
        return None
    elif isinstance(str_or_bytes, str):
        return str_or_bytes
    elif isinstance(str_or_bytes, bytes):
        return str_or_bytes.decode(sys.getdefaultencoding())
    else:
        raise ValueError("str_or_bytes must be of type 'str' or 'bytes', not '%s'" % type(str_or_bytes))


# Define translations between ASCII uppercase and lowercase for
# locale-independent string conversions. The tables are 256-byte string used
# with str.translate. If str.translate is used with a unicode string,
# even if the string contains only 7-bit characters, str.translate will
# raise a UnicodeDecodeError.
_ASCIIlower_table = str.maketrans(string.ascii_uppercase, string.ascii_lowercase)
_ASCIIupper_table = str.maketrans(string.ascii_lowercase, string.ascii_uppercase)


def _toASCII(s):
    """Convert a unicode string to ASCII"""
    if isinstance(s, str):
        # Decompose the string using the NFK decomposition, which in addition
        # to the canonical decomposition replaces characters based on
        # compatibility equivalence (e.g., ROMAN NUMERAL ONE has its own code
        # point but it's really just a capital I), so that we can keep as much
        # of the ASCII part of the string as possible.
        s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode("ascii")
    elif not isinstance(s, bytes):
        s = ''
    return s


def upperASCII(s):
    """Convert a string to uppercase using only ASCII character definitions.

    The returned string will contain only ASCII characters. This function is
    locale-independent.
    """

    # XXX: Python 3 has str.maketrans() and bytes.maketrans() so we should
    # ideally use one or the other depending on the type of 's'. But it turns
    # out we expect this function to always return string even if given bytes.
    s = ensure_str(s)
    return str.translate(_toASCII(s), _ASCIIupper_table)


def lowerASCII(s):
    """Convert a string to lowercase using only ASCII character definitions.

    The returned string will contain only ASCII characters. This function is
    locale-independent.
    """

    # XXX: Python 3 has str.maketrans() and bytes.maketrans() so we should
    # ideally use one or the other depending on the type of 's'. But it turns
    # out we expect this function to always return string even if given bytes.
    s = ensure_str(s)
    return str.translate(_toASCII(s), _ASCIIlower_table)


def upcase_first_letter(text):
    """
    Helper function that upcases the first letter of the string. Python's
    standard string.capitalize() not only upcases the first letter but also
    lowercases all the others. string.title() capitalizes all words in the
    string.

    :type text: str
    :return: the given text with the first letter upcased
    :rtype: str

    """

    if not text:
        # cannot change anything
        return text
    elif len(text) == 1:
        return text.upper()
    else:
        return text[0].upper() + text[1:]


def get_mount_paths(devnode):
    '''given a device node, return a list of all active mountpoints.'''
    devno = os.stat(devnode).st_rdev
    majmin = "%d:%d" % (os.major(devno), os.minor(devno))
    mountinfo = (line.split() for line in open("/proc/self/mountinfo"))
    return [info[4] for info in mountinfo if info[2] == majmin]


def have_word_match(str1, str2):
    """Tells if all words from str1 exist in str2 or not."""

    if str1 is None or str2 is None:
        # None never matches
        return False

    if str1 == "":
        # empty string matches everything except from None
        return True
    elif str2 == "":
        # non-empty string cannot be found in an empty string
        return False

    # Convert both arguments to string if not already
    str1 = ensure_str(str1)
    str2 = ensure_str(str2)

    str1 = str1.lower()
    str1_words = str1.split()
    str2 = str2.lower()

    return all(word in str2 for word in str1_words)


def xprogressive_delay():
    """ A delay generator, the delay starts short and gets longer
        as the internal counter increases.
        For example for 10 retries, the delay will increases from
        0.5 to 256 seconds.

        :returns float: time to wait in seconds
    """
    counter = 1
    while True:
        yield 0.25 * (2 ** counter)
        counter += 1


def get_platform_groupid():
    """ Return a platform group id string

        This runs systemd-detect-virt and if the result is not 'none' it
        prefixes the lower case result with "platform-" for use as a group id.

        :returns: Empty string or a group id for the detected platform
        :rtype: str
    """
    try:
        platform = execWithCapture("systemd-detect-virt", []).strip()
    except (IOError, AttributeError):
        return ""

    if platform == "none":
        return ""

    return "platform-" + platform.lower()


def persistent_root_image():
    """:returns: whether we are running from a persistent (not in RAM) root.img"""

    for line in execReadlines("losetup", ["--list"]):
        # if there is an active loop device for a curl-fetched file that has
        # been deleted, it means we run from a non-persistent root image
        # EXAMPLE line:
        # /dev/loop0  0 0 0 1 /tmp/curl_fetch_url0/my_comps_squashfs.img (deleted)
        if re.match(r'.*curl_fetch_url.*\(deleted\)\s*$', line):
            return False

    return True


_supports_ipmi = None


def ipmi_report(event):
    global _supports_ipmi
    if _supports_ipmi is None:
        _supports_ipmi = os.path.exists("/dev/ipmi0") and os.path.exists("/usr/bin/ipmitool")

    if not _supports_ipmi:
        return

    (fd, path) = tempfile.mkstemp()

    # EVM revision - always 0x4
    # Sensor type - always 0x1F for Base OS Boot/Installation Status
    # Sensor num - always 0x0 for us
    # Event dir & type - always 0x6f for us
    # Event data 1 - the event code passed in
    # Event data 2 & 3 - always 0x0 for us
    event_string = "0x4 0x1F 0x0 0x6f %#x 0x0 0x0\n" % event
    os.write(fd, event_string.encode("utf-8"))
    os.close(fd)

    execWithCapture("ipmitool", ["event", "file", path])

    os.remove(path)


def ipmi_abort(scripts=None):
    ipmi_report(IPMI_ABORTED)
    runOnErrorScripts(scripts)


def runOnErrorScripts(scripts):
    if not scripts:
        return

    log.info("Running kickstart %%onerror script(s)")
    for script in filter(lambda s: s.type == KS_SCRIPT_ONERROR, scripts):
        script.run("/")
    log.info("All kickstart %%onerror script(s) have been run")


def parent_dir(directory):
    """Return the parent's path"""
    return "/".join(os.path.normpath(directory).split("/")[:-1])


def requests_session():
    """Return a requests.Session object with file and ftp support."""
    session = requests.Session()
    session.mount("file://", FileAdapter())
    session.mount("ftp://", FTPAdapter())
    return session


def open_with_perm(path, mode='r', perm=0o777, **kwargs):
    """Open a file with the given permission bits.

       This is more or less the same as using os.open(path, flags, perm), but
       with the builtin open() semantics and return type instead of a file
       descriptor.

       :param str path: The path of the file to be opened
       :param str mode: The same thing as the mode argument to open()
       :param int perm: What permission bits to use if creating a new file
    """
    def _opener(path, open_flags):
        return os.open(path, open_flags, perm)

    return open(path, mode, opener=_opener, **kwargs)


def id_generator():
    """ Id numbers generator.
        Generating numbers from 0 to X and increments after every call.

        :returns: Generator which gives you unique numbers.
    """
    actual_id = 0
    while(True):
        yield actual_id
        actual_id += 1


def sysroot_path(path):
    """Make the given relative or absolute path "sysrooted"
       :param str path: path to be sysrooted
       :returns: sysrooted path
       :rtype: str
    """
    return os.path.join(conf.target.system_root, path.lstrip(os.path.sep))


def join_paths(path, *paths):
    """Always join paths.

    The os.path.join() function has a drawback when second path is absolute. In that case it will
    instead return the second path only.

    :param path: first path we want to join
    :param paths: paths we want to merge
    :returns: return path created from all the input paths
    :rtype: str
    """
    if len(paths) == 0:
        return path

    new_paths = []
    for p in paths:
        new_paths.append(p.lstrip(os.path.sep))

    return os.path.join(path, *new_paths)


def touch(file_path):
    """Create an empty file."""
    # this misrrors how touch works - it does not
    # throw an error if the given path exists,
    # even when the path points to dirrectory
    if not os.path.exists(file_path):
        os.mknod(file_path)


def set_mode(file_path, perm=0o600):
    """Set file permission to a given file

    In case the file doesn't exists - create it.

    :param str file_path: Path to a file
    :param int perm: File permissions in format of os.chmod()
    """
    if not os.path.exists(file_path):
        touch(file_path)
    os.chmod(file_path, perm)


def collect(module_pattern, path, pred):
    """Traverse the directory (given by path), import all files as a module
       module_pattern % filename and find all classes within that match
       the given predicate.  This is then returned as a list of classes.

       It is suggested you use collect_categories or collect_spokes instead of
       this lower-level method.

       :param module_pattern: the full name pattern (pyanaconda.ui.gui.spokes.%s)
                              we want to assign to imported modules
       :type module_pattern: string

       :param path: the directory we are picking up modules from
       :type path: string

       :param pred: function which marks classes as good to import
       :type pred: function with one argument returning True or False
    """

    retval = []
    try:
        contents = os.listdir(path)
    # when the directory "path" does not exist
    except OSError:
        return []

    for module_file in contents:
        if (not module_file.endswith(".py")) and \
           (not module_file.endswith(".so")):
            continue

        if module_file == "__init__.py":
            continue

        try:
            mod_name = module_file[:module_file.rindex(".")]
        except ValueError:
            mod_name = module_file

        mod_info = None
        module = None
        module_path = None

        try:
            (fo, module_path, module_flags) = imp.find_module(mod_name, [path])
            module = sys.modules.get(module_pattern % mod_name)

            # do not load module if any module with the same name
            # is already imported
            if not module:
                # try importing the module the standard way first
                # uses sys.path and the module's full name!
                try:
                    __import__(module_pattern % mod_name)
                    module = sys.modules[module_pattern % mod_name]

                # if it fails (package-less addon?) try importing single file
                # and filling up the package structure voids
                except ImportError:
                    # prepare dummy modules to prevent RuntimeWarnings
                    module_parts = (module_pattern % mod_name).split(".")

                    # remove the last name as it will be inserted by the import
                    module_parts.pop()

                    # make sure all "parent" modules are in sys.modules
                    for l in range(len(module_parts)):
                        module_part_name = ".".join(module_parts[:l + 1])
                        if module_part_name not in sys.modules:
                            module_part = types.ModuleType(module_part_name)
                            module_part.__path__ = [path]
                            sys.modules[module_part_name] = module_part

                    # load the collected module
                    module = imp.load_module(module_pattern % mod_name,
                                             fo, module_path, module_flags)

            # get the filenames without the extensions so we can compare those
            # with the .py[co]? equivalence in mind
            # - we do not have to care about files without extension as the
            #   condition at the beginning of the for loop filters out those
            # - module_flags[0] contains the extension of the module imp found
            candidate_name = module_path[:module_path.rindex(module_flags[0])]
            loaded_name, loaded_ext = module.__file__.rsplit(".", 1)

            # restore the extension dot eaten by split
            loaded_ext = "." + loaded_ext

            # do not collect classes when the module is already imported
            # from different path than we are traversing
            # this condition checks the module name without file extension
            if candidate_name != loaded_name:
                continue

            # if the candidate file is .py[co]? and the loaded is not (.so)
            # skip the file as well
            if module_flags[0].startswith(".py") and not loaded_ext.startswith(".py"):
                continue

            # if the candidate file is not .py[co]? and the loaded is
            # skip the file as well
            if not module_flags[0].startswith(".py") and loaded_ext.startswith(".py"):
                continue

        except RemovedModuleError:
            # collected some removed module
            continue

        except ImportError as imperr:
            # pylint: disable=unsupported-membership-test
            if module_path and "pyanaconda" in module_path:
                # failure when importing our own module:
                raise
            log.error("Failed to import module %s from path %s in collect: %s", mod_name, module_path, imperr)
            continue
        finally:
            if mod_info and mod_info[0]:  # pylint: disable=unsubscriptable-object
                mod_info[0].close()  # pylint: disable=unsubscriptable-object

        p = lambda obj: inspect.isclass(obj) and pred(obj)

        # if __all__ is defined in the module, use it
        if not hasattr(module, "__all__"):
            members = inspect.getmembers(module, p)
        else:
            members = [(name, getattr(module, name))
                       for name in module.__all__
                       if p(getattr(module, name))]

        for (_name, val) in members:
            retval.append(val)

    return retval


def item_counter(item_count):
    """A generator for easy counting of items.

    :param int item_count: number of items

    The general idea is to initialize the generator with the number
    of items and then activating it every time an item is being
    processed.

    The generator produces strings in the <index>/<item count> format,
    for example:
    1/20
    2/20
    3/20
    And so on.

    Such strings can be easily used to add a current/total counter
    to log messages when tasks and task queues are processed.
    """
    if item_count < 0:
        raise ValueError("Item count can't be negative.")
    index = 1
    while index <= item_count:
        yield "%d/%d" % (index, item_count)
        index += 1


def synchronized(wrapped):
    """A locking decorator for methods.

    The decorator is only intended for methods and the class providing
    the method also needs to have a Lock/RLock instantiated in self._lock.

    The decorator prevents the wrapped method from being executed until
    self._lock can be acquired. Once available, it acquires the lock and
    prevents other decorated methods & other users of self._lock from
    executing until the wrapped method finishes running.
    """

    @functools.wraps(wrapped)
    def _wrapper(self, *args, **kwargs):
        with self._lock:
            return wrapped(self, *args, **kwargs)
    return _wrapper


def decode_bytes(data):
    """Decode the given bytes.

    Return the given string or a string decoded from the given bytes.

    :param data: bytes or a string
    :return: a string
    """
    if isinstance(data, str):
        return data

    if isinstance(data, bytes):
        return data.decode('utf-8')

    raise ValueError("Unsupported type '{}'.".format(type(data).__name__))


def get_anaconda_version_string(build_time_version=False):
    """Return a string describing current Anaconda version.
    If the current version can't be determined the string
    "unknown" will be returned.

    :param bool build_time_version: return build time version

    Build time version is set at package build time and will
    in most cases be identified by a build number or other identifier
    appended to the upstream tarball version.

    :returns: string describing Anaconda version
    :rtype: str
    """
    # Ignore pylint not finding the version module, since thanks to automake
    # there's a good chance that version.py is not in the same directory as
    # the rest of pyanaconda.
    try:
        from pyanaconda import version  # pylint: disable=no-name-in-module
        if build_time_version:
            return version.__build_time_version__
        else:
            return version.__version__
    except (ImportError, AttributeError):
        # there is a slight chance version.py might be generated incorrectly
        # during build, so don't crash in that case
        return "unknown"


def is_smt_enabled():
    """Is Simultaneous Multithreading (SMT) enabled?

    :return: True or False
    """
    if flags.automatedInstall \
            or not conf.target.is_hardware \
            or not conf.system.can_detect_enabled_smt:
        log.info("Skipping detection of SMT.")
        return False

    try:
        return int(open("/sys/devices/system/cpu/smt/active").read()) == 1
    except (IOError, ValueError):
        log.warning("Failed to detect SMT.")
        return False


def restorecon(paths, root, skip_nonexistent=False):
    """Try to restore contexts for a list of paths.

    Do not fail if the program does not exist because it was not in the payload, just say so.

    :param [str] paths: list of paths to restore
    :param str root: root to run in; mandatory because we restore contexts only on the new system
    :param bool skip_nonexistent: optionally, do not fail if some of the paths do not exist
    :return bool: did anything run at all
    """
    if skip_nonexistent:
        opts = ["-ir"]
    else:
        opts = ["-r"]

    try:
        execWithRedirect("restorecon", opts + paths, root=root)
    except FileNotFoundError:
        return False
    else:
        return True


class LazyObject(object):
    """The lazy object."""

    def __init__(self, getter):
        """Create a proxy of an object.

        The object might not exist until we call the given
        function. The function is called only when we try
        to access the attributes of the object.

        The returned object is not cached in this class.
        We call the function every time.

        :param getter: a function that returns the object
        """
        self._getter = getter

    @property
    def _object(self):
        return self._getter()

    def __eq__(self, other):
        return self._object == other

    def __hash__(self):
        return self._object.__hash__()

    def __getattr__(self, name):
        return getattr(self._object, name)

    def __setattr__(self, name, value):
        if name in ("_getter", ):
            return super().__setattr__(name, value)

        return setattr(self._object, name, value)
