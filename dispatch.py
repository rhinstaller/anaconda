#
# dispatch.py: install/upgrade master flow control
#
# Erik Troan <ewt@redhat.com>
#
# Copyright 2001-2006 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# general public license.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import string
from types import *
from constants import *
from packages import writeXConfiguration
from packages import writeKSConfiguration, turnOnFilesystems
from packages import doMigrateFilesystems
from packages import doPostAction
from packages import copyAnacondaLogs
from autopart import doAutoPartition
from packages import firstbootConfiguration
from packages import betaNagScreen
from packages import setupTimezone
from packages import setFileCons
from partitioning import partitionObjectsInitialize
from partitioning import partitioningComplete
from bootloader import writeBootloader, bootloaderSetupChoices
from flags import flags
from upgrade import upgradeMountFilesystems
from upgrade import upgradeSwapSuggestion, upgradeMigrateFind
from upgrade import findRootParts, queryUpgradeContinue
from network import networkDeviceCheck
from installmethod import doMethodComplete

from backend import doPostSelection, doRepoSetup, doBasePackageSelect
from backend import doPreInstall, doPostInstall, doInstall
from backend import writeConfiguration

import logging
log = logging.getLogger("anaconda")

# These are all of the install steps, in order. Note that upgrade and
# install steps are the same thing! Upgrades skip install steps, while
# installs skip upgrade steps.

#
# items are one of
#
#	( name, tuple)
#	( name, Function, tuple)
#
# in the second case, the function is called directly from the dispatcher

installSteps = [
    ("welcome", ("anaconda",)),
    ("betanag", betaNagScreen, ("anaconda",)),
    ("language", ("anaconda",)),
    ("keyboard", ("anaconda",)),
    ("findrootparts", findRootParts, ("anaconda",)),
    ("findinstall", ("anaconda",)),
    ("iscsi", ("anaconda",)),
    ("zfcpconfig", ("anaconda",)),
    ("partitionobjinit", partitionObjectsInitialize, ("anaconda",)),
    ("parttype", ("anaconda",)),    
    ("autopartitionexecute", doAutoPartition, ("anaconda",)),
    ("partition", ("anaconda",)),
    ("upgrademount", upgradeMountFilesystems, ("anaconda",)),
    ("upgradecontinue", queryUpgradeContinue, ("anaconda",)),
    ("upgradeswapsuggestion", upgradeSwapSuggestion, ("anaconda",)),
    ("addswap", ("anaconda",)),
    ("partitiondone", partitioningComplete, ("anaconda",)),
    ("upgrademigfind", upgradeMigrateFind, ("anaconda",)),
    ("upgrademigratefs", ("anaconda",)),
    ("upgbootloader", ("anaconda",)),
    ("bootloadersetup", bootloaderSetupChoices, ("anaconda",)),
    ("bootloader", ("anaconda",)),
    ("bootloaderadvanced", ("anaconda",)),
    ("networkdevicecheck", networkDeviceCheck, ("anaconda",)),
    ("network", ("anaconda",)),
    ("timezone", ("anaconda",)),
    ("accounts", ("anaconda",)),
    ("reposetup", doRepoSetup, ("anaconda",)),
    ("basepkgsel", doBasePackageSelect, ("anaconda",)),
    ("tasksel", ("anaconda",)),
    ("group-selection", ("anaconda",)),
    ("postselection", doPostSelection, ("anaconda",)),
    ("confirminstall", ("anaconda",)),
    ("confirmupgrade", ("anaconda",)),
    ("install", ("anaconda",)),
    ("enablefilesystems", turnOnFilesystems, ("anaconda",)),
    ("migratefilesystems", doMigrateFilesystems, ("anaconda",)),
    ("setuptime", setupTimezone, ("anaconda",)),
    ("preinstallconfig", doPreInstall, ("anaconda",)),
    ("installpackages", doInstall, ("anaconda",)),
    ("postinstallconfig", doPostInstall, ("anaconda",)),
    ("writeconfig", writeConfiguration, ("anaconda",)),
    ("firstboot", firstbootConfiguration, ("anaconda",)),
    ("instbootloader", writeBootloader, ("anaconda",)),
    ("writexconfig", writeXConfiguration, ("anaconda",)),
    ("writeksconfig", writeKSConfiguration, ("anaconda",)),
    ("setfilecon", setFileCons, ("anaconda",)),
    ("copylogs", copyAnacondaLogs, ("anaconda",)),
    ("dopostaction", doPostAction, ("anaconda",)),
    ("methodcomplete", doMethodComplete, ("anaconda",)),
    ("complete", ("anaconda",)),
    ]

class Dispatcher:

    def gotoPrev(self):
	self.dir = DISPATCH_BACK
	self.moveStep()

    def gotoNext(self):
	self.dir = DISPATCH_FORWARD
	self.moveStep()

    def canGoBack(self):
        # begin with the step before this one.  If all steps are skipped,
        # we can not go backwards from this screen
        i = self.step - 1
        while i >= self.firstStep:
            if not self.skipSteps.has_key(installSteps[i][0]):
                return 1
            i = i - 1
        return 0

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

    def moveStep(self):
	if self.step == None:
	    self.step = self.firstStep
	else:
	    self.step = self.step + self.dir

	if self.step >= len(installSteps):
	    return None

	while ((self.step >= self.firstStep
                and self.step < len(installSteps))
               and (self.skipSteps.has_key(installSteps[self.step][0])
                    or (type(installSteps[self.step][1]) == FunctionType))):
	    info = installSteps[self.step]
	    if ((type(info[1]) == FunctionType)
                and (not self.skipSteps.has_key(info[0]))):
                log.info("moving (%d) to step %s" %(self.dir, info[0]))
		(func, args) = info[1:]
		rc = apply(func, self.bindArgs(args))
                if rc in [DISPATCH_BACK, DISPATCH_FORWARD]:
		    self.dir = rc
		# if anything else, leave self.dir alone

	    self.step = self.step + self.dir
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
        log.info("moving (%d) to step %s" %(self.dir, installSteps[self.step][0]))

    def bindArgs(self, args):
	newArgs = ()

	if type(args) == TupleType or type(args) == ListType:
	    for arg in args:
	        obj = self
	        for item in string.split(arg, '.'):
		    if not obj.__dict__.has_key(item):
                        exec "obj = self.%s" %(arg,)
                        break
		    obj = obj.__dict__[item]
	        newArgs = newArgs + (obj,)

	return newArgs

    def currentStep(self):
	if self.step == None:
	    self.gotoNext()
	elif self.step >= len(installSteps):
	    return (None, None)

	stepInfo = installSteps[self.step]
	step = stepInfo[0]
	args = self.bindArgs(stepInfo[1])

	return (step, args)

    def __init__(self, anaconda):
        self.anaconda = anaconda
	self.anaconda.dir = DISPATCH_FORWARD
	self.step = None
	self.skipSteps = {}

	self.method = anaconda.method
	self.firstStep = 0

    def _getDir(self):
        return self.anaconda.dir

    def _setDir(self, dir):
        self.anaconda.dir = dir

    dir = property(_getDir,_setDir)
