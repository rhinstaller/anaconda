#
# dispatch.py: install/upgrade master flow control
#
# Erik Troan <ewt@redhat.com>
#
# Copyright 2001-2002 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import string
from types import *
from constants import *
from packages import readPackages, checkDependencies, doInstall
from packages import handleX11Packages, writeConfiguration, writeXConfiguration
from packages import writeKSConfiguration, turnOnFilesystems
from packages import doMigrateFilesystems
from packages import queryUpgradeContinue
from packages import doPreInstall, doPostInstall, doPostAction
from autopart import doAutoPartition
from packages import firstbootConfiguration
from packages import betaNagScreen
from packages import selectLanguageSupportGroups
from packages import setupTimezone
from partitioning import partitionMethodSetup, partitionObjectsInitialize
from partitioning import partitioningComplete
from floppy import makeBootdisk
from bootloader import writeBootloader, bootloaderSetupChoices
from flags import flags
from upgrade import upgradeFindPackages, upgradeMountFilesystems
from upgrade import upgradeSwapSuggestion, upgradeMigrateFind
from upgrade import findRootParts
from network import networkDeviceCheck
from installmethod import doMethodComplete

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
    ("welcome", ("id.configFileData",)),
    ("betanag", betaNagScreen, ("intf", "dir")),
    ("language", ("intf", "id.instLanguage")),
    ("keyboard", ("id.instLanguage.getDefaultKeyboard()", "id.keyboard", "id.xsetup")),
    ("mouse", ("id.mouse",)),
    ("findrootparts", findRootParts, ("intf", "id", "dispatch", "dir", "instPath")),
    ("findinstall", ("dispatch", "intf", "id", "instPath")),
    ("installtype", ("dispatch", "id", "method", "intf")),
    ("partitionmethod", ("id.partitions", "id.instClass")),
    ("partitionobjinit", partitionObjectsInitialize, ("id.diskset",
                                                      "id.partitions",
                                                      "dir", "intf")),
    ("partitionmethodsetup", partitionMethodSetup, ("id.partitions",
                                                    "dispatch")),
    ("autopartition", ("id.diskset", "id.partitions", "intf", "dispatch")),
    ("autopartitionexecute", doAutoPartition, ("dir", "id.diskset",
                                               "id.partitions", "intf",
                                               "id.instClass", "dispatch")),
    ("fdisk", ("id.diskset", "id.partitions", "intf")),
    ("fdasd", ("id.diskset", "id.partitions", "intf")),
    ("partition", ("id.fsset", "id.diskset", "id.partitions", "intf")),
    ("upgrademount", upgradeMountFilesystems, ("intf", "id.upgradeRoot",
                                               "id.fsset", "instPath")),
    ("upgradecontinue", queryUpgradeContinue, ("intf", "dir")),
    ("upgradeswapsuggestion", upgradeSwapSuggestion, ("dispatch", "id",
                                                      "instPath")),
    ("addswap", ("intf", "id.fsset", "instPath",
                 "id.upgradeSwapInfo", "dispatch")),
    ("partitiondone", partitioningComplete, ("id.bootloader", "id.fsset",
                                             "id.diskset", "id.partitions",
                                             "intf", "instPath", "dir")),
    ("upgrademigfind", upgradeMigrateFind, ("dispatch", "id.fsset")),
    ("upgrademigratefs",  ("id.fsset",)),
    ("upgbootloader", ("dispatch", "id.bootloader")),
    ("bootloadersetup", bootloaderSetupChoices, ("dispatch", "id.bootloader",
                                                 "id.fsset", "id.diskset",
                                                 "dir")),
    ("bootloader", ("dispatch", "id.bootloader", "id.fsset", "id.diskset")),
    ("bootloaderadvanced", ("dispatch", "id.bootloader", "id.fsset",
                            "id.diskset")),
    ("networkdevicecheck", networkDeviceCheck, ("id.network", "dispatch")),
    ("network", ("id.network", "dispatch", "intf")),
    ("firewall", ("intf", "id.network", "id.firewall")),
    ("languagesupport", ("id.langSupport",)),
    ("timezone", ("id.instLanguage", "id.timezone")),
    ("accounts", ("id.rootPassword",)),
    ("authentication", ("id.auth",)),
    ("readcomps", readPackages, ("intf", "method", "id")),
    ("desktopchoice", ("intf", "id.instClass", "dispatch")),
    ("findpackages", upgradeFindPackages, ("intf", "method", "id",
                                           "instPath", "dir")),
    ("selectlangpackages", selectLanguageSupportGroups, ("id.comps","id.langSupport")),    
    ("package-selection", ("id.comps", "id.langSupport", "id.instClass", "dispatch")),
    ("indivpackage", ("id.comps", "id.hdList")),
    ("handleX11pkgs", handleX11Packages, ("dir", "intf", "dispatch",
                                          "id", "instPath")),
    ("checkdeps", checkDependencies, ("dir", "intf", "dispatch",
                                      "id", "instPath")),
    ("dependencies", ("id.comps", "id.dependencies")),
    ("confirminstall", ()),
    ("confirmupgrade", ()),
    ("install", ("dir", "intf", "id")),
    ("enablefilesystems", turnOnFilesystems, ("dir", "id.fsset",
                                              "id.diskset", "id.partitions",
                                              "id.upgrade", "instPath")),
    ("migratefilesystems", doMigrateFilesystems, ("dir", "id.fsset",
                                              "id.diskset", "id.upgrade",
                                              "instPath")),
    ("setuptime", setupTimezone, ("id.timezone", "id.upgrade", "instPath",
                                  "dir")),
    ("preinstallconfig", doPreInstall, ("method", "id", "intf", "instPath",
                                        "dir")),
    ("installpackages", doInstall, ("method", "id", "intf", "instPath")),
    ("postinstallconfig", doPostInstall, ("method", "id", "intf", "instPath")),
    ("writeconfig", writeConfiguration, ("id", "instPath")),
    ("firstboot", firstbootConfiguration, ("id", "instPath")),
    ("instbootloader", writeBootloader, ("intf", "instPath", "id.fsset", 
                                         "id.bootloader", "id.langSupport",
                                         "id.comps")),
    ("bootdisk", ("dir", "dispatch", "id.fsset")),
    ("makebootdisk", makeBootdisk, ("intf", "dir", "id.floppyDevice",
                                    "id.hdList", "instPath", "id.bootloader")),
    ("videocard", ("dispatch", "id.xsetup", "id.videocard", "intf")),
    ("monitor", ("id.xsetup", "id.monitor")),
    ("xcustom", ("id.xsetup", "id.monitor", "id.videocard",
                 "id.desktop", "id.comps", "id.instClass", "instPath")),
    ("writexconfig", writeXConfiguration, ("id", "instPath")),
    ("writeksconfig", writeKSConfiguration, ("id", "instPath")),
    ("dopostaction", doPostAction, ("id", "instPath")),
    ("methodcomplete", doMethodComplete, ("method",)),
    ("complete", ()),
    ]

