#
# fdisk_text.py: allows the user to partition disks with fdisk utility
# in text mode
#
# Jeremy Katz <katzj@redhat.com>
#
# Copyright 2001-2002 Red Hat, Inc.
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
from rhpl.translate import _, cat, N_
from constants_text import *
import partitioning

class fdiskPartitionWindow:
    def __call__(self, screen, diskset, partrequests, intf):
        choices = []
        drives = diskset.disks.keys()
        drives.sort()
        for drive in drives:
            choices.append("%s" %(drive))

        # close all references we had to the diskset
        diskset.closeDevices()

        button = None
        while button != "done" and button != "back":
            (button, choice) = \
                     ListboxChoiceWindow(screen, _("Disk Setup"),
                     _("Choose a disk to run fdisk on"), choices,
                     [ (_("OK"), "done"), (_("Edit"), "edit"),
                       TEXT_BACK_BUTTON ], width = 50, help = "fdisk")

            if button != "done" and button != TEXT_BACK_CHECK:
                device = choices[choice]
                
                if os.access("/sbin/fdisk", os.X_OK):
                    path = "/sbin/fdisk"
                else:
                    path = "/usr/sbin/fdisk"

                try:
                    isys.makeDevInode(device, '/tmp/' + device)
                except:
                    pass

                screen.suspend()
                iutil.execWithRedirect (path, [ path, "/tmp/" + device ],
                                        ignoreTermSigs = 1)
                screen.resume()

                try:
                    os.remove('/tmp/' + device)
                except:
                    pass


        diskset.refreshDevices(intf)
        diskset.checkNoDisks(intf)
        partrequests.setFromDisk(diskset)

        if button == TEXT_BACK_CHECK:
            return INSTALL_BACK

        return INSTALL_OK
