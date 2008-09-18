#
# cmdline.py - non-interactive, very very simple frontend to anaconda
#
# Jeremy Katz <katzj@redhat.com
#
# Copyright 2003 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# general public license.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import sys, os
import isys, iutil
import time
import signal
import parted, rpm
from constants import *
from flags import flags

from rhpl.translate import _, cat, N_

import logging
log = logging.getLogger("anaconda")

stepToClasses = { "install" : "setupProgressDisplay" }

class WaitWindow:
    def pop(self):
        pass

    def __init__(self, title, text):
        print text

class ProgressWindow:
    def pop(self):
        print ""

    def set(self, amount):
        if amount == self.total:
            print _("Completed"),

    def refresh(self):
        pass

    def __init__(self, title, text, total, updpct = 0.05):
        self.total = total
        print text
        print _("In progress...   "),

class InstallInterface:
    def __init__(self):
#        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTSTP, signal.SIG_DFL)

    def __del__(self):
        pass

    def shutdown(self):
        pass

    def suspend(self):
        pass

    def resume(self):
        pass

    def getInstallKey(self, *args):
        print _("Can't have a question in command line mode!")
        while 1:
            time.sleep(5)

    def getLuksPassphrase(self, *args):
        print _("Can't have a question in command line mode!")
        while 1:
            time.sleep(5)

    def progressWindow(self, title, text, total, updpct = 0.05):
        return ProgressWindow(title, text, total, updpct)

    def kickstartErrorWindow(self, text):
        s = _("The following error was found while parsing your "
              "kickstart configuration:\n\n%s") %(text,)
        print s

        while 1:
            time.sleep(5)
        
    def messageWindow(self, title, text, type="ok", default = None,
                      custom_icon = None, custom_buttons = []):
        if type == "ok":
            print text
        else:
            print _("Can't have a question in command line mode!")
            print title
            print text
            print type, custom_buttons

            # don't exit
            while 1:
                time.sleep(5)

    def exceptionWindow(self, shortText, longTextFile):
        print shortText

    def partedExceptionWindow(self, exc):
        # if our only option is to cancel, let us handle the exception
        # in our code and avoid popping up the exception window here.
        log.critical("parted exception: %s: %s" %(exc.type_string,exc.message))
        if exc.options == parted.EXCEPTION_CANCEL:
            return parted.EXCEPTION_UNHANDLED

        print _("Parted exceptions can't be handled in command line mode!")
        print exc.message

        # don't exit
        while 1:
            time.sleep(5)

    def waitWindow(self, title, text):
        return WaitWindow(title, text)

    def beep(self):
        pass

    def run(self, anaconda):
        anaconda.id.fsset.registerMessageWindow(self.messageWindow)
        anaconda.id.fsset.registerProgressWindow(self.progressWindow)
        anaconda.id.fsset.registerWaitWindow(self.waitWindow)        
        parted.exception_set_handler(self.partedExceptionWindow)        

        (step, instance) = anaconda.dispatch.currentStep()
        while step:
            if stepToClasses.has_key(step):
                s = "nextWin = %s" %(stepToClasses[step],)
                exec s
                nextWin(instance)
            else:
                print "In interactive step %s, can't continue" %(step,)
                while 1:
                    time.sleep(1)

            anaconda.dispatch.gotoNext()
	    (step, instance) = anaconda.dispatch.currentStep()
            

class progressDisplay:
    def __init__(self):
        pass

    def __del__(self):
        pass

    def completePackage(self, hdr, timer):
        self.numComplete = self.numComplete + 1
	self.sizeComplete = self.sizeComplete + (hdr[rpm.RPMTAG_SIZE] / 1024)

        print _("Done [%d/%d]" %(self.numComplete, self.total))

    def setPackageScale(self, amount, total):
        pass

    def setPackage(self, hdr):
        print _("Installing %s-%s-%s... ") %(hdr[rpm.RPMTAG_NAME],
                                             hdr[rpm.RPMTAG_VERSION],
                                             hdr[rpm.RPMTAG_RELEASE]),

    def processEvents(self):
        pass

    def setSizes(self, total, totalSize, totalFiles):
        self.total = total
        self.totalSize = totalSize
        self.numComplete = 0
        self.sizeComplete = 0

    def setPackageStatus(self, state, amount):
        if state != "downloading":
            print state


def setupProgressDisplay(anaconda):
    if anaconda.dir == DISPATCH_BACK:
        anaconda.id.setInstallProgressClass(None)
        return DISPATCH_BACK
    else:
        anaconda.id.setInstallProgressClass(progressDisplay())
        
    return DISPATCH_FORWARD
