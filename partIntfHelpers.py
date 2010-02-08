#
# partIntfHelpers.py: partitioning interface helper functions
#
# Copyright (C) 2002  Red Hat, Inc.  All rights reserved.
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
# Author(s): Matt Wilson <msw@redhat.com>
#            Jeremy Katz <katzj@redhat.com>
#            Mike Fulbright <msf@redhat.com>
#            Harald Hoyer <harald@redhat.de>
#

"""Helper functions shared between partitioning interfaces."""

import string
from constants import *
import parted
import iutil
from storage.formats import getFormat

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

def sanityCheckVolumeGroupName(volname):
    """Make sure that the volume group name doesn't contain invalid chars."""
    badNames = ['lvm', 'root', '.', '..' ]

    if not volname:
	return _("Please enter a volume group name.")

    # ripped the value for this out of linux/include/lvm.h
    if len(volname) > 128:
        return _("Volume Group Names must be less than 128 characters")

    if volname in badNames:
	return _("Error - the volume group name %s is not valid." % (volname,))

    for i in range(0, len(volname)):
	rc = string.find(string.letters + string.digits + '.' + '_' + '-', volname[i])
	if rc == -1:
	    return _("Error - the volume group name contains illegal "
		     "characters or spaces.  Acceptable characters "
		     "are letters, digits, '.' or '_'.")
    return None

def sanityCheckLogicalVolumeName(logvolname):
    """Make sure that the logical volume name doesn't contain invalid chars."""
    badNames = ['group', '.', '..' ]
    
    if not logvolname:
	return _("Please enter a logical volume name.")

    # ripped the value for this out of linux/include/lvm.h
    if len(logvolname) > 128:
        return _("Logical Volume Names must be less than 128 characters")
    

    if logvolname in badNames:
	return _("Error - the logical volume name %s is not "
                 "valid." % (logvolname,))

    for i in range(0, len(logvolname)):
	rc = string.find(string.letters + string.digits + '.' + '_', logvolname[i])
	if rc == -1:
	    return _("Error - the logical volume name contains illegal "
		     "characters or spaces.  Acceptable characters "
		     "are letters, digits, '.' or '_'.")
    return None

def sanityCheckMountPoint(mntpt, fstype, preexisting, format):
    """Sanity check that the mountpoint is valid.

    mntpt is the mountpoint being used.
    fstype is the file system being used on the request.
    preexisting is whether the request was preexisting (request.preexist)
    format is whether the request is being formatted or not
    """
    if mntpt:
        passed = 1
        if not mntpt:
            passed = 0
        else:
            if mntpt[0] != '/' or (len(mntpt) > 1 and mntpt[-1:] == '/'):
                passed = 0
	    elif mntpt.find(' ') > -1:
		passed = 0
                
        if not passed:
            return _("The mount point %s is invalid.  Mount points must start "
                     "with '/' and cannot end with '/', and must contain "
                     "printable characters and no spaces." % mntpt)
        else:
            return None
    else:
        if (fstype and fstype.mountable and (not preexisting or format)):
            return _("Please specify a mount point for this partition.")
        else:
            # its an existing partition so don't force a mount point
            return None

def doDeleteDevice(intf, storage, device, confirm=1, quiet=0):
    """Delete a partition from the request list.

    intf is the interface
    storage is the storage instance
    device is the device to delete
    """
    if not device:
        intf.messageWindow(_("Unable To Delete"),
                           _("You must first select a partition to delete."),
			   custom_icon="error")
        return False

    reason = storage.deviceImmutable(device)
    if reason:
        intf.messageWindow(_("Unable To Delete"),
                           reason,
                           custom_icon="error")
        return False

    if confirm and not confirmDelete(intf, device):
        return False

    deps = storage.deviceDeps(device)
    while deps:
        leaves = [d for d in deps if d.isleaf]
        for leaf in leaves:
            storage.destroyDevice(leaf)
            deps.remove(leaf)

    storage.destroyDevice(device)
    return True

def doClearPartitionedDevice(intf, storage, device, confirm=1, quiet=0):
    """ Remove all devices/partitions currently on device.

            device -- a partitioned device such as a disk

     """
    if confirm:
	rc = intf.messageWindow(_("Confirm Delete"),
				_("You are about to delete all partitions on "
				  "the device '%s'.") % (device.path,),
				type="custom", custom_icon="warning",
				custom_buttons=[_("Cancel"), _("_Delete")])

	if not rc:
	    return False

    immutable = []
    partitions = [p for p in storage.partitions if p.disk == device]
    if not partitions:
        return False

    partitions.sort(key=lambda p: p.partedPartition.number, reverse=True)
    for p in partitions:
        deps = storage.deviceDeps(p)
        clean = True    # true if part and its deps were removed
        while deps:
            leaves = [d for d in deps if d.isleaf]
            for leaf in leaves:
                if leaf in immutable:
                    # this device was removed from deps at the same time it
                    # was added to immutable, so it won't appear in leaves
                    # in the next iteration
                    continue

                if storage.deviceImmutable(leaf):
                    immutable.append(leaf)
                    for dep in [d for d in deps if d != leaf]:
                        # mark devices this device depends on as immutable
                        # to prevent getting stuck with non-leaf deps
                        # protected by immutable leaf devices
                        if leaf.dependsOn(dep):
                            deps.remove(dep)
                            if dep not in immutable:
                                immutable.append(dep)
                    clean = False
                else:
                    storage.destroyDevice(leaf)
                deps.remove(leaf)

        if storage.deviceImmutable(p):
            immutable.append(p)
            clean = False

        if clean:
            storage.destroyDevice(p)

    if immutable and not quiet:
        remaining = "\t" + "\n\t".join(p.path for p in immutable) + "\n"
        intf.messageWindow(_("Notice"),
                           _("The following partitions were not deleted "
                             "because they are in use:\n\n%s") % remaining,
			   custom_icon="warning")

    return True

