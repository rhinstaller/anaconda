# deviceaction.py
# Device modification action classes for anaconda's storage configuration
# module.
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

from udev import *
import math

from devices import StorageDevice
from devices import PartitionDevice
from devices import LVMLogicalVolumeDevice
from formats import getFormat
from errors import *
from parted import partitionFlag, PARTITION_LBA

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("storage")


# The values are just hints as to the ordering.
# Eg: fsmod and devmod ordering depends on the mod (shrink -v- grow)
ACTION_TYPE_NONE = 0
ACTION_TYPE_DESTROY = 1000
ACTION_TYPE_RESIZE = 500
ACTION_TYPE_MIGRATE = 250
ACTION_TYPE_CREATE = 100

action_strings = {ACTION_TYPE_NONE: "None",
                  ACTION_TYPE_DESTROY: "Destroy",
                  ACTION_TYPE_RESIZE: "Resize",
                  ACTION_TYPE_MIGRATE: "Migrate",
                  ACTION_TYPE_CREATE: "Create"}

ACTION_OBJECT_NONE = 0
ACTION_OBJECT_FORMAT = 1
ACTION_OBJECT_DEVICE = 2

object_strings = {ACTION_OBJECT_NONE: "None",
                  ACTION_OBJECT_FORMAT: "Format",
                  ACTION_OBJECT_DEVICE: "Device"}

RESIZE_SHRINK = 88
RESIZE_GROW = 89

resize_strings = {RESIZE_SHRINK: "Shrink",
                  RESIZE_GROW: "Grow"}

def action_type_from_string(type_string):
    if type_string is None:
        return None

    for (k,v) in action_strings.items():
        if v.lower() == type_string.lower():
            return k

    return resize_type_from_string(type_string)

def action_object_from_string(type_string):
    if type_string is None:
        return None

    for (k,v) in object_strings.items():
        if v.lower() == type_string.lower():
            return k

def resize_type_from_string(type_string):
    if type_string is None:
        return None

    for (k,v) in resize_strings.items():
        if v.lower() == type_string.lower():
            return k

class DeviceAction(object):
    """ An action that will be carried out in the future on a Device.

        These classes represent actions to be performed on devices or
        filesystems.

        The operand Device instance will be modified according to the
        action, but no changes will be made to the underlying device or
        filesystem until the DeviceAction instance's execute method is
        called. The DeviceAction instance's cancel method should reverse
        any modifications made to the Device instance's attributes.

        If the Device instance represents a pre-existing device, the
        constructor should call any methods or set any attributes that the
        action will eventually change. Device/DeviceFormat classes should verify
        that the requested modifications are reasonable and raise an
        exception if not.

        Only one action of any given type/object pair can exist for any
        given device at any given time. This is enforced by the
        DeviceTree.

        Basic usage:

            a = DeviceAction(dev)
            a.execute()

            OR

            a = DeviceAction(dev)
            a.cancel()


        XXX should we back up the device with a deep copy for forcibly
            cancelling actions?

            The downside is that we lose any checking or verification that
            would get done when resetting the Device instance's attributes to
            their original values.

            The upside is that we would be guaranteed to achieve a total
            reversal. No chance of, eg: resizes ending up altering Device
            size due to rounding or other miscalculation.
"""
    type = ACTION_TYPE_NONE
    obj = ACTION_OBJECT_NONE
    _id = 0

    def __init__(self, device):
        if not isinstance(device, StorageDevice):
            raise ValueError("arg 1 must be a StorageDevice instance")
        self.device = device

        # Establish a unique id for each action instance. Making shallow or
        # deep copyies of DeviceAction instances will require __copy__ and
        # __deepcopy__ methods to handle incrementing the id in the copy
        self.id = DeviceAction._id
        DeviceAction._id += 1

    def execute(self):
        """ perform the action """
        pass

    def cancel(self):
        """ cancel the action """
        pass

    @property
    def isDestroy(self):
        return self.type == ACTION_TYPE_DESTROY

    @property
    def isCreate(self):
        return self.type == ACTION_TYPE_CREATE

    @property
    def isMigrate(self):
        return self.type == ACTION_TYPE_MIGRATE

    @property
    def isResize(self):
        return self.type == ACTION_TYPE_RESIZE

    @property
    def isShrink(self):
        return (self.type == ACTION_TYPE_RESIZE and self.dir == RESIZE_SHRINK)

    @property
    def isGrow(self):
        return (self.type == ACTION_TYPE_RESIZE and self.dir == RESIZE_GROW)

    @property
    def isDevice(self):
        return self.obj == ACTION_OBJECT_DEVICE

    @property
    def isFormat(self):
        return self.obj == ACTION_OBJECT_FORMAT

    @property
    def format(self):
        return self.device.format

    def __str__(self):
        s = "[%d] %s %s" % (self.id, action_strings[self.type],
                            object_strings[self.obj])
        if self.isResize:
            s += " (%s)" % resize_strings[self.dir]
        if self.isFormat:
            s += " %s" % self.format.desc
            if self.isMigrate:
                s += " to %s" % self.format.migrationTarget
            s += " on"
        s += " %s %s (id %d)" % (self.device.type, self.device.name,
                                 self.device.id)
        return s

    def requires(self, action):
        """ Return True if self requires action. """
        return False

    def obsoletes(self, action):
        """ Return True is self obsoletes action.

            DeviceAction instances obsolete other DeviceAction instances with
            lower id and same device.
        """
        return (self.device.id == action.device.id and
                self.type == action.type and
                self.obj == action.obj and
                self.id > action.id)


