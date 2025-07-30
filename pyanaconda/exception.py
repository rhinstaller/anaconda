#
# exception.py - general exception formatting and saving
#
# Copyright (C) 2000-2013 Red Hat, Inc.
# All rights reserved.
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
import errno
import glob
import os
import re
import shutil
import sys
import time
import traceback

import blivet.errors
import gi
from meh import Config
from meh.dump import ReverseExceptionDump
from meh.handler import ExceptionHandler
from pykickstart.constants import KS_SCRIPT_ONERROR, KS_SCRIPT_TRACEBACK
from simpleline import App
from simpleline.event_loop.signals import ExceptionSignal

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import util
from pyanaconda.core.async_utils import run_in_loop
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import IPMI_FAILED, THREAD_EXCEPTION_HANDLING_TEST
from pyanaconda.core.i18n import _
from pyanaconda.core.product import get_product_is_final_release
from pyanaconda.core.threads import thread_manager
from pyanaconda.errors import NonInteractiveError
from pyanaconda.modules.common.constants.objects import SCRIPTS
from pyanaconda.modules.common.constants.services import RUNTIME
from pyanaconda.modules.common.errors.storage import UnusableStorageError
from pyanaconda.modules.common.task import sync_run_task
from pyanaconda.ui.communication import hubQ

log = get_module_logger(__name__)


class AnacondaReverseExceptionDump(ReverseExceptionDump):

    @property
    def desc(self):
        """
        When traceback will be part of the exception message split the
        description from traceback. Description is used in name of the
        bug in Bugzilla.
        This is useful when saving exception in exception handler and
        raising this exception elsewhere (subprocess exception).

        :return: Exception description (bug name)
        :rtype: str
        """
        if self.type and self.value:
            parsed_exc = traceback.format_exception_only(self.type, self.value)[0].split("\nTraceback")
            description = parsed_exc[0]
            # TODO: remove when fixed (#1277422)
            # Use only first line of description (because of libreport bug - reported)
            description = description.split("\n")[0]
            return description.strip()
        else:
            return ""


