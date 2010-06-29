#
# installclass.py:  This is the prototypical class for workstation, server, and
# kickstart installs.  The interface to BaseInstallClass is *public* --
# ISVs/OEMs can customize the install by creating a new derived type of this
# class.
#
# Copyright (C) 1999, 2000, 2001, 2002, 2003, 2004, 2005, 2006, 2007
# Red Hat, Inc.  All rights reserved.
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

import os, sys, iutil
import isys
import string
import language
import imputil
import types

from instdata import InstallData

from constants import *
from product import *
from storage.partspec import *

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("anaconda")

from flags import flags

class BaseInstallClass(object):
    # default to not being hidden
    hidden = 0
    pixmap = None
    showMinimal = 1
    showLoginChoice = 0
    _description = ""
    _descriptionFields = ()
    name = "base"
    pkgstext = ""
    # default to showing the upgrade option
    showUpgrade = True
    bootloaderTimeoutDefault = 0
    bootloaderExtraArgs = ""

    # list of of (txt, grplist) tuples for task selection screen
    tasks = []

    # don't select this class by default
    default = 0

    # don't force text mode
    forceTextMode = 0

    # by default, place this under the "install" category; it gets it's
    # own toplevel category otherwise
    parentClass = ( _("Install on System"), "install.png" )

    # we can use a different install data class
    installDataClass = InstallData

    def _get_description(self):
        return _(self._description) % self._descriptionFields
    description = property(_get_description)

    def postAction(self, anaconda):
        anaconda.backend.postAction(anaconda)

    def setSteps(self, anaconda):
        dispatch = anaconda.dispatch
	dispatch.setStepList(
		 "language",
		 "keyboard",
		 "welcome",
                 "filtertype",
                 "filter",
                 "storageinit",
                 "findrootparts",
		 "betanag",
		 "installtype",
                 "cleardiskssel",
                 "parttype",
                 "autopartitionexecute",
                 "partition",
		 "storagedone",
		 "bootloadersetup",                 
		 "bootloader",
		 "network",
		 "timezone",
		 "accounts",
                 "reposetup",
                 "basepkgsel",
		 "tasksel",                                  
		 "postselection",
		 "confirminstall",
                 "reipl",
		 "install",
		 "enablefilesystems",
                 "setuptime",
                 "preinstallconfig",
		 "installpackages",
                 "postinstallconfig",
		 "writeconfig",
                 "firstboot",
		 "instbootloader",
                 "dopostaction",
                 "postscripts",
		 "writeksconfig",
                 "methodcomplete",
                 "copylogs",
                 "setfilecon",
		 "complete"
		)

	if not BETANAG:
	    dispatch.skipStep("betanag", permanent=1)

        if not iutil.isX86():
            dispatch.skipStep("bootloader", permanent=1)

        # allow backends to disable interactive package selection
        if not anaconda.backend.supportsPackageSelection:
            dispatch.skipStep("tasksel", skip = 1, permanent=1)
            dispatch.skipStep("group-selection", skip = 1, permanent=1)

        # allow install classes to turn off the upgrade 
        if not self.showUpgrade or not anaconda.backend.supportsUpgrades:
            dispatch.skipStep("findrootparts", skip = 1)

        # 'noupgrade' can be used on the command line to force not looking
        # for partitions to upgrade.  useful in some cases...
        if flags.cmdline.has_key("noupgrade"):
            dispatch.skipStep("findrootparts", skip = 1)

        # upgrade will also always force looking for an upgrade. 
        if flags.cmdline.has_key("upgrade"):
            dispatch.skipStep("findrootparts", skip = 0)

        # if there's only one install class, it doesn't make much sense
        # to show it
        if len(availableClasses()) < 2:
            dispatch.skipStep("installtype", permanent=1)

        # allow interface backends to skip certain steps.
        anaconda.intf.setSteps(anaconda)

    # modifies the uri from installmethod.getMethodUri() to take into
    # account any installclass specific things including multiple base
    # repositories.  takes a string or list of strings, returns a dict 
    # with string keys and list values {%repo: %uri_list}
    def getPackagePaths(self, uri):
        if not type(uri) == types.ListType:
            uri = [uri,]

        return {'base': uri}

    def setPackageSelection(self, anaconda):
	pass

    def setGroupSelection(self, anaconda):
        grps = anaconda.backend.getDefaultGroups(anaconda)
        map(lambda x: anaconda.backend.selectGroup(x), grps)

    def getBackend(self):
        # this should be overriden in distro install classes
        from backend import AnacondaBackend
        return AnacondaBackend

    def setDefaultPartitioning(self, storage, platform):
        autorequests = [PartSpec(mountpoint="/", fstype=storage.defaultFSType,
                                 size=1024, maxSize=50*1024, grow=True,
                                 asVol=True),
                        PartSpec(mountpoint="/home", fstype=storage.defaultFSType,
                                 size=100, grow=True, asVol=True, requiredSpace=50*1024)]

        bootreq = platform.setDefaultPartitioning()
        if bootreq:
            autorequests.extend(bootreq)

        (minswap, maxswap) = iutil.swapSuggestion()
        autorequests.append(PartSpec(fstype="swap", size=minswap, maxSize=maxswap,
                                     grow=True, asVol=True))

        storage.autoPartitionRequests = autorequests


    def setInstallData(self, anaconda):
        anaconda.id.reset()
        anaconda.id.instClass = self
        anaconda.id.bootloader.timeout = self.bootloaderTimeoutDefault
        anaconda.id.bootloader.args.append(self.bootloaderExtraArgs)

    def versionMatches(self, oldver):
        pass

    def productMatches(self, oldprod):
        pass

    def productUpgradable(self, oldprod, oldver):
        return self.productMatches(oldprod) and self.versionMatches(oldver)

    def __init__(self):
	pass

