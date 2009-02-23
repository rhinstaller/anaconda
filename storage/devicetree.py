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

import sys
sys.path.append("formats")

if __name__ == "__main__":
    import storage_log

from errors import *
from devices import *
from deviceaction import *
from deviceformat import getFormat
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

    if not device.format.configured and passphrase:
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

    def __init__(self, intf=None, ignored=[], exclusive=[],
                 zeroMbr=None, passphrase=None, luksDict=None):
        # internal data members
        self._devices = []
        self._actions = []

        self.intf = intf
        self.ignoredDisks = ignored
        self.exclusiveDisks = exclusive
        self.zeroMbr = zeroMbr
        self.__passphrase = passphrase
        self.__luksDevs = {}
        if luksDict and isinstance(luksDict, dict):
            self.__luksDevs = luksDict

        self._populate()

    def processActions(self, dryRun=None):
        """ Execute all registered actions. """
        def cmpActions(x, y):
            """
                < 1 => x < y
                  0 => x == y
                > 1 => x > y

                FIXME: this is unmanageable.
            """
	    #log.debug("%s | %s" % (x, y))

            # destroy actions come first
            if x.isDestroy() and not y.isDestroy():
		#log.debug("x is destroy -- x first")
                return -1
            elif y.isDestroy() and not x.isDestroy():
		#log.debug("y is destroy -- y first")
                return 1
            elif x.isDestroy() and y.isDestroy():
                # outermost/youngest first
                if x.device.dependsOn(y.device):
                    #log.debug("x depends on y -- x first")
                    return -1
                elif y.device.dependsOn(x.device):
                    #log.debug("y depends on x -- y first")
                    return 1
                # filesystem destruction must precede device destruction
                elif x.isFormat() and not y.isFormat():
		    #log.debug("x is format -- x first")
                    return -1
                elif y.isFormat() and not x.isFormat():
                    #log.debug("y is format -- y first")
                    return 1

            # resize actions come next
            if x.isResize() and not y.isResize():
		#log.debug("x is resize -- x first")
                return -1
            elif y.isResize() and not x.isResize():
	        #log.debug("y is resize -- y first")
                return 1
            elif x.isResize() and y.isResize():
                if x.isGrow() and y.isGrow():
                    # for grow, devices come first, root down
                    if x.isDevice() and not y.isDevice():
                        #log.debug("x is device -- x first")
                        return -1
                    elif y.isDevice() and not x.isDevice():
			#log.debug("y is device -- y first")
                        return 1
                    else:
                        # innermost/oldest first
                        if x.device.dependsOn(y.device):
			    #log.debug("x depends on y -- y first")
                            return 1
                        elif y.device.dependsOn(x.device):
		            #log.debug("y depends on x -- x first")
                            return -1
                elif x.isShrink() and y.isShrink():
                    # for shrink, filesystems come first, leaves up
                    if x.isFormat() and not y.isFormat():
		        #log.debug("x is format -- x first")
                        return -1
                    elif y.isFormat() and not x.isFormat():
                        #log.debug("y is format -- y first")
                        return 1
                    else:
                        # outermost/youngest first
                        if x.device.dependsOn(y.device):
			    #log.debug("x depends on y -- x first")
                            return -1
                        elif y.device.dependsOn(x.device):
                            #log.debug("y depends on x -- y first")
                            return 1
                else:
                    # we don't care about grow action -v- shrink action
                    # since they should be unrelated
		    #log.debug("we don't care")
                    return 0

            # create actions come last
            if x.isCreate() and y.isCreate():
                # innermost/oldest first
                if x.device.dependsOn(y.device):
		    #log.debug("x depends on y")
                    return 1
                elif y.device.dependsOn(x.device):
		    #log.debug("y depends on x")
                    return -1
                # devices first, root down
                elif x.isDevice() and not y.isDevice():
		    #log.debug("x is a device")
                    return -1
                elif y.isDevice() and not x.isDevice():
		    #log.debug("y is a device")
                    return 1
		elif x.device.isleaf and not y.device.isleaf:
		    #log.debug("x is a leaf -- y first")
                    return 1
                elif y.device.isleaf and not x.device.isleaf:
		    #log.debug("y is a leaf -- x first")
                    return -1

	    #log.debug("no decision")
            return 0

        # in most cases the actions will already be sorted because of the
        # rules for registration, but let's not rely on that
        self._actions.sort(cmpActions)
        for action in self._actions:
            log.info("executing action: %s" % action)
            if not dryRun:
                action.execute(intf=self.intf)

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
        if dev.type == "partition":
            dev.disk.removePartition(dev)

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
        removedAction = None
        for _action in self._actions:
            if _action.device == action.device and \
               _action.type == action.type and \
               _action.obj == action.obj:
                #raise DeviceTreeError("duplicate action for this device")
                log.debug("cancelling action '%s' in favor of '%s'" % (_action,
                                                                       action)
                self.cancelAction(_action)
                removedAction = _action
                break

        if (action.isDestroy() or action.isResize() or \
            (action.isCreate() and action.isFormat())) and \
           action.device not in self._devices:
            raise DeviceTreeError("device is not in the tree")
        elif (action.isCreate() and action.isDevice()) and \
             action.device in self._devices:
            raise DeviceTreeError("device is already in the tree")

        if action.isCreate() and action.isDevice():
            self._addDevice(action.device)
        elif action.isDestroy() and action.isDevice():
            self._removeDevice(action.device)
        elif action.isCreate() and action.isFormat():
            if isinstance(action.device.format, FS) and \
               action.device.format.mountpoint in self.filesystems:
                raise DeviceTreeError("mountpoint already in use")

        log.debug("registered action: %s" % action)
        self._actions.append(action)
        return removedAction

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

    def getDependentDevices(self, dep):
        """ Return a list of devices that depend on dep.

            The list includes both direct and indirect dependents.
        """
        dependents = []
        for device in self.devices.values():
            if device.dependsOn(dep):
                dependents.append(device)

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

        if name in self.ignoredDisks:
            return True

        for ignored in self.ignoredDisks:
            if ignored == os.path.basename(os.path.dirname(sysfs_path)):
                # this is a partition on a disk in the ignore list
                return True

        # FIXME: check for virtual devices whose slaves are on the ignore list

    def addUdevDevice(self, info):
        # FIXME: this should be broken up into more discrete chunks
        name = udev_device_get_name(info)
        uuid = udev_device_get_uuid(info)
        sysfs_path = udev_device_get_sysfs_path(info)
        device = None

        if self.isIgnored(sysfs_path):
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
                        #slave_name = block.getNameFromDmNode(slave_name)
                        slave_name = dm.name_from_dm_node(slave_name)
                    slave_dev = self.getDeviceByName(slave_name)
                    if slave_dev:
                        slaves.append(slave_dev)
                    else:
                        # we haven't scanned the slave yet, so do it now
                        path = os.path.normpath("%s/%s" % (dir, slave_name))
                        new_info = udev_get_block_device(os.path.realpath(path))
                        if new_info:
                            self.addUdevDevice(new_info)
                            device = self.getDeviceByName(name)
                            if device is None:
                                # if the current device is still not in
                                # the tree, something has gone wrong
                                log.error("failure scanning device %s" % name)
                                return

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
                        #slave_name = block.getNameFromDmNode(slave_name)
                        slave_name = dm.name_from_dm_node(slave_name)
                    slave_dev = self.getDeviceByName(slave_name)
                    if slave_dev:
                        slaves.append(slave_dev)
                    else:
                        # we haven't scanned the slave yet, so do it now
                        path = os.path.normpath("%s/%s" % (dir, slave_name))
                        new_info = udev_get_block_device(os.path.realpath(path))
                        if new_info:
                            self.addUdevDevice(new_info)
                            device = self.getDeviceByName(name)
                            if device is None:
                                # if the current device is still not in
                                # the tree, something has gone wrong
                                log.error("failure scanning device %s" % name)
                                return

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
        elif udev_device_is_disk(info):
            log.debug("%s is a disk" % name)
            device = self.getDeviceByName(name)
            if device is None:
                device = DiskDevice(name,
                                    major=udev_device_get_major(info),
                                    minor=udev_device_get_minor(info),
                                    sysfsPath=sysfs_path)
                self._addDevice(device)
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

                device = PartitionDevice(name,
                                         sysfsPath=sysfs_path,
                                         major=udev_device_get_major(info),
                                         minor=udev_device_get_minor(info),
                                         exists=True,
                                         parents=[disk])
                self._addDevice(device)

        #
        # now set the format
        #
        format = None
        format_type = udev_device_get_format(info)
        label = udev_device_get_label(info)
        if device and format_type and not device.format:
            args = [format_type]
            kwargs = {"uuid": uuid,
                      "label": label,
                      "device": device.path,
                      "exists": True}

            if format_type == "swap":
                # swap
                pass
            elif format_type == "crypto_LUKS":
                # luks/dmcrypt
                kwargs["mapName"] = "luks-%s" % uuid
            elif format_type == "linux_raid_member":
                # mdraid
                kwargs["mdUuid"] = udev_device_get_md_uuid(info)
            elif format_type == "isw_raid_member":
                # dmraid
                # TODO: collect name of containing raidset
                # TODO: implement dmraid member format class
                pass
            elif format_type == "LVM2_member":
                # lvm
                try:
                    kwargs["vgName"] = udev_device_get_vg_name(info)
                except KeyError as e:
                    log.debug("PV %s has no vg_name" % name)
                kwargs["vgUuid"] = udev_device_get_vg_uuid(info)
                kwargs["peStart"] = udev_device_get_pv_pe_start(info)

            device.format = getFormat(*args, **kwargs)

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

                    luks_device = LUKSDevice(device.format.MapName,
                                             parents=[device],
                                             exists=True)
                    self._addDevice(luks_device)
                    try:
                        luks_device.setup()
                    except DeviceError as e:
                        log.info("setup of %s failed: %s" % (map_name, e))
                else:
                    log.warning("luks device %s already in the tree" % map_name)
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
                    try:
                        md_array.setup()
                    except DeviceError as e:
                        log.info("setup of %s failed: %s" % (md_array.name, e))
            elif format.type == "dmraidmember":
                # look up or create the dmraid array
                pass
            elif format.type == "lvmpv":
                # lookup/create the VG and LVsA
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

    def _populate(self):
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
            log.debug("devices to scan: %s" % [d['name'] for d in devices])
            for dev in devices:
                self.addUdevDevice(dev)

    def teardownAll(self):
        """ Run teardown methods on all devices. """
        for device in self.leaves:
            try:
                device.teardown(recursive=True)
            except DeviceError as e:
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

    def getDevicebyLabel(self, label):
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
            elif uuid:
                uuids[uuid] = dev

            try:
                uuid = dev.format.uuid
            except AttributeError:
                uuid = None
            elif uuid:
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


def test_tree():
    try:
        tree = DeviceTree(ignored_disks=[])
    except Exception as e:
        log.error("tree creation failed: %s" % e)
        raise
    return tree

def test_fstab(tree):
    roots = findExistingRoots(tree, keepall=True)
    print ["%s: %s" % (d.path, d.format.type) for d in roots]
    rootDev = roots[0]
    if not rootDev:
        return

    log.debug("setting up root device %s" % rootDev.path)
    #rootDev.setup()
    #rootDev.format.mount(chroot="/mnt/sysimage", mountpoint="/")
    #fstab = FSTab(tree, chroot="/mnt/sysimage")
    fsset = FSSet(tree)
    m
    #return fstab

if __name__ == "__main__":
    mode = "tree"
    if len(sys.argv) == 2:
        mode = sys.argv[1]

    if mode == "tree":
        tree = test_tree()
        if tree is None:
            sys.exit(1)
        devices = tree.devices.values()
        devices.sort(key=lambda d: d.path)
        for device in devices:
            fs_string = ""
            if device.format:
                fs_string = "%s on " % device.format.type
            print "%s: %s%s" % (device.path, fs_string, device.typeDescription) 
    elif mode == "fstab":
        tree = test_tree()
        tree.teardownAll()
        fstab = test_fstab(tree)
        #print fstab.blkidTab.devices
        #print fstab.cryptTab.mappings
        fmt = "%-23s %-23s %-7s %-15s %s %s"
        for  in fstab.devices:
            (device, mountpoint, fstype, options, dump, passno) = entry
            print fmt % (device.fstabSpec(), mountpoint, fstype,
                         options, dump, passno)

        print
        print "ORIGINAL:"
        print fstab.origBuf
        print
    elif mode == "actions":
        print "creating tree..."
        tree = test_tree()

        # we don't need to actually use any of the devices, so clean up now
        tree.teardownAll()
        print "setting up actions..."
        tree.registerAction(ActionDestroyFormat(tree.getDeviceByName("luks-md0")))
        tree.registerAction(ActionDestroyDevice(tree.getDeviceByName("luks-md0")))
        fs = getFormat("ext3", device="/dev/md0", mountpoint="/opt")
        tree.registerAction(ActionCreateFormat(tree.getDeviceByName("md0"), fs))
        tree.registerAction(ActionDestroyFormat(tree.getDeviceByName("sda1")))
        print "processing actions..."
        tree.processActions(dryRun=True)
        print "done."

    tree.teardownAll()