def checkForSwapNoMatch(anaconda):
    """Check for any partitions of type 0x82 which don't have a swap fs."""
    for device in anaconda.storage.partitions:
        if not device.exists:
            # this is only for existing partitions
            continue

        if device.getFlag(parted.PARTITION_SWAP) and \
           not device.format.type == "swap":
            rc = anaconda.intf.messageWindow(_("Format as Swap?"),
                                    _("%s has a partition type of 0x82 "
                                      "(Linux swap) but does not appear to "
                                      "be formatted as a Linux swap "
                                      "partition.\n\n"
                                      "Would you like to format this "
                                      "partition as a swap partition?")
                                    % device.path, type = "yesno",
                                    custom_icon="question")
            if rc == 1:
                format = getFormat("swap", device=device.path)
                anaconda.storage.formatDevice(device, format)

    return

def mustHaveSelectedDrive(intf):
    txt =_("You need to select at least one hard drive to install %s.") % (productName,)
    intf.messageWindow(_("Error"), txt, custom_icon="error")
     
def queryNoFormatPreExisting(intf):
    """Ensure the user wants to use a partition without formatting."""
    txt = _("You have chosen to use a pre-existing "
            "partition for this installation without formatting it. "
            "We recommend that you format this partition "
            "to make sure files from a previous operating system installation "
            "do not cause problems with this installation of Linux. "
            "However, if this partition contains files that you need "
            "to keep, such as home directories, then "
            "continue without formatting this partition.")
    rc = intf.messageWindow(_("Format?"), txt, type = "custom", custom_buttons=[_("_Modify Partition"), _("Do _Not Format")], custom_icon="warning")
    return rc

def partitionSanityErrors(intf, errors):
    """Errors were found sanity checking.  Tell the user they must fix."""
    rc = 1
    if errors:
        errorstr = string.join(errors, "\n\n")
        rc = intf.messageWindow(_("Error with Partitioning"),
                                _("The following critical errors exist "
                                  "with your requested partitioning "
                                  "scheme. "
                                  "These errors must be corrected prior "
                                  "to continuing with your install of "
                                  "%(productName)s.\n\n%(errorstr)s") \
                                % {'productName': productName,
                                   'errorstr': errorstr},
                                custom_icon="error")
    return rc

def partitionSanityWarnings(intf, warnings):
    """Sanity check found warnings.  Make sure the user wants to continue."""
    rc = 1
    if warnings:
        warningstr = string.join(warnings, "\n\n")
        rc = intf.messageWindow(_("Partitioning Warning"),
                                     _("The following warnings exist with "
                                       "your requested partition scheme.\n\n%s"
                                       "\n\nWould you like to continue with "
                                       "your requested partitioning "
                                       "scheme?") % (warningstr),
                                     type="yesno", custom_icon="warning")
    return rc


def partitionPreExistFormatWarnings(intf, warnings):
    """Double check that preexistings being formatted are fine."""
    rc = 1
    if warnings:

        labelstr1 = _("The following pre-existing partitions have been "
                      "selected to be formatted, destroying all data.")

        labelstr2 = _("Select 'Yes' to continue and format these "
                      "partitions, or 'No' to go back and change these "
                      "settings.")
        commentstr = ""
        for (dev, type, mntpt) in warnings:
            commentstr = commentstr + "/dev/%s %s %s\n" % (dev,type,mntpt)
        rc = intf.messageWindow(_("Format Warning"), "%s\n\n%s\n\n%s" %
                                (labelstr1, labelstr2, commentstr),
                                type="yesno", custom_icon="warning")
    return rc

def getPreExistFormatWarnings(storage):
    """Return a list of preexisting devices being formatted."""
    devices = []
    for device in storage.devicetree.devices:
        if device.exists and not device.format.exists and \
           not device.format.hidden:
            devices.append(device)

    devices.sort(key=lambda d: d.name)
    rc = []
    for device in devices:
        rc.append((device.path,
                   device.format.name,
                   getattr(device.format, "mountpoint", "")))
    return rc
            
def confirmDelete(intf, device):
    """Confirm the deletion of a device."""
    if not device:
	return
    
    if device.type == "lvmvg":
	errmsg = (_("You are about to delete the volume group \"%s\"."
                    "\n\nALL logical volumes in this volume group "
                    "will be lost!") % device.name)
    elif device.type == "lvmlv":
	errmsg = (_("You are about to delete the logical volume \"%s\".")
                  % device.name)
    elif device.type == "mdarray":
	errmsg = _("You are about to delete a RAID device.")
    elif device.type == "partition":
	errmsg = (_("You are about to delete the %s partition.")
                  % device.path)
    else:
        # we may want something a little bit prettier than device.type
        errmsg = (_("You are about to delete the %(type)s %(name)s") \
                  % {'type': device.type, 'name': device.name})

    rc = intf.messageWindow(_("Confirm Delete"), errmsg, type="custom",
				custom_buttons=[_("Cancel"), _("_Delete")],
			    custom_icon="question")

    return rc

def confirmResetPartitionState(intf):
    """Confirm reset of partitioning to that present on the system."""
    rc = intf.messageWindow(_("Confirm Reset"),
                            _("Are you sure you want to reset the "
                              "partition table to its original state?"),
                            type="yesno", custom_icon="question")
    return rc

