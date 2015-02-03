#
# iutil.py - generic install utility functions
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
# Author(s): Erik Troan <ewt@redhat.com>
#

import glob
import os
import stat
import os.path
import errno
import subprocess
import unicodedata
# Used for ascii_lowercase, ascii_uppercase constants
import string # pylint: disable=deprecated-module
import tempfile
import types
import re
from urllib import quote, unquote
import gettext
import signal

from gi.repository import GLib

from pyanaconda.flags import flags
from pyanaconda.constants import DRACUT_SHUTDOWN_EJECT, TRANSLATIONS_UPDATE_DIR, UNSUPPORTED_HW
from pyanaconda.regexes import URL_PARSE

from pyanaconda.i18n import _

import logging
log = logging.getLogger("anaconda")
program_log = logging.getLogger("program")

from pyanaconda.anaconda_log import program_log_lock

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
    env.update({"ANA_INSTALL_PATH": getSysroot()})
    env.update(_child_env)
    return env

_root_path = "/mnt/sysimage"

def getTargetPhysicalRoot():
    """Returns the path to the "physical" storage root, traditionally /mnt/sysimage.

    This may be distinct from the sysroot, which could be a
    chroot-type subdirectory of the physical root.  This is used for
    example by all OSTree-based installations.
    """

    # We always use the traditional /mnt/sysimage - the physical OS
    # target is never mounted anywhere else.  This API call just
    # allows us to have a clean "git grep ROOT_PATH" in other parts of
    # the code.
    return _root_path

def setTargetPhysicalRoot(path):
    """Change the physical root path

    :param string path: Path to use instead of /mnt/sysimage/
    """
    global _root_path
    _root_path = path

_sysroot = _root_path

def getSysroot():
    """Returns the path to the target OS installation.

    For ordinary package-based installations, this is the same as the
    target root.
    """
    return _sysroot

def setSysroot(path):
    """Change the OS root path.
       :param path: The new OS root path

    This should only be used by Payload subclasses which install operating
    systems to non-default roots.
    """
    global _sysroot
    _sysroot = path

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
    if target_root == _root_path:
        target_root = getSysroot()

    # Check for and save a preexec_fn argument
    preexec_fn = kwargs.pop("preexec_fn", None)

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
        program_log.info("Running... %s", " ".join(argv))

    env = augmentEnv()
    for var in env_prune:
        env.pop(var, None)

    if reset_lang:
        env.update({"LC_ALL": "C"})

    if env_add:
        env.update(env_add)

    return subprocess.Popen(argv,
                            stdin=stdin,
                            stdout=stdout,
                            stderr=stderr,
                            close_fds=True,
                            preexec_fn=preexec, cwd=root, env=env, **kwargs)

def startX(argv, output_redirect=None):
    """ Start X and return once X is ready to accept connections.

        X11, if SIGUSR1 is set to SIG_IGN, will send SIGUSR1 to the parent
        process once it is ready to accept client connections. This method
        sets that up and waits for the signal or bombs out if nothing happens
        for a minute. The process will also be added to the list of watched
        processes.

        :param argv: The command line to run, as a list
        :param output_redirect: file or file descriptor to redirect stdout and stderr to
    """
    # Use a list so the value can be modified from the handler function
    x11_started = [False]
    def sigusr1_handler(num, frame):
        log.debug("X server has signalled a successful start.")
        x11_started[0] = True

    # Fail after, let's say a minute, in case something weird happens
    # and we don't receive SIGUSR1
    def sigalrm_handler(num, frame):
        # Check that it didn't make it under the wire
        if x11_started[0]:
            return
        log.error("Timeout trying to start %s", argv[0])
        raise ExitError("Timeout trying to start %s" % argv[0])

    # preexec_fn to add the SIGUSR1 handler in the child
    def sigusr1_preexec():
        signal.signal(signal.SIGUSR1, signal.SIG_IGN)

    try:
        old_sigusr1_handler = signal.signal(signal.SIGUSR1, sigusr1_handler)
        old_sigalrm_handler = signal.signal(signal.SIGALRM, sigalrm_handler)

        # Start the timer
        signal.alarm(60)

        childproc = startProgram(argv, stdout=output_redirect, stderr=output_redirect,
                preexec_fn=sigusr1_preexec)
        watchProcess(childproc, argv[0])

        # Wait for SIGUSR1
        while not x11_started[0]:
            signal.pause()

    finally:
        # Put everything back where it was
        signal.alarm(0)
        signal.signal(signal.SIGUSR1, old_sigusr1_handler)
        signal.signal(signal.SIGALRM, old_sigalrm_handler)

