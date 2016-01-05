# devicetree.py
# Device management for anaconda's storage configuration module.
#
# Copyright (C) 2009  Red Hat, Inc.
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
# Red Hat Author(s): Dave Lehman <dlehman@redhat.com>
#

import os
import stat
import block
import re

from errors import *
from devices import *
from deviceaction import *
from partitioning import shouldClear
from pykickstart.constants import *
import formats
import devicelibs.mdraid
import devicelibs.dm
import devicelibs.lvm
import devicelibs.mpath
from udev import *
from .storage_log import log_method_call
import iutil
import platform
import parted
import _ped

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("storage")

def getLUKSPassphrase(intf, device, globalPassphrase):
    """ Obtain a passphrase for a LUKS encrypted block device.

        The format's mapping name must already be set and the backing
        device must already be set up before calling this function.

        If successful, this function leaves the device mapped.

        Return value is a two-tuple: (passphrase, isglobal)

        passphrase is the passphrase string, if obtained
        isglobal is a boolean indicating whether the passphrase is global

        Either or both can be None, depending on the outcome.
    """
    if device.format.type != "luks":
        # this function only works on luks devices
        raise ValueError("not a luks device")

    if not device.status:
        # the device should have already been set up
        raise RuntimeError("device is not set up")

    if device.format.status:
        # the device is already mapped
        raise RuntimeError("device is already mapped")

    if not device.format.configured and globalPassphrase:
        # try the given passphrase first
        device.format.passphrase =  globalPassphrase
    
        try:
            device.format.setup()
        except CryptoError as e:
            device.format.passphrase = None
        else:
            # we've opened the device so we're done.
            return (globalPassphrase, False)

    if not intf:
        return (None, None)
    
    buttons = [_("Back"), _("Continue")]
    passphrase_incorrect = False
    while True:
        if passphrase_incorrect:
            # TODO: add a flag to passphraseEntryWindow to say the last
            #       passphrase was incorrect so try again
            passphrase_incorrect = False
        (passphrase, isglobal) = intf.passphraseEntryWindow(device.name)
        if not passphrase:
            rc = intf.messageWindow(_("Confirm"),
                                    _("Are you sure you want to skip "
                                      "entering a passphrase for device "
                                      "%s?\n\n"
                                      "If you skip this step the "
                                      "device's contents will not "
                                      "be available during "
                                      "installation.") % device.name,
                                    type = "custom",
                                    default = 0,
                                    custom_buttons = buttons)
            if rc == 0:
                continue
            else:
                passphrase = None
                isglobal = None
                log.info("skipping passphrase for %s" % (device.name,))
                break

        device.format.passphrase = passphrase

        try:
            device.format.setup()
        except CryptoError as e:
            device.format.passphrase = None
            passphrase_incorrect = True
        else:
            # we've opened the device so we're done.
            break

    return (passphrase, isglobal)


