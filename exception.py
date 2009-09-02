#
# exception.py - general exception formatting and saving
#
# Copyright (C) 2000, 2001, 2002, 2003, 2004, 2005, 2006, 2007  Red Hat, Inc.
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
# Author(s): Matt Wilson <msw@redhat.com>
#            Erik Troan <ewt@redhat.com>
#            Chris Lumens <clumens@redhat.com>
#
from meh.handler import *
from meh.dump import *
import isys
import sys
import os
import shutil
import signal
from flags import flags
import kickstart

import logging
log = logging.getLogger("anaconda")

class AnacondaExceptionHandler(ExceptionHandler):
    def postWriteHook(self, (ty, value, tb), anaconda):
        # See if /mnt/sysimage is present and put exception there as well
        if os.access("/mnt/sysimage/root", os.X_OK):
            try:
                shutil.copyfile("/tmp/anacdump.txt", "/mnt/sysimage/root/anacdump.txt")
            except:
                log.error("Failed to copy anacdump.txt to /mnt/sysimage/root")
                pass

        # run kickstart traceback scripts (if necessary)
        try:
            if anaconda.isKickstart:
                kickstart.runTracebackScripts(anaconda)
        except:
            pass

    def runDebug(self, (ty, value, tb)):
        # vtActivate does not work on certain ppc64 machines, so just skip
        # that and continue with the rest of the debugger setup.
        try:
            isys.vtActivate(1)
        except SystemError:
            pass

        self.intf.__del__ ()

        pidfl = "/tmp/vncshell.pid"
        if os.path.exists(pidfl) and os.path.isfile(pidfl):
            pf = open(pidfl, "r")
            for pid in pf.readlines():
                if not int(pid) == os.getpid():
                    os.kill(int(pid), signal.SIGKILL)
            pf.close()

        if not flags.test:
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
        import pdb
        pdb.post_mortem (tb)
        os.kill(os.getpid(), signal.SIGKILL)

def initExceptionHandling(anaconda):
    conf = Config(programName="anaconda",
                  programVersion=isys.getAnacondaVersion(),
                  bugFiler=anaconda.id.instClass.bugFiler,
                  attrSkipList=[ "anaconda.backend.ayum",
                                 "anaconda.backend.dlpkgs",
                                 "anaconda.id.accounts",
                                 "anaconda.id.bootloader.password",
                                 "anaconda.id.comps",
                                 "anaconda.id.dispatch",
                                 "anaconda.id.hdList",
                                 "anaconda.id.ksdata",
                                 "anaconda.id.instLanguage.font",
                                 "anaconda.id.instLanguage.kbd",
                                 "anaconda.id.instLanguage.info",
                                 "anaconda.id.instLanguage.localeInfo",
                                 "anaconda.id.instLanguage.nativeLangNames",
                                 "anaconda.id.instLanguage.tz",
                                 "anaconda.id.keyboard._mods._modelDict",
                                 "anaconda.id.keyboard.modelDict",
                                 "anaconda.id.storage.encryptionPassphrase",
                                 "anaconda.id.rootPassword",
                                 "anaconda.id.tmpData",
                                 "anaconda.intf.icw.buff",
                                 "anaconda.intf.icw.currentWindow.storage.encryptionPassphrase",
                                 "anaconda.intf.icw.stockButtons",
                                 "dispatch.sack.excludes",
                               ],
                  localSkipList=[ "passphrase", "password" ],
                  fileList=[ "/tmp/syslog", "/tmp/anaconda.log", "/tmp/lvmout",
                             "/tmp/resize.out", "/tmp/program.log",
                             "/tmp/storage.log", "/tmp/yum.log",
                             anaconda.rootPath + "/root/install.log",
                             anaconda.rootPath + "/root/upgrade.log",
                             "/proc/cmdline"])
    handler = AnacondaExceptionHandler(conf, anaconda.intf, ReverseExceptionDump)
    handler.install(anaconda)
