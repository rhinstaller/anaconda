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

from distutils.sysconfig import get_python_lib
import os, sys
import imputil

from blivet.partspec import PartSpec
from blivet.devicelibs import swap
from blivet.platform import platform

import logging
log = logging.getLogger("anaconda")

from pyanaconda.flags import flags
from pyanaconda.kickstart import getAvailableDiskSpace

class BaseInstallClass(object):
    # default to not being hidden
    hidden = 0
    name = "base"
    bootloaderTimeoutDefault = None
    bootloaderExtraArgs = []

    # Anaconda flags several packages to be installed based on the configuration
    # of the system -- things like fs utilities, bootloader, &c. This is a list
    # of packages that we should not try to install using the aforementioned
    # mechanism.
    ignoredPackages = []

    # This flag controls whether or not Anaconda should provide an option to
    # install the latest updates during installation source selection.
    installUpdates = True

    _l10n_domain = None

    # The default filesystem type to use.  If None, we will use whatever
    # Blivet uses by default.
    defaultFS = None

    # don't select this class by default
    default = 0

    @property
    def l10n_domain(self):
        if self._l10n_domain is None:
            raise RuntimeError("Localization domain for '%s' not set." %
                               self.name)
        return self._l10n_domain

    def setPackageSelection(self, anaconda):
        pass

    def getBackend(self):
        # The default is to return None here, which means anaconda should
        # use live or yum (whichever can be detected).  This method is
        # provided as a way for other products to specify their own.
        return None

    def setDefaultPartitioning(self, storage):
        autorequests = [PartSpec(mountpoint="/", fstype=storage.defaultFSType,
                                 size=1024, maxSize=50*1024, grow=True,
                                 btr=True, lv=True, thin=True, encrypted=True),
                        PartSpec(mountpoint="/home", fstype=storage.defaultFSType,
                                 size=500, grow=True, requiredSpace=50*1024,
                                 btr=True, lv=True, thin=True, encrypted=True)]

        bootreqs = platform.setDefaultPartitioning()
        if bootreqs:
            autorequests.extend(bootreqs)


        disk_space = getAvailableDiskSpace(storage)
        swp = swap.swapSuggestion(disk_space=disk_space)
        autorequests.append(PartSpec(fstype="swap", size=swp, grow=False,
                                     lv=True, encrypted=True))

        for autoreq in autorequests:
            if autoreq.fstype is None:
                if autoreq.mountpoint == "/boot":
                    autoreq.fstype = storage.defaultBootFSType
                else:
                    autoreq.fstype = storage.defaultFSType

        storage.autoPartitionRequests = autorequests

    def configure(self, anaconda):
        anaconda.bootloader.timeout = self.bootloaderTimeoutDefault
        anaconda.bootloader.boot_args.update(self.bootloaderExtraArgs)

    # sets default ONBOOT values and updates ksdata accordingly
    def setNetworkOnbootDefault(self, ksdata):
        pass

    def __init__(self):
        pass

allClasses = []
allClasses_hidden = []

# returns ( className, classObject, classLogo ) tuples
def availableClasses(showHidden=0):
    global allClasses
    global allClasses_hidden

    def _ordering(first, second):
        ((name1, _), priority1) = first
        ((name2, _), priority2) = second

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
        if allClasses:
            return allClasses
    else:
        if allClasses_hidden:
            return allClasses_hidden

    path = []

    env_path = []
    if "ANACONDA_INSTALL_CLASSES" in os.environ:
        env_path += os.environ["ANACONDA_INSTALL_CLASSES"].split(":")

    for d in env_path + ["installclasses",
              "/tmp/updates/pyanaconda/installclasses",
              "/tmp/product/pyanaconda/installclasses",
              "%s/pyanaconda/installclasses" % get_python_lib(plat_specific=1) ]:
        if os.access(d, os.R_OK):
            path.append(d)

    # append the location of installclasses to the python path so we
    # can import them
    sys.path = path + sys.path

    files = []
    for p in reversed(path):
        files += os.listdir(p)

    done = {}
    lst = []
    for fileName in files:
        if fileName[0] == '.':
            continue
        if len (fileName) < 4:
            continue
        if fileName[-3:] != ".py" and fileName[-4:-1] != ".py":
            continue
        mainName = fileName.split(".")[0]
        if done.has_key(mainName):
            continue
        done[mainName] = 1


        try:
            found = imputil.imp.find_module(mainName)
        except ImportError:
            log.warning ("module import of %s failed: %s", mainName, sys.exc_type)
            continue

        try:
            loaded = imputil.imp.load_module(mainName, found[0], found[1], found[2])

            obj = loaded.InstallClass

            if obj.__dict__.has_key('sortPriority'):
                sortOrder = obj.sortPriority
            else:
                sortOrder = 0

            if obj.hidden == 0 or showHidden == 1:
                lst.append(((obj.name, obj), sortOrder))
        except (ImportError, AttributeError):
            log.warning ("module import of %s failed: %s", mainName, sys.exc_type)
            if flags.debug: raise
            else: continue

    lst.sort(_ordering)
    for (item, _) in lst:
        if showHidden:
            allClasses_hidden += [item]
        else:
            allClasses += [item]

    if showHidden:
        return allClasses_hidden
    else:
        return allClasses

def getBaseInstallClass():
    # figure out what installclass we should base on.
    allavail = availableClasses(showHidden = 1)
    avail = availableClasses(showHidden = 0)

    if len(avail) == 1:
        (cname, cobject) = avail[0]
        log.info("using only installclass %s", cname)
    elif len(allavail) == 1:
        (cname, cobject) = allavail[0]
        log.info("using only installclass %s", cname)

    # Use the highest priority install class if more than one found.
    elif len(avail) > 1:
        (cname, cobject) = avail.pop()
        log.info('%s is the highest priority installclass, using it', cname)
    elif len(allavail) > 1:
        (cname, cobject) = allavail.pop()
        log.info('%s is the highest priority installclass, using it', cname)

    # Default to the base installclass if nothing else is found.
    else:
        raise RuntimeError("Unable to find an install class to use!!!")

    return cobject

baseclass = getBaseInstallClass()

# we need to be able to differentiate between this and custom
class DefaultInstall(baseclass):
    def __init__(self):
        baseclass.__init__(self)
