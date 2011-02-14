#
# dispatch.py: install/upgrade master flow control
#
# Copyright (C) 2001, 2002, 2003, 2004, 2005, 2006  Red Hat, Inc.
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
# Author(s): Erik Troan <ewt@redhat.com>
#

import string
from types import *
from constants import *
from packages import writeKSConfiguration, turnOnFilesystems
from packages import doPostAction
from packages import copyAnacondaLogs
from packages import firstbootConfiguration
from packages import betaNagScreen
from packages import setupTimezone
from packages import setFileCons
from storage import storageInitialize
from storage import storageComplete
from storage.partitioning import doAutoPartition
from bootloader import writeBootloader, bootloaderSetupChoices
from flags import flags
from upgrade import upgradeMountFilesystems
from upgrade import restoreTime
from upgrade import upgradeSwapSuggestion, upgradeMigrateFind
from upgrade import findRootParts, queryUpgradeContinue
from installmethod import doMethodComplete
from kickstart import runPostScripts

from backend import doPostSelection, doBackendSetup, doBasePackageSelect
from backend import doPreInstall, doPostInstall, doInstall
from backend import writeConfiguration

from packages import doReIPL

import logging
log = logging.getLogger("anaconda")

# These are all of the install steps, in order. Note that upgrade and
# install steps are the same thing! Upgrades skip install steps, while
# installs skip upgrade steps.

#
# items are one of
#
#       ( name )
#       ( name, Function )
#
# in the second case, the function is called directly from the dispatcher

# All install steps take the anaconda object as their sole argument.  This
# gets passed in when we call the function.
installSteps = [
    ("language", ),
    ("keyboard", ),
    ("betanag", betaNagScreen, ),
    ("filtertype", ),
    ("filter", ),
    ("storageinit", storageInitialize, ),
    ("findrootparts", findRootParts, ),
    ("findinstall", ),
    ("network", ),
    ("timezone", ),
    ("accounts", ),
    ("setuptime", setupTimezone, ),
    ("parttype", ),
    ("cleardiskssel", ),
    ("autopartitionexecute", doAutoPartition, ),
    ("partition", ),
    ("upgrademount", upgradeMountFilesystems, ),
    ("restoretime", restoreTime, ),
    ("upgradecontinue", queryUpgradeContinue, ),
    ("upgradeswapsuggestion", upgradeSwapSuggestion, ),
    ("addswap", ),
    ("upgrademigfind", upgradeMigrateFind, ),
    ("upgrademigratefs", ),
    ("storagedone", storageComplete, ),
    ("enablefilesystems", turnOnFilesystems, ),
    ("upgbootloader", ),
    ("bootloadersetup", bootloaderSetupChoices, ),
    ("bootloader", ),
    ("reposetup", doBackendSetup, ),
    ("tasksel", ),
    ("basepkgsel", doBasePackageSelect, ),
    ("group-selection", ),
    ("postselection", doPostSelection, ),
    ("install", ),
    ("preinstallconfig", doPreInstall, ),
    ("installpackages", doInstall, ),
    ("postinstallconfig", doPostInstall, ),
    ("writeconfig", writeConfiguration, ),
    ("firstboot", firstbootConfiguration, ),
    ("instbootloader", writeBootloader, ),
    ("reipl", doReIPL, ),
    ("writeksconfig", writeKSConfiguration, ),
    ("setfilecon", setFileCons, ),
    ("copylogs", copyAnacondaLogs, ),
    ("methodcomplete", doMethodComplete, ),
    ("postscripts", runPostScripts, ),
    ("dopostaction", doPostAction, ),
    ("complete", ),
    ]

