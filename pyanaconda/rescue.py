#
# rescue.py - anaconda rescue mode setup
#
# Copyright (C) 2001, 2002, 2003, 2004  Red Hat, Inc.  All rights reserved.
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
# Author(s): Mike Fulbright <msf@redhat.com>
#            Jeremy Katz <katzj@redhat.com>
#
import sys
import os
from pyanaconda import iutil
import shutil
import time
import re

from snack import ButtonChoiceWindow, ListboxChoiceWindow,SnackScreen

from pyanaconda.constants import ANACONDA_CLEANUP
from pyanaconda.constants_text import TEXT_OK_BUTTON, TEXT_NO_BUTTON, TEXT_YES_BUTTON
from pyanaconda.text import WaitWindow, OkCancelWindow, ProgressWindow, PassphraseEntryWindow
from pyanaconda.flags import flags
from pyanaconda.installinterfacebase import InstallInterfaceBase
from pyanaconda.i18n import _
from pyanaconda.kickstart import runPostScripts

from blivet import osinstall
from blivet.errors import StorageError
from blivet.devices import LUKSDevice
from blivet.osinstall import storageInitialize, mountExistingSystem

from pykickstart.constants import KS_REBOOT, KS_SHUTDOWN
from gi.repository import BlockDev as blockdev

import meh.ui.text

import logging
log = logging.getLogger("anaconda")

class RescueInterface(InstallInterfaceBase):
    def waitWindow(self, title, text):
        return WaitWindow(self.screen, title, text)

    def progressWindow(self, title, text, total, updpct = 0.05, pulse = False):
        return ProgressWindow(self.screen, title, text, total, updpct, pulse)

    def detailedMessageWindow(self, title, text, longText=None, ty="ok",
                              default=None, custom_icon=None,
                              custom_buttons=None, expanded=False):
        return self.messageWindow(title, text, ty, default, custom_icon,
                                  custom_buttons)

    def messageWindow(self, title, text, ty = "ok", default = None,
                      custom_icon=None, custom_buttons=None):
        if custom_buttons is None:
            custom_buttons = []

        if ty == "ok":
            ButtonChoiceWindow(self.screen, title, text, buttons=[TEXT_OK_BUTTON])
        elif ty == "yesno":
            if default and default == "no":
                btnlist = [TEXT_NO_BUTTON, TEXT_YES_BUTTON]
            else:
                btnlist = [TEXT_YES_BUTTON, TEXT_NO_BUTTON]
            rc = ButtonChoiceWindow(self.screen, title, text, buttons=btnlist)
            if rc == "yes":
                return 1
            else:
                return 0
        elif ty == "custom":
            tmpbut = []
            for but in custom_buttons:
                tmpbut.append(but.replace("_",""))

            rc = ButtonChoiceWindow(self.screen, title, text, width=60, buttons=tmpbut)

            idx = 0
            for b in tmpbut:
                if b.lower() == rc:
                    return idx
                idx += 1
            return 0
        else:
            return OkCancelWindow(self.screen, title, text)

    def passphraseEntryWindow(self, device):
        w = PassphraseEntryWindow(self.screen, device)
        passphrase = w.run()
        w.pop()
        return passphrase

    @property
    def meh_interface(self):
        return self._meh_interface

    @property
    def tty_num(self):
        return 1

    def shutdown (self):
        self.screen.finish()

    def suspend(self):
        pass

    def resume(self):
        pass

    def __init__(self):
        InstallInterfaceBase.__init__(self)
        self.screen = SnackScreen()
        self._meh_interface = meh.ui.text.TextIntf()

def makeFStab(instPath = ""):
    if os.access("/proc/mounts", os.R_OK):
        f = open("/proc/mounts", "r")
        buf = f.read()
        f.close()
    else:
        buf = ""

    try:
        f = open(instPath + "/etc/fstab", "a")
        if buf:
            f.write(buf)
        f.close()
    except IOError as e:
        log.info("failed to write /etc/fstab: %s", e)

# make sure they have a resolv.conf in the chroot
def makeResolvConf(instPath):
    if flags.imageInstall:
        return

    if not os.access("/etc/resolv.conf", os.R_OK):
        return

    if os.access("%s/etc/resolv.conf" %(instPath,), os.R_OK):
        f = open("%s/etc/resolv.conf" %(instPath,), "r")
        buf = f.read()
        f.close()
    else:
        buf = ""

    # already have a nameserver line, don't worry about it
    if buf.find("nameserver") != -1:
        return

    f = open("/etc/resolv.conf", "r")
    buf = f.read()
    f.close()

    # no nameserver, we can't do much about it
    if buf.find("nameserver") == -1:
        return

    shutil.copyfile("%s/etc/resolv.conf" %(instPath,),
                    "%s/etc/resolv.conf.bak" %(instPath,))
    f = open("%s/etc/resolv.conf" %(instPath,), "w+")
    f.write(buf)
    f.close()

