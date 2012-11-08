# Text storage configuration spoke classes
#
# Copyright (C) 2012  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Jesse Keating <jkeating@redhat.com>
#
# Some of the code here is copied from pyanaconda/ui/gui/spokes/storage.py
# which has the same license and authored by David Lehman <dlehman@redhat.com>
#

from pyanaconda.ui.tui.spokes import NormalTUISpoke
from pyanaconda.ui.tui.simpleline import TextWidget, CheckboxWidget

from pykickstart.constants import AUTOPART_TYPE_LVM
from pyanaconda.storage.size import Size
from pyanaconda.storage.errors import StorageError
from pyanaconda.flags import flags
from pyanaconda.kickstart import doKickstartStorage
from pyanaconda.threads import threadMgr, AnacondaThread

from pykickstart.constants import *

import logging
log = logging.getLogger("anaconda")

import gettext

_ = lambda x: gettext.ldgettext("anaconda", x)
P_ = lambda x, y, z: gettext.ldngettext("anaconda", x, y, z)

__all__ = ["StorageSpoke", "AutoPartSpoke"]

CLEARALL = _("Use All Space")
CLEARLINUX = _("Replace Existing Linux system(s)")
CLEARNONE = _("Use Free Space")

parttypes = {CLEARALL: CLEARPART_TYPE_ALL, CLEARLINUX: CLEARPART_TYPE_LINUX,
             CLEARNONE: CLEARPART_TYPE_NONE}

class FakeDiskLabel(object):
    def __init__(self, free=0):
        self.free = free

class FakeDisk(object):
    def __init__(self, name, size=0, free=0, partitioned=True, vendor=None,
                 model=None, serial=None, removable=False):
        self.name = name
        self.size = size
        self.format = FakeDiskLabel(free=free)
        self.partitioned = partitioned
        self.vendor = vendor
        self.model = model
        self.serial = serial
        self.removable = removable

    @property
    def description(self):
        return "%s %s" % (self.vendor, self.model)

def getDisks(devicetree, fake=False):
    if not fake:
        disks = [d for d in devicetree.devices if d.isDisk and
                                                  not d.format.hidden and
                                                  not (d.protected and
                                                       d.removable)]
    else:
        disks = []
        disks.append(FakeDisk("sda", size=300000, free=10000, serial="00001",
                              vendor="Seagate", model="Monster"))
        disks.append(FakeDisk("sdb", size=300000, free=300000, serial="00002",
                              vendor="Seagate", model="Monster"))
        disks.append(FakeDisk("sdc", size=8000, free=2100, removable=True,
                              vendor="SanDisk", model="Cruzer", serial="00003"))

    return disks

