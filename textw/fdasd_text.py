#
# fdasd_text.py: allows the user to partition disks with fdasd utility
# in text mode
#
# Harald Hoyer <harald@redhat.de>
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

import os
import isys
import iutil
from snack import *
from translate import _, cat, N_
from constants_text import *
import partitioning

class fdasdPartitionWindow:
    def __call__(self, screen, diskset, partrequests, intf):
        choices = []

        fdisk_name = "fdasd"
        listboxtext = _("Choose a disk to run fdasd or dasdfmt on")
        buttons = [ (_("Next"), "done"), (_("Edit Partitions"), "edit"),
                    (_("Format DASD"), "dasdfmt"),
                    TEXT_BACK_BUTTON ]        
        drives =  diskset.driveList()        
        
        drives.sort()
        
        for drive in drives:
            choices.append("%s" %(drive))

        # close all references we had to the diskset
        diskset.closeDevices()

        button = None

        while button != "done" and button != TEXT_BACK_CHECK:
            
            (button, choice) = \
                     ListboxChoiceWindow(screen, _("Disk Setup"),
                     listboxtext, choices,
                     buttons, width = 50, help = "fdasd-s390")

            if button == "edit":
                device = choices[choice]
                
                if os.access("/sbin/fdasd", os.X_OK):
                    path = "/sbin/fdasd"
                else:
                    path = "/usr/sbin/fdasd"

                try:
                    isys.makeDevInode(device, '/tmp/' + device)
                except:
                    pass

                screen.suspend()
                rc = iutil.execWithRedirect (path, [ path, "/tmp/" + device ],
                                        ignoreTermSigs = 1)
                screen.resume()
                
                if rc:
                    intf.messageWindow( _("Error"),
                                        _("An error occured while running %s on drive %s.") % (path, device))
                    
                try:
                    os.remove('/tmp/' + device)
                except:
                    pass

            elif button == "dasdfmt":
                device = choices[choice]

                rc = intf.messageWindow(_("Warning"),
                                        _("Running dasdfmt means the loss of \n"
                                          "ALL DATA on drive %s.\n\n"
                                          "Do you really want this?")
                                        % (device,), type = "yesno")
                if rc == 0:
                    continue
                
                diskset.dasdFmt(intf, device)

            elif button == "done" or button == TEXT_BACK_CHECK:
                diskset.refreshDevices(intf)
                partitioning.checkNoDisks(diskset, intf)            
                partrequests.setFromDisk(diskset)

                if len(diskset.disks.keys()) == 0:
                    rc = intf.messageWindow(_("No Drives Found"),
                                            _("An error has occurred - no valid devices were "
                                              "found on which to create new filesystems. "
                                              "Please check your hardware for the cause "
                                              "of this problem or use dasdfmt.\n\n"
                                              "Back to the fdasd screen?"), type = "yesno")
                    
                    if rc:
                        button = ""

                    
            
        
        if button == TEXT_BACK_CHECK:
            return INSTALL_BACK

        partitioning.checkNoDisks(diskset, intf)            
        partrequests.setFromDisk(diskset)
        
        return INSTALL_OK
