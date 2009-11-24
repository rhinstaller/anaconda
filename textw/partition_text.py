#
# partition_text.py: allows the user to choose how to partition their disks
# in text mode
#
# Jeremy Katz <katzj@redhat.com>
#
# Copyright 2001-2006 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import os, sys
import isys
import string
import copy
import network
import parted
from partitioning import *
from partedUtils import *
from partIntfHelpers import *
from partRequests import *
from fsset import *
from raid import availRaidLevels
from autopart import *
from snack import *
from constants_text import *
from constants import *

from rhpl.translate import _

import logging
log = logging.getLogger("anaconda")

# sanity checking for various numeric input boxes
def invalidInteger(str):
    ints = string.digits
    if str == "":
        return _("Must specify a value")
    for n in str:
        if n not in ints:
            return _("Requested value is not an integer")
    if len(str) > 9:
        return _("Requested value is too large")

    return None

class PartitionWindow:
    def populate(self):
        # XXX we really should separate this stuff out into interface
        # independent bits...
        self.lb.clear()

	# first do LVM
        lvmrequests = self.partitions.getLVMRequests()
        if lvmrequests:
            for vgname in lvmrequests.keys():
		vgrequest = self.partitions.getRequestByVolumeGroupName(vgname)
		size = vgrequest.getActualSize(self.partitions, self.diskset)
		device = "VG %s" % (vgname,)
                self.lb.append(["%s" % (device,),
                                "", "", "%dM" %(size),
                                "VolGroup", ""], str(vgrequest.uniqueID),
                               [LEFT, RIGHT, RIGHT, RIGHT, LEFT, LEFT])
		
		for lvrequest in lvmrequests[vgname]:
		    lvdevice = "LV %s" % (lvrequest.logicalVolumeName,)
		    if lvrequest.fstype and lvrequest.mountpoint:
			mntpt = lvrequest.mountpoint
		    else:
			mntpt = ""
		    lvsize = lvrequest.getActualSize(self.partitions, self.diskset)
                    ptype = lvrequest.fstype.getName()
		    self.lb.append(["%s" %(lvdevice),
				    "", "", "%dM" %(lvsize),
				    "%s" %(ptype), "%s" %(mntpt)], str(lvrequest.uniqueID),
				   [LEFT, RIGHT, RIGHT, RIGHT, LEFT, LEFT])


        # next, add the raid partitions
        raidcounter = 0
        raidrequests = self.partitions.getRaidRequests()
        if raidrequests:
            for request in raidrequests:
                if request and request.mountpoint:
                    mount = request.mountpoint
                else:
                    mount = ""

                if request.fstype:
                    ptype = request.fstype.getName()
                else:
                    ptype = _("None")

		try:
		    device = "/dev/md%d" % (request.raidminor,)
		except:
		    device = _("RAID Device %s" %(str(raidcounter)))
		    
                size = request.size
                self.lb.append(["%s" %(device),
                                "", "", "%dM" %(size),
                                "%s" %(ptype), "%s" %(mount)], str(request.uniqueID),
                               [LEFT, RIGHT, RIGHT, RIGHT, LEFT, LEFT])
                raidcounter = raidcounter + 1
        

        # next, add the drives and partitions to the list
        drives = self.diskset.disks.keys()
        drives.sort()
        for drive in drives:
            disk = self.diskset.disks[drive]
            sectorsPerCyl = disk.dev.heads * disk.dev.sectors

            self.lb.append([devify(drive),"","","","",""], None)

            extendedParent = None
            part = disk.next_partition()
            while part:
                if part.type & parted.PARTITION_METADATA:
#                    print "partition %s has type %d" %(get_partition_name(part), part.type)
                    part = disk.next_partition(part)
                    continue
                # ignore the tiny < 1 MB partitions (#119479)
                if getPartSizeMB(part) <= 1.0:
                    if not part.is_active() or not part.get_flag(parted.PARTITION_BOOT):
                        part = disk.next_partition(part)                    
                        continue

                device = get_partition_name(part)
                request = self.partitions.getRequestByDeviceName(device)
                if request and request.mountpoint:
                    mount = request.mountpoint
                else:
                    mount = ""

                if part.type & parted.PARTITION_FREESPACE:
                    ptype = _("Free space")
                elif part.type & parted.PARTITION_EXTENDED:
                    ptype = _("Extended")
                elif part.get_flag(parted.PARTITION_RAID) == 1:
                    ptype = _("software RAID")
                elif part.fs_type:
                    if request and request.fstype != None:
                        ptype = request.fstype.getName()
                        if ptype == "foreign":
                            ptype = map_foreign_to_fsname(part.native_type)
                    else:
                        ptype = part.fs_type.name
                else:
                    if request and request.fstype != None:
                        ptype = request.fstype.getName()
                        if ptype == "foreign":
                            ptype = map_foreign_to_fsname(part.native_type)
                    else:
                        ptype = _("None")

                start = (part.geom.start / sectorsPerCyl) + 1
                end = (part.geom.end / sectorsPerCyl) + 1
                size = (part.geom.length * disk.dev.sector_size / (1024.0 * 1024.0))

                if part.type & parted.PARTITION_EXTENDED:
                    if extendedParent:
                        raise RuntimeError, ("can't handle more than"
                                             "one extended partition per disk")
                    extendedParent = part.num
                    indent = 2 * " "
                elif part.type & parted.PARTITION_LOGICAL:
                    if not extendedParent:
                        raise RuntimeError("crossed logical partition "
                                           "before extended")
                    indent = 4 * " "
                else:
                    indent = 2 * " "

                if part.type & parted.PARTITION_FREESPACE:
                    self.lb.append(["%s%s" %(indent, _("Free space")),
                                    "%d" %(start),
                                    "%d" %(end),
                                    "%dM" %(size),
                                    "%s" %(ptype),
                                    ""], part,
                                   [LEFT, RIGHT, RIGHT, RIGHT, LEFT, LEFT])
                                    
                else:
                    dev = devify(get_partition_name(part))
                    # save some space per #90838
                    if dev.startswith("/dev/iseries/"):
                        dev = dev[13:]
                    elif dev.startswith("/dev/"):
                        dev = dev[5:]
                    self.lb.append(["%s%s" %(indent, dev),
                                    "%d" %(start),
                                    "%d" %(end),
                                    "%dM" %(size),
                                    "%s" %(ptype),
                                    "%s" %(mount)], part,
                                   [LEFT, RIGHT, RIGHT, RIGHT, LEFT, LEFT])
                part = disk.next_partition(part)

    def refresh(self):
        # XXX need some way to stay at the same place in the list after
        # repopulating

	# XXXX - Backup some info which doPartitioning munges if it fails
	origInfoDict = {}
	for request in self.partitions.requests:
	    try:
		origInfoDict[request.uniqueID] = (request.requestSize, request.currentDrive)
	    except:
		pass

        try:
            doPartitioning(self.diskset, self.partitions)
            rc = 0
        except PartitioningError, msg:
	    try:
		for request in self.partitions.requests:
		    if request.uniqueID in origInfoDict.keys():
			(request.requestSize, request.currentDrive) = origInfoDict[request.uniqueID]
	    except:
		log.error("Failed to restore original info")

            self.intf.messageWindow(_("Error Partitioning"),
                   _("Could not allocate requested partitions: %s.") % (msg))
            rc = -1
        except PartitioningWarning, msg:
            rc = ButtonChoiceWindow(self.screen, _("Warning"), _("Warning: %s") %(msg),
                                    buttons = [ (_("Modify Partition"), "modify"), (_("Add anyway"), "add") ])

            if rc == "modify":
                rc = -1
            else:
                rc = 0
                reqs = self.partitions.getBootableRequest()
                if reqs:
                    for req in reqs:
                        req.ignoreBootConstraints = 1                
                             
        self.populate()
        return rc


    def fstypeSet(self, obj):
        (current, entry) = obj
        flag = FLAGS_RESET
        if not current.isMountable():
            if entry.value() != _("<Not Applicable>"):
                self.oldMount = entry.value()
            entry.set(_("<Not Applicable>"))
            flag = FLAGS_SET
        elif entry.value() == _("<Not Applicable>"):
            if self.oldMount:
                entry.set(self.oldMount)
            else:
                entry.set("")

        entry.setFlags(FLAG_DISABLED, flag)

    def fstypeSetCB(self, obj):
        (listbox, entry) = obj
        self.fstypeSet((listbox.current(), entry))

    # make the entry for the mount point and its label
    def makeMountEntry(self, request):
        mountgrid = Grid(2, 1)
        mountLbl = Label(_("Mount Point:"))
        mountgrid.setField(mountLbl, 0, 0, (0,0,0,0), anchorLeft = 1)
        mountpoint = request.mountpoint
        if mountpoint:
            mount = Entry(20, mountpoint)
        else:
            mount = Entry(20, "")
        mountgrid.setField(mount, 1, 0, anchorRight = 1, growx = 1)
        if request.fstype and not request.fstype.isMountable():
            mount.setFlags(FLAG_DISABLED, FLAGS_SET)
            mount.set(_("<Not Applicable>"))
        return (mount, mountgrid)

    # make the entry for the lv name and it's label
    def makeLVNameEntry(self, request):
        lvnamegrid = Grid(2, 1)
        lvnameLbl = Label(_("Logical Volume Name:"))
        lvnamegrid.setField(lvnameLbl, 0, 0, (0,0,0,0), anchorLeft = 1)
        lvn = request.logicalVolumeName
        if lvn:
            lvname = Entry(20, lvn)
        else:
            lvname = Entry(20, "")
        lvnamegrid.setField(lvname, 1, 0, anchorRight = 1, growx = 1)
        if request.preexist:
            lvname.setFlags(FLAG_DISABLED, FLAGS_SET)
        return (lvname, lvnamegrid)

    # make the size entry for a logical volume
    def makeLVSize(self, request):
        grid = Grid(3, 1)
        lbl = Label(_("Size (MB):"))
        grid.setField(lbl, 0, 0, (0,0,0,0), anchorLeft = 1)
        if request.size:
            size = Entry(8, "%d" %(request.size,))
        else:
            size = Entry(8, "")
        grid.setField(size, 1, 0, anchorRight = 1, growx = 1)