class Dispatcher(object):

    def go_back(self):
        """
        The caller should make sure canGoBack() is True before calling this
        method.
        """
        self._setDir(DISPATCH_BACK)
        self.dispatch()

    def go_forward(self):
        self._setDir(DISPATCH_FORWARD)
        self.dispatch()

    def canGoBack(self):
        # begin with the step before this one.  If all steps are skipped,
        # we can not go backwards from this screen
        i = self.step - 1
        while i >= self.firstStep:
            if not self.stepIsDirect(i) and not self.skipSteps.has_key(installSteps[i][0]):
                return True
            i = i - 1
        return False

    def run(self):
        self.anaconda.intf.run(self.anaconda)
        log.info("dispatch: finished.")

    def setStepList(self, *steps):
        # only remove non-permanently skipped steps from our skip list
        for step, state in self.skipSteps.items():
            if state == 1:
                del self.skipSteps[step]

        stepExists = {}
        for step in installSteps:
            name = step[0]
            if not name in steps:
                self.skipSteps[name] = 1

            stepExists[name] = 1

        for name in steps:
            if not stepExists.has_key(name):
                #XXX: hack for yum support
                #raise KeyError, ("step %s does not exist" % name)
                log.warning("dispatch: step %s does not exist", name)

    def stepInSkipList(self, step):
        if type(step) == type(1):
            step = installSteps[step][0]
        return self.skipSteps.has_key(step)

    def skipStep(self, stepToSkip, skip = 1, permanent = 0):
        for step in installSteps:
            name = step[0]
            if name == stepToSkip:
                if skip:
                    if permanent:
                        self.skipSteps[name] = 2
                    elif not self.skipSteps.has_key(name):
                        self.skipSteps[name] = 1
                elif self.skipSteps.has_key(name):
                    # if marked as permanent then dont change
                    if self.skipSteps[name] != 2:
                        del self.skipSteps[name]
                return

        log.warning("dispatch: step %s does not exist", stepToSkip)

    def stepIsDirect(self, step):
        """Takes a step number"""
        if len(installSteps[step]) == 2:
            return True
        else:
            return False

    def dispatch(self):
        total_steps = len(installSteps)
        if self.step == None:
            log.info("dispatch: resetting to the first step.")
            self.step = self.firstStep
        else:
            log.info("dispatch: leaving (%d) step %s" %
                     (self.dir, installSteps[self.step][0]))
            self.step += self.dir

        while True:
            if self.step >= total_steps:
                # installation has proceeded beyond the last step: finished
                self.anaconda.intf.shutdown()
                return
            if self.step < 0:
                raise RuntimeError("dispatch: out  of bounds "
                                   "(dir: %d, step: %d)" % (self.dir, self.step))

            if self.stepInSkipList(self.step):
                self.step += self.dir
                continue

            if self.stepIsDirect(self.step):
                # handle a direct step by just calling the function
                (step_name, step_func) = installSteps[self.step]
                log.info("dispatch: moving (%d) to step %s" %
                         (self.dir, step_name))
                log.debug("dispatch: %s is a direct step" % step_name)
                self.dir = step_func(self.anaconda)
            else:
                # handle an indirect step (IOW the user interface has a screen
                # to display to the user):
                step_name = installSteps[self.step][0]
                log.info("dispatch: moving (%d) to step %s" %
                         (self.dir, step_name))
                rc = self.anaconda.intf.display_step(step_name)
                if rc == DISPATCH_WAITING:
                    # a new screen has been set up and we are waiting for the
                    # user input now (this only ever happens with the GTK UI and
                    # is because we need to get back to gtk.main())
                    return
                elif rc == DISPATCH_DEFAULT:
                    log.debug("dispatch: the interface chose "
                                "not to display step %s." % step_name)
                else:
                    self.dir = rc
            log.info("dispatch: leaving (%d) step %s" %
                     (self.dir, step_name))
            self.step += self.dir

    def __init__(self, anaconda):
        self.anaconda = anaconda
        self.anaconda.dir = DISPATCH_FORWARD
        self.step = None
        self.skipSteps = {}

        self.firstStep = 0

    def _getDir(self):
        return self.anaconda.dir

    def _setDir(self, dir):
        if dir not in [DISPATCH_BACK, DISPATCH_FORWARD, DISPATCH_DEFAULT]:
            raise RuntimeError("dispatch: wrong direction code")
        if dir in [DISPATCH_BACK, DISPATCH_FORWARD]:
            self.anaconda.dir = dir

    dir = property(_getDir,_setDir)
