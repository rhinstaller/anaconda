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

import upgrade
from snack import *
from constants import *
from constants_text import *
from text import WaitWindow, OkCancelWindow, ProgressWindow, PassphraseEntryWindow, stepToClasses
from flags import flags
import sys
import os
import isys
from storage import mountExistingSystem
from installinterfacebase import InstallInterfaceBase
import iutil
import shutil
import time
import network
import subprocess

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("anaconda")

class RescueInterface(InstallInterfaceBase):
    def waitWindow(self, title, text):
        return WaitWindow(self.screen, title, text)

    def progressWindow(self, title, text, total):
        return ProgressWindow(self.screen, title, text, total)

    def detailedMessageWindow(self, title, text, longText=None, type="ok",
                              default=None, custom_icon=None,
                              custom_buttons=[]):
        return self.messageWindow(title, text, type, default, custom_icon,
                                  custom_buttons)

    def messageWindow(self, title, text, type = "ok", default = None,
                      custom_icon=None, custom_buttons=[]):
	if type == "ok":
	    ButtonChoiceWindow(self.screen, title, text,
			       buttons=[TEXT_OK_BUTTON])
        elif type == "yesno":
            if default and default == "no":
                btnlist = [TEXT_NO_BUTTON, TEXT_YES_BUTTON]
            else:
                btnlist = [TEXT_YES_BUTTON, TEXT_NO_BUTTON]
	    rc = ButtonChoiceWindow(self.screen, title, text,
			       buttons=btnlist)
            if rc == "yes":
                return 1
            else:
                return 0
	elif type == "custom":
	    tmpbut = []
	    for but in custom_buttons:
		tmpbut.append(string.replace(but,"_",""))

	    rc = ButtonChoiceWindow(self.screen, title, text, width=60,
				    buttons=tmpbut)

	    idx = 0
	    for b in tmpbut:
		if string.lower(b) == rc:
		    return idx
		idx = idx + 1
	    return 0
	else:
	    return OkCancelWindow(self.screen, title, text)

    def enableNetwork(self, anaconda):
        if len(anaconda.network.netdevices) == 0:
            return False
        from netconfig_text import NetworkConfiguratorText
        w = NetworkConfiguratorText(self.screen, anaconda)
        ret = w.run()
        return ret != INSTALL_BACK

    def passphraseEntryWindow(self, device):
        w = PassphraseEntryWindow(self.screen, device)
        (passphrase, isglobal) = w.run()
        w.pop()
        return (passphrase, isglobal)

    def resetInitializeDiskQuestion(self):
        self._initLabelAnswers = {}

    def resetReinitInconsistentLVMQuestion(self):
        self._inconsistentLVMAnswers = {}

    def shutdown (self):
        pass

    def suspend(self):
        pass

    def resume(self):
        pass

    def __init__(self, screen):
        InstallInterfaceBase.__init__(self)
        self.screen = screen

# XXX grub-install is stupid and uses df output to figure out
# things when installing grub.  make /etc/mtab be at least
# moderately useful.  
def makeMtab(instPath, storage):
    try:
        f = open(instPath + "/etc/mtab", "w+")
    except IOError, e:
        log.info("failed to open /etc/mtab for write: %s" % e)
        return

    try:
        f.write(storage.mtab)
    finally:
        f.close()

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
    except IOError, e:
        log.info("failed to write /etc/fstab: %s" % e)

# make sure they have a resolv.conf in the chroot
def makeResolvConf(instPath):
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

#
# Write out something useful for networking and start interfaces
#
def startNetworking(network, intf):
    # do lo first
    try:
        os.system("/usr/sbin/ifconfig lo 127.0.0.1")
    except:
        log.error("Error trying to start lo in rescue.py::startNetworking()")

    # start up dhcp interfaces first
    if not network.bringUp():
        log.error("Error bringing up network interfaces")

def runShell(screen = None, msg=""):
    if screen:
        screen.suspend()

    print
    if msg:
        print (msg)
    print(_("When finished please exit from the shell and your "
            "system will reboot."))
    print

    proc = None

    if os.path.exists("/usr/bin/firstaidkit-qs"):
        proc = subprocess.Popen(["/usr/bin/firstaidkit-qs"])
        proc.wait()
    
    if proc is None or proc.returncode!=0:
        if os.path.exists("/bin/bash"):
            iutil.execConsole()
        else:
            print(_("Unable to find /bin/sh to execute!  Not starting shell"))
            time.sleep(5)

    if screen:
        screen.finish()

