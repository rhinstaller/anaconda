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
#	( name )
#	( name, Function )
#
# in the second case, the function is called directly from the dispatcher

# All install steps take the anaconda object as their sole argument.  This
# gets passed in when we call the function.
installSteps = [
    ("welcome", ),
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
    ("reipl", doReIPL, ),
    ("install", ),
    ("preinstallconfig", doPreInstall, ),
    ("installpackages", doInstall, ),
    ("postinstallconfig", doPostInstall, ),
    ("writeconfig", writeConfiguration, ),
    ("firstboot", firstbootConfiguration, ),
    ("instbootloader", writeBootloader, ),
    ("writeksconfig", writeKSConfiguration, ),
    ("setfilecon", setFileCons, ),
    ("copylogs", copyAnacondaLogs, ),
    ("methodcomplete", doMethodComplete, ),
    ("postscripts", runPostScripts, ),
    ("dopostaction", doPostAction, ),
    ("complete", ),
    ]

class Dispatcher(object):

    def gotoPrev(self):
        self._setDir(DISPATCH_BACK)
	self.moveStep()

    def gotoNext(self):
	self._setDir(DISPATCH_FORWARD)
	self.moveStep()

    def canGoBack(self):
        # begin with the step before this one.  If all steps are skipped,
        # we can not go backwards from this screen
        i = self.step - 1
        while i >= self.firstStep:
            if not self.stepIsDirect(i) and not self.skipSteps.has_key(installSteps[i][0]):
                return True
            i = i - 1
        return False

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
                log.warning("step %s does not exist", name)

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

	#raise KeyError, ("unknown step %s" % stepToSkip)
        log.warning("step %s does not exist", name)

    def stepIsDirect(self, step):
        """Takes a step number"""
        if len(installSteps[step]) == 2:
            return True
        else:
            return False

    def moveStep(self):
	if self.step == None:
	    self.step = self.firstStep
	else:
            log.info("leaving (%d) step %s" %(self._getDir(), installSteps[self.step][0]))
            self.step = self.step + self._getDir()

	if self.step >= len(installSteps):
	    return None

        while self.step >= self.firstStep and self.step < len(installSteps) \
            and (self.stepInSkipList(self.step) or self.stepIsDirect(self.step)):

            if self.stepIsDirect(self.step) and not self.stepInSkipList(self.step):
	        (stepName, stepFunc) = installSteps[self.step]
                log.info("moving (%d) to step %s" %(self._getDir(), stepName))
                log.debug("%s is a direct step" %(stepName,))
		rc = stepFunc(self.anaconda)
                if rc in [DISPATCH_BACK, DISPATCH_FORWARD]:
		    self._setDir(rc)
                log.info("leaving (%d) step %s" %(self._getDir(), stepName))
		# if anything else, leave self.dir alone

	    self.step = self.step + self._getDir()
	    if self.step == len(installSteps):
		return None

	if (self.step < 0):
	    # pick the first step not in the skip list
	    self.step = 0
	    while self.skipSteps.has_key(installSteps[self.step][0]):
		self.step = self.step + 1
	elif self.step >= len(installSteps):
	    self.step = len(installSteps) - 1
	    while self.skipSteps.has_key(installSteps[self.step][0]):
		self.step = self.step - 1
        log.info("moving (%d) to step %s" %(self._getDir(), installSteps[self.step][0]))

    def currentStep(self):
	if self.step == None:
	    self.gotoNext()
	elif self.step >= len(installSteps):
	    return (None, None)

	stepInfo = installSteps[self.step]
	step = stepInfo[0]

	return (step, self.anaconda)

    def __init__(self, anaconda):
        self.anaconda = anaconda
	self.anaconda.dir = DISPATCH_FORWARD
	self.step = None
	self.skipSteps = {}

	self.firstStep = 0

    def _getDir(self):
        return self.anaconda.dir

    def _setDir(self, dir):
        self.anaconda.dir = dir

    dir = property(_getDir,_setDir)