def _run_program(argv, root='/', stdin=None, stdout=None, env_prune=None, log_output=True,
        binary_output=False, filter_stderr=False):
    """ Run an external program, log the output and return it to the caller
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
        if output_string:
            if binary_output:
                output_lines = [output_string]
            else:
                if output_string[-1] != "\n":
                    output_string = output_string + "\n"
                output_lines = output_string.splitlines(True)

            if log_output:
                with program_log_lock:
                    for line in output_lines:
                        program_log.info(line.strip())

            if stdout:
                stdout.write(output_string)

        # If stderr was filtered, log it separately
        if filter_stderr and err_string and log_output:
            err_lines = err_string.splitlines(True)

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

def execInSysroot(command, argv, stdin=None):
    """ Run an external program in the target root.
        :param command: The command to run
        :param argv: The argument list
        :param stdin: The file object to read stdin from.
        :return: The return code of the command
    """

    return execWithRedirect(command, argv, stdin=stdin, root=getSysroot())

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
    if flags.testing:
        log.info("not running command because we're testing: %s %s",
                 command, " ".join(argv))
        return 0

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
    if flags.testing:
        log.info("not running command because we're testing: %s %s",
                 command, " ".join(argv))
        return ""

    argv = [command] + argv
    return _run_program(argv, stdin=stdin, root=root, log_output=log_output,
            filter_stderr=filter_stderr)[1]

def execReadlines(command, argv, stdin=None, root='/', env_prune=None):
    """ Execute an external command and return the line output of the command
        in real-time.

        This method assumes that there is a reasonably low delay between the
        end of output and the process exiting. If the child process closes
        stdout and then keeps on truckin' there will be problems.

        :param command: The command to run
        :param argv: The argument list
        :param stdin: The file object to read stdin from.
        :param stdout: Optional file object to redirect stdout and stderr to.
        :param stderr: not used
        :param root: The directory to chroot to before running command.
        :param env_prune: environment variable to remove before execution

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

        def next(self):
            # Read the next line, blocking if a line is not yet available
            line = self._proc.stdout.readline()
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

    try:
        proc = startProgram(argv, root=root, stdin=stdin, env_prune=env_prune, bufsize=1)
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

# Dictionary of processes to watch in the form {pid: [name, GLib event source id], ...}
_forever_pids = {}
# Set to True if process watching is handled by GLib
_watch_process_glib = False
_watch_process_handler_set = False

class ExitError(RuntimeError):
    pass

# Raise an error on process exit. The argument is a list of tuples
# of the form [(name, status), ...] with statuses in the subprocess
# format (>=0 is return codes, <0 is signal)
def _raise_exit_error(statuses):
    exn_message = []

    for proc_name, status in statuses:
        if status >= 0:
            status_str = "with status %s" % status
        else:
            status_str = "on signal %s" % -status

        exn_message.append("%s exited %s" % (proc_name, status_str))

    raise ExitError(", ".join(exn_message))