allClasses = []
allClasses_hidden = []

# returns ( className, classObject, classLogo ) tuples
def availableClasses(showHidden=0):
    global allClasses
    global allClasses_hidden

    def _ordering(first, second):
        ((name1, obj, logo), priority1) = first
        ((name2, obj, logo), priority2) = second

        if priority1 < priority2:
            return -1
        elif priority1 > priority2:
            return 1

        if name1 < name2:
            return -1
        elif name1 > name2:
            return 1

        return 0

    if not showHidden:
        if allClasses: return allClasses
    else:
        if allClasses_hidden: return allClasses_hidden

    path = []

    for dir in ["installclasses", "/tmp/updates/installclasses",
                "/tmp/product/installclasses", "/usr/lib/anaconda/installclasses"]:
        if os.access(dir, os.R_OK):
            path.append(dir)

    # append the location of installclasses to the python path so we
    # can import them
    sys.path = path + sys.path

    files = []
    for p in reversed(path):
        files += os.listdir(p)

    done = {}
    list = []
    for file in files:
	if file[0] == '.': continue
        if len (file) < 4:
	    continue
	if file[-3:] != ".py" and file[-4:-1] != ".py":
	    continue
	mainName = string.split(file, ".")[0]
	if done.has_key(mainName): continue
	done[mainName] = 1

        try:
            found = imputil.imp.find_module(mainName)
        except:
            log.warning ("module import of %s failed: %s" % (mainName, sys.exc_type))
            continue

        try:
            loaded = imputil.imp.load_module(mainName, found[0], found[1], found[2])

            obj = loaded.InstallClass

	    if obj.__dict__.has_key('sortPriority'):
		sortOrder = obj.sortPriority
	    else:
		sortOrder = 0

	    if obj.__dict__.has_key('arch'):
                if obj.arch != iutil.getArch():
                    obj.hidden = 1
                
            if obj.hidden == 0 or showHidden == 1:
                list.append(((obj.name, obj, obj.pixmap), sortOrder))
        except:
            log.warning ("module import of %s failed: %s" % (mainName, sys.exc_type))
            if flags.debug: raise
            else: continue

    list.sort(_ordering)
    for (item, priority) in list:
        if showHidden:
            allClasses_hidden.append(item)
        else:
            allClasses.append(item)

    if showHidden:
        return allClasses_hidden
    else:
        return allClasses

def getBaseInstallClass():
    # figure out what installclass we should base on.
    allavail = availableClasses(showHidden = 1)
    avail = availableClasses(showHidden = 0)
    if len(avail) == 1:
        (cname, cobject, clogo) = avail[0]
        log.info("using only installclass %s" %(cname,))
    elif len(allavail) == 1:
        (cname, cobject, clogo) = allavail[0]
        log.info("using only installclass %s" %(cname,))

    # Use the highest priority install class if more than one found.
    elif len(avail) > 1:
        (cname, cobject, clogo) = avail.pop()
        log.info('%s is the highest priority installclass, using it' % cname)
    elif len(allavail) > 1:
        (cname, cobject, clogo) = allavail.pop()
        log.info('%s is the highest priority installclass, using it' % cname)

    # Default to the base installclass if nothing else is found.
    else:
        raise RuntimeError, "Unable to find an install class to use!!!"

    return cobject

baseclass = getBaseInstallClass()

# we need to be able to differentiate between this and custom
class DefaultInstall(baseclass):
    def __init__(self):
	BaseInstallClass.__init__(self)

