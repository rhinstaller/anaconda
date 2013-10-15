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
# Author(s): Chris Lumens <clumens@redhat.com>
#            David Cantrell <dcantrell@redhat.com>
#            Vratislav Podzimek <vpodzime@redhat.com>
#
from meh import Config
from meh.handler import ExceptionHandler
from meh.dump import ReverseExceptionDump
from pyanaconda import isys, iutil, kickstart
import sys
import os
import shutil
import signal
import time
import re
import errno
import blivet.errors
from pyanaconda.ui.communication import hubQ
from pyanaconda.constants import ROOT_PATH, THREAD_EXCEPTION_HANDLING_TEST
from pyanaconda.threads import threadMgr
from pyanaconda.i18n import _
from pyanaconda import flags

from gi.repository import GLib

import logging
log = logging.getLogger("anaconda")

class AnacondaExceptionHandler(ExceptionHandler):

    def __init__(self, confObj, intfClass, exnClass, tty_num):
        """
        :see: python-meh's ExceptionHandler
        :param tty_num: the number of tty the interface is running on

        """

        ExceptionHandler.__init__(self, confObj, intfClass, exnClass)
        self._intf_tty_num = tty_num

    def run_handleException(self, dump_info):
        """
        Helper method with one argument only so that it can be registered
        with GLib.idle_add() to run on idle or called from a handler.

        :type dump_info: an instance of the meh.DumpInfo class

        """

        super(AnacondaExceptionHandler, self).handleException(dump_info)
        return False

    def handleException(self, dump_info):
        """
        Our own handleException method doing some additional stuff before
        calling the original python-meh's one.

        :type dump_info: an instance of the meh.DumpInfo class
        :see: python-meh's ExceptionHandler.handleException

        """

        log.debug("running handleException")

        ty = dump_info.exc_info.type
        value = dump_info.exc_info.value

        if (issubclass(ty, blivet.errors.StorageError) and value.hardware_fault) \
                or (issubclass(ty, OSError) and value.errno == errno.EIO):
            # hardware fault or '[Errno 5] Input/Output error'
            hw_error_msg = _("The installation was stopped due to what "
                             "seems to be a problem with your hardware. "
                             "The exact error message is:\n\n%s.\n\n "
                             "The installer will now terminate.") % str(value)
            self.intf.messageWindow(_("Hardware error occured"), hw_error_msg)
            sys.exit(0)
        else:
            try:
                from gi.repository import Gtk

                # XXX: Gtk stopped raising RuntimeError if it fails to
                # initialize. Horay! But will it stay like this? Let's be
                # cautious and raise the exception on our own to work in both
                # cases
                initialized = Gtk.init_check(None)[0]
                if not initialized:
                    raise RuntimeError()

                if Gtk.main_level() > 0:
                    # main loop is running, don't crash it by running another one
                    # potentially from a different thread
                    log.debug("Gtk running, queuing exception handler to the "
                             "main loop")
                    GLib.idle_add(self.run_handleException, dump_info)
                else:
                    log.debug("Gtk not running, starting Gtk and running "
                             "exception handler in it")
                    super(AnacondaExceptionHandler, self).handleException(
                                                            dump_info)

            except RuntimeError:
                log.debug("Gtk cannot be initialized")
                # X not running (Gtk cannot be initialized)
                if threadMgr.in_main_thread():
                    log.debug("In the main thread, running exception handler")
                    print "An unknown error has occured, look at the "\
                        "/tmp/anaconda-tb* file(s) for more details"
                    # in the main thread, run exception handler
                    super(AnacondaExceptionHandler, self).handleException(
                                                            dump_info)
                else:
                    log.debug("In a non-main thread, sending a message with "
                             "exception data")
                    # not in the main thread, just send message with exception
                    # data and let message handler run the exception handler in
                    # the main thread
                    exc_info = dump_info.exc_info
                    hubQ.send_exception((exc_info.type,
                                         exc_info.value,
                                         exc_info.stack))

    def postWriteHook(self, dump_info):
        anaconda = dump_info.object

        # See if /mnt/sysimage is present and put exception there as well
        if os.access("/mnt/sysimage/root", os.X_OK):
            try:
                dest = "/mnt/sysimage/root/%s" % os.path.basename(self.exnFile)
                shutil.copyfile(self.exnFile, dest)
            except (shutil.Error, IOError):
                log.error("Failed to copy %s to /mnt/sysimage/root", self.exnFile)

        # run kickstart traceback scripts (if necessary)
        try:
            kickstart.runTracebackScripts(anaconda.ksdata.scripts)
        # pylint: disable-msg=W0702
        except:
            pass

    def runDebug(self, exc_info):
        if flags.can_touch_runtime_system("switch console") \
                and self._intf_tty_num != 1:
            iutil.vtActivate(1)

        pidfl = "/tmp/vncshell.pid"
        if os.path.exists(pidfl) and os.path.isfile(pidfl):
            pf = open(pidfl, "r")
            for pid in pf.readlines():
                if not int(pid) == os.getpid():
                    os.kill(int(pid), signal.SIGKILL)
            pf.close()

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
        print("Use 'continue' command to quit the debugger and get back to "\
              "the main window")
        import pdb
        pdb.post_mortem(exc_info.stack)

        if flags.can_touch_runtime_system("switch console") \
                and self._intf_tty_num != 1:
            iutil.vtActivate(self._intf_tty_num)

