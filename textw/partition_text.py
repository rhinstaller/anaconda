#
# partition_text.py: allows the user to choose how to partition their disks
# in text mode
#
# Jeremy Katz <katzj@redhat.com>
#
# Copyright 2001 Red Hat, Inc.
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
import parted
from partitioning import *
from fsset import *
from autopart import *
from snack import *
from constants_text import *
from translate import _
from log import log

class PartitionWindow:
    def populate(self):
        # XXX we really should separate this stuff out into interface
        # independent bits...
        self.lb.clear()

        # first, add the drives and partitions to the list
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
                    ptype = _("software RAID component")
                elif part.fs_type:
                    if request.fstype != None:
                        ptype = request.fstype.getName()
                    else:
                        ptype = part.fs_type.name
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
                    self.lb.append(["%s%s" %(indent, devify(get_partition_name(part))),
                                    "%d" %(start),
                                    "%d" %(end),
                                    "%dM" %(size),
                                    "%s" %(ptype),
                                    "%s" %(mount)], part,
                                   [LEFT, RIGHT, RIGHT, RIGHT, LEFT, LEFT])
                part = disk.next_partition(part)

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

                device = _("RAID Device %s" %(str(raidcounter)))
                size = get_raid_device_size(request) / 1024.0 / 1024.0
                self.lb.append(["%s" %(device),
                                "", "", "%dM" %(size),
                                "%s" %(ptype), "%s" %(mount)], request.device,
                               [LEFT, RIGHT, RIGHT, RIGHT, LEFT, LEFT])
        

    def refresh(self):
        # XXX need some way to stay at the same place in the list after
        # repopulating

        try:
            doPartitioning(self.diskset, self.partitions)
            rc = 0
        except PartitioningError, msg:
            self.intf.messageWindow(_("Error Partitioning"),
                   _("Could not allocated requested partitions: %s.") % (msg))
            rc = -1            
        self.populate()
        return rc


    def fstypeSet(self, obj):
        (listbox, entry) = obj
        flag = FLAGS_RESET
        if not listbox.current().isMountable():
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


    # make the entry for the mount point and it's label
    def makeMountEntry(self, request):
        mountgrid = Grid(2, 1)
        mountLbl = Label(_("Mount Point:"))
        mountgrid.setField(mountLbl, 0, 0, (0,0,6,0), anchorLeft = 1)
        mountpoint = request.mountpoint
        if mountpoint:
            mount = Entry(20, mountpoint)
        else:
            mount = Entry(20, "")
        mountgrid.setField(mount, 1, 0, anchorRight = 1, growx = 1)
        if not request.fstype.isMountable():
            mount.setFlags(FLAG_DISABLED, FLAGS_SET)
            mount.set(_("<Not Applicable>"))
        return (mount, mountgrid)
        

    # make the list of available filesystems and it's label
    def makeFsList(self, request):
        subgrid = Grid(1, 2)
        # filesystem type selection
        typeLbl = Label(_("Filesystem type:"))
        subgrid.setField(typeLbl, 0, 0)
        fstype = Listbox(height=2, scroll=1)
        types = fileSystemTypeGetTypes()
        names = types.keys()
        names.sort()
        for name in names:
            if fileSystemTypeGet(name).isFormattable():
                fstype.append(name, types[name])
        if request.fstype:
            fstype.setCurrent(request.fstype)
        subgrid.setField(fstype, 0, 1)
        fstype.setCallback(self.fstypeSet, (fstype, self.mount))
        return (fstype, subgrid)


    # make the list of drives
    def makeDriveList(self, request):
        subgrid = Grid(1, 2)
        driveLbl = Label(_("Allowable Drives:"))
        subgrid.setField(driveLbl, 0, 0)
        disks = self.diskset.disks.keys()
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
            if request.maxSize != None:
                limitdef = 1
                limitentrydef = "%s" %(int(request.maxSize))
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
        driveLbl = Label(_("Raid Members:"))
        subgrid.setField(driveLbl, 0, 0)
        disks = self.diskset.disks.keys()
        drivelist = CheckboxTree(height=2, scroll=1)
        avail = get_available_raid_partitions(self.diskset, self.partitions.requests, request)
        # XXX
        if not request.raidmembers:
            for (part, used) in avail:
                drivelist.append(get_partition_name(part), part, 1)
        else:
            for (part, used) in avail:
                drivelist.append(get_partition_name(part), part, used)
        subgrid.setField(drivelist, 0, 1)
        return (drivelist, subgrid)


    def makeSpareEntry(self, request):
        subgrid = Grid(2, 1)
        label = Label(_("Number of spares?"))
        subgrid.setField(label, 1, 0)
        entry = Entry(3)
        if request.raidspares:
            entry.set(request.raidspares)
        else:
            entry.set("0")
        subgrid.setField(entry, 0, 0, (0,0,1,0))
        return (entry, subgrid)
    
        
    def editPartitionRequest(self, origrequest):
        poplevel = GridFormHelp(self.screen, _("Add partition"), "addpart", 1, 6)

        # mount point entry
        row = 0
        (self.mount, mountgrid) = self.makeMountEntry(origrequest)
        poplevel.add(mountgrid, 0, row)

        row = row + 1

        if origrequest.type == REQUEST_NEW:
            subgrid = Grid(2, 1)
            (fstype, fsgrid) = self.makeFsList(origrequest)
            subgrid.setField(fsgrid, 0, 0, anchorLeft = 1, anchorTop=1)

            if origrequest.start == None:
                (drivelist, drivegrid) = self.makeDriveList(origrequest)
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
            poplevel.add(primary, 0, row, (0,1,0,0))
        
        else:
            subgrid = Grid(2, 4)
            # filesystem type selection
            typeLbl = Label(_("Filesystem type:"))
            subgrid.setField(typeLbl, 0, 0, (0,0,2,0), anchorLeft = 1)
            type = Label(origrequest.fstype.getName())
            subgrid.setField(type, 1, 0, anchorRight = 1)
            sizeLbl = Label(_("Size (MB):"))
            subgrid.setField(sizeLbl, 0, 1, (0,1,2,0), anchorLeft = 1)
            size = Label("%s" %(int(origrequest.size)))
            subgrid.setField(size, 1, 1, (0,1,0,0), anchorRight = 1)
            poplevel.add(subgrid, 0, row, (0,1,0,0))

            if origrequest.fstype and origrequest.fstype.isFormattable():
                row = row + 1
                # XXX make use a label and checkbox to look like spares
                format = Checkbox(_("Format partition?"))
                poplevel.add(format, 0, row, (0,1,0,0))
            else:
                format = None

            

        row = row + 1
        popbb = ButtonBar(self.screen, (TEXT_OK_BUTTON,TEXT_CANCEL_BUTTON))
        poplevel.add(popbb, 0, row, (0,1,0,0), growx = 1)        


        while 1:
            res = poplevel.run()

            # if the user hit cancel, do nothing
            if popbb.buttonPressed(res) == 'cancel':
                self.screen.popWindow()
                return

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

                if origrequest.start == None:
                    request.size = int(size.value())
                
                    growtype = sizeopts.getSelection()
                    if growtype == "fixed":
                        grow = None
                    else:
                        grow = TRUE
                    if growtype == "limit":
                        maxsize = int(limitentry.value())
                    else:
                        maxsize = None
                    request.grow = grow
                    request.maxSize = maxsize

                    if len(drivelist.getSelection()) == len(self.diskset.disks.keys()):
                        allowdrives = None
                    else:
                        allowdrives = []
                        for i in drivelist.getSelection():
                            allowdrives.append(i) 
                    request.drive = allowdrives
                else:
                    request.start = int(start.value())

                    cyltype = cylopts.getSelection()
                    if cyltype == "end":
                        request.end = int(end.value())
                        request.size = None
                    elif cyltype == "size":
                        request.end = None
                        request.size = int(size.value())
                    else: # can't ever get here
                        raise RuntimeError, "Selected a way of partitioning by cylinder that's not supported"
                    

                err = sanityCheckPartitionRequest(self.partitions, request)
                if err:
                    self.intf.messageWindow(_("Error With Request"),
                                            "%s" % (err))
                    continue
            else:
                # pre-existing partition, just set mount point and format flag
                if origrequest.fstype.isMountable():
                    origrequest.mountpoint = self.mount.value()

                if format:
                    origrequest.format = format.selected()
                else:
                    origrequest.format = 0

                err = sanityCheckPartitionRequest(self.partitions, origrequest)
                if err:
                    self.intf.messageWindow(_("Error With Request"),
                                            "%s" % (err))
                    continue
                request = origrequest

            # backup current (known working) configuration
            backpart = self.partitions.copy()
            if origrequest.device or origrequest.type != REQUEST_NEW:
                self.partitions.removeRequest(origrequest)

            self.partitions.addRequest(request)
            if self.refresh():
                self.partitions = backpart
                self.refresh()
            else:
                break

        # clean up
        self.screen.popWindow()