class ActionCreateDevice(DeviceAction):
    """ Action representing the creation of a new device. """
    type = ACTION_TYPE_CREATE
    obj = ACTION_OBJECT_DEVICE

    def __init__(self, device):
        if device.exists:
            raise ValueError("device already exists")

        # FIXME: assert device.fs is None
        DeviceAction.__init__(self, device)

    def execute(self):
        self.device.create()

    def requires(self, action):
        """ Return True if self requires action.

            Device create actions require other actions when either of the
            following is true:

                - this action's device depends on the other action's device
                - both actions are partition create actions on the same disk
                  and this partition has a higher number
        """
        rc = False
        if self.device.dependsOn(action.device):
            rc = True
        elif (action.isCreate and action.isDevice and
              isinstance(self.device, PartitionDevice) and
              isinstance(action.device, PartitionDevice) and
              self.device.disk == action.device.disk):
            # create partitions in ascending numerical order
            selfNum = self.device.partedPartition.number
            otherNum = action.device.partedPartition.number
            if selfNum > otherNum:
                rc = True
        elif (action.isCreate and action.isDevice and
              isinstance(self.device, LVMLogicalVolumeDevice) and
              isinstance(action.device, LVMLogicalVolumeDevice) and
              self.device.vg == action.device.vg and
              action.device.singlePV and not self.device.singlePV):
            rc = True
        return rc


class ActionDestroyDevice(DeviceAction):
    """ An action representing the deletion of an existing device. """
    type = ACTION_TYPE_DESTROY
    obj = ACTION_OBJECT_DEVICE

    def __init__(self, device):
        # XXX should we insist that device.fs be None?
        DeviceAction.__init__(self, device)
        if device.exists:
            device.teardown()

    def execute(self):
        self.device.destroy()

        # Make sure libparted does not keep cached info for this device
        # and returns it when we create a new device with the same name
        if self.device.partedDevice:
            try:
                self.device.partedDevice.removeFromCache()
            except Exception:
                pass

    def requires(self, action):
        """ Return True if self requires action.

            Device destroy actions require other actions when either of the
            following is true:

                - the other action's device depends on this action's device
                - both actions are partition create actions on the same disk
                  and this partition has a lower number
        """
        rc = False
        if action.device.dependsOn(self.device) and action.isDestroy:
            rc = True
        elif (action.isDestroy and action.isDevice and
              isinstance(self.device, PartitionDevice) and
              isinstance(action.device, PartitionDevice) and
              self.device.disk == action.device.disk):
            # remove partitions in descending numerical order
            selfNum = self.device.partedPartition.number
            otherNum = action.device.partedPartition.number
            if selfNum < otherNum:
                rc = True
        elif (action.isDestroy and action.isFormat and
              action.device.id == self.device.id):
            # device destruction comes after destruction of device's format
            rc = True
        return rc

    def obsoletes(self, action):
        """ Return True if self obsoletes action.

            - obsoletes all actions w/ lower id that act on the same device,
              including self, if device does not exist

            - obsoletes all but ActionDestroyFormat actions w/ lower id on the
              same device if device exists
        """
        rc = False
        if action.device.id == self.device.id:
            if self.id >= action.id and not self.device.exists:
                rc = True
            elif self.id > action.id and \
                 self.device.exists and \
                 not (action.isDestroy and action.isFormat):
                rc = True

        return rc