class AnacondaExceptionHandler(ExceptionHandler):

    def __init__(self, confObj, intfClass, exnClass, tty_num, gui_lock, interactive):
        """
        :see: python-meh's ExceptionHandler
        :param tty_num: the number of tty the interface is running on

        """

        super().__init__(confObj, intfClass, exnClass)
        self._gui_lock = gui_lock
        self._intf_tty_num = tty_num
        self._interactive = interactive

    def _main_loop_handleException(self, dump_info):
        """
        Helper method with one argument only so that it can be registered
        with run_in_loop to run on idle or called from a handler.

        :type dump_info: an instance of the meh.DumpInfo class

        """

        ty = dump_info.exc_info.type
        value = dump_info.exc_info.value

        if (issubclass(ty, blivet.errors.StorageError) and value.hardware_fault) \
                or (issubclass(ty, OSError) and value.errno == errno.EIO):
            # hardware fault or '[Errno 5] Input/Output error'
            hw_error_msg = _("The installation was stopped due to what "
                             "seems to be a problem with your hardware. "
                             "The exact error message is:\n\n%s.\n\n "
                             "The installer will now terminate.") % str(value)
            self.intf.messageWindow(_("Hardware error occurred"), hw_error_msg)
            self._run_kickstart_scripts()
            util.ipmi_report(IPMI_FAILED)
            sys.exit(1)
        elif isinstance(value, UnusableStorageError):
            self._run_kickstart_scripts()
            util.ipmi_report(IPMI_FAILED)
            sys.exit(1)
        elif isinstance(value, NonInteractiveError):
            self._run_kickstart_scripts()
            util.ipmi_report(IPMI_FAILED)
            sys.exit(1)
        else:
            # This will call postWriteHook.
            super().handleException(dump_info)
            return False

    def handleException(self, dump_info):
        """
        Our own handleException method doing some additional stuff before
        calling the original python-meh's one.

        :type dump_info: an instance of the meh.DumpInfo class
        :see: python-meh's ExceptionHandler.handleException

        """

        log.debug("running handleException")
        # don't try and attach empty or non-existent files (#2185827)
        self.conf.fileList = [
            fn for fn in self.conf.fileList if os.path.exists(fn) and os.path.getsize(fn) > 0
        ]
        exception_lines = traceback.format_exception(*dump_info.exc_info)
        log.critical("\n".join(exception_lines))

        ty = dump_info.exc_info.type
        value = dump_info.exc_info.value

        try:
            gi.require_version("Gtk", "3.0")

            from gi.repository import Gtk

            # XXX: Gtk stopped raising RuntimeError if it fails to
            # initialize. Horay! But will it stay like this? Let's be
            # cautious and raise the exception on our own to work in both
            # cases
            initialized = Gtk.init_check(None)[0]
            if not initialized:
                raise RuntimeError()

            # Attempt to grab the GUI initializing lock, do not block
            if not self._gui_lock.acquire(False):
                # the graphical interface is running, don't crash it by
                # running another one potentially from a different thread
                log.debug("Gtk running, queuing exception handler to the main loop")
                run_in_loop(self._main_loop_handleException, dump_info)
            else:
                log.debug("Gtk not running, starting Gtk and running exception handler in it")
                self._main_loop_handleException(dump_info)

        except (RuntimeError, ImportError, ValueError):
            log.debug("Gtk cannot be initialized")
            # Wayland not running (Gtk cannot be initialized)
            if thread_manager.in_main_thread():
                log.debug("In the main thread, running exception handler")
                if issubclass(ty, NonInteractiveError) or not self._interactive:
                    if issubclass(ty, NonInteractiveError):
                        cmdline_error_msg = _("\nThe installation was stopped due to an "
                                              "error which occurred while running in "
                                              "non-interactive cmdline mode. Since there "
                                              "cannot be any questions in cmdline mode, edit "
                                              "your kickstart file and retry installation. "
                                              "\nThe exact error message is: \n\n%s. \n\nThe "
                                              "installer will now terminate.") % str(value)
                    else:
                        cmdline_error_msg = _("\nRunning in cmdline mode, no interactive "
                                              "debugging allowed.\nThe exact error message is: "
                                              "\n\n%s.\n\nThe installer will now terminate."
                                              ) % str(value)

                    # since there is no UI in cmdline mode and it is completely
                    # non-interactive, we can't show a message window asking the user
                    # to acknowledge the error; instead, print the error out and sleep
                    # for a few seconds before exiting the installer
                    print(cmdline_error_msg, flush=True)
                    self._run_kickstart_scripts()
                    util.ipmi_report(IPMI_FAILED)
                    time.sleep(180)
                    sys.exit(1)
                else:
                    print("\nAn unknown error has occured, look at the "
                          "/tmp/anaconda-tb* file(s) for more details")
                    # in the main thread, run exception handler
                    self._main_loop_handleException(dump_info)
            else:
                log.debug("In a non-main thread, sending a message with exception data")
                # not in the main thread, just send message with exception
                # data and let message handler run the exception handler in
                # the main thread
                exc_info = dump_info.exc_info
                # new Simpleline package is now used in TUI. Look if Simpleline is
                # initialized or if this is some fallback from GTK or other stuff.
                if App.is_initialized():
                    # if Simpleline is initialized enqueue exception there
                    loop = App.get_event_loop()
                    loop.enqueue_signal(ExceptionSignal(App.get_scheduler(), exception_info=exc_info))
                else:
                    hubQ.send_exception((exc_info.type,
                                         exc_info.value,
                                         exc_info.stack))

    def postWriteHook(self, dump_info):
        # See if there is a /root present in the root path and put exception there as well
        if os.access(conf.target.system_root + "/root", os.X_OK):
            try:
                dest = conf.target.system_root + "/root/%s" % os.path.basename(self.exnFile)
                shutil.copyfile(self.exnFile, dest)
            except (shutil.Error, OSError):
                log.error("Failed to copy %s to %s/root", self.exnFile, conf.target.system_root)

        # run kickstart traceback scripts (if necessary)
        self._run_kickstart_scripts()

        util.ipmi_report(IPMI_FAILED)

    def _run_kickstart_scripts(self):
        """Run the %traceback and %onerror kickstart scripts."""
        scripts_proxy = RUNTIME.get_proxy(SCRIPTS)

        # OnError script call
        onerror_task_path = scripts_proxy.RunScriptsWithTask(KS_SCRIPT_ONERROR)
        onerror_task_proxy = RUNTIME.get_proxy(onerror_task_path)

        # Traceback script call
        traceback_task_path = scripts_proxy.RunScriptsWithTask(KS_SCRIPT_TRACEBACK)
        traceback_task_proxy = RUNTIME.get_proxy(traceback_task_path)
        try:
            sync_run_task(onerror_task_proxy)
            sync_run_task(traceback_task_proxy)
        # pylint: disable=bare-except
        # ruff: noqa: E722
        except:
            pass

    def runDebug(self, exc_info):
        if conf.system.can_switch_tty and self._intf_tty_num != 1:
            util.vtActivate(1)

        os.open("/dev/console", os.O_RDWR)   # reclaim stdin
        os.dup2(0, 1)                        # reclaim stdout
        os.dup2(0, 2)                        # reclaim stderr
        #   ^
        #   |
        #   +------ dup2 is magic, I tells ya!

        # bring back the echo
        import termios
        si = sys.stdin.fileno()
        attr = termios.tcgetattr(si)
        attr[3] = attr[3] & termios.ECHO
        termios.tcsetattr(si, termios.TCSADRAIN, attr)

        print("\nEntering debugger...")
        print("Use 'continue' command to quit the debugger and get back to the main window")
        import pdb
        pdb.post_mortem(exc_info.stack)

        if conf.system.can_switch_tty and self._intf_tty_num != 1:
            util.vtActivate(self._intf_tty_num)


