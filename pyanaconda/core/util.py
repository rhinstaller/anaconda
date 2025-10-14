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

import functools
import importlib.machinery
import importlib.util
import inspect
import os
import os.path
import re
import signal
import subprocess
import sys

# Used for ascii_lowercase, ascii_uppercase constants
import tempfile
import types

import requests
from pykickstart.constants import KS_SCRIPT_ONERROR
from requests_file import FileAdapter
from requests_ftp import FTPAdapter

from pyanaconda.anaconda_loggers import get_module_logger, get_program_logger
from pyanaconda.anaconda_logging import program_log_lock
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import (
    DRACUT_REPO_DIR,
    DRACUT_SHUTDOWN_EJECT,
    IPMI_ABORTED,
    IPMI_FAILED,
    PACKAGES_LIST_FILE,
)
from pyanaconda.core.live_user import get_live_user
from pyanaconda.core.path import join_paths, make_directories, open_with_perm
from pyanaconda.errors import RemovedModuleError
from pyanaconda.modules.common.constants.objects import SCRIPTS
from pyanaconda.modules.common.constants.services import RUNTIME

log = get_module_logger(__name__)
program_log = get_program_logger()

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
    # FIXME: Remove the support for the ANA_INSTALL_PATH variable.
    env.update({"ANA_INSTALL_PATH": conf.target.system_root})
    env.update(_child_env)
    return env


def startProgram(argv, root='/', stdin=None, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                 env_prune=None, env_add=None, reset_handlers=True, reset_lang=True,
                 do_preexec=True, **kwargs):
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
        :param do_preexec: whether to use the preexec function
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

    # Map reset_handlers to the restore_signals Popen argument.
    # restore_signals handles SIGPIPE, and preexec below handles any additional
    # signals ignored by anaconda.
    restore_signals = reset_handlers

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
    partsubp = functools.partial(subprocess.Popen,
                                 argv,
                                 stdin=stdin,
                                 stdout=stdout,
                                 stderr=stderr,
                                 close_fds=True,
                                 restore_signals=restore_signals,
                                 cwd=root, env=env, **kwargs)
    if not do_preexec:
        return partsubp()

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

    return partsubp(preexec_fn=preexec)


def _run_program(argv, root='/', stdin=None, stdout=None, env_prune=None,
                 replace_utf_decode_errors=False,
                 log_output=True, binary_output=False, filter_stderr=False,
                 do_preexec=True, env_add=None, user=None):
    """ Run an external program, log the output and return it to the caller

        NOTE/WARNING: UnicodeDecodeError will be raised if the output of the of the
                      external command can't be decoded as UTF-8.

        :param argv: The command to run and argument
        :param root: The directory to chroot to before running command.
        :param stdin: The file object to read stdin from.
        :param stdout: Optional file object to write the output to.
        :param env_prune: environment variable to remove before execution
        :param replace_utf_decode_errors: whether to substitute � for decoding errors.
        :param log_output: whether to log the output of command
        :param binary_output: whether to treat the output of command as binary data
        :param filter_stderr: whether to exclude the contents of stderr from the returned output
        :param do_preexec: whether to use a preexec_fn for subprocess.Popen
        :param env_add: environment variables added for the execution
        :param user: Specify user UID under which the command will be executed
        :return: The return code of the command and the output
    """
    try:
        if filter_stderr:
            stderr = subprocess.PIPE
        else:
            stderr = subprocess.STDOUT

        proc = startProgram(argv, root=root, stdin=stdin, stdout=subprocess.PIPE, stderr=stderr,
                            env_prune=env_prune, env_add=env_add, do_preexec=do_preexec, user=user)

        (output_string, err_string) = proc.communicate()
        if not binary_output:
            output_string = output_string.decode(
                "utf-8",
                errors="strict" if not replace_utf_decode_errors else "replace"
            )
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
        program_log.debug("Return code of %s: %d", argv[0], proc.returncode)

    return (proc.returncode, output_string)


def execWithRedirect(command, argv, stdin=None, stdout=None, root='/',
                     env_prune=None, env_add=None, log_output=True, binary_output=False,
                     replace_utf_decode_errors=False,
                     do_preexec=True):
    """ Run an external program and redirect the output to a file.

        :param command: The command to run
        :param argv: The argument list
        :param stdin: The file object to read stdin from.
        :param stdout: Optional file object to redirect stdout and stderr to.
        :param root: The directory to chroot to before running command.
        :param env_prune: environment variable to remove before execution
        :param env_add: environment variables added for the execution
        :param replace_utf_decode_errors: whether to ignore decode errors
        :param log_output: whether to log the output of command
        :param binary_output: whether to treat the output of command as binary data
        :param do_preexec: whether to use a preexec_fn for subprocess.Popen
        :return: The return code of the command
    """
    argv = [command] + argv
    return _run_program(argv, stdin=stdin, stdout=stdout, root=root,
                        env_prune=env_prune, env_add=env_add,
                        log_output=log_output, binary_output=binary_output,
                        replace_utf_decode_errors=replace_utf_decode_errors,
                        do_preexec=do_preexec)[0]