class DeviceTree(object):
    """ A quasi-tree that represents the devices in the system.

        The tree contains a list of device instances, which does not
        necessarily reflect the actual state of the system's devices.
        DeviceActions are used to perform modifications to the tree,
        except when initially populating the tree.

        DeviceAction instances are registered, possibly causing the
        addition or removal of Device instances to/from the tree. The
        DeviceActions are all reversible up to the time their execute
        method has been called.

        Only one action of any given type/object pair should exist for
        any given device at any given time.

        DeviceAction instances can only be registered for leaf devices,
        except for resize actions.
    """

    def __init__(self, intf=None, ignored=[], exclusive=[], type=CLEARPART_TYPE_NONE,
                 clear=[], zeroMbr=None, reinitializeDisks=None, protected=[],
                 passphrase=None, luksDict=None, iscsi=None, dasd=None,
                 mpathFriendlyNames=True, cdl=False):
        # internal data members
        self._devices = []
        self._actions = []

        # indicates whether or not the tree has been fully populated
        self.populated = False

        self.intf = intf
        self.exclusiveDisks = exclusive
        self.clearPartType = type
        self.clearPartDisks = clear
        self.zeroMbr = zeroMbr
        self.cdl = cdl
        self.reinitializeDisks = reinitializeDisks
        self.iscsi = iscsi
        self.dasd = dasd
        self.platform = platform.getPlatform(None)
        self.mpathFriendlyNames = mpathFriendlyNames

        # protected device specs as provided by the user
        self.protectedDevSpecs = protected

        # names of protected devices at the time of tree population
        self.protectedDevNames = []

        self.unusedRaidMembers = []

        self.__multipaths = {}
        self.__multipathConfigWriter = devicelibs.mpath.MultipathConfigWriter()

        self.__passphrase = passphrase
        self.__luksDevs = {}
        if luksDict and isinstance(luksDict, dict):
            self.__luksDevs = luksDict
        self._ignoredDisks = []
        for disk in ignored:
            self.addIgnoredDisk(disk)
        lvm.lvm_cc_resetFilter()

    def addIgnoredDisk(self, disk):
        self._ignoredDisks.append(disk)
        lvm.lvm_cc_addFilterRejectRegexp(disk)

    def pruneActions(self):
        """ Prune loops and redundant actions from the queue. """

        # handle device destroy actions
        actions = self.findActions(type="destroy", object="device")
        for a in actions:
            if a not in self._actions:
                # we may have removed some of the actions in a previous
                # iteration of this loop
                continue

            log.debug("action '%s' (%s)" % (a, id(a)))
            destroys = self.findActions(devid=a.device.id,
                                        type="destroy",
                                        object="device")

            creates = self.findActions(devid=a.device.id,
                                       type="create",
                                       object="device")
            log.debug("found %d create and %d destroy actions for device id %d"
                        % (len(creates), len(destroys), a.device.id))

            # If the device is not preexisting, we remove all actions up
            # to and including the last destroy action.
            # If the device is preexisting, we remove all actions from
            # after the first destroy action up to and including the last
            # destroy action.
            # If the device is preexisting and there is only one device
            # destroy action we remove all resize and format create/migrate
            # actions on that device that precede the destroy action.
            loops = []
            first_destroy_idx = None
            first_create_idx = None
            stop_action = None
            start = None
            if len(destroys) > 1:
                # there are multiple destroy actions for this device
                loops = destroys
                first_destroy_idx = self._actions.index(loops[0])
                start = self._actions.index(a) + 1
                stop_action = destroys[-1]

            if creates:
                first_create_idx = self._actions.index(creates[0])
                if not loops or first_destroy_idx > first_create_idx:
                    # this device is not preexisting
                    start = first_create_idx
                    stop_action = destroys[-1]

            prune_actions = self.findActions(devid=a.device.id)
            if start is None:
                # only one device destroy, so prune preceding resizes and format
                # creates and migrates and the destroy itself if the device
                # doesn't exist
                for act in prune_actions[:]:
                    if act.isResize() or \
                       (act.isFormat() and not act.isDestroy()) or \
                       (act.isDestroy() and not act.device.exists):
                        continue

                    prune_actions.remove(act)

                if not prune_actions:
                    # nothing to prune
                    continue

                start = self._actions.index(prune_actions[0])
                stop_action = prune_actions[-1]

            # now we remove all actions on this device between the start
            # index (into self._actions) and stop_action.
            for rem in prune_actions:
                end = self._actions.index(stop_action)
                if start <= self._actions.index(rem) <= end:
                    log.debug(" removing action '%s' (%s)" % (rem, id(rem)))
                    self._actions.remove(rem)

                if rem == stop_action:
                    break

        # device create actions
        actions = self.findActions(type="create", object="device")
        for a in actions:
            if a not in self._actions:
                # we may have removed some of the actions in a previous
                # iteration of this loop
                continue

            log.debug("action '%s' (%s)" % (a, id(a)))
            creates = self.findActions(devid=a.device.id,
                                       type="create",
                                       object="device")

            destroys = self.findActions(devid=a.device.id,
                                        type="destroy",
                                        object="device")

            # If the device is preexisting, we remove everything between
            # the first destroy and the last create.
            # If the device is not preexisting, we remove everything up to
            # the last create.
            loops = []
            first_destroy_idx = None
            first_create_idx = None
            stop_action = None
            start = None
            if len(creates) > 1:
                # there are multiple create actions for this device
                loops = creates
                first_create_idx = self._actions.index(loops[0])
                start = 0
                stop_action = creates[-1]

            if destroys:
                first_destroy_idx = self._actions.index(destroys[0])
                if not loops or first_create_idx > first_destroy_idx:
                    # this device is preexisting
                    start = first_destroy_idx + 1
                    stop_action = creates[-1]

            if start is None:
                continue

            # remove all actions on this from after the first destroy up
            # to the last create
            prune_actions = self.findActions(devid=a.device.id)
            for rem in prune_actions:
                if rem == stop_action:
                    break

                end = self._actions.index(stop_action)
                if start <= self._actions.index(rem) < end:
                    log.debug(" removing action '%s' (%s)" % (rem, id(rem)))
                    self._actions.remove(rem)

        # device resize actions
        actions = self.findActions(type="resize", object="device")
        for a in actions:
            if a not in self._actions:
                # we may have removed some of the actions in a previous
                # iteration of this loop
                continue

            log.debug("action '%s' (%s)" % (a, id(a)))
            loops = self.findActions(devid=a.device.id,
                                     type="resize",
                                     object="device")

            if len(loops) == 1:
                continue

            # remove all but the last resize action on this device
            for rem in loops[:-1]:
                log.debug(" removing action '%s' (%s)" % (rem, id(rem)))
                self._actions.remove(rem)

        # format destroy
        # XXX I don't think there's a way for these loops to happen
        actions = self.findActions(type="destroy", object="format")
        for a in actions:
            if a not in self._actions:
                # we may have removed some of the actions in a previous
                # iteration of this loop
                continue

            log.debug("action '%s' (%s)" % (a, id(a)))
            destroys = self.findActions(devid=a.device.id,
                                        type="destroy",
                                        object="format")

            creates = self.findActions(devid=a.device.id,
                                       type="create",
                                       object="format")

            # If the format is not preexisting, we remove all actions up
            # to and including the last destroy action.
            # If the format is preexisting, we remove all actions from
            # after the first destroy action up to and including the last
            # destroy action.
            loops = []
            first_destroy_idx = None
            first_create_idx = None
            stop_action = None
            start = None
            if len(destroys) > 1:
                # there are multiple destroy actions for this format
                loops = destroys
                first_destroy_idx = self._actions.index(loops[0])
                start = self._actions.index(a) + 1
                stop_action = destroys[-1]

            if creates:
                first_create_idx = self._actions.index(creates[0])
                if not loops or first_destroy_idx > first_create_idx:
                    # this format is not preexisting
                    start = first_create_idx
                    stop_action = destroys[-1]

            if start is None:
                continue

            # now we remove all actions on this device's format between
            # the start index (into self._actions) and stop_action.
            prune_actions = self.findActions(devid=a.device.id,
                                           object="format")
            for rem in prune_actions:
                end = self._actions.index(stop_action)
                if start <= self._actions.index(rem) <= end:
                    log.debug(" removing action '%s' (%s)" % (rem, id(rem)))
                    self._actions.remove(rem)

                if rem == stop_action:
                    break

        # format create
        # XXX I don't think there's a way for these loops to happen
        actions = self.findActions(type="create", object="format")
        for a in actions:
            if a not in self._actions:
                # we may have removed some of the actions in a previous
                # iteration of this loop
                continue

            log.debug("action '%s' (%s)" % (a, id(a)))
            creates = self.findActions(devid=a.device.id,
                                       type="create",
                                       object="format")

            destroys = self.findActions(devid=a.device.id,
                                        type="destroy",
                                        object="format")

            # If the format is preexisting, we remove everything between
            # the first destroy and the last create.
            # If the format is not preexisting, we remove everything up to
            # the last create.
            loops = []
            first_destroy_idx = None
            first_create_idx = None
            stop_action = None
            start = None
            if len(creates) > 1:
                # there are multiple create actions for this format
                loops = creates
                first_create_idx = self._actions.index(loops[0])
                start = 0
                stop_action = creates[-1]

            if destroys:
                first_destroy_idx = self._actions.index(destroys[0])
                if not loops or first_create_idx > first_destroy_idx:
                    # this format is preexisting
                    start = first_destroy_idx + 1
                    stop_action = creates[-1]

            if start is None:
                continue

            # remove all actions on this from after the first destroy up
            # to the last create
            dev_actions = self.findActions(devid=a.device.id,
                                           object="format")
            for rem in dev_actions:
                if rem == stop_action:
                    break

                end = self._actions.index(stop_action)
                if start <= self._actions.index(rem) < end:
                    log.debug(" removing action '%s' (%s)" % (rem, id(rem)))
                    self._actions.remove(rem)

        # format resize
        actions = self.findActions(type="resize", object="format")
        for a in actions:
            if a not in self._actions:
                # we may have removed some of the actions in a previous
                # iteration of this loop
                continue

            log.debug("action '%s' (%s)" % (a, id(a)))
            loops = self.findActions(devid=a.device.id,
                                     type="resize",
                                     object="format")

            if len(loops) == 1:
                continue

            # remove all but the last resize action on this format
            for rem in loops[:-1]:
                log.debug(" removing action '%s' (%s)" % (rem, id(rem)))
                self._actions.remove(rem)

        # format migrate
        # XXX I don't think there's away for these loops to occur
        actions = self.findActions(type="migrate", object="format")
        for a in actions:
            if a not in self._actions:
                # we may have removed some of the actions in a previous
                # iteration of this loop
                continue

            log.debug("action '%s' (%s)" % (a, id(a)))
            loops = self.findActions(devid=a.device.id,
                                     type="migrate",
                                     object="format")

            if len(loops) == 1:
                continue

            # remove all but the last migrate action on this format
            for rem in loops[:-1]:
                log.debug(" removing action '%s' (%s)" % (rem, id(rem)))
                self._actions.remove(rem)

    def processActions(self, dryRun=None):
        """ Execute all registered actions. """
        # in most cases the actions will already be sorted because of the
        # rules for registration, but let's not rely on that
        def cmpActions(a1, a2):
            ret = 0
            if a1.isDestroy() and a2.isDestroy():
                if a1.device.path == a2.device.path:
                    # if it's the same device, destroy the format first
                    if a1.isFormat() and a2.isFormat():
                        ret = 0
                    elif a1.isFormat() and not a2.isFormat():
                        ret = -1
                    elif not a1.isFormat() and a2.isFormat():
                        ret = 1
                elif a1.device.dependsOn(a2.device):
                    ret = -1
                elif a2.device.dependsOn(a1.device):
                    ret = 1
                # generally destroy partitions after lvs, vgs, &c
                elif isinstance(a1.device, PartitionDevice) and \
                     isinstance(a2.device, PartitionDevice):
                    if a1.device.disk == a2.device.disk:
                        ret = cmp(a2.device.partedPartition.number,
                                  a1.device.partedPartition.number)
                    else:
                        ret = cmp(a2.device.name, a1.device.name)
                elif isinstance(a1.device, PartitionDevice) and \
                     a2.device.partitioned:
                    ret = -1
                elif isinstance(a2.device, PartitionDevice) and \
                     a1.device.partitioned:
                    ret = 1
                # remove partitions before unpartitioned non-partition
                # devices
                elif isinstance(a1.device, PartitionDevice) and \
                     not isinstance(a2.device, PartitionDevice):
                    ret = 1
                elif isinstance(a2.device, PartitionDevice) and \
                     not isinstance(a1.device, PartitionDevice):
                    ret = -1
                else:
                    ret = 0
            elif a1.isDestroy():
                ret = -1
            elif a2.isDestroy():
                ret = 1
            elif a1.isResize() and a2.isResize():
                if a1.device.path == a2.device.path:
                    if a1.obj == a2.obj:
                        ret = 0
                    elif a1.isFormat() and not a2.isFormat():
                        # same path, one device, one format
                        if a1.isGrow():
                            ret = 1
                        else:
                            ret = -1
                    elif not a1.isFormat() and a2.isFormat():
                        # same path, one device, one format
                        if a1.isGrow():
                            ret = -1
                        else:
                            ret = 1
                    else:
                        ret = cmp(a1.device.name, a2.device.name)
                elif a1.device.dependsOn(a2.device):
                    if a1.isGrow():
                        ret = 1
                    else:
                        ret = -1
                elif a2.device.dependsOn(a1.device):
                    if a1.isGrow():
                        ret = -1
                    else:
                        ret = 1
                elif isinstance(a1.device, PartitionDevice) and \
                     isinstance(a2.device, PartitionDevice):
                    ret = cmp(a1.device.name, a2.device.name)
                else:
                    ret = 0
            elif a1.isResize():
                ret = -1
            elif a2.isResize():
                ret = 1
            elif a1.isCreate() and a2.isCreate():
                if a1.device.path == a2.device.path:
                    if a1.obj == a2.obj:
                        ret = 0
                    if a1.isFormat():
                        ret = 1
                    elif a2.isFormat():
                        ret = -1
                    else:
                        ret = 0
                elif a1.device.dependsOn(a2.device):
                    ret = 1
                elif a2.device.dependsOn(a1.device):
                    ret = -1
                # generally create partitions before other device types
                elif isinstance(a1.device, PartitionDevice) and \
                     isinstance(a2.device, PartitionDevice):
                    if a1.device.disk == a2.device.disk:
                        ret = cmp(a1.device.partedPartition.number,
                                  a2.device.partedPartition.number)
                    else:
                        ret = cmp(a1.device.name, a2.device.name)
                elif isinstance(a1.device, LVMLogicalVolumeDevice) and \
                     isinstance(a2.device, LVMLogicalVolumeDevice) and \
                     a1.device.vg == a2.device.vg:
                    if a1.device.singlePV and not a2.device.singlePV:
                        ret = -1
                    elif not a1.device.singlePV and a2.device.singlePV:
                        ret = 1
                elif isinstance(a1.device, PartitionDevice) and \
                     a2.device.partitioned:
                    ret = 1
                elif isinstance(a2.device, PartitionDevice) and \
                     a1.device.partitioned:
                    ret = -1
                elif isinstance(a1.device, PartitionDevice) and \
                     not isinstance(a2.device, PartitionDevice):
                    ret = -1
                elif isinstance(a2.device, PartitionDevice) and \
                     not isinstance(a1.device, PartitionDevice):
                    ret = 1
                else:
                    ret = 0
            elif a1.isCreate():
                ret = -1
            elif a2.isCreate():
                ret = 1
            elif a1.isMigrate() and a2.isMigrate():
                if a1.device.path == a2.device.path:
                    ret = 0
                elif a1.device.dependsOn(a2.device):
                    ret = 1
                elif a2.device.dependsOn(a1.device):
                    ret = -1
                elif isinstance(a1.device, PartitionDevice) and \
                     isinstance(a2.device, PartitionDevice):
                    if a1.device.disk == a2.device.disk:
                        ret = cmp(a1.device.partedPartition.number,
                                  a2.device.partedPartition.number)
                    else:
                        ret = cmp(a1.device.name, a2.device.name)
                else:
                    ret = 0
            else:
                ret = 0

            log.debug("cmp: %d -- %s | %s" % (ret, a1, a2))
            return ret

        log.debug("resetting parted disks...")
        for device in self.devices:
            if device.partitioned:
                device.format.resetPartedDisk()
                if device.originalFormat.type == "disklabel" and \
                   device.originalFormat != device.format:
                    device.originalFormat.resetPartedDisk()

        # Call preCommitFixup on all devices
        mpoints = [getattr(d.format, 'mountpoint', "") for d in self.devices]
        for device in self.devices:
            device.preCommitFixup(mountpoints=mpoints)

        # Also call preCommitFixup on any devices we're going to
        # destroy (these are already removed from the tree)
        for action in self._actions:
            if isinstance(action, ActionDestroyDevice):
                action.device.preCommitFixup(mountpoints=mpoints)

        # setup actions to create any extended partitions we added
        #
        # XXX At this point there can be duplicate partition paths in the
        #     tree (eg: non-existent sda6 and previous sda6 that will become
        #     sda5 in the course of partitioning), so we access the list
        #     directly here.
        for device in self._devices:
            if isinstance(device, PartitionDevice) and \
               device.isExtended and not device.exists:
                # don't properly register the action since the device is
                # already in the tree
                self._actions.append(ActionCreateDevice(device))

        for action in self._actions:
            log.debug("action: %s" % action)

        log.debug("pruning action queue...")
        self.pruneActions()
        for action in self._actions:
            log.debug("action: %s" % action)

        log.debug("sorting actions...")
        self._actions.sort(cmp=cmpActions)
        for action in self._actions:
            log.debug("action: %s" % action)

            # Remove lvm filters for devices we are operating on
            for device in (d for d in self._devices if d.dependsOn(action.device)):
                lvm.lvm_cc_removeFilterRejectRegexp(device.name)

        for action in self._actions:
            log.info("executing action: %s" % action)
            if not dryRun:
                try:
                    action.execute(intf=self.intf)
                except DiskLabelCommitError:
                    # it's likely that a previous format destroy action
                    # triggered setup of an lvm or md device.
                    self.teardownAll()
                    action.execute(intf=self.intf)

                udev_settle()
                for device in self._devices:
                    # make sure we catch any renumbering parted does
                    if device.exists and isinstance(device, PartitionDevice):
                        device.updateName()
                        device.format.device = device.path

    def _addDevice(self, newdev):
        """ Add a device to the tree.

            Raise ValueError if the device's identifier is already
            in the list.
        """
        if newdev.path in [d.path for d in self._devices] and \
           not isinstance(newdev, NoDevice):
            raise ValueError("device is already in tree")

        # make sure this device's parent devices are in the tree already
        for parent in newdev.parents:
            if parent not in self._devices:
                raise DeviceTreeError("parent device not in tree")

        self._devices.append(newdev)
        log.debug("added %s %s (id %d) to device tree" % (newdev.type,
                                                          newdev.name,
                                                          newdev.id))

    def _removeDevice(self, dev, force=None, moddisk=True):
        """ Remove a device from the tree.

            Only leaves may be removed.
        """
        if dev not in self._devices:
            raise ValueError("Device '%s' not in tree" % dev.name)

        if not dev.isleaf and not force:
            log.debug("%s has %d kids" % (dev.name, dev.kids))
            raise ValueError("Cannot remove non-leaf device '%s'" % dev.name)

        # if this is a partition we need to remove it from the parted.Disk
        if moddisk and isinstance(dev, PartitionDevice) and \
                dev.disk is not None:
            # if this partition hasn't been allocated it could not have
            # a disk attribute
            if dev.partedPartition.type == parted.PARTITION_EXTENDED and \
                    len(dev.disk.format.logicalPartitions) > 0:
                raise ValueError("Cannot remove extended partition %s.  "
                        "Logical partitions present." % dev.name)

            dev.disk.format.removePartition(dev.partedPartition)

            # adjust all other PartitionDevice instances belonging to the
            # same disk so the device name matches the potentially altered
            # name of the parted.Partition
            for device in self._devices:
                if isinstance(device, PartitionDevice) and \
                   device.disk == dev.disk:
                    device.updateName()

        self._devices.remove(dev)
        log.debug("removed %s %s (id %d) from device tree" % (dev.type,
                                                              dev.name,
                                                              dev.id))

        for parent in dev.parents:
            # Will this cause issues with garbage collection?
            #   Do we care about garbage collection? At all?
            parent.removeChild()

    def registerAction(self, action):
        """ Register an action to be performed at a later time.

            Modifications to the Device instance are handled before we
            get here.
        """
        if (action.isDestroy() or action.isResize() or \
            (action.isCreate() and action.isFormat())) and \
           action.device not in self._devices:
            raise DeviceTreeError("device is not in the tree")
        elif (action.isCreate() and action.isDevice()):
            # this allows multiple create actions w/o destroy in between;
            # we will clean it up before processing actions
            #raise DeviceTreeError("device is already in the tree")
            if action.device in self._devices:
                self._removeDevice(action.device)
            for d in self._devices:
                if d.path == action.device.path:
                    self._removeDevice(d)

        if action.isCreate() and action.isDevice():
            self._addDevice(action.device)
        elif action.isDestroy() and action.isDevice():
            self._removeDevice(action.device)
        elif action.isCreate() and action.isFormat():
            if isinstance(action.device.format, formats.fs.FS) and \
               action.device.format.mountpoint in self.filesystems:
                raise DeviceTreeError("mountpoint already in use")

        log.debug("registered action: %s" % action)
        self._actions.append(action)

    def cancelAction(self, action):
        """ Cancel a registered action.

            This will unregister the action and do any required
            modifications to the device list.

            Actions all operate on a Device, so we can use the devices
            to determine dependencies.
        """
        if action.isCreate() and action.isDevice():
            # remove the device from the tree
            self._removeDevice(action.device)
        elif action.isDestroy() and action.isDevice():
            # add the device back into the tree
            self._addDevice(action.device)
        elif action.isFormat() and \
             (action.isCreate() or action.isMigrate() or action.isResize()):
            action.cancel()

        self._actions.remove(action)

    def findActions(self, device=None, type=None, object=None, path=None,
                    devid=None):
        """ Find all actions that match all specified parameters.

            Keyword arguments:

                device -- device to match (Device, or None to match any)
                type -- action type to match (string, or None to match any)
                object -- operand type to match (string, or None to match any)
                path -- device path to match (string, or None to match any)

        """
        if device is None and type is None and object is None and \
           path is None and devid is None:
            return self._actions[:]

        # convert the string arguments to the types used in actions
        _type = action_type_from_string(type)
        _object = action_object_from_string(object)

        actions = []
        for action in self._actions:
            if device is not None and action.device != device:
                continue

            if _type is not None and action.type != _type:
                continue

            if _object is not None and action.obj != _object:
                continue

            if path is not None and action.device.path != path:
                continue

            if devid is not None and action.device.id != devid:
                continue
                
            actions.append(action)

        return actions

    def getDependentDevices(self, dep):
        """ Return a list of devices that depend on dep.

            The list includes both direct and indirect dependents.
        """
        dependents = []

        # special handling for extended partitions since the logical
        # partitions and their deps effectively depend on the extended
        logicals = []
        if isinstance(dep, PartitionDevice) and dep.partType and \
           dep.isExtended:
            # collect all of the logicals on the same disk
            for part in self.getDevicesByInstance(PartitionDevice):
                if part.partType and part.isLogical and part.disk == dep.disk:
                    logicals.append(part)

        for device in self.devices:
            if device.dependsOn(dep):
                dependents.append(device)
            else:
                for logical in logicals:
                    if device.dependsOn(logical):
                        dependents.append(device)
                        break

        return dependents

    def isIgnored(self, info):
        """ Return True if info is a device we should ignore.

            Arguments:

                info -- a dict representing a udev db entry

            TODO:

                - filtering of SAN/FC devices
                - filtering by driver?

        """
        sysfs_path = udev_device_get_sysfs_path(info)
        name = udev_device_get_name(info)
        if not sysfs_path:
            return None

        if name in self._ignoredDisks:
            log.debug("device '%s' in ignoredDisks" % name)
            return True

        # Special handling for mdraid external metadata sets (mdraid BIOSRAID):
        # 1) The containers are intermediate devices which will never be
        # in exclusiveDisks
        # 2) Sets get added to exclusive disks with their dmraid set name by
        # the filter ui.  Note that making the ui use md names instead is not
        # possible as the md names are simpy md# and we cannot predict the #
        if udev_device_get_md_level(info) == "container":
            return False

        if udev_device_get_md_container(info) and \
               udev_device_get_md_name(info):
            md_name = udev_device_get_md_name(info)
            for i in range(0, len(self.exclusiveDisks)):
                # Udev changes special characters in md device names
                # Substitute them in name from exclusiveDisks before matching
                disk_name = re.sub('[ \t]', '_', self.exclusiveDisks[i]).replace('/', '-')
                if re.match("isw_[a-z]*_%s" % md_name, disk_name):
                    self.exclusiveDisks[i] = name
                    return False

        # We want exclusiveDisks to operate on anything that could be
        # considered a directly usable disk, ie: fwraid array, mpath, or disk.
        #
        # Unfortunately, since so many things are represented as disks by
        # udev/sysfs, we have to define what is a disk in terms of what is
        # not a disk.
        if udev_device_is_disk(info) and \
           not udev_device_is_dm_partition(info) and \
           not udev_device_is_dm_lvm(info) and \
           not udev_device_is_dm_crypt(info) and \
           not (udev_device_is_md(info) and
                not udev_device_get_md_container(info)):
            if self.exclusiveDisks and name not in self.exclusiveDisks:
                log.debug("device '%s' not in exclusiveDisks" % name)
                self.addIgnoredDisk(name)
                return True

        # Ignore loop and ram devices, we normally already skip these in
        # udev.py: enumerate_block_devices(), but we can still end up trying
        # to add them to the tree when they are slaves of other devices, this
        # happens for example with the livecd
        if name.startswith("loop") or name.startswith("ram"):
            return True

        # Ignore any readonly disks
        if (udev_device_is_disk(info) and not
            (udev_device_is_cdrom(info) or
             udev_device_is_partition(info) or
             udev_device_is_dm_partition(info) or
             udev_device_is_dm_lvm(info) or
             udev_device_is_dm_crypt(info) or
             (udev_device_is_md(info) and not
              udev_device_get_md_container(info)))):
            if iutil.get_sysfs_attr(info["sysfs_path"], 'ro') == '1':
                log.debug("Ignoring read only device %s" % name)
                self.addIgnoredDisk(name)
                return True

        # FIXME: check for virtual devices whose slaves are on the ignore list

    def addUdevDMDevice(self, info):
        name = udev_device_get_name(info)
        log_method_call(self, name=name)
        uuid = udev_device_get_uuid(info)
        sysfs_path = udev_device_get_sysfs_path(info)
        device = None

        for dmdev in self.devices:
            if not isinstance(dmdev, DMDevice):
                continue

            try:
                # there is a device in the tree already with the same
                # major/minor as this one but with a different name
                # XXX this is kind of racy
                if dmdev.getDMNode() == os.path.basename(sysfs_path):
                    # XXX should we take the name already in use?
                    device = dmdev
                    break
            except DMError:
                # This is a little lame, but the VG device is a DMDevice
                # and it won't have a dm node. At any rate, this is not
                # important enough to crash the install.
                log.debug("failed to find dm node for %s" % dmdev.name)
                continue

        if device is None:
            # we couldn't find it, so create it
            # first, get a list of the slave devs and look them up
            slaves = []
            dir = os.path.normpath("/sys/%s/slaves" % sysfs_path)
            slave_names = os.listdir(dir)
            for slave_name in slave_names:
                # if it's a dm-X name, resolve it to a map name first
                if slave_name.startswith("dm-"):
                    dev_name = dm.name_from_dm_node(slave_name)
                else:
                    dev_name = slave_name
                slave_dev = self.getDeviceByName(dev_name)
                if slave_dev:
                    slaves.append(slave_dev)
                else:
                    # we haven't scanned the slave yet, so do it now
                    path = os.path.normpath("%s/%s" % (dir, slave_name))
                    new_info = udev_get_block_device(os.path.realpath(path)[4:])
                    if new_info:
                        self.addUdevDevice(new_info)
                        if self.getDeviceByName(dev_name) is None:
                            # if the current slave is still not in
                            # the tree, something has gone wrong
                            log.error("failure scanning device %s: could not add slave %s" % (name, dev_name))
                            return

            # try to get the device again now that we've got all the slaves
            device = self.getDeviceByName(name)

            if device is None and udev_device_is_dm_partition(info):
                    diskname = udev_device_get_dm_partition_disk(info)
                    disk = self.getDeviceByName(diskname)
                    return self.addUdevPartitionDevice(info, disk=disk)

            # if we get here, we found all of the slave devices and
            # something must be wrong -- if all of the slaves are in
            # the tree, this device should be as well
            if device is None:
                log.warning("ignoring dm device %s" % name)

        return device

    def addUdevMDDevice(self, info):
        name = udev_device_get_name(info)
        log_method_call(self, name=name)
        uuid = udev_device_get_uuid(info)
        sysfs_path = udev_device_get_sysfs_path(info)
        device = None

        slaves = []
        dir = os.path.normpath("/sys/%s/slaves" % sysfs_path)
        slave_names = os.listdir(dir)
        for slave_name in slave_names:
            # if it's a dm-X name, resolve it to a map name
            if slave_name.startswith("dm-"):
                dev_name = dm.name_from_dm_node(slave_name)
            else:
                dev_name = slave_name
            slave_dev = self.getDeviceByName(dev_name)
            if slave_dev:
                slaves.append(slave_dev)
            else:
                # we haven't scanned the slave yet, so do it now
                path = os.path.normpath("%s/%s" % (dir, slave_name))
                new_info = udev_get_block_device(os.path.realpath(path)[4:])
                if new_info:
                    self.addUdevDevice(new_info)
                    if self.getDeviceByName(dev_name) is None:
                        # if the current slave is still not in
                        # the tree, something has gone wrong
                        log.error("failure scanning device %s: could not add slave %s" % (name, dev_name))
                        return

        # try to get the device again now that we've got all the slaves
        device = self.getDeviceByName(name)

        if device is None:
            device = self.getDeviceByUuid(info.get("MD_UUID"))
            if device:
                raise DeviceTreeError("MD RAID device %s already in "
                                      "devicetree as %s" % (name, device.name))

        # if we get here, we found all of the slave devices and
        # something must be wrong -- if all of the slaves we in
        # the tree, this device should be as well
        if device is None:
            log.warning("using MD RAID device for %s" % name)
            try:
                # level is reported as, eg: "raid1"
                md_level = udev_device_get_md_level(info)
                md_devices = int(udev_device_get_md_devices(info))
                md_uuid = udev_device_get_md_uuid(info)
            except (KeyError, IndexError, ValueError) as e:
                log.warning("invalid data for %s: %s" % (name, e))
                return

            device = MDRaidArrayDevice(name,
                                       level=md_level,
                                       memberDevices=md_devices,
                                       uuid=md_uuid,
                                       exists=True,
                                       parents=slaves)
            self._addDevice(device)

        return device

    def addUdevPartitionDevice(self, info, disk=None):
        name = udev_device_get_name(info)
        log_method_call(self, name=name)
        uuid = udev_device_get_uuid(info)
        sysfs_path = udev_device_get_sysfs_path(info)
        device = None

        if disk is None:
            disk_name = os.path.basename(os.path.dirname(sysfs_path))
            disk_name = disk_name.replace('!','/')
            disk = self.getDeviceByName(disk_name)

        if disk is None:
            # create a device instance for the disk
            new_info = udev_get_block_device(os.path.dirname(sysfs_path))
            if new_info:
                self.addUdevDevice(new_info)
                disk = self.getDeviceByName(disk_name)

            if disk is None:
                # if the current device is still not in
                # the tree, something has gone wrong
                log.error("failure scanning device %s" % disk_name)
                lvm.lvm_cc_addFilterRejectRegexp(name)
                return

        # Check that the disk has partitions. If it does not, we must have
        # reinitialized the disklabel.
        #
        # Also ignore partitions on devices we do not support partitioning
        # of, like logical volumes.
        if not getattr(disk.format, "partitions", None) or \
           not disk.partitionable:
            # When we got here because the disk does not have a disklabel
            # format (ie a biosraid member), or because it is not
            # partitionable we want LVM to ignore this partition too
            if disk.format.type != "disklabel" or not disk.partitionable:
                lvm.lvm_cc_addFilterRejectRegexp(name)
            log.debug("ignoring partition %s" % name)
            return

        try:
            device = PartitionDevice(name, sysfsPath=sysfs_path,
                                     major=udev_device_get_major(info),
                                     minor=udev_device_get_minor(info),
                                     exists=True, parents=[disk])
        except DeviceError:
            # corner case sometime the kernel accepts a partition table
            # which gets rejected by parted, in this case we will
            # prompt to re-initialize the disk, so simply skip the
            # faulty partitions.
            return

        self._addDevice(device)
        return device

    def addUdevDiskDevice(self, info):
        name = udev_device_get_name(info)
        log_method_call(self, name=name)
        uuid = udev_device_get_uuid(info)
        sysfs_path = udev_device_get_sysfs_path(info)
        serial = udev_device_get_serial(info)
        bus = udev_device_get_bus(info)

        # udev doesn't always provide a vendor.
        vendor = udev_device_get_vendor(info)
        if not vendor:
            vendor = ""

        device = None

        kwargs = { "serial": serial, "vendor": vendor, "bus": bus }
        if udev_device_is_iscsi(info):
            diskType = iScsiDiskDevice
            initiator = udev_device_get_iscsi_initiator(info)
            target = udev_device_get_iscsi_name(info)
            address = udev_device_get_iscsi_address(info)
            port = udev_device_get_iscsi_port(info)
            nic = udev_device_get_iscsi_nic(info)
            kwargs["initiator"] = initiator
            if initiator == self.iscsi.initiator:
                node = self.iscsi.getNode(target, address, port, nic)
                kwargs["node"] = node
                kwargs["ibft"] = node in self.iscsi.ibftNodes
                kwargs["nic"] = self.iscsi.ifaces.get(node.iface, node.iface)
                log.debug("%s is an iscsi disk" % name)
            else:
                # qla4xxx partial offload
                kwargs["node"] = None
                kwargs["ibft"] = False
                kwargs["nic"] = "offload:not_accessible_via_iscsiadm"
                kwargs["fw_address"] = address
                kwargs["fw_port"] = port
                kwargs["fw_name"] = name
        elif udev_device_is_fcoe(info):
            diskType = FcoeDiskDevice
            kwargs["nic"]        = udev_device_get_fcoe_nic(info)
            kwargs["identifier"] = udev_device_get_fcoe_identifier(info)
            log.debug("%s is an fcoe disk" % name)
        elif udev_device_get_md_container(info):
            diskType = MDRaidArrayDevice
            parentName = devicePathToName(udev_device_get_md_container(info))
            container = self.getDeviceByName(parentName)
            if not container:
                container_sysfs = "/class/block/" + parentName
                container_info = udev_get_block_device(container_sysfs)
                if not container_info:
                    log.error("failed to find md container %s at %s"
                                % (parentName, container_sysfs))
                    return

                self.addUdevDevice(container_info)
                container = self.getDeviceByName(parentName)
                if not container:
                    log.error("failed to scan md container %s" % parentName)
                    return

            kwargs["parents"] = [container]
            kwargs["level"]  = udev_device_get_md_level(info)
            kwargs["memberDevices"] = int(udev_device_get_md_devices(info))
            kwargs["uuid"] = udev_device_get_md_uuid(info)
            kwargs["exists"]  = True
            del kwargs["serial"]
            del kwargs["vendor"]
            del kwargs["bus"]
        elif udev_device_is_dasd(info):
            diskType = DASDDevice
            kwargs["dasd"] = self.dasd
            kwargs["busid"] = udev_device_get_dasd_bus_id(info)
            kwargs["opts"] = {}

            for attr in ['readonly', 'use_diag', 'erplog', 'failfast']:
                kwargs["opts"][attr] = udev_device_get_dasd_flag(info, attr)

            log.debug("%s is a dasd device" % name)
        elif udev_device_is_zfcp(info):
            diskType = ZFCPDiskDevice

            for attr in ['hba_id', 'wwpn', 'fcp_lun']:
                kwargs[attr] = udev_device_get_zfcp_attribute(info, attr=attr)

            log.debug("%s is a zfcp device" % name)
        else:
            diskType = DiskDevice
            log.debug("%s is a disk" % name)

        device = diskType(name,
                          major=udev_device_get_major(info),
                          minor=udev_device_get_minor(info),
                          sysfsPath=sysfs_path, **kwargs)
        self._addDevice(device)
        return device

    def addUdevOpticalDevice(self, info):
        log_method_call(self)
        # XXX should this be RemovableDevice instead?
        #
        # Looks like if it has ID_INSTANCE=0:1 we can ignore it.
        device = OpticalDevice(udev_device_get_name(info),
                               major=udev_device_get_major(info),
                               minor=udev_device_get_minor(info),
                               sysfsPath=udev_device_get_sysfs_path(info),
                               vendor=udev_device_get_vendor(info),
                               model=udev_device_get_model(info))
        self._addDevice(device)
        return device

    def addUdevDevice(self, info):
        name = udev_device_get_name(info)
        log_method_call(self, name=name, info=info)
        uuid = udev_device_get_uuid(info)
        sysfs_path = udev_device_get_sysfs_path(info)

        if self.isIgnored(info):
            log.debug("ignoring %s (%s)" % (name, sysfs_path))
            if name not in self._ignoredDisks:
                self.addIgnoredDisk(name)

            if udev_device_is_multipath_member(info):
                # last time we are seeing this mpath member is now, so make sure
                # LVM ignores its partitions too else a duplicate VG name could
                # harm us later during partition creation:
                if udev_device_is_dm(info):
                    path = "/dev/mapper/%s" % name
                else:
                    path = "/dev/%s" % name
                log.debug("adding partitions on %s to the lvm ignore list" % path)
                partitions_paths = []
                try:
                    partitions_paths = [p.path
                                       for p in parted.Disk(device=parted.Device(path=path)).partitions]
                except (_ped.IOException, _ped.DeviceException, _ped.DiskLabelException) as e:
                    log.error("Parted error scanning partitions on %s:" % path)
                    log.error(str(e))
                # slice off the "/dev/" part, lvm filter cares only about the rest
                partitions_paths = [p[5:] for p in partitions_paths]
                map(lvm.lvm_cc_addFilterRejectRegexp, partitions_paths)
            return

        log.debug("scanning %s (%s)..." % (name, sysfs_path))
        device = self.getDeviceByName(name)

        #
        # The first step is to either look up or create the device
        #
        if udev_device_is_multipath_member(info) and device is None:
            device = self.addUdevDiskDevice(info)
        elif udev_device_is_dm(info) and udev_device_is_dm_mpath(info) and device is None:
            log.debug("%s is a multipath device" % name)
            device = self.addUdevDMDevice(info)
        elif udev_device_is_dm(info):
            log.debug("%s is a device-mapper device" % name)
            # try to look up the device
            if device is None and uuid:
                # try to find the device by uuid
                device = self.getDeviceByUuid(uuid)

            if device is None:
                device = self.addUdevDMDevice(info)
        elif udev_device_is_md(info):
            log.debug("%s is an md device" % name)
            if device is None and uuid:
                # try to find the device by uuid
                device = self.getDeviceByUuid(info.get("MD_UUID"))

            if device is None:
                device = self.addUdevMDDevice(info)
        elif udev_device_is_cdrom(info):
            log.debug("%s is a cdrom" % name)
            if device is None:
                device = self.addUdevOpticalDevice(info)
        elif udev_device_is_biosraid(info) and udev_device_is_disk(info):
            log.debug("%s is part of a biosraid" % name)
            if device is None:
                device = DiskDevice(name,
                                major=udev_device_get_major(info),
                                minor=udev_device_get_minor(info),
                                sysfsPath=sysfs_path, exists=True)
                self._addDevice(device)
        elif udev_device_is_disk(info):
            if device is None:
                device = self.addUdevDiskDevice(info)
        elif udev_device_is_partition(info):
            log.debug("%s is a partition" % name)
            if device is None:
                device = self.addUdevPartitionDevice(info)
        else:
            log.error("Unknown block device type for: %s" % name)
            return

        # If this device is protected, mark it as such now. Once the tree
        # has been populated, devices' protected attribute is how we will
        # identify protected devices.
        if device and device.name in self.protectedDevNames:
            device.protected = True

        # Don't try to do format handling on drives without media or
        # if we didn't end up with a device somehow.
        if not device or not device.mediaPresent:
            return

        # now handle the device's formatting
        self.handleUdevDeviceFormat(info, device)
        log.debug("got device: %s" % device)
        if device.format.type:
            log.debug("got format: %s" % device.format)
        device.originalFormat = device.format

    def handleUdevDiskLabelFormat(self, info, device):
        log_method_call(self, device=device.name)
        # if there is preexisting formatting on the device use it
        if getFormat(udev_device_get_format(info)).type is not None:
            log.debug("device %s does not contain a disklabel" % device.name)
            return

        if device.partitioned:
            # this device is already set up
            log.debug("disklabel format on %s already set up" % device.name)
            return

        try:
            device.setup()
        except Exception as e:
            log.debug("setup of %s failed: %s" % (device.name, e))
            log.warning("aborting disklabel handler for %s" % device.name)
            return

        # special handling for unsupported partitioned devices
        if not device.partitionable:
            try:
                format = getFormat("disklabel",
                                   device=device.path,
                                   exists=True)
            except InvalidDiskLabelError:
                pass
            else:
                if format.partitions:
                    # parted's checks for disklabel presence are less than
                    # rigorous, so we will assume that detected disklabels
                    # with no partitions are spurious
                    device.format = format
            return

        if self.zeroMbr:
            initcb = lambda: True
        else:
            description = device.description or device.model
            try:
                bypath = os.path.basename(deviceNameToDiskByPath(device.name))
                details = "\n\nDevice details:\n%s" % (bypath,)
            except DeviceNotFoundError:
                # some devices don't have a /dev/disk/by-path/ #!@#@!@#
                bypath = device.name
                details = ""

            initcb = lambda: self.intf.questionInitializeDisk(bypath,
                                                              description,
                                                              device.size,
                                                              details)

        labelType = self.platform.bestDiskLabelType(device)

        try:
            format = getFormat("disklabel",
                               device=device.path,
                               labelType=labelType,
                               exists=True)
        except InvalidDiskLabelError:
            # if we have a cb function use it. else we ignore the device.
            if initcb is not None and initcb():
                format = getFormat("disklabel",
                                   device=device.path,
                                   labelType=labelType,
                                   exists=False)
            else:
                self._removeDevice(device)
                self.addIgnoredDisk(device.name)
                return

        if not format.exists:
            # if we just initialized a disklabel we should schedule
            # actions for destruction of the previous format and creation
            # of the new one
            self.registerAction(ActionDestroyFormat(device))
            self.registerAction(ActionCreateFormat(device, format))

            # If this is a mac-formatted disk we just initialized, make
            # sure the partition table partition gets added to the device
            # tree.
            if device.format.partedDisk.type == "mac" and \
               len(device.format.partitions) == 1:
                name = device.format.partitions[0].getDeviceNodeName()
                if not self.getDeviceByName(name):
                    partDevice = PartitionDevice(name, exists=True,
                                                 parents=[device])
                    self._addDevice(partDevice)

        else:
            device.format = format

    def handleUdevLUKSFormat(self, info, device):
        log_method_call(self, name=device.name, type=device.format.type)
        if not device.format.uuid:
            log.info("luks device %s has no uuid" % device.path)
            return

        # look up or create the mapped device
        if not self.getDeviceByName(device.format.mapName):
            passphrase = self.__luksDevs.get(device.format.uuid)
            if passphrase:
                device.format.passphrase = passphrase
            else:
                (passphrase, isglobal) = getLUKSPassphrase(self.intf,
                                                    device,
                                                    self.__passphrase)
                if isglobal and device.format.status:
                    self.__passphrase = passphrase

            luks_device = LUKSDevice(device.format.mapName,
                                     parents=[device],
                                     exists=True)
            try:
                luks_device.setup()
            except (LUKSError, CryptoError, DeviceError) as e:
                log.info("setup of %s failed: %s" % (device.format.mapName,
                                                     e))
                device.removeChild()
            else:
                self._addDevice(luks_device)
        else:
            log.warning("luks device %s already in the tree"
                        % device.format.mapName)

    def handleVgLvs(self, vg_device):
        ret = False
        vg_name = vg_device.name

        if not vg_device.complete:
            log.warning("Skipping LVs for incomplete VG %s" % vg_name)
            return False

        lv_info = devicelibs.lvm.lvs(vg_name)
        try:
            lv_names = udev_device_get_lv_names(lv_info)
            lv_uuids = udev_device_get_lv_uuids(lv_info)
            lv_sizes = udev_device_get_lv_sizes(lv_info)
            lv_attr = udev_device_get_lv_attr(lv_info)
            lv_types = udev_device_get_lv_types(lv_info)
        except KeyError as e:
            log.warning("invalid data for VG %s: %s" % (vg_name, e))
            return

        if not lv_names:
            log.debug("no LVs listed for VG %s" % vg_name)
            return False

        def addRequiredLV(name, msg):
            """ Add a prerequisite/parent LV.

                The parent is strictly required in order to be able to add
                some other LV that depends on it. For this reason, failure to
                add the specified LV results in a DeviceTreeError with the
                message string specified in the msg parameter.

                :param str name: the full name of the LV (including vgname)
                :param str msg: message to pass DeviceTreeError ctor on error
                :returns: None
                :raises: :class:`~.errors.DeviceTreeError` on failure

            """
            vol = self.getDeviceByName(name)
            if vol is None:
                addLV(lv_info[name])
                vol = self.getDeviceByName(name)

                if vol is None:
                    log.error("%s: %s", msg, name)
                    raise DeviceTreeError(msg)

        def addLV(lv_name, lv_uuid, lv_size, lv_attr, lv_type):
            """ Instantiate and add an LV based on data from the VG. """
            lv_class = LVMLogicalVolumeDevice
            lv_parents = [vg_device]
            lv_kwargs = {}
            name = "%s-%s" % (vg_name, lv_name)

            if self.getDeviceByName(name):
                # some lvs may have been added on demand below
                log.debug("already added %s", name)
                return

            if lv_attr[0] in 'Ss':
                log.info("found lvm snapshot volume '%s'", name)
                origin_name = devicelibs.lvm.lvorigin(vg_name, lv_name)
                if not origin_name:
                    log.error("lvm snapshot '%s-%s' has unknown origin",
                                vg_name, lv_name)
                    return

                if origin_name.endswith("_vorigin]"):
                    log.info("snapshot volume '%s' has vorigin" % name)
                    lv_kwargs["vorigin"] = True
                    vg_device.voriginSnapshots[lv_name] = lv_size
                    return
                else:
                    origin_device_name = "%s-%s" % (vg_name, origin_name)
                    addRequiredLV(origin_device_name,
                                  "failed to locate origin lv")
                    origin = self.getDeviceByName(origin_device_name)

                if not origin:
                    log.warning("snapshot lv '%s' origin lv '%s-%s' "
                                "not found" % (name, vg_name, origin_name))
                    return

                if lv_name in origin.snapshots:
                    return

                log.debug("adding %dMB to %s snapshot total"
                            % (lv_size, origin.name))
                origin.snapshotSpace += lv_size
                origin.snapshots.append(lv_name)
                return
            elif lv_attr[0] == 'v':
                # skip vorigins
                return
            elif lv_attr[0] in 'Ii':
                # mirror image
                rname = re.sub(r'_[rm]image.+', '', lv_name[1:-1])
                name = "%s-%s" % (vg_name, rname)
                addRequiredLV(name, "failed to look up raid lv")
                raid[name]["copies"] += 1
                return
            elif lv_attr[0] == 'e':
                if lv_name.endswith("_pmspare]"):
                    # spare metadata area for any thin pool that needs repair
                    return

                # raid metadata volume
                lv_name = re.sub(r'_[tr]meta.*', '', lv_name[1:-1])
                name = "%s-%s" % (vg_name, lv_name)
                addRequiredLV(name, "failed to look up raid lv")
                raid[name]["meta"] += lv_size
                return
            elif lv_attr[0] == 'l':
                # log volume
                rname = re.sub(r'_mlog.*', '', lv_name[1:-1])
                name = "%s-%s" % (vg_name, rname)
                addRequiredLV(name, "failed to look up log lv")
                raid[name]["log"] = lv_size
                return
            elif lv_attr[0] == 't':
                # thin pool
                lv_class = LVMThinPoolDevice
            elif lv_attr[0] == 'V':
                # thin volume
                pool_name = devicelibs.lvm.thinlvpoolname(vg_name, lv_name)
                pool_device_name = "%s-%s" % (vg_name, pool_name)
                addRequiredLV(pool_device_name, "failed to look up thin pool")

                lv_class = LVMThinLogicalVolumeDevice
                lv_parents = [self.getDeviceByName(pool_device_name)]
            elif lv_name.endswith(']'):
                # Internal LVM2 device
                return
            elif lv_attr[0] not in '-mMrRoO':
                # Ignore anything else except for the following:
                #   - normal lv
                #   m mirrored
                #   M mirrored without initial sync
                #   r raid
                #   R raid without initial sync
                #   o origin
                #   O origin with merging snapshot
                return

            added = False
            lv_dev = self.getDeviceByUuid(lv_uuid)
            if lv_dev is None:
                lv_device = lv_class(lv_name, lv_parents,
                                     uuid=lv_uuid, size=lv_size,segType=lv_type,
                                     exists=True, **lv_kwargs)
                self._addDevice(lv_device)
                try:
                    lv_device.setup()
                    added = True
                except DeviceError as (msg, name):
                    log.info("setup of %s failed: %s"
                                        % (lv_device.name, msg))

                if lv_device.status:
                    lv_device.updateSysfsPath()
                    lv_info = udev_get_block_device(lv_device.sysfsPath)
                    if not lv_info:
                        log.error("failed to get udev data for lv %s", lv_device.name)
                        return

                    # do format handling now
                    self.addUdevDevice(lv_info)

            return added

        raid = dict(("%s-%s" % (vg_name, n.replace("[", "").replace("]", "")),
                     {"copies": 0, "log": 0, "meta": 0})
                     for n in lv_names)
        for lv in zip(lv_names, lv_uuids, lv_sizes, lv_attr, lv_types):
            ret = addLV(*lv) or ret

        for name, data in raid.items():
            lv_dev = self.getDeviceByName(name)
            if not lv_dev:
                # hidden lv, eg: pool00_tdata
                continue

            lv_dev.copies = data["copies"] or 1
            lv_dev.metaDataSize = data["meta"]
            lv_dev.logSize = data["log"]
            log.debug("set %s copies to %d, metadata size to %s, log size "
                      "to %s, total size %s",
                        lv_dev.name, lv_dev.copies, lv_dev.metaDataSize,
                        lv_dev.logSize, lv_dev.vgSpaceUsed)

        return ret

    def handleUdevLVMPVFormat(self, info, device):
        log_method_call(self, name=device.name, type=device.format.type)
        # lookup/create the VG and LVs
        try:
            vg_name = udev_device_get_vg_name(info)
        except KeyError:
            # no vg name means no vg -- we're done with this pv
            return

        vg_device = self.getDeviceByName(vg_name)
        if vg_device:
            vg_device._addDevice(device)
        else:
            try:
                vg_uuid = udev_device_get_vg_uuid(info)
                vg_size = udev_device_get_vg_size(info)
                vg_free = udev_device_get_vg_free(info)
                pe_size = udev_device_get_vg_extent_size(info)
                pe_count = udev_device_get_vg_extent_count(info)
                pe_free = udev_device_get_vg_free_extents(info)
                pv_count = udev_device_get_vg_pv_count(info)
            except (KeyError, ValueError) as e:
                log.warning("invalid data for %s: %s" % (device.name, e))
                return

            vg_device = LVMVolumeGroupDevice(vg_name,
                                             device,
                                             uuid=vg_uuid,
                                             size=vg_size,
                                             free=vg_free,
                                             peSize=pe_size,
                                             peCount=pe_count,
                                             peFree=pe_free,
                                             pvCount=pv_count,
                                             exists=True)
            self._addDevice(vg_device)

    def handleUdevMDMemberFormat(self, info, device):
        log_method_call(self, name=device.name, type=device.format.type)
        # either look up or create the array device
        name = udev_device_get_name(info)
        sysfs_path = udev_device_get_sysfs_path(info)

        md_array = self.getDeviceByUuid(device.format.mdUuid)
        if device.format.mdUuid and md_array:
            md_array._addDevice(device)
        else:
            # create the array with just this one member
            try:
                # level is reported as, eg: "raid1"
                md_level = udev_device_get_md_level(info)
                md_devices = int(udev_device_get_md_devices(info))
                md_uuid = udev_device_get_md_uuid(info)
            except (KeyError, ValueError) as e:
                log.warning("invalid data for %s: %s" % (name, e))
                return

            # try to name the array based on the preferred minor
            md_info = devicelibs.mdraid.mdexamine(device.path)
            md_path = md_info.get("device", "")
            md_metadata = md_info.get("metadata")
            md_name = devicePathToName(md_info.get("device", ""))
            if md_name:
                try:
                    # md_name can be either md# or md/#
                    if md_name.startswith("md/"):
                        minor = int(md_name[3:])     # strip off leading "md/"
                        md_name = "md%d" % minor     # use a regular md# name
                    else:
                        minor = int(md_name[2:])     # strip off leading "md"
                except (IndexError, ValueError):
                    minor = None
                    md_name = None
                else:
                    array = self.getDeviceByName(md_name)
                    if array and array.uuid != md_uuid:
                        md_name = None

            if not md_name:
                # if we don't have a name yet, find the first unused minor
                minor = 0
                while True:
                    if self.getDeviceByName("md%d" % minor):
                        minor += 1
                    else:
                        break

                md_name = "md%d" % minor

            log.debug("using name %s for md array containing member %s"
                        % (md_name, device.name))
            md_array = MDRaidArrayDevice(md_name,
                                         level=md_level,
                                         minor=minor,
                                         memberDevices=md_devices,
                                         uuid=md_uuid,
                                         metadataVersion=md_metadata,
                                         sysfsPath=sysfs_path,
                                         exists=True)
            md_array._addDevice(device)
            self._addDevice(md_array)

    def handleMultipathMemberFormat(self, info, device):
        log_method_call(self, name=device.name, type=device.format.type)

        name = udev_device_get_multipath_name(info)
        if self.__multipaths.has_key(name):
            mp = self.__multipaths[name]
            mp.addParent(device)
        else:
            mp = MultipathDevice(name, info, parents=[device])
            self.__multipaths[name] = mp

    def handleUdevDMRaidMemberFormat(self, info, device):
        log_method_call(self, name=device.name, type=device.format.type)
        name = udev_device_get_name(info)
        sysfs_path = udev_device_get_sysfs_path(info)
        uuid = udev_device_get_uuid(info)
        major = udev_device_get_major(info)
        minor = udev_device_get_minor(info)

        def _all_ignored(rss):
            retval = True
            for rs in rss:
                if rs.name not in self._ignoredDisks:
                    retval = False
                    break
            return retval

        # Have we already created the DMRaidArrayDevice?
        rss = block.getRaidSetFromRelatedMem(uuid=uuid, name=name,
                                            major=major, minor=minor)
        if len(rss) == 0:
            # we ignore the device in the hope that all the devices
            # from this set will be ignored.
            self.unusedRaidMembers.append(device.name)
            self.addIgnoredDisk(device.name)
            return

        # We ignore the device if all the rss are in self._ignoredDisks
        if _all_ignored(rss):
            self.addIgnoredDisk(device.name)
            return

        for rs in rss:
            dm_array = self.getDeviceByName(rs.name)
            if dm_array is not None:
                # We add the new device.
                dm_array._addDevice(device)
            else:
                # Activate the Raid set.
                rs.activate(mknod=True)
                dm_array = DMRaidArrayDevice(rs.name,
                                             raidSet=rs,
                                             parents=[device])

                self._addDevice(dm_array)

                # Wait for udev to scan the just created nodes, to avoid a race
                # with the udev_get_block_device() call below.
                udev_settle()

                # Get the DMRaidArrayDevice a DiskLabel format *now*, in case
                # its partitions get scanned before it does.
                dm_array.updateSysfsPath()
                dm_array_info = udev_get_block_device(dm_array.sysfsPath)
                self.handleUdevDiskLabelFormat(dm_array_info, dm_array)

                # Use the rs's object on the device.
                # pyblock can return the memebers of a set and the
                # device has the attribute to hold it.  But ATM we
                # are not really using it. Commenting this out until
                # we really need it.
                #device.format.raidmem = block.getMemFromRaidSet(dm_array,
                #        major=major, minor=minor, uuid=uuid, name=name)

    def handleUdevDeviceFormat(self, info, device):
        log_method_call(self, name=getattr(device, "name", None))
        name = udev_device_get_name(info)
        sysfs_path = udev_device_get_sysfs_path(info)
        uuid = udev_device_get_uuid(info)
        label = udev_device_get_label(info)
        format_type = udev_device_get_format(info)
        serial = udev_device_get_serial(info)

        # Now, if the device is a disk, see if there is a usable disklabel.
        # If not, see if the user would like to create one.
        # XXX ignore disklabels on multipath or biosraid member disks
        if not udev_device_is_biosraid(info) and \
           not udev_device_is_multipath_member(info):
            self.handleUdevDiskLabelFormat(info, device)
            if device.partitioned or self.isIgnored(info) or \
               (not device.partitionable and
                device.format.type == "disklabel"):
                # If the device has a disklabel, or the user chose not to
                # create one, we are finished with this device. Otherwise
                # it must have some non-disklabel formatting, in which case
                # we fall through to handle that.
                return

        format = None
        if (not device) or (not format_type) or device.format.type:
            # this device has no formatting or it has already been set up
            # FIXME: this probably needs something special for disklabels
            log.debug("no type or existing type for %s, bailing" % (name,))
            return

        # set up the common arguments for the format constructor
        args = [format_type]
        kwargs = {"uuid": uuid,
                  "label": label,
                  "device": device.path,
                  "serial": serial,
                  "exists": True}

        # set up type-specific arguments for the format constructor
        if format_type == "multipath_member":
            kwargs["multipath_members"] = self.getDevicesBySerial(serial)
        elif format_type == "crypto_LUKS":
            # luks/dmcrypt
            kwargs["name"] = "luks-%s" % uuid
        elif format_type in formats.mdraid.MDRaidMember._udevTypes:
            # mdraid
            try:
                kwargs["mdUuid"] = udev_device_get_md_uuid(info)
            except KeyError:
                log.debug("mdraid member %s has no md uuid" % name)
            kwargs["biosraid"] = udev_device_is_biosraid(info)
        elif format_type == "LVM2_member":
            # lvm
            try:
                kwargs["vgName"] = udev_device_get_vg_name(info)
            except KeyError as e:
                log.debug("PV %s has no vg_name" % name)
            try:
                kwargs["vgUuid"] = udev_device_get_vg_uuid(info)
            except KeyError:
                log.debug("PV %s has no vg_uuid" % name)
            try:
                kwargs["peStart"] = udev_device_get_pv_pe_start(info)
            except KeyError:
                log.debug("PV %s has no pe_start" % name)
        elif format_type == "vfat":
            # efi magic
            if isinstance(device, PartitionDevice) and device.bootable:
                efi = formats.getFormat("efi")
                if efi.minSize <= device.size <= efi.maxSize:
                    args[0] = "efi"
        elif format_type == "hfs":
            # apple bootstrap magic
            if isinstance(device, PartitionDevice) and device.bootable:
                apple = formats.getFormat("appleboot")
                if apple.minSize <= device.size <= apple.maxSize:
                    args[0] = "appleboot"

        try:
            log.debug("type detected on '%s' is '%s'" % (name, format_type,))
            device.format = formats.getFormat(*args, **kwargs)
        except FSError:
            log.debug("type '%s' on '%s' invalid, assuming no format" %
                      (format_type, name,))
            device.format = formats.DeviceFormat()
            return

        if shouldClear(device, self.clearPartType,
                       clearPartDisks=self.clearPartDisks):
            # if this is a device that will be cleared by clearpart,
            # don't bother with format-specific processing
            return

        #
        # now do any special handling required for the device's format
        #
        if device.format.type == "luks":
            self.handleUdevLUKSFormat(info, device)
        elif device.format.type == "mdmember":
            self.handleUdevMDMemberFormat(info, device)
        elif device.format.type == "dmraidmember":
            self.handleUdevDMRaidMemberFormat(info, device)
        elif device.format.type == "lvmpv":
            self.handleUdevLVMPVFormat(info, device)
        elif device.format.type == "multipath_member":
            self.handleMultipathMemberFormat(info, device)

    def updateDeviceFormat(self, device):
        log.debug("updating format of device: %s" % device)
        iutil.notify_kernel("/sys%s" % device.sysfsPath)
        udev_settle()
        info = udev_get_device(device.sysfsPath)
        self.handleUdevDeviceFormat(info, device)
        if device.format.type:
            log.debug("got format: %s" % device.format)

    def _handleInconsistencies(self):
        def reinitializeVG(vg):
            # First we remove VG data
            try:
                vg.destroy()
            except DeviceError:
                # the pvremoves will finish the job.
                log.debug("There was an error destroying the VG %s." % vg.name)

            # remove VG device from list.
            self._removeDevice(vg)

            for parent in vg.parents:
                parent.format.destroy()

                # Give the vg the a default format
                kwargs = {"device": parent.path,
                          "exists": parent.exists}
                parent.format = formats.getFormat(*[""], **kwargs)

        def leafInconsistencies(device):
            if device.type == "lvmvg":
                if device.complete:
                    return

                paths = []
                for parent in device.parents:
                    paths.append(parent.path)

                # if zeroMbr is true don't ask.
                if (self.zeroMbr or
                    self.intf.questionReinitInconsistentLVM(pv_names=paths,
                                                            vg_name=device.name)):
                    reinitializeVG(device)
                else:
                    # The user chose not to reinitialize.
                    # hopefully this will ignore the vg components too.
                    self._removeDevice(device)
                    lvm.lvm_cc_addFilterRejectRegexp(device.name)
                    lvm.blacklistVG(device.name)
                    for parent in device.parents:
                        if parent.type == "partition":
                            parent.immutable = \
                                _("This partition is part of an inconsistent LVM Volume Group.")
                        else:
                            self._removeDevice(parent, moddisk=False)
                            self.addIgnoredDisk(parent.name)
                        lvm.lvm_cc_addFilterRejectRegexp(parent.name)

            elif device.type == "lvmlv":
                # we might have already fixed this.
                if device not in self._devices or \
                        device.name in self._ignoredDisks:
                    return
                if device.complete:
                    return

                paths = []
                for parent in device.vg.parents:
                    paths.append(parent.path)

                if (self.zeroMbr or
                    self.intf.questionReinitInconsistentLVM(pv_names=paths,
                                                            lv_name=device.name)):

                    # destroy all lvs.
                    for lv in device.vg.lvs:
                        try:
                            # reinitializeVG should clean up if necessary
                            lv.destroy()
                        except StorageError as e:
                            log.info("error removing lv %s from "
                                     "inconsistent/incomplete vg %s"
                                     % (lv.lvname, device.vg.name))
                        device.vg._removeLogVol(lv)
                        self._removeDevice(lv)

                    reinitializeVG(device.vg)
                else:
                    # ignore all the lvs.
                    for lv in device.vg.lvs:
                        self._removeDevice(lv)
                        lvm.lvm_cc_addFilterRejectRegexp(lv.name)
                    # ignore the vg
                    self._removeDevice(device.vg)
                    lvm.lvm_cc_addFilterRejectRegexp(device.vg.name)
                    lvm.blacklistVG(device.vg.name)
                    # ignore all the pvs
                    for parent in device.vg.parents:
                        if parent.type == "partition":
                            parent.immutable = \
                                _("This partition is part of an inconsistent LVM Volume Group.")
                        else:
                            self._removeDevice(parent, moddisk=False)
                            self.addIgnoredDisk(parent.name)
                        lvm.lvm_cc_addFilterRejectRegexp(parent.name)

        # Address the inconsistencies present in the tree leaves.
        for leaf in self.leaves:
            leafInconsistencies(leaf)

        # Check for unused BIOS raid members, unused dmraid members are added
        # to self.unusedRaidMembers as they are processed, extend this list
        # with unused mdraid BIOS raid members
        for c in self.getDevicesByType("mdcontainer"):
            if c.kids == 0:
                self.unusedRaidMembers.extend(map(lambda m: m.name, c.devices))

        self.intf.unusedRaidMembersWarning(self.unusedRaidMembers)

        # remove md array devices for which we did not find all members
        for array in self.getDevicesByType("mdarray"):
            if array.memberDevices > len(array.parents):
                self._recursiveRemove(array)

    def _recursiveRemove(self, device):
        for d in self.getChildren(device):
            self._recursiveRemove(d)

        device.teardown()
        self._removeDevice(device)

    def _setupLvs(self):
        ret = False

        for device in self.getDevicesByType("lvmvg"):
            if self.handleVgLvs(device):
                ret = True

        return ret

    def populate(self, progressWindow=None):
        """ Locate all storage devices. """
        log.debug("DeviceTree.populate: ignoredDisks is %s ; exclusiveDisks is %s"
                    % (self._ignoredDisks, self.exclusiveDisks))

        # mark the tree as unpopulated so exception handlers can tell the
        # exception originated while finding storage devices
        self.populated = False

        # resolve the protected device specs to device names
        for spec in self.protectedDevSpecs:
            name = udev_resolve_devspec(spec)
            if name:
                self.protectedDevNames.append(name)

        # FIXME: the backing dev for the live image can't be used as an
        # install target.  note that this is a little bit of a hack
        # since we're assuming that /dev/live will exist
        if os.path.exists("/dev/live") and \
           stat.S_ISBLK(os.stat("/dev/live")[stat.ST_MODE]):
            livetarget = devicePathToName(os.path.realpath("/dev/live"))
            log.info("%s looks to be the live device; marking as protected"
                     % (livetarget,))
            self.protectedDevNames.append(livetarget)

        devicelibs.mpath.writeMultipathConf(writer=self.__multipathConfigWriter,
                                            friendly_names=self.mpathFriendlyNames)

        devices = udev_get_block_devices()
        if os.access("/etc/multipath.conf", os.R_OK):
            (singles, mpaths, partitions) = devicelibs.mpath.identifyMultipaths(devices)
            devices = singles + reduce(list.__add__, mpaths, []) + partitions

        # remember all the devices idenitfyMultipaths() gave us at this point
        old_devices = {}
        for dev in devices:
            old_devices[dev['name']] = dev

        log.info("devices to scan: %s" % [d['name'] for d in devices])
        for dev in devices:
            self.addUdevDevice(dev)
            if progressWindow:
                progressWindow.pulse()

        # Having found all the disks, we can now find all the multipaths built
        # upon them.
        whitelist = []
        mpaths = self.__multipaths.values()
        mpaths.sort(key=lambda d: d.name)
        for mp in mpaths:
            log.info("adding mpath device %s" % mp.name)
            mp.setup()
            mp.updateSysfsPath()
            mp_info = udev_get_block_device(mp.sysfsPath)
            if mp_info is None or self.isIgnored(mp_info):
                mp.teardown()
                continue

            whitelist.append(mp.name)
            for p in mp.parents:
                whitelist.append(p.name)
            self.__multipathConfigWriter.addMultipathDevice(mp)
            self._addDevice(mp)
            self.addUdevDevice(mp_info)
            if progressWindow:
                progressWindow.pulse()
        for d in self.devices:
            if not d.name in whitelist:
                self.__multipathConfigWriter.addBlacklistDevice(d)

        devicelibs.mpath.writeMultipathConf(writer=self.__multipathConfigWriter,
                                            friendly_names=self.mpathFriendlyNames)

        # Now, loop and scan for devices that have appeared since the two above
        # blocks or since previous iterations.
        while True:
            devices = []
            new_devices = udev_get_block_devices()

            for new_device in new_devices:
                if not old_devices.has_key(new_device['name']):
                    old_devices[new_device['name']] = new_device
                    devices.append(new_device)

            if len(devices) == 0:
                # nothing is changing -- time to setup lvm lvs and scan them
                # we delay this till all other devices are scanned so that
                # 1) the lvm filter for ignored disks is completely setup
                # 2) we have checked all devs for duplicate vg names
                if self._setupLvs():
                    continue
                # nothing is changing -- we are finished building devices
                break

            log.info("devices to scan: %s" % [d['name'] for d in devices])
            for dev in devices:
                self.addUdevDevice(dev)
                if progressWindow:
                    progressWindow.pulse()

        self.populated = True

        # After having the complete tree we make sure that the system
        # inconsistencies are ignored or resolved.
        self._handleInconsistencies()

        self.teardownAll()
        try:
            os.unlink("/etc/mdadm.conf")
        except OSError:
            log.info("failed to unlink /etc/mdadm.conf")

    def teardownAll(self):
        """ Run teardown methods on all devices. """
        for device in self.leaves:
            try:
                device.teardown(recursive=True)
            except StorageError as e:
                log.info("teardown of %s failed: %s" % (device.name, e))

    def setupAll(self):
        """ Run setup methods on all devices. """
        for device in self.leaves:
            try:
                device.setup()
            except DeviceError as (msg, name):
                log.debug("setup of %s failed: %s" % (device.name, msg))

    def getDeviceBySysfsPath(self, path):
        if not path:
            return None

        found = None
        for device in self._devices:
            if device.sysfsPath == path:
                found = device
                break

        return found

    def getDeviceByUuid(self, uuid):
        if not uuid:
            return None

        found = None
        for device in self._devices:
            if device.uuid == uuid:
                found = device
                break
            elif device.format.uuid == uuid:
                found = device
                break

        return found

    def getDevicesBySerial(self, serial):
        devices = []
        for device in self._devices:
            if not hasattr(device, "serial"):
                log.warning("device %s has no serial attr" % device.name)
                continue
            if device.serial == serial:
                devices.append(device)
        return devices

    def getDeviceByLabel(self, label):
        if not label:
            return None

        found = None
        for device in self._devices:
            _label = getattr(device.format, "label", None)
            if not _label:
                continue

            if _label == label:
                found = device
                break

        return found

    def getDeviceByName(self, name):
        log.debug("looking for device '%s'..." % name)
        if not name:
            return None

        found = None
        for device in self._devices:
            if device.name == name:
                found = device
                break
            elif (device.type == "lvmlv" or device.type == "lvmvg") and \
                    device.name == name.replace("--","-"):
                found = device
                break

        log.debug("found %s" % found)
        return found

    def getDeviceByPath(self, path):
        log.debug("looking for device '%s'..." % path)
        if not path:
            return None

        found = None
        for device in self._devices:
            if device.path == path:
                found = device
                break
            elif (device.type == "lvmlv" or device.type == "lvmvg") and \
                    device.path == path.replace("--","-"):
                found = device
                break

        log.debug("found %s" % found)
        return found

    def getDevicesByType(self, device_type):
        # TODO: expand this to catch device format types
        return [d for d in self._devices if d.type == device_type]

    def getDevicesByInstance(self, device_class):
        return [d for d in self._devices if isinstance(d, device_class)]

    @property
    def devices(self):
        """ List of device instances """
        devices = []
        for device in self._devices:
            if device.path in [d.path for d in devices] and \
               not isinstance(device, NoDevice):
                raise DeviceTreeError("duplicate paths in device tree")

            devices.append(device)

        return devices

    @property
    def filesystems(self):
        """ List of filesystems. """
        #""" Dict with mountpoint keys and filesystem values. """
        filesystems = []
        for dev in self.leaves:
            if dev.format and getattr(dev.format, 'mountpoint', None):
                filesystems.append(dev.format)

        return filesystems

    @property
    def uuids(self):
        """ Dict with uuid keys and Device values. """
        uuids = {}
        for dev in self._devices:
            try:
                uuid = dev.uuid
            except AttributeError:
                uuid = None

            if uuid:
                uuids[uuid] = dev

            try:
                uuid = dev.format.uuid
            except AttributeError:
                uuid = None

            if uuid:
                uuids[uuid] = dev

        return uuids

    @property
    def labels(self):
        """ Dict with label keys and Device values.

            FIXME: duplicate labels are a possibility
        """
        labels = {}
        for dev in self._devices:
            if dev.format and getattr(dev.format, "label", None):
                labels[dev.format.label] = dev

        return labels

    @property
    def leaves(self):
        """ List of all devices upon which no other devices exist. """
        leaves = [d for d in self._devices if d.isleaf]
        return leaves

    def getChildren(self, device):
        """ Return a list of a device's children. """
        return [c for c in self._devices if device in c.parents]

    def resolveDevice(self, devspec, blkidTab=None, cryptTab=None):
        # find device in the tree
        device = None
        if devspec.startswith("UUID="):
            # device-by-uuid
            uuid = devspec.partition("=")[2]
            device = self.uuids.get(uuid)
            if device is None:
                log.error("failed to resolve device %s" % devspec)
        elif devspec.startswith("LABEL="):
            # device-by-label
            label = devspec.partition("=")[2]
            device = self.labels.get(label)
            if device is None:
                log.error("failed to resolve device %s" % devspec)
        elif devspec.startswith("/dev/"):
            if devspec.startswith("/dev/disk/"):
                devspec = os.path.realpath(devspec)

                if devspec.startswith("/dev/dm-"):
                    dm_name = devicelibs.dm.name_from_dm_node(devspec[5:])
                    if dm_name:
                        devspec = "/dev/mapper/" + dm_name

            # device path
            device = self.getDeviceByPath(devspec)
            if device is None:
                if blkidTab:
                    # try to use the blkid.tab to correlate the device
                    # path with a UUID
                    blkidTabEnt = blkidTab.get(devspec)
                    if blkidTabEnt:
                        log.debug("found blkid.tab entry for '%s'" % devspec)
                        uuid = blkidTabEnt.get("UUID")
                        if uuid:
                            device = self.getDeviceByUuid(uuid)
                            if device:
                                devstr = device.name
                            else:
                                devstr = "None"
                            log.debug("found device '%s' in tree" % devstr)
                        if device and device.format and \
                           device.format.type == "luks":
                            map_name = device.format.mapName
                            log.debug("luks device; map name is '%s'" % map_name)
                            mapped_dev = self.getDeviceByName(map_name)
                            if mapped_dev:
                                device = mapped_dev

                if device is None and cryptTab and \
                   devspec.startswith("/dev/mapper/"):
                    # try to use a dm-crypt mapping name to 
                    # obtain the underlying device, possibly
                    # using blkid.tab
                    cryptTabEnt = cryptTab.get(devspec.split("/")[-1])
                    if cryptTabEnt:
                        luks_dev = cryptTabEnt['device']
                        try:
                            device = self.getChildren(luks_dev)[0]
                        except IndexError as e:
                            pass
                elif device is None:
                    # dear lvm: can we please have a few more device nodes
                    #           for each logical volume?
                    #           three just doesn't seem like enough.
                    name = devspec[5:]      # strip off leading "/dev/"
                    (vg_name, slash, lv_name) = name.partition("/")
                    if lv_name and not "/" in lv_name:
                        # looks like we may have one
                        lv = "%s-%s" % (vg_name, lv_name)
                        device = self.getDeviceByName(lv)

        if device:
            log.debug("resolved '%s' to '%s' (%s)" % (devspec, device.name, device.type))
        else:
            log.debug("failed to resolve '%s'" % devspec)
        return device