def runShell(screen = None, msg=""):
    if screen:
        screen.suspend()

    print
    if msg:
        print(msg)

    if flags.imageInstall:
        print(_("Run %s to unmount the system when you are finished.")
              % ANACONDA_CLEANUP)
    else:
        print(_("When finished please exit from the shell and your "
                "system will reboot."))
    print

    proc = None

    if os.path.exists("/usr/bin/firstaidkit-qs"):
        iutil.execWithRedirect("/usr/bin/firstaidkit-qs", [])

    if proc is None or proc.returncode!=0:
        if os.path.exists("/bin/bash"):
            iutil.execConsole()
        else:
            print(_("Unable to find /bin/sh to execute!  Not starting shell"))
            time.sleep(5)

    if screen:
        screen.finish()

def _exception_handler_wrapper(orig_except_handler, screen, *args):
    """
    Helper function that wraps the exception handler with snack shutdown.

    :param orig_except_handler: original exception handler that should be run
                                after the wrapping changes are done
    :type orig_except_handler: exception handler as can be set as sys.excepthook
    :param screen: snack screen that should be shut down before further actions
    :type screen: snack screen

    """

    screen.finish()
    return orig_except_handler(*args)

def _unlock_devices(intf, storage):
    try_passphrase = None
    for device in storage.devices:
        if device.format.type == "luks":
            skip = False
            unlocked = False
            while not (skip or unlocked):
                if try_passphrase is None:
                    passphrase = intf.passphraseEntryWindow(device.name)
                else:
                    passphrase = try_passphrase

                if passphrase is None:
                    # canceled
                    skip = True
                else:
                    device.format.passphrase = passphrase
                    try:
                        device.setup()
                        device.format.setup()
                        luks_dev = LUKSDevice(device.format.mapName,
                                              parents=[device],
                                              exists=True)
                        storage.devicetree._addDevice(luks_dev)
                        storage.devicetree.populate()
                        unlocked = True
                        # try to use the same passhprase for other devices
                        try_passphrase = passphrase
                    except (StorageError, blockdev.CryptoError) as err:
                        log.error("Failed to unlock %s: %s", device.name, err)
                        device.teardown(recursive=True)
                        device.format.passphrase = None
                        try_passphrase = None