class ActionResizeDevice(DeviceAction):
    """ An action representing the resizing of an existing device. """
    type = ACTION_TYPE_RESIZE
    obj = ACTION_OBJECT_DEVICE

    def __init__(self, device, newsize):
        if not device.resizable:
            raise ValueError("device is not resizable")

        if long(math.floor(device.currentSize)) == newsize:
            raise ValueError("new size same as old size")

        DeviceAction.__init__(self, device)
        if newsize > long(math.floor(device.currentSize)):
            self.dir = RESIZE_GROW
        else:
            self.dir = RESIZE_SHRINK
        if device.targetSize > 0:
            self.origsize = device.targetSize
        else:
            self.origsize = device.size

        self.device.targetSize = newsize

    def execute(self):
        self.device.resize()

    def cancel(self):
        self.device.targetSize = self.origsize

    def requires(self, action):
        """ Return True if self requires action.

            A device resize action requires another action if:

                - the other action is a format resize on the same device and
                  both are shrink operations
                - the other action grows a device (or format it contains) that
                  this action's device depends on
                - the other action shrinks a device (or format it contains)
                  that depends on this action's device
        """
        retval = False
        if action.isResize:
            if self.device.id == action.device.id and \
               self.dir == action.dir and \
               action.isFormat and self.isShrink:
                retval = True
            elif action.isGrow and self.device.dependsOn(action.device):
                retval = True
            elif action.isShrink and action.device.dependsOn(self.device):
                retval = True

        return retval


class ActionCreateFormat(DeviceAction):
    """ An action representing creation of a new filesystem. """
    type = ACTION_TYPE_CREATE
    obj = ACTION_OBJECT_FORMAT

    def __init__(self, device, format=None):
        DeviceAction.__init__(self, device)
        if format:
            self.origFormat = device.format
            if self.device.format.exists:
                self.device.format.teardown()
            self.device.format = format
        else:
            self.origFormat = getFormat(None)

    def execute(self):
        from pyanaconda.progress import progress_report

        msg = _("Creating %(type)s on %(device)s") % {"type": self.device.format.type, "device": self.device.path}
        with progress_report(msg):
            self.device.setup()

            if isinstance(self.device, PartitionDevice):
                for flag in partitionFlag.keys():
                    # Keep the LBA flag on pre-existing partitions
                    if flag in [ PARTITION_LBA, self.format.partedFlag ]:
                        continue
                    self.device.unsetFlag(flag)

                if self.format.partedFlag is not None:
                    self.device.setFlag(self.format.partedFlag)

                if self.format.partedSystem is not None:
                    self.device.partedPartition.system = self.format.partedSystem

                self.device.disk.format.commitToDisk()

            self.device.format.create(device=self.device.path,
                                      options=self.device.formatArgs)
            # Get the UUID now that the format is created
            udev_settle()
            self.device.updateSysfsPath()
            info = udev_get_block_device(self.device.sysfsPath)
            self.device.format.uuid = udev_device_get_uuid(info)

    def cancel(self):
        self.device.format = self.origFormat

    def requires(self, action):
        """ Return True if self requires action.

            Format create action can require another action if:

                - this action's device depends on the other action's device
                  and the other action is not a device destroy action
                - the other action is a create or resize of this action's
                  device
        """
        return ((self.device.dependsOn(action.device) and
                 not (action.isDestroy and action.isDevice)) or
                (action.isDevice and (action.isCreate or action.isResize) and
                 self.device.id == action.device.id))

    def obsoletes(self, action):
        """ Return True if this action obsoletes action.

            Format create actions obsolete the following actions:

                - format actions w/ lower id on this action's device, other
                  than those that destroy existing formats
        """
        return (self.device.id == action.device.id and
                self.obj == action.obj and
                not (action.isDestroy and action.format.exists) and
                self.id > action.id)


