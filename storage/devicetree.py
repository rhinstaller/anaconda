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
import block
import re

from errors import *
from devices import *
from deviceaction import *
import formats
from udev import *

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

# Don't really know where to put this.
def questionInitializeDisk(intf=None, name=None):
    retVal = False # The less destructive default
    if not intf or not name:
        pass
    else:
        rc = intf.messageWindow(_("Warning"),
                _("Error processing drive %s.\n"
                  "Maybe it needs to be reinitialized."
                  "YOU WILL LOSE ALL DATA ON THIS DRIVE!") % (name,),
                type="custom",
                custom_buttons = [ _("_Ignore drive"),
                                   _("_Re-initialize drive") ],
                custom_icon="question")
        if rc == 0:
            pass
        else:
            retVal = True
    return retVal

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

    def __init__(self, intf=None, ignored=[], exclusive=[], clear=[],
                 zeroMbr=None, reinitializeDisks=None, protected=[],
                 passphrase=None, luksDict=None):
        # internal data members
        self._devices = []
        self._actions = []

        self.intf = intf
        self.exclusiveDisks = exclusive
        self.clearPartDisks = clear
        self.zeroMbr = zeroMbr
        self.reinitializeDisks = reinitializeDisks
        self.protectedPartitions = protected
        self.__passphrase = passphrase
        self.__luksDevs = {}
        if luksDict and isinstance(luksDict, dict):
            self.__luksDevs = luksDict
        self._ignoredDisks = []
        for disk in ignored:
            self.addIgnoredDisk(disk)

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
            destroys = self.findActions(path=a.device.path,
                                        type="destroy",
                                        object="device")

            creates = self.findActions(path=a.device.path,
                                       type="create",
                                       object="device")

            # If the device is not preexisting, we remove all actions up
            # to and including the last destroy action.
            # If the device is preexisting, we remove all actions from
            # after the first destroy action up to and including the last
            # destroy action.
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

            if start is None:
                continue

            # now we remove all actions on this device between the start
            # index (into self._actions) and stop_action.
            dev_actions = self.findActions(path=a.device.path)
            for rem in dev_actions:
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
            creates = self.findActions(path=a.device.path,
                                       type="create",
                                       object="device")

            destroys = self.findActions(path=a.device.path,
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
            dev_actions = self.findActions(path=a.device.path)
            for rem in dev_actions:
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
            loops = self.findActions(path=a.device.path,
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
            destroys = self.findActions(path=a.device.path,
                                        type="destroy",
                                        object="format")

            creates = self.findActions(path=a.device.path,
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
            dev_actions = self.findActions(path=a.device.path,
                                           object="format")
            for rem in dev_actions:
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
            creates = self.findActions(path=a.device.path,
                                       type="create",
                                       object="format")

            destroys = self.findActions(path=a.device.path,
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
            dev_actions = self.findActions(path=a.device.path,
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
            loops = self.findActions(path=a.device.path,
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
            loops = self.findActions(path=a.device.path,
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
                    ret = cmp(a2.device.name, a1.device.name)
                elif isinstance(a1.device, PartitionDevice) and \
                     not isinstance(a2.device, DiskDevice):
                    ret = 1
                elif isinstance(a2.device, PartitionDevice) and \
                     not isinstance(a1.device, DiskDevice):
                    ret = -1
                else:
                    ret = cmp(a2.device.name, a1.device.name)
            elif a1.isDestroy():
                ret = -1
            elif a2.isDestroy():
                ret = 1
            elif a1.isResize() and a2.isResize():
                if a1.device.path == a2.device.path:
                    if a1.obj and a2.obj:
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
                elif isinstance(a1.device, PartitionDevice) and \
                     not isinstance(a2.device, DiskDevice):
                    if a1.isGrow():
                        ret = -1
                    else:
                        ret = 1
                elif isinstance(a2.device, PartitionDevice) and \
                     not isinstance(a1.device, DiskDevice):
                    if a2.isGrow():
                        ret = 1
                    else:
                        ret = -1
                else:
                    ret = cmp(a1.device.name, a2.device.name)
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
                        ret = cmp(a1.device.name, a2.device.name)
                elif a1.device.dependsOn(a2.device):
                    ret = 1
                elif a2.device.dependsOn(a1.device):
                    ret = -1
                # generally create partitions before other device types
                elif isinstance(a1.device, PartitionDevice) and \
                     isinstance(a2.device, PartitionDevice):
                    ret = cmp(a1.device.name, a2.device.name)
                elif isinstance(a1.device, PartitionDevice) and \
                     not isinstance(a2.device, DiskDevice):
                    ret = -1
                elif isinstance(a2.device, PartitionDevice) and \
                     not isinstance(a1.device, DiskDevice):
                    ret = 1
                else:
                    ret = cmp(a1.device.name, a2.device.name)
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
                    ret = cmp(a1.device.name, a2.device.name)
                else:
                    ret = cmp(a1.device.name, a2.device.name)
            else:
                ret = cmp(a1.device.name, a2.device.name)

            log.debug("cmp: %d -- %s | %s" % (ret, a1, a2))
            return ret

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

        log.debug("resetting parted disks...")
        for device in self.devices.itervalues():
            if isinstance(device, DiskDevice):
                device.resetPartedDisk()

        for action in self._actions:
            log.info("executing action: %s" % action)
            if not dryRun:
                action.execute(intf=self.intf)
                udev_settle(timeout=10)

    def _addDevice(self, newdev):
        """ Add a device to the tree.

            Raise ValueError if the device's identifier is already
            in the list.
        """
        if newdev.path in [d.path for d in self._devices]:
            raise ValueError("device is already in tree")

        # make sure this device's parent devices are in the tree already
        for parent in newdev.parents:
            if parent not in self._devices:
                raise DeviceTreeError("parent device not in tree")

        self._devices.append(newdev)
        log.debug("added %s (%s) to device tree" % (newdev.name,
                                                    newdev.type))

    def _removeDevice(self, dev, force=None):
        """ Remove a device from the tree.

            Only leaves may be removed.
        """
        if dev not in self._devices:
            raise ValueError("Device '%s' not in tree" % dev.name)

        if not dev.isleaf and not force:
            log.debug("%s has %d kids" % (dev.name, dev.kids))
            raise ValueError("Cannot remove non-leaf device '%s'" % dev.name)

        # if this is a partition we need to remove it from the parted.Disk
        if isinstance(dev, PartitionDevice) and dev.disk is not None:
            # if this partition hasn't been allocated it could not have
            # a disk attribute
            dev.disk.partedDisk.removePartition(dev.partedPartition)

        self._devices.remove(dev)
        log.debug("removed %s (%s) from device tree" % (dev.name,
                                                        dev.type))

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
        elif (action.isCreate() and action.isDevice()) and \
             (action.device in self._devices or \
              action.device.path in [d.path for d in self._devices]):
            # this allows multiple create actions w/o destroy in between;
            # we will clean it up before processing actions
            #raise DeviceTreeError("device is already in the tree")
            self._removeDevice(action.device)

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

    def findActions(self, device=None, type=None, object=None, path=None):
        """ Find all actions that match all specified parameters.

            Keyword arguments:

                device -- device to match (Device, or None to match any)
                type -- action type to match (string, or None to match any)
                object -- operand type to match (string, or None to match any)
                path -- device path to match (string, or None to match any)

        """
        if device is None and type is None and object is None and path is None:
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

        for device in self.devices.values():
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
            return True

        for ignored in self._ignoredDisks:
            if ignored == os.path.basename(os.path.dirname(sysfs_path)):
                # this is a partition on a disk in the ignore list
                return True

        # Ignore partitions found on the raw disks which are part of a
        # dmraidset
        for set in self.getDevicesByType("dm-raid array"):
            for disk in set.parents:
                if disk.name == os.path.basename(os.path.dirname(sysfs_path)):
                    return True

        # Ignore loop and ram devices, we normally already skip these in
        # udev.py: enumerate_block_devices(), but we can still end up trying
        # to add them to the tree when they are slaves of other devices, this
        # happens for example with the livecd
        if name.startswith("loop") or name.startswith("ram"):
            return True

        # FIXME: check for virtual devices whose slaves are on the ignore list

    def addUdevDevice(self, info):
        # FIXME: this should be broken up into more discrete chunks
        name = udev_device_get_name(info)
        uuid = udev_device_get_uuid(info)
        sysfs_path = udev_device_get_sysfs_path(info)
        device = None

        if self.isIgnored(info):
            log.debug("ignoring %s (%s)" % (name, sysfs_path))
            return

        log.debug("scanning %s (%s)..." % (name, sysfs_path))

        #
        # The first step is to either look up or create the device
        #
        if udev_device_is_dm(info):
            log.debug("%s is a device-mapper device" % name)
            # try to look up the device
            device = self.getDeviceByName(name)
            if device is None and uuid:
                # try to find the device by uuid
                device = self.getDeviceByUuid(uuid)

            if device is None:
                for dmdev in self.devices:
                    if not isinstance(dmdev, DMDevice):
                        continue

                    # there is a device in the tree already with the same
                    # major/minor as this one but with a different name
                    # XXX this is kind of racy
                    if dmdev.getDMNode() == os.path.basename(sysfs_path):
                        # XXX should we take the name already in use?
                        device = dmdev
                        break

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
                        new_info = udev_get_block_device(os.path.realpath(path))
                        if new_info:
                            self.addUdevDevice(new_info)
                            if self.getDeviceByName(dev_name) is None:
                                # if the current slave is still not in
                                # the tree, something has gone wrong
                                log.error("failure scanning device %s: could not add slave %s" % (name, dev_name))
                                return

                # try to get the device again now that we've got all the slaves
                device = self.getDeviceByName(name)

                if device is None and \
                        udev_device_is_dmraid_partition(info, self):
                    diskname = udev_device_get_dmraid_partition_disk(info)
                    disk = self.getDeviceByName(diskname)
                    device = PartitionDeviceFactory(name, \
                                           sysfsPath=sysfs_path, \
                                           major=udev_device_get_major(info), \
                                           minor=udev_device_get_minor(info), \
                                           exists=True, \
                                           parents=[disk])
                    if not device:
                        return
                    self._addDevice(device)
                    #self.addIgnoredDisk(name)

                # if we get here, we found all of the slave devices and
                # something must be wrong -- if all of the slaves are in
                # the tree, this device should be as well
                if device is None:
                    log.warning("using generic DM device for %s" % name)
                    device = DMDevice(name, exists=True, parents=slaves)
                    self._addDevice(device)
        elif udev_device_is_md(info):
            log.debug("%s is an md device" % name)
            # try to look up the device
            device = self.getDeviceByName(name)
            if device is None and uuid:
                # try to find the device by uuid
                device = self.getDeviceByUuid(uuid)

            if device is None:
                # we didn't find a device instance, so we will create one
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
                        new_info = udev_get_block_device(os.path.realpath(path))
                        if new_info:
                            self.addUdevDevice(new_info)
                            if self.getDeviceByName(dev_name) is None:
                                # if the current slave is still not in
                                # the tree, something has gone wrong
                                log.error("failure scanning device %s: could not add slave %s" % (name, dev_name))
                                return

                # try to get the device again now that we've got all the slaves
                device = self.getDeviceByName(name)

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
        elif udev_device_is_cdrom(info):
            log.debug("%s is a cdrom" % name)
            device = self.getDeviceByName(name)
            if device is None:
                # XXX should this be RemovableDevice instead?
                #
                # Looks like if it has ID_INSTANCE=0:1 we can ignore it.
                device = OpticalDevice(name,
                                       major=udev_device_get_major(info),
                                       minor=udev_device_get_minor(info),
                                       sysfsPath=sysfs_path)
                self._addDevice(device)
        elif udev_device_is_dmraid(info):
            # This is just temporary as I need to differentiate between the
            # device that has partitions and device that dont.
            log.debug("%s is part of a dmraid" % name)
            device = self.getDeviceByName(name)
            if device is None:
                device = StorageDevice(name,
                                major=udev_device_get_major(info),
                                minor=udev_device_get_minor(info),
                                sysfsPath=sysfs_path, exists=True)
                self._addDevice(device)
        elif udev_device_is_disk(info):
            kwargs = {}
            if udev_device_is_iscsi(info):
                diskType = iScsiDiskDevice
                kwargs["iscsi_name"]    = udev_device_get_iscsi_name(info)
                kwargs["iscsi_address"] = udev_device_get_iscsi_address(info)
                kwargs["iscsi_port"]    = udev_device_get_iscsi_port(info)
                log.debug("%s is an iscsi disk" % name)
            else:
                diskType = DiskDevice
                log.debug("%s is a disk" % name)
            device = self.getDeviceByName(name)
            if device is None:
                try:
                    if self.zeroMbr:
                        cb = lambda: True
                    else:
                        cb = lambda: questionInitializeDisk(self.intf, name)

                    # if the disk contains protected partitions we will
                    # not wipe the disklabel even if clearpart --initlabel
                    # was specified
                    if not self.clearPartDisks or name in self.clearPartDisks:
                        initlabel = self.reinitializeDisks

                        for protected in self.protectedPartitions:
                            _p = "/sys/%s/%s" % (sysfs_path, protected)
                            if os.path.exists(os.path.normpath(_p)):
                                initlabel = False
                                break
                    else:
                        initlabel = False

                    device = diskType(name,
                                    major=udev_device_get_major(info),
                                    minor=udev_device_get_minor(info),
                                    sysfsPath=sysfs_path,
                                    initcb=cb, initlabel=initlabel, **kwargs)
                    self._addDevice(device)
                except DeviceUserDeniedFormatError: #drive not initialized?
                    self.addIgnoredDisk(name)
        elif udev_device_is_partition(info):
            log.debug("%s is a partition" % name)
            device = self.getDeviceByName(name)
            if device is None:
                disk_name = os.path.basename(os.path.dirname(sysfs_path))
                disk = self.getDeviceByName(disk_name)

                if disk is None:
                    # create a device instance for the disk
                    path = os.path.dirname(os.path.realpath(sysfs_path))
                    new_info = udev_get_block_device(path)
                    if new_info:
                        self.addUdevDevice(new_info)
                        disk = self.getDeviceByName(disk_name)

                    if disk is None:
                        # if the current device is still not in
                        # the tree, something has gone wrong
                        log.error("failure scanning device %s" % disk_name)
                        return

                device = PartitionDeviceFactory(name,
                                                sysfsPath=sysfs_path,
                                                major=udev_device_get_major(info),
                                                minor=udev_device_get_minor(info),
                                                exists=True,
                                                parents=[disk])
                if not device:
                    return
                self._addDevice(device)

        #
        # now set the format
        #
        format = None
        format_type = udev_device_get_format(info)
        label = udev_device_get_label(info)
        if device and format_type and not device.format.type:
            args = [format_type]
            kwargs = {"uuid": uuid,
                      "label": label,
                      "device": device.path,
                      "exists": True}

            if format_type == "crypto_LUKS":
                # luks/dmcrypt
                kwargs["name"] = "luks-%s" % uuid
            elif format_type == "linux_raid_member":
                # mdraid
                try:
                    kwargs["mdUuid"] = udev_device_get_md_uuid(info)
                except KeyError:
                    log.debug("mdraid member %s has no md uuid" % name)
            elif format_type == "isw_raid_member":
                # We dont add any new args because we intend to use the same
                # block.RaidSet object for all the related devices.
                pass
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

            format = formats.getFormat(*args, **kwargs)
            device.format = format

        #
        # now lookup or create any compound devices we have discovered
        #        
        if format:
            if format.type == "luks":
                if not format.uuid:
                    log.info("luks device %s has no uuid" % device.path)
                    return

                # look up or create the mapped device
                if not self.getDeviceByName(device.format.mapName):
                    passphrase = self.__luksDevs.get(format.uuid)
                    if passphrase:
                        format.passphrase = passphrase
                    else:
                        (passphrase, isglobal) = getLUKSPassphrase(self.intf,
                                                            device,
                                                            self.__passphrase)
                        if isglobal and format.status:
                            self.__passphrase = passphrase

                    luks_device = LUKSDevice(device.format.mapName,
                                             parents=[device],
                                             exists=True)
                    try:
                        luks_device.setup()
                    except (LUKSError, CryptoError, DeviceError) as e:
                        log.info("setup of %s failed: %s" % (format.mapName,
                                                             e))
                        device.removeChild()
                    else:
                        self._addDevice(luks_device)
                else:
                    log.warning("luks device %s already in the tree"
                                % format.mapName)
            elif format.type == "mdmember":
                # either look up or create the array device
                md_array = self.getDeviceByUuid(format.mdUuid)
                if format.mdUuid and md_array:
                    md_array._addDevice(device)
                else:
                    # create the array with just this one member
                    # FIXME: why does this exact block appear twice?
                    try:
                        # level is reported as, eg: "raid1"
                        md_level = udev_device_get_md_level(info)
                        md_devices = int(udev_device_get_md_devices(info))
                        md_uuid = udev_device_get_md_uuid(info)
                    except (KeyError, ValueError) as e:
                        log.warning("invalid data for %s: %s" % (name, e))
                        return

                    # find the first unused minor
                    minor = 0
                    while True:
                        if self.getDeviceByName("md%d" % minor):
                            minor += 1
                        else:
                            break

                    md_name = "md%d" % minor
                    md_array = MDRaidArrayDevice(md_name,
                                                 level=md_level,
                                                 minor=minor,
                                                 memberDevices=md_devices,
                                                 uuid=md_uuid,
                                                 exists=True,
                                                 parents=[device])
                    self._addDevice(md_array)
            elif format.type == "dmraidmember":
                major = udev_device_get_major(info)
                minor = udev_device_get_minor(info)
                # Have we already created the DMRaidArrayDevice?
                rs = block.getRaidSetFromRelatedMem(uuid=uuid, name=name,
                                                    major=major, minor=minor)
                if rs is None:
                    # we ignore the device in the hope that all the devices
                    # from this set will be ignored.
                    self.addIgnoredDisk(device.name)
                    return

                elif rs.name in self._ignoredDisks:
                    # If the rs is being ignored, we should ignore device too.
                    self.addIgnoredDisk(device.name)
                    return

                else:
                    dm_array = self.getDeviceByName(rs.name)
                    if dm_array is not None:
                        # We add the new device.
                        dm_array._addDevice(device)
                    else:
                        # Activate the Raid set.
                        rs.activate(mknod=True)

                        # Create the DMRaidArray
                        if self.zeroMbr:
                            cb = lambda: True
                        else:
                            cb = lambda: questionInitializeDisk(self.intf,
                                                                rs.name)

                        if not self.clearPartDisks or \
                           rs.name in self.clearPartDisks:
                            # if the disk contains protected partitions
                            # we will not wipe the disklabel even if
                            # clearpart --initlabel was specified
                            initlabel = self.reinitializeDisks
                            for protected in self.protectedPartitions:
                                disk_name = re.sub(r'p\d+$', protected)
                                if disk_name != protected and \
                                   disk_name == rs.name:
                                    initlabel = False
                                    break
                        else:
                            initlabel = False

                        try:
                            dm_array = DMRaidArrayDevice(rs.name,
                                                    major=major, minor=minor,
                                                    raidSet=rs,
                                                    level=rs.level,
                                                    parents=[device],
                                                    initcb=cb,
                                                    initlabel=initlabel)

                            self._addDevice(dm_array)
                            # Use the rs's object on the device.
                            # pyblock can return the memebers of a set and the
                            # device has the attribute to hold it.  But ATM we
                            # are not really using it. Commenting this out until
                            # we really need it.
                            #device.format.raidmem = block.getMemFromRaidSet(dm_array,
                            #        major=major, minor=minor, uuid=uuid, name=name)
                        except DeviceUserDeniedFormatError:
                            # We should ignore the dmriad and its components
                            self.addIgnoredDisk(rs.name)
                            self.addIgnoredDisk(device.name)
                            rs.deactivate()
            elif format.type == "lvmpv":
                # lookup/create the VG and LVs
                try:
                    vg_name = udev_device_get_vg_name(info)
                except KeyError:
                    # no vg name means no vg -- we're done with this pv
                    return

                vg_device = self.getDeviceByName(vg_name)
                if vg_device:
                    vg_device._addDevice(device)
                    for lv in vg_device.lvs:
                        try:
                            lv.setup()
                        except DeviceError as e:
                            log.info("setup of %s failed: %s" % (lv.name, e))
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
                        log.warning("invalid data for %s: %s" % (name, e))
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

                    try:
                        lv_names = udev_device_get_lv_names(info)
                        lv_uuids = udev_device_get_lv_uuids(info)
                        lv_sizes = udev_device_get_lv_sizes(info)
                    except KeyError as e:
                        log.warning("invalid data for %s: %s" % (name, e))
                        return

                    if not lv_names:
                        log.debug("no LVs listed for VG %s" % name)
                        return

                    lvs = []
                    for (index, lv_name) in enumerate(lv_names):
                        name = "%s-%s" % (vg_name, lv_name)
                        lv_dev = self.getDeviceByName(name)
                        if lv_dev is None:
                            lv_uuid = lv_uuids[index]
                            lv_size = lv_sizes[index]
                            lv_device = LVMLogicalVolumeDevice(lv_name,
                                                               vg_device,
                                                               uuid=lv_uuid,
                                                               size=lv_size,
                                                               exists=True)
                            self._addDevice(lv_device)
                            try:
                                lv_device.setup()
                            except DeviceError as e:
                                log.info("setup of %s failed: %s" 
                                                    % (lv_device.name, e))

    def populate(self):
        """ Locate all storage devices. """
        # each iteration scans any devices that have appeared since the
        # previous iteration
        old_devices = []
        ignored_devices = []
        while True:
            devices = []
            new_devices = udev_get_block_devices()

            for new_device in new_devices:
                found = False
                for old_device in old_devices:
                    if old_device['name'] == new_device['name']:
                        found = True
                        break

                if not found:
                    devices.append(new_device)

            if len(devices) == 0:
                # nothing is changing -- we are finished building devices
                break

            old_devices = new_devices
            log.info("devices to scan: %s" % [d['name'] for d in devices])
            for dev in devices:
                self.addUdevDevice(dev)

        self.teardownAll()

    def teardownAll(self):
        """ Run teardown methods on all devices. """
        for device in self.leaves:
            try:
                device.teardown(recursive=True)
            except (DeviceError, DeviceFormatError, LVMError) as e:
                log.info("teardown of %s failed: %s" % (device.name, e))

    def setupAll(self):
        """ Run setup methods on all devices. """
        for device in self.leaves:
            try:
                device.setup()
            except DeviceError as e:
                log.debug("setup of %s failed: %s" % (device.name, e))

    def getDeviceBySysfsPath(self, path):
        found = None
        for device in self._devices:
            if device.sysfsPath == path:
                found = device
                break

        return found

    def getDeviceByUuid(self, uuid):
        found = None
        for device in self._devices:
            if device.uuid == uuid:
                found = device
                break
            elif device.format.uuid == uuid:
                found = device
                break

        return found

    def getDeviceByLabel(self, label):
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
        found = None
        for device in self._devices:
            if device.name == name:
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
        """ Dict with device path keys and Device values. """
        devices = {}

        for device in self._devices:
            if device.path in devices:
                raise DeviceTreeError("duplicate paths in device tree")

            devices[device.path] = device

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



