#
# dispatch.py: install/upgrade master flow control
#
# Erik Troan <ewt@redhat.com>
#
# Copyright 2001 Red Hat, Inc.
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
from packages import queryUpgradeContinue
from autopart import doAutoPartition
from floppy import makeBootdisk
from bootloader import partitioningComplete, writeBootloader
from flags import flags
from upgrade import upgradeFindPackages

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
    ( "language", ("intf", "id.instLanguage") ),
    ( "keyboard", ("id.instLanguage", "id.keyboard") ),
    ( "mouse", ("id.mouse", ) ),
    ( "welcome", () ),
    ( "reconfigwelcome", () ),
    ( "reconfigkeyboard", ("id.instLanguage", "id.keyboard" ) ),
    ( "installtype", ("dispatch", "id", "method", "intf") ),
    ( "findinstall", ("dispatch", "intf", "id", "instPath") ),
    ( "upgradecontinue", queryUpgradeContinue, ("intf", "dir")),
    ( "addswap", ("dispatch", "intf", "id.fsset", "id.diskset", "instPath") ),
    ( "autopartition", ("id.autoClearPartType", "id.autoClearPartDrives", "id.diskset", "intf")),
    ( "autopartitionexecute", doAutoPartition, ("id",)),
    ( "partition", ("id.fsset", "id.diskset", "id.partrequests", "intf")),
    ( "partitiondone", partitioningComplete, ("dispatch", "id.bootloader",
                                              "id.fsset", "id.diskset" ) ),
    ( "bootloader", ("dispatch", "id.bootloader", "id.fsset", "id.diskset") ),
    ( "network", ("id.network",) ),
    ( "firewall", ("id.network", "id.firewall") ),
    ( "languagesupport", ("id.langSupport", ) ),
    ( "timezone", ("id.instLanguage", "id.timezone", ) ),
    ( "accounts", ("id.rootPassword", "id.accounts", ) ),
    ( "authentication", ("id.auth", ) ),
    ( "readcomps", readPackages, ("intf", "method", "id" )),
    ( "findpackages", upgradeFindPackages, ("intf", "method", "id",
                                            "instPath")),
    ( "package-selection", ("id.comps", "dispatch") ),
    ( "indivpackage", ("id.comps", "id.hdList", ) ),
    ( "handleX11pkgs", handleX11Packages, ("dir", "intf", "dispatch",
                                           "id", "instPath" )),
    ( "videocard", ("dispatch", "id.xconfig", "id.videocard")),
    ( "checkdeps", checkDependencies, ("dir", "intf", "dispatch",
                                       "id", "instPath" )),
    ( "dependencies", ("id.comps", "id.dependencies",) ),
    ( "confirminstall", () ),
    ( "confirmupgrade", () ),
    ( "install", ("dir", "intf", "id", ) ),
    ( "enablefilesystems", turnOnFilesystems, ( "dir", "id.fsset",
                                                "id.diskset", "id.upgrade",
                                                "instPath") ),
    ( "installpackages", doInstall, ( "method", "id", "intf", "instPath" )),
    ( "writeconfig", writeConfiguration, ("id", "instPath" )),
    ( "instbootloader", writeBootloader, ("intf", "instPath", "id.fsset", 
                                          "id.bootloader", "id.langSupport",
                                          "id.comps") ),
    ( "monitor", ("id.xconfig", "id.monitor") ),
    ( "xcustom", ("id.xconfig", "id.monitor", "id.videocard",
                  "id.desktop", "id.comps") ),
    ( "writexconfig", writeXConfiguration, ("id", "instPath")),
    ( "writeksconfig", writeKSConfiguration, ("id", "instPath")),
    ( "bootdisk", ("dir", "dispatch") ),
    ( "makebootdisk", makeBootdisk, ("intf", "id.floppyDevice",
				     "id.hdList", "instPath") ),
    ( "complete", () ),
    ( "reconfigcomplete", () )
    ]

class Dispatcher:

    def gotoPrev(self):
	self.dir = -1
	self.moveStep()

    def gotoNext(self):
	self.dir = 1
	self.moveStep()

    def setStepList(self, *steps):
	self.skipSteps = {}
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

    def skipStep(self, stepToSkip, skip = 1):
	for step in installSteps:
	    name = step[0]
	    if name == stepToSkip:
		if skip:
		    self.skipSteps[name] = 1
		elif self.skipSteps.has_key(name):
		    del self.skipSteps[name]
		return

	raise KeyError, ("unknown step %s" % stepToSkip)

    def moveStep(self):
	if self.step == None:
	    self.step = self.firstStep
	else:
	    self.step = self.step + self.dir

	if self.step == len(installSteps):
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
		    print "cannot find %s in %s" % (item, obj)
		obj = obj.__dict__[item]
	    newArgs = newArgs + (obj,)

	return newArgs

    def currentStep(self):
	if self.step == None:
	    self.gotoNext()
	elif self.step == len(installSteps):
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