def initExceptionHandling(anaconda):
    file_list = ["/tmp/anaconda.log", "/tmp/packaging.log",
                 "/tmp/program.log", "/tmp/storage.log",
                 "/tmp/dnf.librepo.log", "/tmp/hawkey.log",
                 "/tmp/lvm.log", conf.target.system_root + "/root/install.log",
                 "/proc/cmdline", "/root/lorax-packages.log",
                 "/tmp/blivet-gui-utils.log", "/tmp/dbus.log"]

    if os.path.exists("/tmp/syslog"):
        file_list.extend(["/tmp/syslog"])

    if anaconda.opts and anaconda.opts.ksfile:
        file_list.extend([anaconda.opts.ksfile])

    config = Config(programName="anaconda",
                  programVersion=util.get_anaconda_version_string(),
                  programArch=os.uname()[4],
                  attrSkipList=["_intf._actions",
                                "_intf._currentAction._xklwrapper",
                                "_intf._currentAction._spokes[\"KeyboardSpoke\"]._xkl_wrapper",
                                "_intf._currentAction._storage_playground",
                                "_intf._currentAction._spokes[\"CustomPartitioningSpoke\"]._storage_playground",
                                "_intf._currentAction.language.translations",
                                "_intf._currentAction.language.locales",
                                "_intf._currentAction._spokes[\"PasswordSpoke\"]._oldweak",
                                "_intf._currentAction._spokes[\"PasswordSpoke\"]._password",
                                "_intf._currentAction._spokes[\"UserSpoke\"]._password",
                                "_intf._currentAction._spokes[\"UserSpoke\"]._oldweak",
                                "_intf.storage.bootloader.password",
                                "_intf.storage.data",
                                "_intf.storage.ksdata",
                                "_intf.data",
                                "_bootloader.encrypted_password",
                                "_bootloader.password",
                                "payload._groups"],
                  localSkipList=["passphrase", "password", "_oldweak", "_password", "try_passphrase"],
                  fileList=file_list)

    config.register_callback("lsblk_output", lsblk_callback, attchmnt_only=False)
    config.register_callback("nmcli_dev_list", nmcli_dev_list_callback,
                           attchmnt_only=True)

    # provide extra information for libreport
    config.register_callback("type", lambda: "anaconda", attchmnt_only=True)
    config.register_callback("addons", list_addons_callback, attchmnt_only=False)

    if "/tmp/syslog" not in file_list:
        # no syslog, grab output from journalctl and put it also to the
        # anaconda-tb file
        config.register_callback("journalctl", journalctl_callback, attchmnt_only=False)

    if not get_product_is_final_release():
        config.register_callback("release_type", lambda: "pre-release", attchmnt_only=True)

    handler = AnacondaExceptionHandler(config, anaconda.intf.meh_interface,
                                       AnacondaReverseExceptionDump, anaconda.intf.tty_num,
                                       anaconda.gui_initialized, anaconda.interactive_mode)
    handler.install(anaconda)

    return config


def lsblk_callback():
    """Callback to get info about block devices."""

    options = "NAME,SIZE,OWNER,GROUP,MODE,FSTYPE,LABEL,UUID,PARTUUID,FSAVAIL,FSUSE%,MOUNTPOINT"

    return util.execWithCapture("lsblk", ["--bytes", "-o", options])


def nmcli_dev_list_callback():
    """Callback to get info about network devices."""

    return util.execWithCapture("nmcli", ["device", "show"])


def journalctl_callback():
    """Callback to get logs from journalctl."""

    # regex to filter log messages from anaconda's process (we have that in our
    # logs)
    anaconda_log_line = re.compile(r"\[%d\]:" % os.getpid())
    ret = ""
    for line in util.execReadlines("journalctl", ["-b"]):
        if anaconda_log_line.search(line) is None:
            # not an anaconda's message
            ret += line + "\n"

    return ret


def list_addons_callback():
    """
    Callback to get info about the addons potentially affecting Anaconda's
    behaviour.

    """

    # list available addons and take their package names
    addon_pkgs = glob.glob("/usr/share/anaconda/addons/*")
    return ", ".join(addon.rsplit("/", 1)[1] for addon in addon_pkgs)


def test_exception_handling():
    """
    Function that can be used for testing exception handling in anaconda. It
    tries to prepare a worst case scenario designed from bugs seen so far.

    """

    # XXX: this is a huge hack, but probably the only way, how we can get
    #      "unique" stack and thus unique hash and new bugreport
    def raise_exception(msg, non_ascii):
        timestamp = str(time.time()).split(".", 1)[0]

        code = """
def f%s(msg, non_ascii):
        raise RuntimeError(msg)

f%s(msg, non_ascii)
""" % (timestamp, timestamp)

        eval(compile(code, "str_eval", "exec"))  # pylint: disable=eval-used

    # test non-ascii characters dumping
    non_ascii = '\u0159'

    msg = "NOTABUG: testing exception handling"

    # raise exception from a separate thread
    thread_manager.add_thread(
        name=THREAD_EXCEPTION_HANDLING_TEST,
        target=raise_exception,
        args=(msg, non_ascii)
    )