class StorageSpoke(NormalTUISpoke):
    title = _("Install Destination")
    category = "destination"

    def __init__(self, app, data, storage, payload, instclass):
        NormalTUISpoke.__init__(self, app, data, storage, payload, instclass)
        self.selected_disks = self.data.ignoredisk.onlyuse[:]

        self._ready = False

        # This list gets set up once in initialize and should not be modified
        # except perhaps to add advanced devices. It will remain the full list
        # of disks that can be included in the install.
        self.disks = []
        self.errors = []

    @property
    def completed(self):
        return bool(self.storage.rootDevice and not self.errors)

    @property
    def ready(self):
        # By default, the storage spoke is not ready.  We have to wait until
        # storageInitialize is done.
        return self._ready and not threadMgr.get("AnaStorageWatcher")

    @property
    def status(self):
        """ A short string describing the current status of storage setup. """
        msg = _("No disks selected")
        if self.data.ignoredisk.onlyuse:
            msg = P_(("%d disk selected"),
                     ("%d disks selected"),
                     len(self.data.ignoredisk.onlyuse)) % len(self.data.ignoredisk.onlyuse)

            if self.errors:
                msg = _("Error checking storage configuration")
            # Maybe show what type of clearpart and which disks selected?
            elif self.data.autopart.autopart:
                msg = _("Automatic partitioning selected")
            else:
                msg = _("Custom partitioning selected")

        return msg

    def _update_disk_list(self, disk):
        """ Update self.selected_disks based on the selection."""

        name = disk.name

        # if the disk isn't already selected, select it.
        if name not in self.selected_disks:
            self.selected_disks.append(name)
        # If the disk is already selected, deselect it.
        elif name in self.selected_disks:
            self.selected_disks.remove(name)

    def _update_summary(self):
        """ Update the summary based on the UI. """
        count = 0
        capacity = 0
        free = Size(bytes=0)

        # pass in our disk list so hidden disks' free space is available
        free_space = self.storage.getFreeSpace(disks=self.disks)
        selected = [d for d in self.disks if d.name in self.selected_disks]

        for disk in selected:
            capacity += disk.size
            free += free_space[disk.name][0]
            count += 1

        summary = (P_(("%d disk selected; %s capacity; %s free ..."),
                      ("%d disks selected; %s capacity; %s free ..."),
                      count) % (count, str(Size(spec="%s MB" % capacity)), free))

        if len(self.disks) == 0:
            summary = _("No disks detected.  Please shut down the computer, connect at least one disk, and restart to complete installation.")
        elif count == 0:
            summary = (_("No disks selected; please select at least one disk to install to."))

        # Append storage errors to the summary
        if self.errors:
            summary = summary + "\n" + "\n".join(self.errors)

        return summary

    def refresh(self, args = None):
        NormalTUISpoke.refresh(self, args)

        # Join the initialization thread to block on it
        initThread = threadMgr.get("AnaStorageWatcher")
        if initThread:
            # This print is foul.  Need a better message display
            print(_("Probing storage..."))
            initThread.join()

        # synchronize our local data store with the global ksdata
        # Commment out because there is no way to select a disk right
        # now without putting it in ksdata.  Seems wrong?
        #self.selected_disks = self.data.ignoredisk.onlyuse[:]
        self.autopart = self.data.autopart.autopart

        message = self._update_summary()

        # loop through the disks and present them.
        for disk in self.disks:
            c = CheckboxWidget(title="%i) %s" % (self.disks.index(disk) + 1,
                                                 disk.name),
                               completed=(disk.name in self.selected_disks))
            self._window += [c, ""]

        self._window += [TextWidget(message), ""]

        return True

    def input(self, args, key):
        """Grab the disk choice and update things"""

        if key == "c":
            if self.selected_disks:
                newspoke = AutoPartSpoke(self.app, self.data, self.storage,
                                         self.payload, self.instclass)
                self.app.switch_screen_modal(newspoke)
                self.apply()
                self.execute()
                self.close()
            return None

        try:
            number = int(key)
            self._update_disk_list(self.disks[number -1])
            return None

        except (ValueError, KeyError, IndexError):
            return key

    def apply(self):
        if not flags.automatedInstall:
            # default to using autopart for interactive installs
            self.data.autopart.autopart = True

        self.autopart = self.data.autopart.autopart
        self.data.ignoredisk.onlyuse = self.selected_disks[:]
        self.data.clearpart.drives = self.selected_disks[:]

        self.data.autopart.type = AUTOPART_TYPE_LVM

        if self.autopart:
            self.clearPartType = CLEARPART_TYPE_ALL
        else:
            self.clearPartType = CLEARPART_TYPE_NONE

        for disk in self.disks:
            if disk.name not in self.selected_disks and \
               disk in self.storage.devices:
                self.storage.devicetree.hide(disk)
            elif disk.name in self.selected_disks and \
                 disk not in self.storage.devices:
                self.storage.devicetree.unhide(disk)

        self.data.bootloader.location = "mbr"

        self.storage.config.update(self.data)

        # If autopart is selected we want to remove whatever has been
        # created/scheduled to make room for autopart.
        # If custom is selected, we want to leave alone any storage layout the
        # user may have set up before now.
        self.storage.config.clearNonExistent = self.data.autopart.autopart

    def execute(self):
        print(_("Generating updated storage configuration"))
        try:
            doKickstartStorage(self.storage, self.data, self.instclass)
        except StorageError as e:
            log.error("storage configuration failed: %s" % e)
            print _("storage configuration failed: %s") % e
            self.errors = [str(e)]
            self.data.clearpart.type = CLEARPART_TYPE_ALL
            self.data.clearpart.initAll = False
            self.storage.config.update(self.data)
            self.storage.autoPartType = self.data.clearpart.type
            self.storage.reset()
            self._ready = True
        else:
            print(_("Checking storage configuration..."))
            (self.errors, warnings) = self.storage.sanityCheck()
            self._ready = True
            for e in self.errors:
                log.error(e)
                print e
            for w in warnings:
                log.warn(w)
                print w

    def initialize(self):
        NormalTUISpoke.initialize(self)

        threadMgr.add(AnacondaThread(name="AnaStorageWatcher",
                                     target=self._initialize))

        self.selected_disks = self.data.ignoredisk.onlyuse[:]
        # Probably need something here to track which disks are selected?

    def _initialize(self):
        # Secondary initialize so wait for the storage thread
        # to complete before populating our disk list

        storageThread = threadMgr.get("AnaStorageThread")
        if storageThread:
            storageThread.join()

        self.disks = sorted(getDisks(self.storage.devicetree),
                            key=lambda d: d.name)

        self._update_summary()
        self._ready = True

class AutoPartSpoke(NormalTUISpoke):
    title = _("Autopartitioning Options")
    category = "destination"

    def __init__(self, app, data, storage, payload, instclass):
        NormalTUISpoke.__init__(self, app, data, storage, payload, instclass)
        self.clearPartType = self.data.clearpart.type

    @property
    def indirect(self):
        return True

    @property
    def completed(self):
        return True # We're always complete

    def refresh(self, args = None):
        NormalTUISpoke.refresh(self, args)
        # synchronize our local data store with the global ksdata
        self.clearPartType = self.data.clearpart.type
        # I dislike "is None", but bool(0) returns false :(
        if self.clearPartType is None:
            # Default to clearing everything.
            self.clearPartType = CLEARPART_TYPE_ALL

        self.parttypelist = sorted(parttypes.keys())
        for parttype in self.parttypelist:
            c = CheckboxWidget(title="%i) %s" % (self.parttypelist.index(parttype) + 1,
                                                 parttype),
                               completed=(parttypes[parttype] == self.clearPartType))
            self._window += [c, ""]

        message = _("Installation requires partitioning of your hard drive.  Select what space to use for the install target.")

        self._window += [TextWidget(message), ""]

        return True

    def apply(self):
        self.data.clearpart.type = self.clearPartType
        self.data.clearpart.initAll = True

    def input(self, args, key):
        """Grab the choice and update things"""

        if key == "c":
            self.apply()
            self.close()
            return False

        try:
            number = int(key)
            self.clearPartType = parttypes[self.parttypelist[number -1]]
            self.apply()
            self.close()
            return False

        except (ValueError, KeyError, IndexError):
            return key