def initExceptionHandling(anaconda):
    fileList = [ "/tmp/anaconda.log", "/tmp/packaging.log",
                 "/tmp/program.log", "/tmp/storage.log", "/tmp/ifcfg.log",
                 "/tmp/yum.log", ROOT_PATH + "/root/install.log",
                 "/proc/cmdline" ]

    if os.path.exists("/tmp/syslog"):
        fileList.extend(["/tmp/syslog"])

    if anaconda.opts and anaconda.opts.ksfile:
        fileList.extend([anaconda.opts.ksfile])

    conf = Config(programName="anaconda",
                  programVersion=isys.getAnacondaVersion(),
                  programArch=os.uname()[4],
                  attrSkipList=["_intf._actions",
                                "_intf._currentAction._xklwrapper",
                                "_intf._currentAction._spokes[\"KeyboardSpoke\"]._xkl_wrapper",
                                "_intf._currentAction.language.translations",
                                "_intf._currentAction.language.locales",
                                "_intf._currentAction._spokes[\"PasswordSpoke\"]._oldweak",
                                "_intf._currentAction._spokes[\"PasswordSpoke\"]._password",
                                "_intf._currentAction._spokes[\"UserSpoke\"]._password",
                                "_intf._currentAction._spokes[\"UserSpoke\"]._oldweak",
                                "_intf.storage.bootloader.password",
                                "_intf.storage.data",
                                "_intf.storage.encryptionPassphrase",
                                "_bootloader.encrypted_password",
                                "_bootloader.password",
                                "payload._groups",
                                "payload._yum"],
                  localSkipList=[ "passphrase", "password", "_oldweak", "_password" ],
                  fileList=fileList)

    conf.register_callback("lsblk_output", lsblk_callback, attchmnt_only=True)
    conf.register_callback("nmcli_dev_list", nmcli_dev_list_callback,
                           attchmnt_only=True)
    conf.register_callback("type", lambda: "anaconda", attchmnt_only=True)

    if "/tmp/syslog" not in fileList:
        # no syslog, grab output from journalctl and put it also to the
        # anaconda-tb file
        conf.register_callback("journalctl", journalctl_callback, attchmnt_only=False)

    handler = AnacondaExceptionHandler(conf, anaconda.intf.meh_interface,
                                       ReverseExceptionDump, anaconda.intf.tty_num)
    handler.install(anaconda)

    return conf

def lsblk_callback():
    """Callback to get info about block devices."""

    return iutil.execWithCapture("lsblk", ["--perms", "--fs", "--bytes"])

def nmcli_dev_list_callback():
    """Callback to get info about network devices."""

    return iutil.execWithCapture("nmcli", ["device", "show"])

def journalctl_callback():
    """Callback to get logs from journalctl."""

    # regex to filter log messages from anaconda's process (we have that in our
    # logs)
    anaconda_log_line = re.compile(r"\[%d\]:" % os.getpid())
    ret = ""
    for line in iutil.execReadlines("journalctl", ["-b"]):
        if anaconda_log_line.search(line) is None:
            # not an anaconda's message
            ret += line + "\n"

    return ret

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

        eval(compile(code, "str_eval", "exec"))

    # test non-ascii characters dumping
    non_ascii = u'\u0159'

    msg = "NOTABUG: testing exception handling"

    # raise exception from a separate thread
    from pyanaconda.threads import AnacondaThread
    threadMgr.add(AnacondaThread(name=THREAD_EXCEPTION_HANDLING_TEST,
                                 target=raise_exception,
                                 args=(msg, non_ascii)))