#        self.refresh()


    def editRaidRequest(self, raidrequest):
        poplevel = GridFormHelp(self.screen, _("Make RAID Device"), "makeraid", 1, 6)

        # mount point entry
        row = 0
        (self.mount, mountgrid) = self.makeMountEntry(raidrequest)
        poplevel.add(mountgrid, 0, row)

        row = row + 1
        subgrid = Grid(2, 1)
        (fstype, fsgrid) = self.makeFsList(raidrequest)
        subgrid.setField(fsgrid, 0, 0, anchorLeft = 1, anchorTop=1)
        (raidtype, raidgrid) = self.makeRaidList(raidrequest)
        subgrid.setField(raidgrid, 1, 0, (2,0,0,0), anchorRight=1, anchorTop=1)
        poplevel.add(subgrid, 0, row, (0,1,0,0))

        row = row + 1
        drivegrid = Grid(2, 1)
        (drivelist, drivesubgrid) = self.makeRaidDriveList(raidrequest)
        drivegrid.setField(drivesubgrid, 0, 0, (0,0,4,0), anchorLeft = 1, anchorTop = 1)

        miscgrid = Grid(1, 2)
        (spares, sparegrid) = self.makeSpareEntry(raidrequest)
        miscgrid.setField(sparegrid, 0, 0, anchorRight=1, anchorTop=1)

        if raidrequest.fstype and raidrequest.fstype.isFormattable():
            format = Checkbox(_("Format partition?"))
            miscgrid.setField(format, 0, 1)
        else:
            format = None

        if raidrequest.format == 1:
            format.setValue("*")

        drivegrid.setField(miscgrid, 1, 0, anchorTop=1)
        poplevel.add(drivegrid, 0, row, (0,1,0,0))        
        
        row = row + 1
        popbb = ButtonBar(self.screen, (TEXT_OK_BUTTON,TEXT_CANCEL_BUTTON))
        poplevel.add(popbb, 0, row, (0,1,0,0), growx = 1)        

        while 1:
            res = poplevel.run()

            if popbb.buttonPressed(res) == 'cancel':
                self.screen.popWindow()
                return

            request = copy.copy(raidrequest)
            filesystem = fstype.current()

            if request.fstype.isMountable():
                request.mountpoint = self.mount.value()
            else:
                request.mountpoint = None

            raidmembers = []
            for drive in drivelist.getSelection():
                raidmembers.append(PartedPartitionDevice(drive))
            request.raidmembers = raidmembers
            request.raidspares = int(spares.value())
            request.raidlevel = raidtype.current()

            if format:
                request.format = format.selected()
            else:
                request.format = 0
            
            err = sanityCheckRaidRequest(self.partitions, request)
            if err:
                self.intf.messageWindow(_("Error With Request"),
                                        "%s" % (err))
                continue

            # backup current (known working) configuration
            backpart = self.partitions.copy()

            # XXX should only remove if we know we put it in before
            try:
                self.partitions.removeRequest(raidrequest)
            except:
                pass

            self.partitions.addRequest(request)
            
            if self.refresh():
                self.partitions = backpart
                self.refresh()
            else:
                break            

            break

        # clean up
        self.screen.popWindow()