# Signal handler used with watchProcess
def _sigchld_handler(num=None, frame=None):
    # Check whether anything in the list of processes being watched has
    # exited. We don't want to call waitpid(-1), since that would break
    # anything else using wait/waitpid (like the subprocess module).
    exited_pids = []
    exit_statuses = []

    for child_pid in _forever_pids:
        try:
            pid_result, status = eintr_retry_call(os.waitpid, child_pid, os.WNOHANG)
        except OSError as e:
            if e.errno == errno.ECHILD:
                continue

        if pid_result:
            proc_name = _forever_pids[child_pid][0]
            exited_pids.append(child_pid)

            # Convert the wait-encoded status to the format used by subprocess
            if os.WIFEXITED(status):
                sub_status = os.WEXITSTATUS(status)
            else:
                # subprocess uses negative return codes to indicate signal exit
                sub_status = -os.WTERMSIG(status)

            exit_statuses.append((proc_name, sub_status))

    for child_pid in exited_pids:
        if _forever_pids[child_pid][1]:
            GLib.source_remove(_forever_pids[child_pid][1])
        del _forever_pids[child_pid]

    if exit_statuses:
        _raise_exit_error(exit_statuses)

# GLib callback used with watchProcess
def _watch_process_cb(pid, status, proc_name):
    # Convert the wait-encoded status to the format used by subprocess
    if os.WIFEXITED(status):
        sub_status = os.WEXITSTATUS(status)
    else:
        # subprocess uses negative return codes to indicate signal exit
        sub_status = -os.WTERMSIG(status)

    _raise_exit_error([(proc_name, sub_status)])

def watchProcess(proc, name):
    """Watch for a process exit, and raise a ExitError when it does.

       This method installs a SIGCHLD signal handler and thus interferes
       the child_watch_add methods in GLib. Use watchProcessGLib to convert
       to GLib mode if using a GLib main loop.

       Since the SIGCHLD handler calls wait() on the watched process, this call
       cannot be combined with Popen.wait() or Popen.communicate, and also
       doing so wouldn't make a whole lot of sense.

       :param proc: The Popen object for the process
       :param name: The name of the process
    """
    global _watch_process_handler_set

    if not _watch_process_glib and not _watch_process_handler_set:
        signal.signal(signal.SIGCHLD, _sigchld_handler)
        _watch_process_handler_set = True

    # Add the PID to the dictionary
    # The second item in the list is for the GLib event source id and will be
    # replaced with the id once we have one.
    _forever_pids[proc.pid] = [name, None]

    # If GLib is watching processes, add a watcher. child_watch_add checks if
    # the process has already exited.
    if _watch_process_glib:
        _forever_pids[proc.id][1] = GLib.child_watch_add(proc.pid, _watch_process_cb, name)
    else:
        # Check that the process didn't already exit
        if proc.poll() is not None:
            del _forever_pids[proc.pid]
            _raise_exit_error([(name, proc.returncode)])

def watchProcessGLib():
    """Convert process watching to GLib mode.

       This allows anaconda modes that use GLib main loops to use
       GLib.child_watch_add and continue to watch processes started before the
       main loop.
    """

    global _watch_process_glib

    # The first call to child_watch_add will replace our SIGCHLD handler, and
    # child_watch_add checks if the process has already exited before it returns,
    # which will handle processes that exit while we're in the loop.

    _watch_process_glib = True
    for child_pid in _forever_pids:
        _forever_pids[child_pid][1] = GLib.child_watch_add(child_pid, _watch_process_cb,
                _forever_pids[child_pid])

def unwatchProcess(proc):
    """Unwatch a process watched by watchProcess.

       :param proc: The Popen object for the process.
    """
    if _forever_pids[proc.pid][1]:
        GLib.source_remove(_forever_pids[proc.pid][1])
    del _forever_pids[proc.pid]

def unwatchAllProcesses():
    """Clear the watched process list."""
    global _forever_pids
    for child_pid in _forever_pids:
        if _forever_pids[child_pid][1]:
            GLib.source_remove(_forever_pids[child_pid][1])
    _forever_pids = {}

