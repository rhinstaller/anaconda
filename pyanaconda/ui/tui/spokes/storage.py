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

from pyanaconda.ui.lib.disks import getDisks, size_str
from pyanaconda.ui.tui.spokes import NormalTUISpoke
from pyanaconda.ui.tui.simpleline import TextWidget, CheckboxWidget

from pykickstart.constants import AUTOPART_TYPE_LVM, AUTOPART_TYPE_BTRFS, AUTOPART_TYPE_PLAIN
from blivet.size import Size
from blivet.errors import StorageError
from pyanaconda.flags import flags
from pyanaconda.kickstart import doKickstartStorage
from pyanaconda.threads import threadMgr, AnacondaThread
from pyanaconda.constants import THREAD_STORAGE, THREAD_STORAGE_WATCHER
from pyanaconda.constants_text import INPUT_PROCESSED
from pyanaconda.i18n import _, P_
from pyanaconda.bootloader import BootLoaderError

from pykickstart.constants import CLEARPART_TYPE_ALL, CLEARPART_TYPE_LINUX, CLEARPART_TYPE_NONE
from pykickstart.errors import KickstartValueError

from collections import OrderedDict

import logging
log = logging.getLogger("anaconda")

__all__ = ["StorageSpoke", "AutoPartSpoke"]

CLEARALL = _("Use All Space")
CLEARLINUX = _("Replace Existing Linux system(s)")
CLEARNONE = _("Use Free Space")

PARTTYPES = {CLEARALL: CLEARPART_TYPE_ALL, CLEARLINUX: CLEARPART_TYPE_LINUX,
             CLEARNONE: CLEARPART_TYPE_NONE}

class StorageSpoke(NormalTUISpoke):
    """
    Storage spoke where users proceed to customize storage features such
    as disk selection, partitioning, and fs type.
    """
    title = _("Install Destination")
    category = "system"

    def __init__(self, app, data, storage, payload, instclass):
        NormalTUISpoke.__init__(self, app, data, storage, payload, instclass)

        self._ready = False
        self.selected_disks = self.data.ignoredisk.onlyuse[:]

        self.autopart = None
        self.clearPartType = None

        # This list gets set up once in initialize and should not be modified
        # except perhaps to add advanced devices. It will remain the full list
        # of disks that can be included in the install.
        self.disks = []
        self.errors = []
        self.warnings = []

        if not flags.automatedInstall:
            # default to using autopart for interactive installs
            self.data.autopart.autopart = True

    @property
    def completed(self):
        retval = bool(self.storage.rootDevice and not self.errors)

        if flags.automatedInstall:
            return retval and self.data.bootloader.seen
        else:
            return retval

    @property
    def ready(self):
        # By default, the storage spoke is not ready.  We have to wait until
        # storageInitialize is done.
        return self._ready and not threadMgr.get(THREAD_STORAGE_WATCHER)

    @property
    def mandatory(self):
        return True

    @property
    def showable(self):
        return not flags.dirInstall

    @property
    def status(self):
        """ A short string describing the current status of storage setup. """
        msg = _("No disks selected")

        if flags.automatedInstall and not self.storage.rootDevice:
            return msg
        elif flags.automatedInstall and not self.data.bootloader.seen:
            msg = _("No bootloader configured")
        elif self.data.ignoredisk.onlyuse:
            msg = P_(("%d disk selected"),
                     ("%d disks selected"),
                     len(self.data.ignoredisk.onlyuse)) % len(self.data.ignoredisk.onlyuse)

            if self.errors:
                msg = _("Error checking storage configuration")
            elif self.warnings:
                msg = _("Warning checking storage configuration")
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
        elif self.warnings:
            summary = summary + "\n" + "\n".join(self.warnings)

        return summary

    def refresh(self, args = None):
        NormalTUISpoke.refresh(self, args)

        # Join the initialization thread to block on it
        # This print is foul.  Need a better message display
        print(_("Probing storage..."))
        threadMgr.wait(THREAD_STORAGE_WATCHER)

        # synchronize our local data store with the global ksdata
        # Commment out because there is no way to select a disk right
        # now without putting it in ksdata.  Seems wrong?
        #self.selected_disks = self.data.ignoredisk.onlyuse[:]
        self.autopart = self.data.autopart.autopart

        message = self._update_summary()

        # loop through the disks and present them.
        for disk in self.disks:
            size = size_str(disk.size)
            c = CheckboxWidget(title="%i) %s: %s (%s)" % (self.disks.index(disk) + 1,
                                                 disk.model, size, disk.name),
                               completed=(disk.name in self.selected_disks))
            self._window += [c, ""]

        self._window += [TextWidget(message), ""]

        return True

    def input(self, args, key):
        """Grab the disk choice and update things"""

        try:
            keyid = int(key) - 1
            self._update_disk_list(self.disks[keyid])
            return INPUT_PROCESSED
        except (ValueError, IndexError):
            if key.lower() == "c":
                if self.selected_disks:
                    newspoke = AutoPartSpoke(self.app, self.data, self.storage,
                                             self.payload, self.instclass)
                    self.app.switch_screen_modal(newspoke)
                    self.apply()
                    self.execute()
                    self.close()
                return INPUT_PROCESSED
            else:
                return key

    def apply(self):
        self.autopart = self.data.autopart.autopart
        self.data.ignoredisk.onlyuse = self.selected_disks[:]
        self.data.clearpart.drives = self.selected_disks[:]

        if self.data.autopart.type is None:
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
        except (StorageError, BootLoaderError, KickstartValueError) as e:
            log.error("storage configuration failed: %s", e)
            print _("storage configuration failed: %s") % e
            self.errors = [str(e)]
            self.data.bootloader.bootDrive = ""
            self.data.clearpart.type = CLEARPART_TYPE_ALL
            self.data.clearpart.initAll = False
            self.storage.config.update(self.data)
            self.storage.autoPartType = self.data.clearpart.type
            self.storage.reset()
            self._ready = True
        else:
            print(_("Checking storage configuration..."))
            (self.errors, self.warnings) = self.storage.sanityCheck()
            self._ready = True
            for e in self.errors:
                log.error(e)
                print e
            for w in self.warnings:
                log.warn(w)
                print w

    def initialize(self):
        NormalTUISpoke.initialize(self)

        threadMgr.add(AnacondaThread(name=THREAD_STORAGE_WATCHER,
                                     target=self._initialize))

        self.selected_disks = self.data.ignoredisk.onlyuse[:]
        # Probably need something here to track which disks are selected?

    def _initialize(self):
        """
        Secondary initialize so wait for the storage thread to complete before
        populating our disk list
        """

        threadMgr.wait(THREAD_STORAGE)

        self.disks = sorted(getDisks(self.storage.devicetree),
                            key=lambda d: d.name)
        # if only one disk is available, go ahead and mark it as selected
        if len(self.disks) == 1:
            self._update_disk_list(self.disks[0])

        self._update_summary()
        self._ready = True