#        self.refresh()
        
    def newCb(self):
        request = PartitionSpec(fileSystemTypeGetDefault(), REQUEST_NEW, 1)
        self.editPartitionRequest(request)


    def makeraidCb(self):
        request = PartitionSpec(fileSystemTypeGetDefault(), REQUEST_RAID, 1)
        self.editRaidRequest(request)


    def editCb(self):
        part = self.lb.current()
        if part == None:
            ButtonChoiceWindow(self.screen, _("Not a Partition"),
                      _("You must select a partition to edit"),
                               buttons = [ TEXT_OK_BUTTON ] )
            return
        elif type(part) == type("RAID"):
            request = self.partitions.getRequestByDeviceName(part)
            self.editRaidRequest(request)
            return
        elif part.type & parted.PARTITION_FREESPACE:
            request = PartitionSpec(fileSystemTypeGetDefault(), REQUEST_NEW,
                                    start = start_sector_to_cyl(part.geom.disk.dev, part.geom.start),
                                    end = end_sector_to_cyl(part.geom.disk.dev, part.geom.end),
                                    drive = [ get_partition_drive(part) ])
            self.editPartitionRequest(request)
            return
        elif (part.fs_type == None) or (part.fs_type and not part.fs_type.name):
            ButtonChoiceWindow(self.screen, _("You cannot edit partitions "
                               "without a filesystem type."),
                               buttons = [ TEXT_OK_BUTTON ] )
            return
        elif part.type & parted.PARTITION_EXTENDED:
            return

        request = self.partitions.getRequestByDeviceName(get_partition_name(part))
        if request:
            if request.type == REQUEST_PROTECTED:
                ButtonChoiceWindow(self.screen, _("You cannot edit this "
                          "partition, as it is part of a RAID device."),
                                   buttons = [ TEXT_OK_BUTTON ] )
                return
            if self.partitions.isRaidMember(request):
                ButtonChoiceWindow(self.screen, _("Unable to Remove"),
                                   _("You cannot remove this partition "
                                     "as it is part of a RAID device"),
                                   buttons = [ TEXT_OK_BUTTON ])
                return
            
            self.editPartitionRequest(request)
        else: # shouldn't ever happen
            raise ValueError, "Trying to edit non-existent partition %s" %(get_partition_name(part))

        
    def deleteCb(self):
        partition = self.lb.current()

        if partition == None:
            ButtonChoiceWindow(self.screen, _("Unable to Remove"),
                      _("You must first select a partition"),
                               buttons = [ TEXT_OK_BUTTON ] )
            return
        elif type(partition) == type("RAID"):
            device = partition
        elif partition.type & parted.PARTITION_FREESPACE:
            ButtonChoiceWindow(self.screen, _("Unable to Remove"),
                      _("You cannot remove freespace"),
                               buttons = [ TEXT_OK_BUTTON ] )
            return
        else:
            device = get_partition_name(partition)

        request = self.partitions.getRequestByDeviceName(device)
        

        if request:
            if request.type == REQUEST_PROTECTED:
                ButtonChoiceWindow(self.screen, _("You cannot edit this "
                          "partition, as it is part of a RAID device."),
                                   buttons = [ TEXT_OK_BUTTON ] )
                return
            
            if self.partitions.isRaidMember(request):
                ButtonChoiceWindow(self.screen, _("Unable to Remove"),
                                   _("You cannot remove this partition "
                                     "as it is part of a RAID device"),
                                   buttons = [ TEXT_OK_BUTTON ])
                return
                
            self.partitions.removeRequest(request)
            if request.type == REQUEST_PREEXIST:
                # get the drive
                drive = get_partition_drive(partition)

                if partition.type & parted.PARTITION_EXTENDED:
                    deleteAllLogicalPartitions(partition, self.partitions)
                
                delete = DeleteSpec(drive, partition.geom.start, partition.geom.end)
                self.partitions.addDelete(delete)
        else: # shouldn't happen
            raise ValueError, "Deleting a non-existenent partition"
            
        del partition
        self.refresh()
        
        
    def resetCb(self):
        self.diskset.refreshDevices()
        self.partitions.setFromDisk(self.diskset)        
        self.populate()


    def __call__(self, screen, fsset, diskset, partitions, intf):
        self.screen = screen
        self.fsset = fsset
        self.diskset = diskset
        self.intf = intf

        self.diskset.openDevices()
        self.partitions = partitions

        self.g = GridFormHelp(screen, _("Partitioning"), "partitioning", 1, 5)

        self.lb = CListbox(height=10, cols=6,
                           col_widths=[17,5,5,7,10,12],
                           scroll=1, returnExit = 1,
                           width=70, col_pad=2,
                           col_labels=['Device', 'Start', 'End', 'Size', 'Type', 'Mount Point'],
                           col_label_align=[CENTER, CENTER,CENTER,CENTER,CENTER,CENTER])
        self.g.add(self.lb, 0, 1)

        self.bb = ButtonBar (screen, ((_("New"), "new", "F2"), (_("Edit"), "edit", "F3"), (("Delete"), "delete", "F4"), (_("RAID"), "raid", "F11"), TEXT_OK_BUTTON, TEXT_BACK_BUTTON))
        self.g.add(self.bb, 0, 2, (0, 1, 0, 0))
        self.g.addHotKey("F5")
        screen.pushHelpLine( _("    F1-Help     F2-New      F3-Edit   F4-Delete    F5-Reset    F12-Ok        "))

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
                screen.popHelpLine()
                screen.popWindow()
                return INSTALL_BACK
            else:
                if not self.partitions.getRequestByMountPoint("/"):
                    self.intf.messageWindow(_("No Root Partition"),
                        _("Must have a / partition to install on."))
                    continue
                self.fsset.reset()
                for request in self.partitions.requests:
                    # XXX improve sanity checking
                    if not request.fstype or (request.fstype.isMountable() and not request.mountpoint):
                        continue
                    entry = request.toEntry()
                    self.fsset.add (entry)                
                screen.popHelpLine()
                screen.popWindow()                
                return INSTALL_OK
        