def getDirSize(directory):
    """ Get the size of a directory and all its subdirectories.
    :param dir: The name of the directory to find the size of.
    :return: The size of the directory in kilobytes.
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
def mkdirChain(directory):
    """
    :param dir: The directory path to create

    """

    try:
        os.makedirs(directory, 0o755)
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
    for rpmfile in glob.glob("%s/var/lib/rpm/__db.*" % getSysroot()):
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

def add_po_path(directory):
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
            gettext.bindtextdomain(basename[:-3], directory)

def setup_translations():
    if os.path.isdir(TRANSLATIONS_UPDATE_DIR):
        add_po_path(TRANSLATIONS_UPDATE_DIR)
    gettext.textdomain("anaconda")

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
        eintr_retry_call(os.chmod, DRACUT_SHUTDOWN_EJECT, 0o755)
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
            raise ProxyStringError(_("No host url"))
        else:
            self.parse_components()

    def parse_url(self):
        """ Parse the proxy url into its component pieces
        """
        # NOTE: If this changes, update tests/regex/proxy.py
        #
        # proxy=[protocol://][username[:password]@]host[:port][path][?query][#fragment]
        # groups (both named and numbered)
        # 1 = protocol
        # 2 = username
        # 3 = password
        # 4 = host
        # 5 = port
        # 6 = path
        # 7 = query
        # 8 = fragment
        m = URL_PARSE.match(self.url)
        if not m:
            raise ProxyStringError(_("malformed URL, cannot parse it."))

        # If no protocol was given default to http.
        self.protocol = m.group("protocol") or "http://"

        if m.group("username"):
            self.username = unquote(m.group("username"))

        if m.group("password"):
            self.password = unquote(m.group("password"))

        if m.group("host"):
            self.host = m.group("host")
            if m.group("port"):
                self.port = m.group("port")
        else:
            raise ProxyStringError(_("URL has no host component"))

        self.parse_components()

    def parse_components(self):
        """ Parse the components of a proxy url into url and noauth_url
        """
        if self.username or self.password:
            self.proxy_auth = "%s:%s@" % (quote(self.username) or "",
                                          quote(self.password) or "")

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
        eintr_retry_call(os.chown, path, uid, gid)

    if not from_uid_only and not from_gid_only:
        # the easy way
        dir_tree_map(root, lambda path: eintr_retry_call(os.chown, path, uid, gid))
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
        tainted = int(open("/proc/sys/kernel/tainted").read())
    except (IOError, ValueError):
        tainted = 0

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

def get_mount_paths(devnode):
    '''given a device node, return a list of all active mountpoints.'''
    devno = os.stat(devnode).st_rdev
    majmin = "%d:%d" % (os.major(devno),os.minor(devno))
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

    # Convert both arguments to unicode if not already
    if isinstance(str1, str):
        str1 = str1.decode('utf-8')
    if isinstance(str2, str):
        str2 = str2.decode('utf-8')

    str1 = str1.lower()
    str1_words = str1.split()
    str2 = str2.lower()

    return all(word in str2 for word in str1_words)

class DataHolder(dict):
    """ A dict that lets you also access keys using dot notation. """
    def __init__(self, **kwargs):
        """ kwargs are set as keys for the dict. """
        dict.__init__(self)

        for attr, value in kwargs.items():
            self[attr] = value

    def __getattr__(self, attr):
        return self[attr]

    def __setattr__(self, attr, value):
        self[attr] = value

    def copy(self):
        return DataHolder(**dict.copy(self))

def xprogressive_delay():
    """ A delay generator, the delay starts short and gets longer
        as the internal counter increases.
        For example for 10 retries, the delay will increases from
        0.5 to 256 seconds.

        :param int retry_number: retry counter
        :returns float: time to wait in seconds
    """
    counter = 1
    while True:
        yield 0.25*(2**counter)
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
    # Sensor num - passed in event
    # Event dir & type - always 0x0 for anaconda's purposes
    # Event data 1, 2, 3 - 0x0 for now
    eintr_retry_call(os.write, fd, "0x4 0x1F %#x 0x0 0x0 0x0 0x0\n" % event)
    eintr_retry_call(os.close, fd)

    execWithCapture("ipmitool", ["sel", "add", path])

    os.remove(path)

# Copied from python's subprocess.py
def eintr_retry_call(func, *args):
    """Retry an interruptible system call if interrupted."""
    while True:
        try:
            return func(*args)
        except (OSError, IOError) as e:
            if e.errno == errno.EINTR:
                continue
            raise

def parent_dir(directory):
    """Return the parent's path"""
    return "/".join(os.path.normpath(directory).split("/")[:-1])