class ActionDestroyFormat(DeviceAction):
    """ An action representing the removal of an existing filesystem. """
    type = ACTION_TYPE_DESTROY
    obj = ACTION_OBJECT_FORMAT

    def __init__(self, device):
        DeviceAction.__init__(self, device)
        self.origFormat = self.device.format
        if device.format.exists:
            device.format.teardown()
        self.device.format = None

    def execute(self):
        """ wipe the filesystem signature from the device """
        self.device.setup(orig=True)
        self.format.destroy()
        udev_settle()
        self.device.teardown()

    def cancel(self):
        self.device.format = self.origFormat

    @property
    def format(self):
        return self.origFormat

    def requires(self, action):
        """ Return True if self requires action.

            Format destroy actions require other actions when:

                - the other action's device depends on this action's device
                  and the other action is a destroy action
        """
        return action.device.dependsOn(self.device) and action.isDestroy

    def obsoletes(self, action):
        """ Return True if this action obsoletes action.

            Format destroy actions obsolete the following actions:

            - format actions w/ lower id on same device, including self if
              format does not exist

            - format destroy action on a non-existent format shouldn't
              obsolete a format destroy action on an existing one
        """
        return (self.device.id == action.device.id and
                self.obj == action.obj and
                (self.id > action.id or
                 (self.id == action.id and not self.format.exists)) and
                not (action.format.exists and not self.format.exists))


class ActionResizeFormat(DeviceAction):
    """ An action representing the resizing of an existing filesystem.

        XXX Do we even want to support resizing of a filesystem without
            also resizing the device it resides on?
    """
    type = ACTION_TYPE_RESIZE
    obj = ACTION_OBJECT_FORMAT

    def __init__(self, device, newsize):
        if not device.format.resizable:
            raise ValueError("format is not resizable")

        if long(math.floor(device.format.currentSize)) == newsize:
            raise ValueError("new size same as old size")

        DeviceAction.__init__(self, device)
        if newsize > long(math.floor(device.format.currentSize)):
            self.dir = RESIZE_GROW
        else:
            self.dir = RESIZE_SHRINK
        self.origSize = self.device.format.targetSize
        self.device.format.targetSize = newsize

    def execute(self):
        from pyanaconda.progress import progress_report

        msg = _("Resizing filesystem on %(device)s") % {"device": self.device.path}
        with progress_report(msg):
            self.device.setup(orig=True)
            self.device.format.doResize()

    def cancel(self):
        self.device.format.targetSize = self.origSize

    def requires(self, action):
        """ Return True if self requires action.

            A format resize action requires another action if:

                - the other action is a device resize on the same device and
                  both are grow operations
                - the other action shrinks a device (or format it contains)
                  that depends on this action's device
                - the other action grows a device (or format) that this
                  action's device depends on
        """
        retval = False
        if action.isResize:
            if self.device.id == action.device.id and \
               self.dir == action.dir and \
               action.isDevice and self.isGrow:
                retval = True
            elif action.isShrink and action.device.dependsOn(self.device):
                retval = True
            elif action.isGrow and self.device.dependsOn(action.device):
                retval = True

        return retval


class ActionMigrateFormat(DeviceAction):
    """ An action representing the migration of an existing filesystem. """
    type = ACTION_TYPE_MIGRATE
    obj = ACTION_OBJECT_FORMAT

    def __init__(self, device):
        if not device.format.migratable or not device.format.exists:
            raise ValueError("device format is not migratable")

        DeviceAction.__init__(self, device)
        self.device.format.migrate = True

    def execute(self):
        from pyanaconda.progress import progress_report

        msg = _("Migrating filesystem on %(device)s") % {"device": self.device.path}
        with progress_report(msg):
            self.device.setup(orig=True)
            self.device.format.doMigrate()

    def cancel(self):
        self.device.format.migrate = False