#        maxLbl = Label(_("(Max is %s MB") %(maxlv,))
#        grid.setField(maxLbl, 2, 0, anchorRight = 1)
        if request.preexist:
            size.setFlags(FLAG_DISABLED, FLAGS_SET)
        return (size, grid)


    # make the list of available filesystems and its label
    def makeFsList(self, request, usecallback=1, uselabel=1, usetypes=None,
                   ignorefs = None):
        subgrid = Grid(1, 2)
        row = 0
        # filesystem type selection
        if uselabel:
            typeLbl = Label(_("File System type:"))
            subgrid.setField(typeLbl, 0, row)
            row = row + 1
            
        fstype = Listbox(height=2, scroll=1)
        types = fileSystemTypeGetTypes()
        if usetypes:
            names = usetypes
        else:
            names = types.keys()
        names.sort()
        for name in names:
            if not fileSystemTypeGet(name).isSupported():
                continue

            if ignorefs and name in ignorefs:
                continue

            if fileSystemTypeGet(name).isFormattable():
                fstype.append(name, types[name])
        if request.fstype and request.fstype.getName() in names and \
           request.fstype.isFormattable() and request.fstype.isSupported():
            fstype.setCurrent(request.fstype)
        else:
            fstype.setCurrent(fileSystemTypeGetDefault())
        subgrid.setField(fstype, 0, row)
        if usecallback:
            fstype.setCallback(self.fstypeSetCB, (fstype, self.mount))
        return (fstype, subgrid)


    # make the list of drives
    def makeDriveList(self, request):
        subgrid = Grid(1, 2)
        driveLbl = Label(_("Allowable Drives:"))
        subgrid.setField(driveLbl, 0, 0)
        disks = self.diskset.disks.keys()
        disks.sort()
        drivelist = CheckboxTree(height=2, scroll=1)
        if not request.drive:
            for disk in disks:
                drivelist.append(disk, selected = 1)
        else:
            for disk in disks:
                if disk in request.drive:
                    selected = 1
                else:
                    selected = 0
                drivelist.append(disk, selected = selected)
        subgrid.setField(drivelist, 0, 1)
        return (drivelist, subgrid)


    def makeSizeEntry(self, request):
        # requested size
        sizegrid = Grid(2, 1)
        sizeLbl = Label(_("Size (MB):"))
        sizegrid.setField(sizeLbl, 0, 0, (0,0,2,0))
        if request.size:
            origsize = "%s" %(int(request.size))
        else:
            origsize = "1"
        size = Entry(7, origsize)
        sizegrid.setField(size, 1, 0, growx = 1, anchorLeft = 1)
        return (size, sizegrid)


    def sizeOptionsChange(self, (sizeopts, limitentry)):
        flag = FLAGS_RESET
        if sizeopts.getSelection() != "limit":
            flag = FLAGS_SET
        limitentry.setFlags(FLAG_DISABLED, flag)


    def makeSizeOptions(self, request):
        # size options
        optiongrid = Grid(2, 3)
        sizeopts = RadioGroup()
        limitdef = 0
        maxdef = 0
        fixeddef = 0
        limitentrydef = "1"
        if request.grow:
            if request.maxSizeMB != None:
                limitdef = 1
                limitentrydef = "%s" %(int(request.maxSizeMB))
            else:
                maxdef = 1
        else:
            fixeddef = 1
        fixed = sizeopts.add(_("Fixed Size:"), "fixed", fixeddef)
        optiongrid.setField(fixed, 0, 0, anchorRight = 1)
        limit = sizeopts.add(_("Fill maximum size of (MB):"), "limit", limitdef)
        optiongrid.setField(limit, 0, 1, anchorRight = 1)
        limitentry = Entry(5, limitentrydef)
        optiongrid.setField(limitentry, 1, 1, (1,0,0,0), anchorRight = 1)
        max = sizeopts.add(_("Fill all available space:"), "max", maxdef)
        optiongrid.setField(max, 0, 2, anchorRight = 1)
        fixed.setCallback(self.sizeOptionsChange, (sizeopts, limitentry))
        limit.setCallback(self.sizeOptionsChange, (sizeopts, limitentry))
        max.setCallback(self.sizeOptionsChange, (sizeopts, limitentry))
        self.sizeOptionsChange((sizeopts, limitentry))
        return (sizeopts, limitentry, optiongrid)


    # the selected cylinder boundary type changed
    def cylOptionsChange(self, (cylopts, end, size)):
        if cylopts.getSelection() == "end":
            end.setFlags(FLAG_DISABLED, FLAGS_RESET)
            size.setFlags(FLAG_DISABLED, FLAGS_SET)
        elif cylopts.getSelection() == "size":
            end.setFlags(FLAG_DISABLED, FLAGS_SET)            
            size.setFlags(FLAG_DISABLED, FLAGS_RESET)


    # make the list of cylinder stuff
    def makeCylEntries(self, request):
        subgrid = Grid(2, 4)

        startLbl = Label(_("Start Cylinder:"))
        subgrid.setField(startLbl, 0, 0, (0,0,2,0), anchorRight=1)
        start = "%s" %(int(request.start))
        start = Entry(7, start)
        subgrid.setField(start, 1, 0, anchorLeft=1)

        cylopts = RadioGroup()
        enddef = 1
        sizedef = 0
        if not request.end:
            enddef = 0
            sizedef = 1

        endrb = cylopts.add(_("End Cylinder:"), "end", enddef)
        subgrid.setField(endrb, 0, 1, (0,0,2,0), anchorRight=1)
        end = Entry(7)
        if request.end:
            end.set("%s" %(int(request.end)))
        subgrid.setField(end, 1, 1, anchorLeft=1)

        sizerb = cylopts.add(_("Size (MB):"), "size", sizedef)
        subgrid.setField(sizerb, 0, 2, (0,0,2,0), anchorRight=1)
        size = Entry(7)
        if request.size:
            size.set("%s" %(int(request.size)))
        subgrid.setField(size, 1, 2, anchorLeft=1)

        endrb.setCallback(self.cylOptionsChange, (cylopts, end, size))
        sizerb.setCallback(self.cylOptionsChange, (cylopts, end, size))
        self.cylOptionsChange((cylopts, end, size))
        
        return (cylopts, start, end, size, subgrid)

    # make the list of VGs
    def makeVGList(self, request):
        subgrid = Grid(1, 2)
        vgLbl = Label(_("Volume Group:"))
        subgrid.setField(vgLbl, 0, 0)
        vgs = self.partitions.getLVMVGRequests()
        if len(vgs) > 3:
            scroll = 1
        else:
            scroll = 0
        vgBox = Listbox(height=3, scroll=scroll)
        current = None
        for vg in vgs:
            vgBox.append(vg.volumeGroupName, vg)
            if vg.uniqueID == request.volumeGroup:
                current = vg
        if request.volumeGroup is not None:
            vgBox.setCurrent(current)

        subgrid.setField(vgBox, 0, 1)
        return (vgBox, subgrid)
        
    # make the list of RAID levels
    def makeRaidList(self, request):
        subgrid = Grid(1, 2)
        raidLbl = Label(_("RAID Level:"))
        subgrid.setField(raidLbl, 0, 0)
        if len(availRaidLevels) > 3:
            scroll = 1
        else:
            scroll = 0
        raidBox = Listbox(height=3, scroll=scroll)
        for level in availRaidLevels:
            raidBox.append(level, level)
        if request.raidlevel:
            raidBox.setCurrent(request.raidlevel)
        subgrid.setField(raidBox, 0, 1)
        return (raidBox, subgrid)


    # make the list of drives for the RAID
    def makeRaidDriveList(self, request):
        subgrid = Grid(1, 2)
        driveLbl = Label(_("RAID Members:"))
        subgrid.setField(driveLbl, 0, 0)
        disks = self.diskset.disks.keys()
        drivelist = CheckboxTree(height=2, scroll=1)
        avail = self.partitions.getAvailRaidPartitions(request, self.diskset)

        # XXX
        if not request.raidmembers:
            for (part, size, used) in avail:
                drivelist.append(part, part, 1)
        else:
            for (part, size, used) in avail:
                drivelist.append(part, part, used)
        subgrid.setField(drivelist, 0, 1)
        return (drivelist, subgrid)


    def makeSpareEntry(self, request):
        subgrid = Grid(2, 1)
        label = Label(_("Number of spares?"))
        subgrid.setField(label, 1, 0)
        entry = Entry(3)
        if request.raidspares:
            entry.set(str(request.raidspares))
        else:
            entry.set("0")
        subgrid.setField(entry, 0, 0, (0,0,1,0))
        return (entry, subgrid)

    def fsOptionsGrid(self, origrequest, newfstype):
	subgrid = Grid(2, 4)
	# filesystem type selection
	srow = 0
	typeLbl = Label(_("File System Type:"))
	subgrid.setField(typeLbl, 0, srow, (0,0,0,1), anchorLeft = 1)
	ptype = origrequest.fstype.getName()
	if ptype == "foreign":
	    part = get_partition_by_name(self.diskset.disks, origrequest.device)
            if part is not None:
                ptype = map_foreign_to_fsname(part.native_type)
            else:
                pytype = _("Foreign")
	type = Label(ptype)
	subgrid.setField(type, 1, srow, (0,0,0,1), anchorRight = 1)
	srow = srow +1
	if origrequest.type != REQUEST_NEW and origrequest.fslabel:
	    fsLbl = Label(_("File System Label:"))
	    subgrid.setField(fsLbl, 0, srow, (0,0,0,1), anchorLeft = 1)
	    label = Label(origrequest.fslabel)
	    subgrid.setField(label, 1, srow, (0,0,0,1), anchorRight = 1)
	    srow = srow + 1

	sizeLbl = Label(_("Size (MB):"))
	subgrid.setField(sizeLbl, 0, srow, (0,0,0,1), anchorLeft = 1)
	size = Label("%s" %(int(origrequest.size)))
	subgrid.setField(size, 1, srow, (0,0,0,1), anchorRight = 1)
	srow = srow + 1
	tmpLbl = Label(_("File System Option:"))
	subgrid.setField(tmpLbl, 0, srow, (0,0,0,1), anchorLeft = 1)
	if origrequest.format:
	    fsoptLbl = Label(_("Format as %s") % (newfstype.getName()))
	elif origrequest.migrate:
	    fsoptLbl = Label(_("Migrate to %s") %(newfstype.getName()))
	else:
	    fsoptLbl = Label(_("Leave unchanged"))
	subgrid.setField(fsoptLbl, 1, srow, (0,0,0,1), anchorLeft = 1)

	return (subgrid, fsoptLbl, type)
	

    def fsOptionsDialog(self, origrequest, format, migrate, newfstype, badblocks, showbadblocks=0):

        def formatChanged((formatrb, badblocksCB)):
            flag = FLAGS_SET
            if formatrb.selected():
                flag = FLAGS_RESET

	    if badblocksCB:
		badblocksCB.setFlags(FLAG_DISABLED, flag)

        poplevel = GridFormHelp(self.screen, _("File System Options"),
                                "fsoption", 1, 6)
        row = 0
        poplevel.add(TextboxReflowed(40, _("Please choose how you would "
                                           "like to prepare the file system "
                                           "on this partition.")), 0, 0)
        row = row + 1
        subgrid = Grid(2, 5)
        srow = 0

	if showbadblocks:
	    badblocksCB = Checkbox(_("Check for bad blocks"))
	else:
	    badblocksCB = None
        
        noformatrb = SingleRadioButton(_("Leave unchanged (preserve data)"),
                                       None, not format and not migrate)
        subgrid.setField(noformatrb, 0, srow, (0,0,0,1),anchorLeft = 1)
        
        srow = srow + 1
        if format:
            forflag = 1
        else:
            forflag = 0
        formatrb = SingleRadioButton(_("Format as:"), noformatrb, forflag)
        formatrb.setCallback(formatChanged, (formatrb, badblocksCB))
        noformatrb.setCallback(formatChanged, (formatrb, badblocksCB))        
       
        subgrid.setField(formatrb, 0, srow, (0,0,0,1), anchorLeft = 1)

        (fortype, forgrid) = self.makeFsList(origrequest, usecallback = 0,
                                             uselabel = 0)
        if newfstype and newfstype.isFormattable() and \
           newfstype.getName() in fileSystemTypeGetTypes().keys() and \
           newfstype.isSupported():
            fortype.setCurrent(newfstype)
        subgrid.setField(forgrid, 1, srow, (0,0,0,1))

        if origrequest.origfstype and origrequest.origfstype.isMigratable():
            srow = srow + 1
            if migrate:
                migflag = 1
            else:
                migflag = 0
            migraterb = SingleRadioButton(_("Migrate to:"), formatrb, migflag)
            migraterb.setCallback(formatChanged, (formatrb, badblocksCB))
            subgrid.setField(migraterb, 0, srow, (0,0,0,1), anchorLeft = 1)
            
            migtypes = origrequest.origfstype.getMigratableFSTargets()

            (migtype, miggrid) = self.makeFsList(origrequest, usecallback = 0,
                                                 uselabel = 0,
                                                 usetypes = migtypes)
                                                 
            if newfstype and newfstype.getName() in migtypes:
                migtype.setCurrent(newfstype)
            subgrid.setField(miggrid, 1, srow, (0,0,0,1))
        else:
            migraterb = None
            
        poplevel.add(subgrid, 0, row, (0,1,0,1))

        row = row + 1

	if badblocksCB:
	    poplevel.add(badblocksCB, 0, row, (0,1,0,1))
	    if badblocks:
		badblocksCB.setValue("*")
	    row = row + 1

        formatChanged((formatrb, badblocksCB))        
        
        popbb = ButtonBar(self.screen, (TEXT_OK_BUTTON, TEXT_CANCEL_BUTTON))
        poplevel.add(popbb, 0, row, (0,0,0,0), growx = 1)        

        while 1:
            res = poplevel.run()

            if popbb.buttonPressed(res) == 'cancel':
                self.screen.popWindow()
                return (format, migrate, newfstype, badblocks)

            if noformatrb.selected():
                format = 0
                migrate = 0
                newfstype = origrequest.origfstype
            elif formatrb and formatrb.selected():
                format = 1
                migrate = 0
                newfstype = fortype.current()
            elif migraterb and migraterb.selected():
                format = 0
                migrate = 1
                newfstype = migtype.current()

            self.screen.popWindow()

	    if badblocksCB:
		badblockstate = badblocksCB.selected()
	    else:
		badblockstate = 0
            return (format, migrate, newfstype, badblockstate)
        
    def shutdownUI(self):
        # XXX remove parted object refs
        #     need to put in clear() method for checkboxtree in snack
        if self.drivelist:
            self.drivelist.key2item = {}
            self.drivelist.item2key = {}

    # isNew implies that this request has never been successfully used before
    def editPartitionRequest(self, origrequest, isNew = 0):
        self.oldMount = None
        
        poplevel = GridFormHelp(self.screen,_("Add Partition"),"addpart", 1, 6)

        # mount point entry
        row = 0
        (self.mount, mountgrid) = self.makeMountEntry(origrequest)
        poplevel.add(mountgrid, 0, row)

        row = row + 1

        self.drivelist = None
        if origrequest.type == REQUEST_NEW:
            subgrid = Grid(2, 1)
            (fstype, fsgrid) = self.makeFsList(origrequest)
            subgrid.setField(fsgrid, 0, 0, anchorLeft = 1, anchorTop=1)

            if origrequest.start == None:
                (self.drivelist, drivegrid) = self.makeDriveList(origrequest)
                subgrid.setField(drivegrid, 1, 0, (2,0,0,0), anchorRight=1, anchorTop=1)
                poplevel.add(subgrid, 0, row, (0,1,0,0), growx=1)

                # size stuff
                row = row + 1

                allsize = Grid(2, 1)
                (size, sizegrid) = self.makeSizeEntry(origrequest)
                allsize.setField(sizegrid, 0, 0, anchorTop = 1)

                (sizeopts, limitentry, optiongrid) = self.makeSizeOptions(origrequest)
                allsize.setField(optiongrid, 1, 0)

                poplevel.add(allsize, 0, row, (0,1,0,0), growx=1)
            else: # explicit add via cylinder
                poplevel.add(subgrid, 0, row, (0,1,0,0))

                row = row + 1
                (cylopts, start, end, size, cylgrid) = self.makeCylEntries(origrequest)
                poplevel.add(cylgrid, 0, row, (0,1,0,0))
                

            # primary
            # XXX need to see if cylinder range is in extended or not
            row = row + 1
            primary = Checkbox(_("Force to be a primary partition"))
            # only show if we have something other than primary
            if not self.diskset.onlyPrimaryParts():
                poplevel.add(primary, 0, row, (0,1,0,0))
                row = row + 1

	    # XXX We are not allowing badblocks checking
	    badblocksCB = None
	    # uncomment code to reactivate
            #badblocksCB = Checkbox(_("Check for bad blocks"))
            #poplevel.add(badblocksCB, 0, row)
            #if origrequest.badblocks:
	    #     badblocksCB.setValue("*")

            fsoptLbl = None

	elif origrequest.type == REQUEST_VG:
	    self.intf.messageWindow(_("Not Supported"),
				    _("LVM Volume Groups can only be "
				      "edited in the graphical installer."))
	    return

        elif (origrequest.type == REQUEST_LV or origrequest.type == REQUEST_PREEXIST) and origrequest.fstype:

            # set some defaults
            format = origrequest.format
            migrate = origrequest.migrate
            newfstype = origrequest.fstype
            badblocks = origrequest.badblocks

            (subgrid, fsoptLbl, fstypeLbl) = self.fsOptionsGrid(origrequest, newfstype)
            poplevel.add(subgrid, 0, row, (0,1,0,0))


        row = row + 1
        if origrequest.type == REQUEST_NEW or origrequest.getProtected():
            popbb = ButtonBar(self.screen, (TEXT_OK_BUTTON, TEXT_CANCEL_BUTTON))
        else:
            popbb = ButtonBar(self.screen, (TEXT_OK_BUTTON,
                                            (_("File System Options"), "fsopts"),
                                            TEXT_CANCEL_BUTTON))
        poplevel.add(popbb, 0, row, (0,1,0,0), growx = 1)

        while 1:
            
            res = poplevel.run()

            # if the user hit cancel, do nothing
            if popbb.buttonPressed(res) == 'cancel':
                self.screen.popWindow()
                return

            if popbb.buttonPressed(res) == 'fsopts':
		# we do not show the badblock option any longer as it is
		# not supported.
		showbad = 0
                (format, migrate, newfstype, badblocks) = self.fsOptionsDialog(origrequest, format, migrate, newfstype, badblocks, showbadblocks = showbad)
                self.fstypeSet((newfstype, self.mount))
                fstypeLbl.setText(newfstype.getName())

                if fsoptLbl:
                    if format:
                        fsoptLbl.setText(_("Format as %s") % (newfstype.getName()))
                    elif migrate:
                        fsoptLbl.setText(_("Migrate to %s") %(newfstype.getName()))
                    else:
                        fsoptLbl.setText(_("Leave unchanged"))
                
                continue

            if origrequest.type == REQUEST_NEW:
                filesystem = fstype.current()

                if primary.selected():
                    primonly = TRUE
                else:
                    primonly = None

                request = copy.copy(origrequest)
                request.fstype = filesystem
                if request.fstype.isMountable():
                    request.mountpoint = self.mount.value()
                else:
                    request.mountpoint = None
                request.format = TRUE
                request.primary = primonly

		if badblocksCB is not None:
		    request.badblocks = badblocksCB.selected()
		else:
		    request.badblocks = 0

                if origrequest.start == None:
                    if invalidInteger(size.value()):
                        self.intf.messageWindow(_("Invalid Entry for Partition Size"),
                                                invalidInteger(size.value()))
                        continue
                    request.size = int(size.value())
                
                    growtype = sizeopts.getSelection()
                    if growtype == "fixed":
                        grow = None
                    else:
                        grow = TRUE
                    if growtype == "limit":
                        if invalidInteger(limitentry.value()):
                            self.intf.messageWindow(_("Invalid Entry for Maximum Size"),
                                           invalidInteger(limitentry.value()))
                            continue
                            
                        maxsize = int(limitentry.value())
                    else:
                        maxsize = None
                    request.grow = grow
                    request.maxSizeMB = maxsize

                    if len(self.drivelist.getSelection()) == len(self.diskset.disks.keys()):
                        allowdrives = None
                    else:
                        allowdrives = []
                        for i in self.drivelist.getSelection():
                            allowdrives.append(i) 
                    request.drive = allowdrives
                else:
                    if invalidInteger(start.value()):
                        self.intf.messageWindow(_("Invalid Entry for Starting Cylinder"),
                                           invalidInteger(start.value()))
                        continue
                    
                    request.start = int(start.value())

		    if badblocksCB is not None:
			request.badblocks = badblocksCB.selected()
		    else:
			request.badblocks = 0

                    cyltype = cylopts.getSelection()
                    if cyltype == "end":
                        if invalidInteger(end.value()):
                            self.intf.messageWindow(_("Invalid Entry for End Cylinder"),
                                           invalidInteger(end.value()))
                            continue
                        
                        request.end = int(end.value())
                        request.size = None
                    elif cyltype == "size":
                        if invalidInteger(size.value()):
                            self.intf.messageWindow(_("Invalid Entry for Partition Size"),
                                           invalidInteger(size.value()))
                            continue
                        request.end = None
                        request.size = int(size.value())
                    else: # can't ever get here
                        raise RuntimeError, "Selected a way of partitioning by cylinder that's not supported"
                    
                err = request.sanityCheckRequest(self.partitions)
                if err:
                    self.intf.messageWindow(_("Error With Request"),
                                            "%s" % (err))
                    continue
            else:
                request = copy.copy(origrequest)

                if request.type == REQUEST_PREEXIST or request.type == REQUEST_LV:
                    request.fstype = newfstype
                    
                if request.fstype.isMountable():
                    request.mountpoint = self.mount.value()
                else:
                    request.mountpoint = None

                if request.type == REQUEST_PREEXIST or request.type == REQUEST_LV:
                    request.format = format
                    request.migrate = migrate
                    request.fstype = newfstype
                    request.badblocks = badblocks

                err = request.sanityCheckRequest(self.partitions)
                if err:
                    self.intf.messageWindow(_("Error With Request"),
                                            "%s" % (err))
                    continue

                if (not request.format and request.mountpoint
                    and request.formatByDefault()):
                    if not queryNoFormatPreExisting(self.intf):
                        continue

            if not isNew:
                self.partitions.removeRequest(origrequest)

            self.partitions.addRequest(request)
            if self.refresh():
                # the add failed; remove what we just added and put
                # back what was there if we removed it
                self.partitions.removeRequest(request)
                if not isNew:
                    self.partitions.addRequest(origrequest)
                if self.refresh():
                    # this worked before and doesn't now...
                    raise RuntimeError, "Returning partitions to state prior to edit failed"
            else:
                break

        # clean up
        self.shutdownUI()
        self.screen.popWindow()

    # isNew implies that this request has never been successfully used before
    def editRaidRequest(self, raidrequest, isNew = 0):
	preexist = raidrequest and raidrequest.preexist
	if preexist:
	    tmpstr = _("Edit RAID Device")
	else:
	    tmpstr = _("Make RAID Device")
        poplevel = GridFormHelp(self.screen, tmpstr, "makeraid", 1, 6)

        # mount point entry
        row = 0
        (self.mount, mountgrid) = self.makeMountEntry(raidrequest)
        poplevel.add(mountgrid, 0, row)
        row = row + 1

	# initialize holder for temporary mount point value
	self.oldMount = None

	if preexist:
            # set some defaults
            format = raidrequest.format
            migrate = raidrequest.migrate
            newfstype = raidrequest.fstype
            badblocks = raidrequest.badblocks

            (subgrid, fsoptLbl, fstypeLbl) = self.fsOptionsGrid(raidrequest, newfstype)
            poplevel.add(subgrid, 0, row, (0,1,0,0))
	    self.drivelist = None
	else:
	    subgrid = Grid(2, 1)
	    (fstype, fsgrid) = self.makeFsList(raidrequest, ignorefs = ["software RAID", "PPC PReP Boot", "Apple Bootstrap"])
	    subgrid.setField(fsgrid, 0, 0, anchorLeft = 1, anchorTop=1)
	    (raidtype, raidgrid) = self.makeRaidList(raidrequest)
	    subgrid.setField(raidgrid, 1, 0, (2,0,0,0), anchorRight=1, anchorTop=1)
	    poplevel.add(subgrid, 0, row, (0,1,0,0))

	    row = row + 1
	    drivegrid = Grid(2, 1)

	    #Let's see if we have any RAID partitions to make a RAID device with
	    avail = self.partitions.getAvailRaidPartitions(raidrequest, self.diskset)

	    #If we don't, then tell the user that none exist
	    if len(avail) < 2:
		ButtonChoiceWindow (self.screen, _("No RAID partitions"),
				    _("At least two software RAID partitions are needed."),
				    [ TEXT_OK_BUTTON ])
		return

	    (self.drivelist, drivesubgrid) = self.makeRaidDriveList(raidrequest)
	    drivegrid.setField(drivesubgrid, 0, 0, (0,0,4,0), anchorLeft = 1, anchorTop = 1)

	    miscgrid = Grid(1, 2)
	    (spares, sparegrid) = self.makeSpareEntry(raidrequest)
	    miscgrid.setField(sparegrid, 0, 0, anchorRight=1, anchorTop=1)

	    if raidrequest.fstype and raidrequest.fstype.isFormattable():
		format = Checkbox(_("Format partition?"))
		miscgrid.setField(format, 0, 1)
	    else:
		format = None

	    if raidrequest.format == 1 or raidrequest.format == None:
		format.setValue("*")

	    drivegrid.setField(miscgrid, 1, 0, anchorTop=1)
	    poplevel.add(drivegrid, 0, row, (0,1,0,0))        

        row = row + 1
	if preexist:
            popbb = ButtonBar(self.screen, (TEXT_OK_BUTTON,
                                            (_("File System Options"), "fsopts"),
                                            TEXT_CANCEL_BUTTON))
	else:
	    popbb = ButtonBar(self.screen, (TEXT_OK_BUTTON,TEXT_CANCEL_BUTTON))
        poplevel.add(popbb, 0, row, (0,1,0,0), growx = 1)        

        while 1:
            res = poplevel.run()

            if popbb.buttonPressed(res) == 'cancel':
                self.screen.popWindow()
                return

            if popbb.buttonPressed(res) == 'fsopts':
                (format, migrate, newfstype, badblocks) = self.fsOptionsDialog(raidrequest, format, migrate, newfstype, badblocks, showbadblocks=0)
                self.fstypeSet((newfstype, self.mount))
                fstypeLbl.setText(newfstype.getName())

                if fsoptLbl:
                    if format:
                        fsoptLbl.setText(_("Format as %s") % (newfstype.getName()))
                    elif migrate:
                        fsoptLbl.setText(_("Migrate to %s") %(newfstype.getName()))
                    else:
                        fsoptLbl.setText(_("Leave unchanged"))
                
                continue

            request = copy.copy(raidrequest)

	    if not preexist:
		request.fstype = fstype.current()
	    else:
		request.fstype = newfstype

            if request.fstype.isMountable():
                request.mountpoint = self.mount.value()
            else:
                request.mountpoint = None

	    if not preexist:
		raidmembers = []
		for drive in self.drivelist.getSelection():
		    id = self.partitions.getRequestByDeviceName(drive).uniqueID
		    raidmembers.append(id)

		request.raidmembers = raidmembers
		if invalidInteger(spares.value()):
		    self.intf.messageWindow(_("Invalid Entry for RAID Spares"),
					    invalidInteger(spares.value()))
		    continue

		request.raidspares = int(spares.value())
		request.raidlevel = raidtype.current()

		if format:
		    request.format = format.selected()
		else:
		    request.format = 0

		if request.raidlevel == "RAID0" and request.raidspares > 0:
		    self.intf.messageWindow(_("Too many spares"),
					      _("The maximum number of spares with "
					      "a RAID0 array is 0."))
		    continue
	    else:                
		request.format = format
		request.migrate = migrate
		request.fstype = newfstype
		request.badblocks = badblocks

            err = request.sanityCheckRequest(self.partitions)
            if err:
                self.intf.messageWindow(_("Error With Request"),
                                        "%s" % (err))
                continue

            if not isNew:
                self.partitions.removeRequest(raidrequest)

            self.partitions.addRequest(request)
            
            if self.refresh():
                # how can this fail?  well, if it does, do the remove new,
                # add old back in dance
                self.partitions.removeRequest(request)
                if not isNew:
                    self.partitions.addRequest(raidrequest)
                if self.refresh():
                    raise RuntimeError, "Returning partitions to state prior to RAID edit failed"
            else:
                break

            break

        # clean up
        self.shutdownUI()
        self.screen.popWindow()
        
    # isNew implies that this request has never been successfully used before
    def editLVRequest(self, lvrequest, isNew = 0):
	preexist = lvrequest and lvrequest.preexist
	if preexist:
	    tmpstr = _("Edit Logical Volume")
	else:
	    tmpstr = _("Make Logical Volume")
        self.drivelist = None            
        poplevel = GridFormHelp(self.screen, tmpstr, "makelv", 1, 8)

        # mount point entry
        row = 0
        (self.mount, mountgrid) = self.makeMountEntry(lvrequest)
        poplevel.add(mountgrid, 0, row)
        row = row + 1

        (self.lvname, lvgrid) = self.makeLVNameEntry(lvrequest)
        poplevel.add(lvgrid, 0, row)
        row = row + 1

        (lvsize, lvsizegrid) = self.makeLVSize(lvrequest)
        poplevel.add(lvsizegrid, 0, row)
        row = row + 1

	# initialize holder for temporary mount point value
	self.oldMount = None

	if preexist:
            # set some defaults
            format = lvrequest.format
            migrate = lvrequest.migrate
            newfstype = lvrequest.fstype
            badblocks = lvrequest.badblocks

            (subgrid, fsoptLbl, fstypeLbl) = self.fsOptionsGrid(lvrequest, newfstype)
            poplevel.add(subgrid, 0, row, (0,1,0,0))
	    self.drivelist = None
	else:
	    subgrid = Grid(2, 1)
	    (fstype, fsgrid) = self.makeFsList(lvrequest, ignorefs = ["software RAID", "PPC PReP Boot", "Apple Bootstrap"])
	    subgrid.setField(fsgrid, 0, 0, anchorLeft = 1, anchorTop=1)

            vgs = self.partitions.getLVMVGRequests()
            if len(vgs) < 1:
                ButtonChoiceWindow (self.screen, _("No Volume Groups"),
                                    _("No volume groups in which to create "
                                      "a logical volume"),[ TEXT_OK_BUTTON ])
                return

            (vgtype, vggrid) = self.makeVGList(lvrequest)
	    subgrid.setField(vggrid, 1, 0, (2,0,0,0), anchorRight=1, anchorTop=1)
	    poplevel.add(subgrid, 0, row, (0,1,0,0))

	    row = row + 1

	    miscgrid = Grid(1, 3)

	    if lvrequest.fstype and lvrequest.fstype.isFormattable():
		format = Checkbox(_("Format partition?"))
		miscgrid.setField(format, 0, 1)
	    else:
		format = None

	    if lvrequest.format == 1 or lvrequest.format == None:
		format.setValue("*")

	    poplevel.add(miscgrid, 0, row, (0,1,0,0))        

        row = row + 1
	if preexist:
            popbb = ButtonBar(self.screen, (TEXT_OK_BUTTON,
                                            (_("File System Options"), "fsopts"),
                                            TEXT_CANCEL_BUTTON))
	else:
	    popbb = ButtonBar(self.screen, (TEXT_OK_BUTTON,TEXT_CANCEL_BUTTON))
        poplevel.add(popbb, 0, row, (0,1,0,0), growx = 1)        

        while 1:
            res = poplevel.run()

            if popbb.buttonPressed(res) == 'cancel':
                self.screen.popWindow()
                return

            if popbb.buttonPressed(res) == 'fsopts':
                (format, migrate, newfstype, badblocks) = self.fsOptionsDialog(lvrequest, format, migrate, newfstype, badblocks, showbadblocks=0)
                self.fstypeSet((newfstype, self.mount))
                fstypeLbl.setText(newfstype.getName())

                if fsoptLbl:
                    if format:
                        fsoptLbl.setText(_("Format as %s") % (newfstype.getName()))
                    elif migrate:
                        fsoptLbl.setText(_("Migrate to %s") %(newfstype.getName()))
                    else:
                        fsoptLbl.setText(_("Leave unchanged"))
                
                continue

            request = copy.copy(lvrequest)

	    if not preexist:
		request.fstype = fstype.current()
	    else:
		request.fstype = newfstype

            if request.fstype.isMountable():
                request.mountpoint = self.mount.value()
            else:
                request.mountpoint = None

	    if not preexist:
		if format:
		    request.format = format.selected()
		else:
		    request.format = 0

                # set the vg
                vgreq = vgtype.current()
                request.volumeGroup = vgreq.uniqueID

                if vgreq is None:
                    raise RuntimeError, "Somehow ended up with a None volume group!"

                # get the lv name, check for a "valid" name
                lvn = self.lvname.value().strip()
                err = sanityCheckLogicalVolumeName(lvn)
                if err:
                    self.intf.messageWindow(_("Illegal Logical Volume Name"), err, custom_icon="error")
                    
                    continue

                # make sure we don't have an LV in this volume group by
                # this name already
                used = 0
                origlvname = lvrequest.logicalVolumeName
                for lv in self.partitions.getLVMLVRequests():
                    if origlvname and lvn == origlvname:
                        break
                    if ((lv.logicalVolumeName == lvn) and
                        (lv.volumeGroup == vgreq.uniqueID)):
                        used = 1
                        break

                if used:
                    self.intf.messageWindow(_("Illegal logical volume name"),
                                            _("The logical volume name \"%s\" "
                                              "is already in use. Please "
                                              "pick another.") % (lvn,),
                                            custom_icon="error")
                    continue
                    
                request.logicalVolumeName = lvn

                try:
                    size = int(lvsize.value().strip())
                except:
                    self.intf.messageWindow(_("Illegal size"),
                                            _("The requested size as entered is "
                                              "not a valid number greater "
                                              "than 0."), custom_icon="error")
                    continue
                                            
                pesize = vgreq.pesize
                size = lvm.clampLVSizeRequest(size, pesize, roundup=1)

                maxlv = lvm.getMaxLVSize(pesize)
                if size > lvm.getMaxLVSize(pesize):
                    self.intf.messageWindow(_("Not enough space"),
                                            _("The current requested size "
                                              "(%10.2f MB) is larger than "
                                              "maximum logical volume "
                                              "size (%10.2f MB). ") % (size,
                                                                       maxlv),
                                            custom_icon="error")
                    continue
                    
                vgsize = vgreq.getActualSize(self.partitions, self.diskset)
                avail = vgsize
                for req in self.partitions.requests:
                    if ((req.type == REQUEST_LV) and 
                        (req.volumeGroup == vgreq.uniqueID)):
                        avail -= req.size
                if lvrequest.size:
                    avail += lvrequest.size

                if size > avail:
                    self.intf.messageWindow(_("Not enough space"),
                                            _("The current requested size "
                                              "(%10.2f MB) is larger than "
                                              "the available size in "
                                              "the volume group "
                                              "(%10.2f MB).") %(size, avail),
                                            custom_icon="error")
                    continue

                request.size = size
                request.grow = 0
                request.dev = None
	    else:                
		request.format = format
		request.migrate = migrate
		request.fstype = newfstype
		request.badblocks = badblocks

            err = request.sanityCheckRequest(self.partitions)
            if err:
                self.intf.messageWindow(_("Error With Request"),
                                        "%s" % (err))
                continue

            if not isNew:
                self.partitions.removeRequest(lvrequest)

            self.partitions.addRequest(request)

            if self.refresh():
                # how can this fail?  well, if it does, do the remove new,
                # add old back in dance
                self.partitions.removeRequest(request)
                if not isNew:
                    self.partitions.addRequest(lvrequest)
                if self.refresh():
                    raise RuntimeError, "Returning partitions to state prior to RAID edit failed"
            else:
                break

            break

        # clean up
        self.shutdownUI()
        self.screen.popWindow()

    def newCb(self):
        hasvg = 0
        dolv = 0
        for request in self.partitions.requests:
            if request.type == REQUEST_VG:
                hasvg = 1
                break
        if hasvg:
            rc = ListboxChoiceWindow(self.screen,
                                     _("New Partition or Logical Volume?"),
                                     _("Would you like to create a new "
                                       "partition or a new logical volume?"),
                                     [ _("partition"), _("logical volume") ],
                                     [ TEXT_OK_BUTTON, TEXT_CANCEL_BUTTON ],
                                     width = 30, scroll = 0, height = 2)
            (button, choice) = rc
            if button == TEXT_CANCEL_CHECK:
                return
            if choice == 1:
                dolv = 1

        if not dolv:
            request = NewPartitionSpec(fileSystemTypeGetDefault(), 1)
            self.editPartitionRequest(request, isNew = 1)
        else:
            request = LogicalVolumeRequestSpec(fileSystemTypeGetDefault(),
                                               size=1)
            self.editLVRequest(request, isNew = 1)

    def makeraidCb(self):
        request = RaidRequestSpec(fileSystemTypeGetDefault())
        self.editRaidRequest(request, isNew = 1)

    def editCb(self):
        part = self.lb.current()
        (type, request) = doEditPartitionByRequest(self.intf, self.partitions, part)
        if request:
            if type == "RAID":
                self.editRaidRequest(request)
            elif type == "LVMLV":
                self.editLVRequest(request)
            elif type == "NEW":
                self.editPartitionRequest(request, isNew = 1)
            else:
                self.editPartitionRequest(request)
        
    def deleteCb(self):
        partition = self.lb.current()

        if doDeletePartitionByRequest(self.intf, self.partitions, partition):
            self.refresh()
        
        
    def resetCb(self):
        if not confirmResetPartitionState(self.intf):
            return
        
        self.diskset.refreshDevices()
        self.partitions.setFromDisk(self.diskset)        
        self.populate()

    def shutdownMainUI(self):
        self.lb.clear()

    def __call__(self, screen, anaconda):
        self.screen = screen
        self.fsset = anaconda.id.fsset
        self.diskset = anaconda.id.diskset
        self.intf = anaconda.intf

        self.diskset.openDevices()
        self.partitions = anaconda.id.partitions

        checkForSwapNoMatch(anaconda)

        self.g = GridFormHelp(screen, _("Partitioning"), "partition", 1, 5)

        self.lb = CListbox(height=10, cols=6,
                           col_widths=[21,6,6,7,10,12],
                           scroll=1, returnExit = 1,
                           width=74, col_pad=2,
                           col_labels=[_('Device'), _('Start'), _('End'), _('Size'), _('Type'), _('Mount Point')],
                           col_label_align=[CENTER, CENTER,CENTER,CENTER,CENTER,CENTER])
        self.g.add(self.lb, 0, 1)

        self.bb = ButtonBar (screen, ((_("New"), "new", "F2"),
                                      (_("Edit"), "edit", "F3"),
                                      (_("Delete"), "delete", "F4"),
                                      (_("RAID"), "raid", "F11"),
                                      TEXT_OK_BUTTON, TEXT_BACK_BUTTON))
        
        screen.pushHelpLine( _("    F1-Help     F2-New      F3-Edit   F4-Delete    F5-Reset    F12-OK        "))

        self.g.add(self.bb, 0, 2, (0, 1, 0, 0))
        self.g.addHotKey("F5")
        self.populate()

        while 1:
            rc = self.g.run()
            res = self.bb.buttonPressed(rc)
            
            if res == "new":
                self.newCb()
            elif res == "edit" or rc == self.lb.listbox: # XXX better way?
                self.editCb()
            elif res == "delete":
                self.deleteCb()
            elif res == "raid":
                self.makeraidCb()
            elif res == "reset" or rc == "F5":
                self.resetCb()
            elif res == TEXT_BACK_CHECK:
                # remove refs to parted objects
                self.shutdownMainUI()
                
                screen.popHelpLine()
                screen.popWindow()
                return INSTALL_BACK
            else:
                if not self.partitions.getRequestByMountPoint("/"):
                    self.intf.messageWindow(_("No Root Partition"),
                        _("Must have a / partition to install on."))
                    continue
                
                (errors, warnings) = self.partitions.sanityCheckAllRequests(self.diskset)
                rc = partitionSanityErrors(self.intf, errors)
                if rc != 1:
                    continue
        
                rc = partitionSanityWarnings(self.intf, warnings)
                if rc != 1:
                    continue

                warnings = getPreExistFormatWarnings(self.partitions,
                                                     self.diskset)
                rc = partitionPreExistFormatWarnings(self.intf, warnings)
                if rc != 1:
                    continue

                # remove refs to parted objects
                self.shutdownMainUI()

                screen.popHelpLine()
                screen.popWindow()                
                return INSTALL_OK
        