def execWithCapture(command, argv, stdin=None, root='/',
                    env_prune=None, env_add=None, replace_utf_decode_errors=False,
                    log_output=True, filter_stderr=False, do_preexec=True):
    """ Run an external program and capture standard out and err.

        :param command: The command to run
        :param argv: The argument list
        :param stdin: The file object to read stdin from.
        :param root: The directory to chroot to before running command.
        :param env_prune: environment variable to remove before execution
        :param env_add: environment variables added for the execution
        :param replace_utf_decode_errors: whether to ignore decode errors
        :param log_output: Whether to log the output of command
        :param filter_stderr: Whether stderr should be excluded from the returned output
        :param do_preexec: whether to use the preexec function
        :return: The output of the command
    """
    argv = [command] + argv

    return _run_program(argv, stdin=stdin, root=root, log_output=log_output,
                        env_prune=env_prune, env_add=env_add,
                        replace_utf_decode_errors=replace_utf_decode_errors,
                        filter_stderr=filter_stderr, do_preexec=do_preexec)[1]

def execProgram(command, argv, stdin=None, root='/', env_prune=None, env_add=None,
                log_output=True, filter_stderr=False, do_preexec=True):
    """ Run an external program and capture standard out and err as well as the return code.

        :param command: The command to run
        :param argv: The argument list
        :param stdin: The file object to read stdin from.
        :param root: The directory to chroot to before running command.
        :param env_prune: environment variable to remove before execution
        :param env_add: environment variables added for the execution
        :param log_output: Whether to log the output of command
        :param filter_stderr: Whether stderr should be excluded from the returned output
        :param do_preexec: whether to use the preexec function
        :return: Tuple of the return code and the output of the command
    """
    argv = [command] + argv

    return _run_program(argv, stdin=stdin, root=root, log_output=log_output, env_prune=env_prune,
                        env_add=env_add, filter_stderr=filter_stderr, do_preexec=do_preexec)


def execWithCaptureAsLiveUser(command, argv, stdin=None, root='/', log_output=True,
                              filter_stderr=False, do_preexec=True):
    """ Run an external program and capture standard out and err as liveuser user.

        The liveuser user account is used on Fedora live media. If we need to read values from the
        running live system we might need to run the commands under the liveuser account.

        :param command: The command to run
        :param argv: The argument list
        :param stdin: The file object to read stdin from.
        :param root: The directory to chroot to before running command.
        :param log_output: Whether to log the output of command
        :param filter_stderr: Whether stderr should be excluded from the returned output
        :param do_preexec: whether to use the preexec function
        :return: The output of the command
    """
    argv = [command] + argv

    user = get_live_user()

    if user is None:
        raise OSError("Live user is requested to run command but can't be found")

    return _run_program(argv, stdin=stdin, root=root, log_output=log_output,
                        filter_stderr=filter_stderr, do_preexec=do_preexec,
                        user=user.uid, env_add=user.env_add, env_prune=user.env_prune)[1]