class Dispatcher:

    def gotoPrev(self):
	self.dir = -1
	self.moveStep()

    def gotoNext(self):
	self.dir = 1
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
		raise KeyError, ("step %s does not exist" % name)

    def stepInSkipList(self, step):
	return self.skipSteps.has_key(step)

    def skipStep(self, stepToSkip, skip = 1, permanent = 0):
	for step in installSteps:
	    name = step[0]
	    if name == stepToSkip:
		if skip:
                    if permanent:
                        self.skipSteps[name] = 2
                    else:
                        self.skipSteps[name] = 1
		elif self.skipSteps.has_key(name):
		    # if marked as permanent then dont change
		    if self.skipSteps[name] != 2:
			del self.skipSteps[name]
		return

	raise KeyError, ("unknown step %s" % stepToSkip)

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
		(func, args) = info[1:]
		rc = apply(func, self.bindArgs(args))
		if rc == DISPATCH_BACK:
		    self.dir = -1
		elif rc == DISPATCH_FORWARD:
		    self.dir = 1
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

    def bindArgs(self, args):
	newArgs = ()
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

    def __init__(self, intf, id, method, instPath):
	self.dir = DISPATCH_FORWARD
	self.step = None
	self.skipSteps = {}

	self.id = id
	self.flags = flags
	self.intf = intf
	self.method = method
	self.dispatch = self
	self.instPath = instPath
	self.firstStep = 0