def doRescue(intf, rescue_mount, ksdata):
    import blivet

    # XXX: hook the exception handler wrapper that turns off snack first
    orig_hook = sys.excepthook
    sys.excepthook = lambda ty, val, tb: _exception_handler_wrapper(orig_hook,
                                                                    intf.screen,
                                                                    ty, val, tb)

    for f in [ "services", "protocols", "group", "joe", "man.config",
               "nsswitch.conf", "selinux", "mke2fs.conf" ]:
        try:
            os.symlink('/mnt/runtime/etc/' + f, '/etc/' + f)
        except OSError:
            pass

    # Early shell access with no disk access attempts
    if not rescue_mount:
        # the %post should be responsible for mounting all needed file systems
        # NOTE: 1st script must be bash or simple python as nothing else might be available in the rescue image
        if flags.automatedInstall and ksdata.scripts:
            runPostScripts(ksdata.scripts)
        else:
            runShell()

        sys.exit(0)

    if flags.automatedInstall:
        readOnly = ksdata.rescue.romount
    else:
        # prompt to see if we should try and find root filesystem and mount
        # everything in /etc/fstab on that root
        while True:
            rc = ButtonChoiceWindow(intf.screen, _("Rescue"),
                _("The rescue environment will now attempt to find your "
                  "Linux installation and mount it under the directory "
                  "%s.  You can then make any changes required to your "
                  "system.  If you want to proceed with this step choose "
                  "'Continue'.  You can also choose to mount your file systems "
                  "read-only instead of read-write by choosing 'Read-Only'.  "
                  "\n\n"
                  "If for some reason this process fails you can choose 'Skip' "
                  "and this step will be skipped and you will go directly to a "
                  "command shell.\n\n") % (iutil.getSysroot(),),
                  [_("Continue"), _("Read-Only"), _("Skip")] )

            if rc == _("Skip").lower():
                runShell(intf.screen)
                sys.exit(0)
            else:
                readOnly = rc == _("Read-Only").lower()

            break

    sto = blivet.Blivet(ksdata=ksdata)
    storageInitialize(sto, ksdata, [])
    _unlock_devices(intf, sto)
    roots = osinstall.findExistingInstallations(sto.devicetree)

    if not roots:
        root = None
    elif len(roots) == 1:
        root = roots[0]
    else:
        height = min (len (roots), 12)
        if height == 12:
            scroll = 1
        else:
            scroll = 0

        lst = []
        for root in roots:
            lst.append("%s" % root.name)

        (button, choice) = \
            ListboxChoiceWindow(intf.screen, _("System to Rescue"),
                                _("Which device holds the root partition "
                                  "of your installation?"), lst,
                                [ _("OK"), _("Exit") ], width = 30,
                                scroll = scroll, height = height,
                                help = "multipleroot")

        if button == _("Exit").lower():
            root = None
        else:
            root = roots[choice]

    rootmounted = False

    if root:
        try:
            if not flags.imageInstall:
                msg = _("The system will reboot automatically when you exit "
                        "from the shell.")
            else:
                msg = _("Run %s to unmount the system "
                        "when you are finished.") % ANACONDA_CLEANUP

            mountExistingSystem(sto.fsset, root.device, readOnly=readOnly)

            if flags.automatedInstall:
                log.info("System has been mounted under: %s", iutil.getSysroot())
            else:
                ButtonChoiceWindow(intf.screen, _("Rescue"),
                   _("Your system has been mounted under %(rootPath)s.\n\n"
                     "Press <return> to get a shell. If you would like to "
                     "make your system the root environment, run the command:\n\n"
                     "\tchroot %(rootPath)s\n\n%(msg)s") %
                                   {'rootPath': iutil.getSysroot(),
                                    'msg': msg},
                                   [_("OK")] )
            rootmounted = True

            # now turn on swap
            if not readOnly:
                try:
                    sto.turnOnSwap()
                except StorageError:
                    log.error("Error enabling swap")

            # and selinux too
            if flags.selinux:
                # we have to catch the possible exception
                # because we support read-only mounting
                try:
                    fd = open("%s/.autorelabel" % iutil.getSysroot(), "w+")
                    fd.close()
                except IOError:
                    log.warning("cannot touch /.autorelabel")

            # set a library path to use mounted fs
            libdirs = os.environ.get("LD_LIBRARY_PATH", "").split(":")
            mounted = ["/mnt/sysimage%s" % mdir for mdir in libdirs]
            iutil.setenv("LD_LIBRARY_PATH", ":".join(libdirs + mounted))

            # find groff data dir
            gversion = None
            try:
                glst = os.listdir("/mnt/sysimage/usr/share/groff")
            except OSError:
                pass
            else:
                # find a directory which is a numeral, its where
                # data files are
                for gdir in glst:
                    if re.match(r'\d[.\d]+\d$', gdir):
                        gversion = gdir
                        break

            if gversion is not None:
                gpath = "/mnt/sysimage/usr/share/groff/"+gversion
                iutil.setenv("GROFF_FONT_PATH", gpath + '/font')
                iutil.setenv("GROFF_TMAC_PATH", "%s:/mnt/sysimage/usr/share/groff/site-tmac" % (gpath + '/tmac',))

            # do we have bash?
            try:
                if os.access("/usr/bin/bash", os.R_OK):
                    os.symlink ("/usr/bin/bash", "/bin/bash")
            except OSError:
                pass
        except (ValueError, LookupError, SyntaxError, NameError):
            raise
        except Exception as e:    # pylint: disable=broad-except
            log.error("doRescue caught exception: %s", e)
            if flags.automatedInstall:
                log.error("An error occurred trying to mount some or all of your system")
            else:
                if not flags.imageInstall:
                    msg = _("The system will reboot automatically when you "
                            "exit from the shell.")
                else:
                    msg = _("Run %s to unmount the system "
                            "when you are finished.") % ANACONDA_CLEANUP

                ButtonChoiceWindow(intf.screen, _("Rescue"),
                    _("An error occurred trying to mount some or all of your "
                      "system. Some of it may be mounted under %s.\n\n"
                      "Press <return> to get a shell.") % iutil.getSysroot() + msg,
                      [_("OK")] )
    else:
        if flags.automatedInstall and ksdata.reboot.action in [KS_REBOOT, KS_SHUTDOWN]:
            log.info("No Linux partitions found")
            intf.screen.finish()
            print(_("You don't have any Linux partitions.  Rebooting.\n"))
            sys.exit(0)
        else:
            if not flags.imageInstall:
                msg = _(" The system will reboot automatically when you exit "
                        "from the shell.")
            else:
                msg = ""
            ButtonChoiceWindow(intf.screen, _("Rescue Mode"),
                               _("You don't have any Linux partitions. Press "
                                 "return to get a shell.%s") % msg,
                               [ _("OK") ], width = 50)

    msgStr = ""

    if rootmounted and not readOnly:
        sto.makeMtab()
        try:
            makeResolvConf(iutil.getSysroot())
        except (OSError, IOError) as e:
            log.error("error making a resolv.conf: %s", e)
        msgStr = _("Your system is mounted under the %s directory.") % (iutil.getSysroot(),)
        ButtonChoiceWindow(intf.screen, _("Rescue"), msgStr, [_("OK")] )

    # we do not need ncurses anymore, shut them down
    intf.shutdown()

    #create /etc/fstab in ramdisk, so it is easier to work with RO mounted filesystems
    makeFStab()

    # run %post if we've mounted everything
    if rootmounted and not readOnly and flags.automatedInstall:
        runPostScripts(ksdata.scripts)

    # start shell if reboot wasn't requested
    if not flags.automatedInstall or not ksdata.reboot.action in [KS_REBOOT, KS_SHUTDOWN]:
        runShell(msg=msgStr)

    sys.exit(0)