def execReadlines(command, argv, stdin=None, root='/', env_prune=None, filter_stderr=False,
                  raise_on_nozero=True):
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
        :param raise_on_nozero: Whether a nonzero exit status of the tool should cause an exception

        Output from the file is not logged to program.log
        This returns an iterator with the lines from the command until it has finished
    """

    class ExecLineReader:
        """Iterator class for returning lines from a process and cleaning
           up the process when the output is no longer needed.
        """

        def __init__(self, proc, argv, raise_on_nozero):
            self._proc = proc
            self._argv = argv
            self._raise_on_nozero = raise_on_nozero

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

                # If we don't care about return codes, just finish
                if not self._raise_on_nozero:
                    raise StopIteration

                # Check for successful exit
                if self._proc.returncode < 0:
                    raise OSError("process '%s' was killed by signal %s" %
                                  (self._argv, -self._proc.returncode))
                elif self._proc.returncode > 0:
                    raise OSError("process '%s' exited with status %s" %
                                  (self._argv, self._proc.returncode))
                raise StopIteration

            return line.strip()

        @property
        def rc(self):
            return self._proc.returncode

    argv = [command] + argv

    if filter_stderr:
        stderr = subprocess.DEVNULL
    else:
        stderr = subprocess.STDOUT

    try:
        proc = startProgram(argv, root=root, stdin=stdin, stderr=stderr, env_prune=env_prune)
    except OSError as e:
        with program_log_lock:
            program_log.error("Error running %s: %s", argv[0], e.strerror)
        raise

    return ExecLineReader(proc, argv, raise_on_nozero)


## Run a shell.
def execConsole():
    try:
        proc = startProgram(["/bin/bash"], stdout=None, stderr=None, reset_lang=False)
        proc.wait()
    except OSError as e:
        raise RuntimeError("Error running /bin/bash: " + e.strerror) from e


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
            make_directories(os.path.dirname(DRACUT_SHUTDOWN_EJECT))
            f = open_with_perm(DRACUT_SHUTDOWN_EJECT, "w", 0o755)
            f.write("#!/bin/sh\n")
            f.write("# Created by Anaconda\n")
        else:
            f = open(DRACUT_SHUTDOWN_EJECT, "a")

        f.write("eject %s\n" % (device,))
        f.close()
        log.info("Wrote dracut shutdown eject hook for %s", device)
    except OSError as e:
        log.error("Error writing dracut shutdown eject hook for %s: %s", device, e)


def vtActivate(num):
    """
    Try to switch to tty number $num.

    :type num: int
    :return: whether the switch was successful or not
    :rtype: bool

    """

    try:
        ret = execWithRedirect("chvt", [str(num)], do_preexec=False)
    except OSError as oserr:
        ret = -1
        log.error("Failed to run chvt: %s", oserr.strerror)

    if ret != 0:
        log.error("Failed to switch to tty%d", num)

    return ret == 0


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
    log.info("Reporting the IPMI event: %s", event)

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


def ipmi_abort():
    ipmi_report(IPMI_ABORTED)
    runOnErrorScripts()


def ipmi_failed():
    ipmi_report(IPMI_FAILED)
    runOnErrorScripts()


def runOnErrorScripts():
    from pyanaconda.modules.common.task import sync_run_task
    scripts_proxy = RUNTIME.get_proxy(SCRIPTS)

    # OnError script call
    onerror_task_path = scripts_proxy.RunScriptsWithTask(KS_SCRIPT_ONERROR)
    onerror_task_proxy = RUNTIME.get_proxy(onerror_task_path)
    sync_run_task(onerror_task_proxy)
    log.info("All kickstart %%onerror script(s) have been run")


def requests_session():
    """Return a requests.Session object with file and ftp support."""
    session = requests.Session()
    session.mount("file://", FileAdapter())
    session.mount("ftp://", FTPAdapter())
    return session


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

        module = None
        module_path = None

        try:
            # see what can be found
            spec = importlib.machinery.PathFinder.find_spec(mod_name, [path])
            module_path = spec.origin
            candidate_name, dot, found_ext = module_path.rpartition(".")
            if not dot:
                continue
            found_ext = dot + found_ext

            # see what is already loaded
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
                    for ind in range(len(module_parts)):
                        module_part_name = ".".join(module_parts[:ind + 1])
                        if module_part_name not in sys.modules:
                            module_part = types.ModuleType(module_part_name)
                            module_part.__path__ = [path]
                            sys.modules[module_part_name] = module_part

                    # load the collected module
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[mod_name] = module
                    spec.loader.exec_module(module)

            # get the filenames without the extensions so we can compare those
            # with the .py[co]? equivalence in mind
            # - we do not have to care about files without extension as the
            #   condition at the beginning of the for loop filters out those
            # - found_ext contains the extension of the module importlib found
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
            if found_ext.startswith(".py") and not loaded_ext.startswith(".py"):
                continue

            # if the candidate file is not .py[co]? and the loaded is
            # skip the file as well
            if not found_ext.startswith(".py") and loaded_ext.startswith(".py"):
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


class LazyObject:
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


def get_os_release_value(name, sysroot="/"):
    """Read os-release files and return a value of the specified parameter.

    :param name: a name of the parameter (for example, "VERSION_ID")
    :param sysroot: a path to the system root
    :return: a string with the value of None if nothing found
    """
    # Match the variable assignment (for example, "VERSION_ID=").
    name += "="

    # Search all os-release files in the system root.
    paths = ("/etc/os-release", "/usr/lib/os-release")

    for path in paths:
        try:
            with open(join_paths(sysroot, path), "r") as f:
                for line in f:
                    # Match the current line.
                    if not line.startswith(name):
                        continue

                    # Get the value.
                    value = line[len(name):]

                    # Strip spaces and then quotes.
                    value = value.strip().strip("\"'")
                    return value
        except FileNotFoundError:
            pass

    # No value found.
    log.debug("%s not found in os-release files", name[:-1])
    return None


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


def get_image_packages_info(max_string_chars=0):
    """List of strings containing versions of installer image packages.

    The package version specifications are space separated in the strings.

    :param int max_string_chars: maximum number of character in a string
    :return [str]
    """
    info_lines = []
    if os.path.exists(PACKAGES_LIST_FILE):
        with open(PACKAGES_LIST_FILE) as f:
            while True:
                lines = f.readlines(max_string_chars)
                if not lines:
                    break
                info_lines.append(' '.join(line.strip() for line in lines))
    return info_lines


def is_stage2_on_nfs():
    """Is the installation running from image mounted via NFS?"""
    for line in open("/proc/mounts").readlines():
        values = line.split()
        if len(values) > 2:
            if values[1] == DRACUT_REPO_DIR and values[2] in ("nfs", "nfs4"):
                return True
    return False