def runRescue(anaconda):
    for file in [ "services", "protocols", "group", "joe", "man.config",
                  "nsswitch.conf", "selinux", "mke2fs.conf" ]:
        try:
            os.symlink('/mnt/runtime/etc/' + file, '/etc/' + file)
        except:
            pass

    # see if they would like networking enabled
    if not network.hasActiveNetDev():
        screen = SnackScreen()

        while True:
            rc = ButtonChoiceWindow(screen, _("Setup Networking"),
                _("Do you want to start the network interfaces on "
                  "this system?"), [_("Yes"), _("No")])

            if rc != string.lower(_("No")):
                anaconda.intf = RescueInterface(screen)

                if not anaconda.intf.enableNetwork(anaconda):
                    anaconda.intf.messageWindow(_("No Network Available"),
                        _("Unable to activate a networking device.  Networking "
                          "will not be available in rescue mode."))
                    break

                startNetworking(anaconda.network, anaconda.intf)
                break
            else:
                break

        anaconda.intf = None
        screen.finish()

    # Early shell access with no disk access attempts
    if not anaconda.rescue_mount:
        # the %post should be responsible for mounting all needed file systems
        # NOTE: 1st script must be bash or simple python as nothing else might be available in the rescue image
        if anaconda.ksdata:
           from kickstart import runPostScripts
           runPostScripts(anaconda)
        else:
           runShell()

        sys.exit(0)

    screen = SnackScreen()
    anaconda.intf = RescueInterface(screen)

    if anaconda.ksdata:
        if anaconda.ksdata.rescue and anaconda.ksdata.rescue.romount:
            readOnly = 1
        else:
            readOnly = 0
    else:
        # prompt to see if we should try and find root filesystem and mount
        # everything in /etc/fstab on that root
        rc = ButtonChoiceWindow(screen, _("Rescue"),
            _("The rescue environment will now attempt to find your "
              "Linux installation and mount it under the directory "
              "%s.  You can then make any changes required to your "
              "system.  If you want to proceed with this step choose "
              "'Continue'.  You can also choose to mount your file systems "
              "read-only instead of read-write by choosing 'Read-Only'."
              "\n\n"
              "If for some reason this process fails you can choose 'Skip' "
              "and this step will be skipped and you will go directly to a "
              "command shell.\n\n") % (anaconda.rootPath,),
              [_("Continue"), _("Read-Only"), _("Skip")] )

        if rc == string.lower(_("Skip")):
            runShell(screen)
            sys.exit(0)
        elif rc == string.lower(_("Read-Only")):
            readOnly = 1
        else:
            readOnly = 0

    import storage
    storage.storageInitialize(anaconda)

    disks = upgrade.findExistingRoots(anaconda, upgradeany=True)

    if not disks:
        root = None
    elif (len(disks) == 1) or anaconda.ksdata:
        root = disks[0]
    else:
        height = min (len (disks), 12)
        if height == 12:
            scroll = 1
        else:
            scroll = 0

        devList = []
        for (device, relstr) in disks:
            if getattr(device.format, "label", None):
                devList.append("%s (%s) - %s" % (device.name, device.format.label, relstr))
            else:
                devList.append("%s - %s" % (device.name, relstr))

        (button, choice) = \
            ListboxChoiceWindow(screen, _("System to Rescue"),
                                _("Which device holds the root partition "
                                  "of your installation?"), devList,
                                [ _("OK"), _("Exit") ], width = 30,
                                scroll = scroll, height = height,
                                help = "multipleroot")

        if button == string.lower (_("Exit")):
            root = None
        else:
            root = disks[choice]

    rootmounted = 0

    if root:
        try:
            rc = mountExistingSystem(anaconda, root,
                                     allowDirty = 1, warnDirty = 1,
                                     readOnly = readOnly)

            if rc == -1:
                if anaconda.ksdata:
                    log.error("System had dirty file systems which you chose not to mount")
                else:
                    ButtonChoiceWindow(screen, _("Rescue"),
                        _("Your system had dirty file systems which you chose not "
                          "to mount.  Press return to get a shell from which "
                          "you can fsck and mount your partitions.  The system "
                          "will reboot automatically when you exit from the "
                          "shell."), [_("OK")], width = 50)
                rootmounted = 0
            else:
                if anaconda.ksdata:
                    log.info("System has been mounted under: %s" % anaconda.rootPath)
                else:
                    ButtonChoiceWindow(screen, _("Rescue"),
                       _("Your system has been mounted under %(rootPath)s.\n\n"
                         "Press <return> to get a shell. If you would like to "
                         "make your system the root environment, run the command:\n\n"
                         "\tchroot %(rootPath)s\n\nThe system will reboot "
                         "automatically when you exit from the shell.") %
                                       {'rootPath': anaconda.rootPath},
                                       [_("OK")] )
                rootmounted = 1

                # now turn on swap
                if not readOnly:
                    try:
                        anaconda.storage.turnOnSwap()
                    except:
                        log.error("Error enabling swap")

                # and /selinux too
                if flags.selinux and os.path.isdir("%s/selinux" %(anaconda.rootPath,)):
                    try:
                        isys.mount("/selinux", "%s/selinux" %(anaconda.rootPath,),
                                   "selinuxfs")
                    except Exception, e:
                        log.error("error mounting selinuxfs: %s" %(e,))

                    # we have to catch the possible exception
                    # because we support read-only mounting
                    try:
                        fd = open("%s/.autorelabel" % anaconda.rootPath, "w+")
                        fd.close()
                    except Exception, e:
                        log.warning("cannot touch /.autorelabel")

                # set a library path to use mounted fs
                libdirs = os.environ["LD_LIBRARY_PATH"].split(":")
                mounted = map(lambda dir: "/mnt/sysimage%s" % dir, libdirs)
                os.environ["LD_LIBRARY_PATH"] = ":".join(libdirs + mounted)

                # find groff data dir
                try:
                    glst = os.listdir("/mnt/sysimage/usr/share/groff")

                    # find a directory which is a numeral, its where
                    # data files are
                    gversion = None
                    for gdir in glst:
                        try:
                            isone = 1
                            for idx in range(0, len(gdir)):
                                if string.find(string.digits + '.', gdir[idx]) == -1:
                                    isone = 0
                                    break
                            if isone:
                                gversion = gdir
                                break
                        except:
                            gversion = None
                            continue
                except:
                    gversion = None

                if gversion is not None:
                    gpath = "/mnt/sysimage/usr/share/groff/"+gversion
                    os.environ["GROFF_FONT_PATH"] = gpath + '/font'
                    os.environ["GROFF_TMAC_PATH"] = "%s:/mnt/sysimage/usr/share/groff/site-tmac" % (gpath + '/tmac',)

                # do we have bash?
                try:
                    if os.access("/usr/bin/bash", os.R_OK):
                        os.symlink ("/usr/bin/bash", "/bin/bash")
                except:
                    pass
        except:
            # This looks horrible, but all it does is catch every exception,
            # and reraise those in the tuple check. This lets programming
            # errors raise exceptions, while any runtime error will
            # still result in a shell
            (exc, val) = sys.exc_info()[0:2]
            log.error(str(exc)+": "+str(val))
            if exc in (IndexError, ValueError, SyntaxError):
                raise exc, val, sys.exc_info()[2]

            if anaconda.ksdata:
                log.error("An error occurred trying to mount some or all of your system")
            else:
                ButtonChoiceWindow(screen, _("Rescue"),
                    _("An error occurred trying to mount some or all of your "
                      "system. Some of it may be mounted under %s.\n\n"
                      "Press <return> to get a shell. The system will reboot "
                      "automatically when you exit from the shell.") % (anaconda.rootPath,),
                      [_("OK")] )
    else:
        if anaconda.ksdata:
            log.info("No Linux partitions found")
            screen.finish()
            print(_("You don't have any Linux partitions.  Rebooting.\n"))
            sys.exit(0)
        else:
            ButtonChoiceWindow(screen, _("Rescue Mode"),
                               _("You don't have any Linux partitions. Press "
                                 "return to get a shell. The system will reboot "
                                 "automatically when you exit from the shell."),
                               [ _("OK") ], width = 50)

    msgStr = ""

    if rootmounted and not readOnly:
        makeMtab(anaconda.rootPath, anaconda.storage)
        try:
            makeResolvConf(anaconda.rootPath)
        except Exception, e:
            log.error("error making a resolv.conf: %s" %(e,))
        msgStr = _("Your system is mounted under the %s directory.") % (anaconda.rootPath,)

    #create /etc/fstab in ramdisk, so it is easier to work with RO mounted filesystems
    makeFStab()

    # run %post if we've mounted everything
    if anaconda.ksdata:
        from kickstart import runPostScripts
        runPostScripts(anaconda)
    else:
        runShell(screen, msgStr)

    sys.exit(0)