class AutoPartSpoke(NormalTUISpoke):
    """ Autopartitioning options are presented here. """
    title = _("Autopartitioning Options")
    category = "system"

    def __init__(self, app, data, storage, payload, instclass):
        NormalTUISpoke.__init__(self, app, data, storage, payload, instclass)
        self.clearPartType = self.data.clearpart.type
        self.parttypelist = sorted(PARTTYPES.keys())

    @property
    def indirect(self):
        return True

    def refresh(self, args = None):
        NormalTUISpoke.refresh(self, args)
        # synchronize our local data store with the global ksdata
        self.clearPartType = self.data.clearpart.type
        # I dislike "is None", but bool(0) returns false :(
        if self.clearPartType is None:
            # Default to clearing everything.
            self.clearPartType = CLEARPART_TYPE_ALL

        for parttype in self.parttypelist:
            c = CheckboxWidget(title="%i) %s" % (self.parttypelist.index(parttype) + 1,
                                                 parttype),
                               completed=(PARTTYPES[parttype] == self.clearPartType))
            self._window += [c, ""]

        message = _("Installation requires partitioning of your hard drive. Select what space to use for the install target.")

        self._window += [TextWidget(message), ""]

        return True

    def apply(self):
        # kind of a hack, but if we're actually getting to this spoke, there
        # is no doubt that we are doing autopartitioning, so set autopart to
        # True. In the case of ks installs which may not have defined any
        # partition options, autopart was never set to True, causing some
        # issues. (rhbz#1001061)
        self.data.autopart.autopart = True
        self.data.clearpart.type = self.clearPartType
        self.data.clearpart.initAll = True

    def input(self, args, key):
        """Grab the choice and update things"""

        try:
            keyid = int(key) - 1
        except ValueError:
            if key.lower() == "c":
                newspoke = PartitionSchemeSpoke(self.app, self.data, self.storage,
                                                self.payload, self.instclass)
                self.app.switch_screen_modal(newspoke)
                self.apply()
                self.close()
                return INPUT_PROCESSED
            else:
                return key

        if 0 <= keyid < len(self.parttypelist):
            self.clearPartType = PARTTYPES[self.parttypelist[keyid]]
            self.apply()
        return INPUT_PROCESSED

class PartitionSchemeSpoke(NormalTUISpoke):
    """ Spoke to select what partitioning scheme to use on disk(s). """
    title = _("Partition Scheme Options")
    category = "system"

    # set default FS to LVM, for consistency with graphical behavior
    _selection = 1

    def __init__(self, app, data, storage, payload, instclass):
        NormalTUISpoke.__init__(self, app, data, storage, payload, instclass)
        self.partschemes = OrderedDict([("Standard Partition", AUTOPART_TYPE_PLAIN),
                        ("LVM", AUTOPART_TYPE_LVM), ("BTRFS", AUTOPART_TYPE_BTRFS)])

    @property
    def indirect(self):
        return True

    def refresh(self, args=None):
        NormalTUISpoke.refresh(self, args)

        schemelist = self.partschemes.keys()
        for sch in schemelist:
            box = CheckboxWidget(title="%i) %s" %(schemelist.index(sch) \
                                 + 1, sch), completed=(schemelist.index(sch) \
                                 == self._selection))
            self._window += [box, ""]

        message = _("Select a partition scheme configuration.")
        self._window += [TextWidget(message), ""]
        return True

    def input(self, args, key):
        """ Grab the choice and update things. """

        try:
            keyid = int(key) - 1
        except ValueError:
            if key.lower() == "c":
                self.apply()
                self.close()
                return INPUT_PROCESSED
            else:
                return key

        if 0 <= keyid < len(self.partschemes):
            self._selection = keyid
        return INPUT_PROCESSED

    def apply(self):
        """ Apply our selections. """

        schemelist = self.partschemes.values()
        try:
            self.data.autopart.type = schemelist[self._selection]
        except IndexError:
            # we shouldn't ever see this, but just in case, don't crash.
            # when autopart.type is detected as None in AutoPartSpoke.apply(),
            # it'll automatically just be set to LVM
            pass