class AutoPartitionWindow:
    def typeboxChange(self, (typebox, drivelist)):
        flag = FLAGS_RESET
        if typebox.current() == CLEARPART_TYPE_NONE:
            flag = FLAGS_SET
        # XXX need a way to disable the checkbox tree
        
    def __call__(self, screen, id, diskset, intf):
        if not id.useAutopartitioning:
            return INSTALL_NOOP
        
        self.g = GridFormHelp(screen, _("Autopartitioning"), "autopartitioning", 1, 6)

        # listbox for types of removal
        typebox = Listbox(height=3, scroll=0)
        typebox.append(_("Remove all Linux partitions"), CLEARPART_TYPE_LINUX)
        typebox.append(_("Remove all partitions"), CLEARPART_TYPE_ALL)
        typebox.append(_("Remove no partitions"), CLEARPART_TYPE_NONE)
        if id.autoClearPartType == CLEARPART_TYPE_LINUX:
            typebox.setCurrent(CLEARPART_TYPE_LINUX)
        elif id.autoClearPartType == CLEARPART_TYPE_ALL:
            typebox.setCurrent(CLEARPART_TYPE_ALL)
        else:
            typebox.setCurrent(CLEARPART_TYPE_NONE)
            
        self.g.add(typebox, 0, 2, (0,1,0,0))

        # list of drives to select which to clear
        subgrid = Grid(1, 2)
        driveLbl = Label(_("Clear Partitions on These Drives:"))
        cleardrives = id.autoClearPartDrives
        subgrid.setField(driveLbl, 0, 0)
        disks = id.diskset.disks.keys()
        drivelist = CheckboxTree(height=3, scroll=1)
        if not cleardrives or len(cleardrives) < 1:
            for disk in disks:
                drivelist.append(disk, selected = 1)
        else:
            for disk in disks:
                if disk in cleardrives:
                    selected = 1
                else:
                    selected = 0
                drivelist.append(disk, selected = selected)
        subgrid.setField(drivelist, 0, 1)
        self.g.add(subgrid, 0, 3, (0,1,0,0))

        typebox.setCallback(self.typeboxChange, (typebox, drivelist))

        bb = ButtonBar(screen, [ TEXT_OK_BUTTON, TEXT_BACK_BUTTON ])
        self.g.add(bb, 0, 4, (0,1,0,0))

        rc = self.g.run()
        res = bb.buttonPressed(rc)

        screen.popWindow()
        if res == TEXT_BACK_CHECK:
            return INSTALL_BACK

        id.autoClearPartType = typebox.current()
        id.autoClearPartDrives = drivelist.getSelection()
        return INSTALL_OK