class PartitionTypeWindow:
    def typeboxChange(self, (typebox, drivelist)):
        flag = FLAGS_RESET
        if typebox.current() == CLEARPART_TYPE_NONE:
            flag = FLAGS_SET
        # XXX need a way to disable the checkbox tree

    def clearDrivelist(self):
        # XXX remove parted object refs
        #     need to put in clear() method for checkboxtree in snack
        self.drivelist.key2item = {}
        self.drivelist.item2key = {}

    def __call__(self, screen, anaconda):
        self.anaconda = anaconda

        while 1:
            g = GridFormHelp(screen, _("Partitioning Type"), "autopart", 1, 6)

            txt = TextboxReflowed(65, _("Installation requires partitioning "
                                    "of your hard drive.  The default "
                                    "layout is reasonable for most "
                                    "users.  You can either choose "
                                    "to use this or create your own."))
            g.add(txt, 0, 0, (0, 0, 0, 0))

            opts = ((_("Remove all partitions on selected drives and create default layout."), CLEARPART_TYPE_ALL),
                    (_("Remove linux partitions on selected drives and create default layout."), CLEARPART_TYPE_LINUX),
                    (_("Use free space on selected drives and create default layout."), CLEARPART_TYPE_NONE),
                    (_("Create custom layout."), -1))
            typebox = Listbox(height = len(opts), scroll = 0)
            for (txt, val) in opts:
                typebox.append(txt, val)

            if anaconda.dispatch.stepInSkipList("autopartitionexecute"):
                typebox.setCurrent(-1)
            else:
                typebox.setCurrent(anaconda.id.partitions.autoClearPartType)        

            g.add(typebox, 0, 1, (0, 1, 0, 0))

            # list of drives to select which to clear
            subgrid = Grid(1, 2)
            subgrid.setField(TextboxReflowed(55, _("Which drive(s) do you want to "
                                                   "use for this installation?")),
                             0, 0)
            drivelist = CheckboxTree(height=2, scroll=1)
            subgrid.setField(drivelist, 0, 1)
            g.add(subgrid, 0, 2, (0, 1, 0, 0))

            bb = ButtonBar(screen, [ TEXT_OK_BUTTON, TEXT_BACK_BUTTON ])
            g.add(bb, 0, 5, (0,1,0,0))


            typebox.setCallback(self.typeboxChange, (typebox, drivelist))        
            self.drivelist = drivelist

            g.addHotKey("F2")
            screen.pushHelpLine (_("<Space>,<+>,<-> selection   |   <F2> Add drive   |   <F12> next screen"))        

            # restore the drive list each time
            disks = anaconda.id.diskset.disks.keys()
            disks.sort()
            cleardrives = anaconda.id.partitions.autoClearPartDrives

            for disk in disks:
                size = getDeviceSizeMB(anaconda.id.diskset.disks[disk].dev)
                if disk.find('mapper/mpath') != -1:
                    model = isys.getMpathModel(disk)
                else:
                    model = anaconda.id.diskset.disks[disk].dev.model

                if not cleardrives or len(cleardrives) < 1:
                    selected = 1
                else:
                    if disk in cleardrives:
                        selected = 1
                    else:
                        selected = 0

                sizestr = "%8.0f MB" % (size,)
                diskdesc = "%6s %s (%s)" % (disk, sizestr, model[:24],)

                drivelist.append(diskdesc, selected = selected)

            rc = g.run()

            sel = map(lambda s: s.split()[0], self.drivelist.getSelection())
            partmethod_ans = typebox.current()
            res = bb.buttonPressed(rc)
            
            self.clearDrivelist()
            screen.popHelpLine()
            screen.popWindow()

            if rc == "F2":
                if self.addDriveDialog(screen) != INSTALL_BACK:
                    partitionObjectsInitialize(anaconda)
                continue
            
            if res == TEXT_BACK_CHECK:
                return INSTALL_BACK

            if anaconda.id.diskset.checkNoDisks():
                continue

            if len(sel) < 1:
                mustHaveSelectedDrive(anaconda.intf)
                continue

            if partmethod_ans == -1:
                anaconda.dispatch.skipStep("autopartitionexecute", skip = 1)
                break
            else:
                anaconda.dispatch.skipStep("autopartitionexecute", skip = 0)

                anaconda.id.partitions.autoClearPartType = partmethod_ans
                anaconda.id.partitions.autoClearPartDrives = sel
                
                if queryAutoPartitionOK(anaconda):
                    break

        # ask to review autopartition layout - but only if it's not custom partitioning
        anaconda.dispatch.skipStep("partition", skip = 0)
        anaconda.dispatch.skipStep("bootloader", skip = 0)

	if partmethod_ans != -1:
            reviewLayout = anaconda.intf.messageWindow(_("Review Partition Layout"),
                               _("Review and modify partitioning layout?"),
                               type = "yesno")

            if reviewLayout != 1:
                anaconda.dispatch.skipStep("partition", skip = 1)
                anaconda.dispatch.skipStep("bootloader", skip = 1)

        return INSTALL_OK

    def addDriveDialog(self, screen):
        newdrv = []
        import iscsi
        if iscsi.has_iscsi():
            newdrv.append("Add iSCSI target")
        if rhpl.getArch() in ("s390", "s390x"):
            newdrv.append( "Add zFCP LUN" )

        if len(newdrv) == 0:
            return INSTALL_BACK

        (button, choice) = ListboxChoiceWindow(screen,
                                   _("Advanced Storage Options"),
                                   _("How would you like to modify "
                                     "your drive configuration?"),
                                   newdrv,
                                   [ TEXT_OK_BUTTON, TEXT_BACK_BUTTON],
                                               width=55, height=3)

        if button == TEXT_BACK_CHECK:
            return INSTALL_BACK
        if choice == 1:
            try:
                return self.addZFCPDriveDialog(screen)
            except ValueError, e:
                ButtonChoiceWindow(screen, _("Error"), "%s" %(e,))
                return INSTALL_BACK
        else:
            try:
                return self.addIscsiDriveDialog(screen)
            except (ValueError, IOError), e:
                ButtonChoiceWindow(screen, _("Error"), "%s" %(e,))
                return INSTALL_BACK

    def addZFCPDriveDialog(self, screen):
        (button, entries) = EntryWindow(screen,
                                        _("Add FCP Device"),
                                        _("zSeries machines can access industry-standard SCSI devices via Fibre Channel (FCP). You need to provide a 16 bit device number, a 64 bit World Wide Port Name (WWPN), and a 64 bit FCP LUN for each device."),
                                        prompts = [ "Device number",
                                                    "WWPN",
                                                    "FCP LUN" ] )
        if button == 'cancel':
            return INSTALL_BACK

        devnum = entries[0].strip()
        wwpn = entries[1].strip()
        fcplun = entries[2].strip()
        self.anaconda.id.zfcp.addFCP(devnum, wwpn, fcplun)        
                                        
        return INSTALL_OK

    def addIscsiDriveDialog(self, screen):
        if not network.hasActiveNetDev():
            ButtonChoiceWindow(screen, _("Error"),
                               "Must have a network configuration set up "
                               "for iSCSI config.  Please boot with "
                               "'linux asknetwork'")
            return INSTALL_BACK
        
        (button, entries) = EntryWindow(screen,
                                        _("Configure iSCSI Parameters"),
                                        _("To use iSCSI disks, you must provide the address of your iSCSI target and the iSCSI initiator name you've configured for your host."),
                                        prompts = [ "Target IP Address",
                                                    "iSCSI Initiator Name",
                                                    "CHAP username",
                                                    "CHAP password",
                                                    "Reverse CHAP username",
                                                    "Reverse CHAP password" ])

        if button == 'cancel':
            return INSTALL_BACK

        (user, pw, user_in, pw_in) = entries[2:]

        target = entries[0].strip()
        try:
            count = len(target.split(":"))
            idx = target.rfind("]:")
            # Check for IPV6 [IPV6-ip]:port
            if idx != -1:
                ip = target[1:idx]
                port = target[idx+2:]
            # Check for IPV4 aaa.bbb.ccc.ddd:port
            elif count == 2:
                idx = target.rfind(":")
                ip = target[:idx]
                port = target[idx+1:]
            else:
                ip = target
                port = "3260"
            network.sanityCheckIPString(ip)
        except network.IPMissing, msg:
            raise ValueError, msg
        except network.IPError, msg:
            raise ValueError, msg

        iname = entries[1].strip()
        if not self.anaconda.id.iscsi.initiatorSet:
            self.anaconda.id.iscsi.initiator = iname
        self.anaconda.id.iscsi.addTarget(ip, port, user, pw, user_in, pw_in)
                                        
        return INSTALL_OK
