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

from abc import ABCMeta, abstractmethod
import string
from constants import *
import parted
import iutil
import network
from storage.formats import getFormat
from storage.devicelibs.lvm import LVM_MAX_NAME_LEN

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("anaconda")


def sanityCheckVolumeGroupName(volname):
    """Make sure that the volume group name doesn't contain invalid chars."""
    badNames = ['lvm', 'root', '.', '..' ]

    if not volname:
	return _("Please enter a volume group name.")

    # ripped the value for this out of linux/include/lvm.h
    if len(volname) > LVM_MAX_NAME_LEN:
        return _("Volume Group Names must be less than %d characters") % LVM_MAX_NAME_LEN

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
    if len(logvolname) > LVM_MAX_NAME_LEN:
        return _("Logical Volume Names must be less than %d characters") % LVM_MAX_NAME_LEN
    

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

def sanityCheckMountPoint(mntpt):
    """Sanity check that the mountpoint is valid.

    mntpt is the mountpoint being used.

    The Rules
        Start with one /
        Don't end with /
        No spaces
        No /../
        No /./
        No //
        Don't end with /..
        Don't end with /.
    """
    if not mntpt.startswith("/") or \
       (len(mntpt) > 1 and mntpt.endswith("/")) or \
       " " in mntpt or \
       "/../" in mntpt or \
       "/./" in mntpt or \
       "//" in mntpt or \
       mntpt.endswith("/..") or \
       mntpt.endswith("/.") :
           return _("The mount point %s is invalid.  Mount points must start "
                    "with '/' and cannot end with '/', and must contain "
                    "printable characters and no spaces.") % mntpt

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
    for device in anaconda.id.storage.partitions:
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
                anaconda.id.storage.formatDevice(device, format)

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


""" iSCSI GUI helper objects """

# the credentials constants: are necessary to implement a concrete iSCSIWizard
CRED_NONE   = (0, _("No authentication"))
CRED_ONE    = (1, _("CHAP pair"))
CRED_BOTH   = (2, _("CHAP pair and a reverse pair"))
CRED_REUSE  = (3, _("Use the credentials from the discovery step"))

def parse_ip(string_ip):
    """
    May rise network.IPMissing or network.IPError

    Returns (ip, port) tuple.
    """
    count = len(string_ip.split(":"))
    idx = string_ip.rfind("]:")
    # Check for IPV6 [IPV6-ip]:port
    if idx != -1:
        ip = string_ip[1:idx]
        port = string_ip[idx+2:]
    # Check for IPV4 aaa.bbb.ccc.ddd:port
    elif count == 2:
        idx = string_ip.rfind(":")
        ip = string_ip[:idx]
        port = string_ip[idx+1:]
    else:
        ip = string_ip
        port = "3260"
    network.sanityCheckIPString(ip)

    return (ip, port)

class iSCSIWizard():
    """
    A base class for both the GUI and TUI iSCSI wizards.

    To get an instantiable class, all its methods have to be overriden.
    """
    __metaclass__ = ABCMeta
    
    @abstractmethod
    def destroy_dialogs(self):
        pass

    @abstractmethod
    def display_discovery_dialog(self, initiator, initiator_set):
        pass

    @abstractmethod
    def display_login_dialog(self):
        pass

    @abstractmethod
    def display_nodes_dialog(self, found_nodes, ifaces):
        pass

    @abstractmethod
    def display_success_dialog(self, success_nodes, fail_nodes, fail_reason,
                               ifaces):
        pass

    @abstractmethod
    def get_discovery_dict(self):
        pass

    @abstractmethod
    def get_initiator(self):
        pass

    @abstractmethod
    def get_login_dict(self):
        pass

    @abstractmethod
    def set_initiator(self, initiator, initiator_set):
        pass

def drive_iscsi_addition(anaconda, wizard):
    """
    This method is the UI controller that drives adding of iSCSI drives

    wizard is the UI wizard object of class derived from iSCSIWizard.

    Returns a list of all newly added iSCSI nodes (or empty list on error etc.)
    """

    STEP_DISCOVERY = 0
    STEP_NODES     = 1
    STEP_LOGIN     = 2
    STEP_SUMMARY   = 3
    STEP_STABILIZE = 4
    STEP_DONE      = 10

    login_ok_nodes = []
    step = STEP_DISCOVERY
    while step != STEP_DONE:
        # go through the wizard's dialogs, read the user input (selected nodes,
        # login credentials) and provide it to the iscsi subsystem
        try:
            if step == STEP_DISCOVERY:
                rc = wizard.display_discovery_dialog(
                    anaconda.id.storage.iscsi.initiator,
                    anaconda.id.storage.iscsi.initiatorSet)
                if not rc:
                    break
                anaconda.id.storage.iscsi.initiator = wizard.get_initiator()
                discovery_dict = wizard.get_discovery_dict()
                discovery_dict["intf"] = anaconda.intf
                found_nodes = anaconda.id.storage.iscsi.discover(**discovery_dict)
                step = STEP_NODES
            elif step == STEP_NODES:
                if not found_nodes:
                    log.debug("iscsi: no iSCSI nodes to log in")
                    anaconda.intf.messageWindow(_("iSCSI Nodes"), 
                                                _("No iSCSI nodes to log in"))
                    break
                (rc, selected_nodes) = wizard.display_nodes_dialog(found_nodes,
                                                                  anaconda.id.storage.iscsi.ifaces)
                if not rc or len(selected_nodes) == 0:
                    break
                step = STEP_LOGIN
            elif step == STEP_LOGIN:
                rc = wizard.display_login_dialog()
                if not rc:
                    break
                login_dict = wizard.get_login_dict()
                login_dict["intf"] = anaconda.intf
                login_fail_nodes = []
                login_fail_msg = ""
                for node in selected_nodes:
                    (rc, msg) = anaconda.id.storage.iscsi.log_into_node(node,
                                                                     **login_dict)
                    if rc:
                        login_ok_nodes.append(node)
                    else:
                        login_fail_nodes.append(node)
                    if msg:
                        # only remember the last message:
                        login_fail_msg = msg
                step = STEP_SUMMARY
            elif step == STEP_SUMMARY:
                rc = wizard.display_success_dialog(login_ok_nodes, 
                                                   login_fail_nodes,
                                                   login_fail_msg,
                                                   anaconda.id.storage.iscsi.ifaces)
                if rc:
                    step = STEP_STABILIZE
                else:
                    # user wants to try logging into the failed nodes again
                    found_nodes = login_fail_nodes
                    step = STEP_NODES
            elif step == STEP_STABILIZE:
                anaconda.id.storage.iscsi.stabilize(anaconda.intf)
                step = STEP_DONE

        except (network.IPMissing, network.IPError) as msg:
            log.info("addIscsiDrive() cancelled due to an invalid IP address.")
            anaconda.intf.messageWindow(_("iSCSI Error"), msg)
            if step != STEP_DISCOVERY:
                break
        except (ValueError, IOError) as e:
            log.info("addIscsiDrive() IOError exception: %s" % e)
            step_str = _("Discovery") if step == STEP_DISCOVERY else _("Login")
            anaconda.intf.messageWindow(_("iSCSI %s Error") % step_str, str(e))
            break

    wizard.destroy_dialogs()
    
    return login_ok_nodes
