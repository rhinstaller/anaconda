#
# fdisk_gui.py: interface that allows the user to run util-linux fdisk.
#
# Copyright 2000-2002 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import gtk
from iw_gui import *
import vte
from rhpl.translate import _
from dispatch import DISPATCH_NOOP
import partitioning
import isys
import os

class FDiskWindow(InstallWindow):		
    def __init__(self, ics):
	InstallWindow.__init__(self, ics)
        ics.setTitle(_("Partitioning with fdisk"))
        ics.readHTML("fdisk")

    def getNext(self):
        # reread partitions
        self.diskset.refreshDevices(self.intf)
        self.diskset.checkNoDisks(self.intf)
        self.partrequests.setFromDisk(self.diskset)

        return None
        

    def child_died(self, widget, button):
        self.windowContainer.remove(self.windowContainer.get_children()[0])
        self.windowContainer.pack_start(self.buttonBox)
        button.set_state(gtk.STATE_NORMAL)
        try:
            os.remove('/tmp/' + self.drive)
        except:
            # XXX fixme
            pass

        self.ics.readHTML("fdisk")
        self.ics.setPrevEnabled(1)
        self.ics.setNextEnabled(1)
        cw = self.ics.getICW()
        if cw.displayHelp:
            cw.refreshHelp()
#        self.ics.setHelpEnabled (1)


    def button_clicked(self, widget, drive):
        term = vte.Terminal()
        term.set_encoding("UTF-8")
        term.set_font_from_string("monospace 10")
        term.set_color_background(gtk.gdk.color_parse('white'))
        term.set_color_foreground(gtk.gdk.color_parse('black'))
        term.connect("child_exited", self.child_died, widget)
        term.reset(True, True)

        self.drive = drive

	# free our fd's to the hard drive -- we have to 
	# fstab.rescanDrives() after this or bad things happen!
        if os.access("/sbin/fdisk", os.X_OK):
            path = "/sbin/fdisk"
        else:
            path = "/usr/sbin/fdisk"
        
	isys.makeDevInode(drive, '/tmp/' + drive)

        term.fork_command(path, (path, '/tmp/' + drive))
        term.show()
        
        self.windowContainer.remove(self.buttonBox)
        self.windowContainer.pack_start(term)

        self.ics.readHTML("fdiskpart")
        cw = self.ics.getICW()
        if cw.displayHelp:
            cw.refreshHelp()

        self.ics.setPrevEnabled(0)
        self.ics.setNextEnabled(0)

    # FDiskWindow tag="fdisk"
    def getScreen(self, diskset, partrequests, intf):
        
        self.diskset = diskset
        self.partrequests = partrequests
        self.intf = intf
        
        self.windowContainer = gtk.VBox(False)
        self.buttonBox = gtk.VBox(False, 5)
        self.buttonBox.set_border_width(5)
        box = gtk.VButtonBox()
        box.set_layout("start")
        label = gtk.Label(_("Select a drive to partition with fdisk:"))

        drives =  self.diskset.driveList()
        
        # close all references we had to the diskset
        self.diskset.closeDevices()

        for drive in drives:
            button = gtk.Button(drive)
            button.connect("clicked", self.button_clicked, drive)
            box.pack_start(button)

        # put the button box in a scrolled window in case there are
        # a lot of drives
        sw = gtk.ScrolledWindow()
        sw.add_with_viewport(box)
        sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        viewport = sw.get_children()[0]
        viewport.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        sw.set_size_request(-1, 400)

        self.buttonBox.pack_start(label, False)
        self.buttonBox.pack_start(sw, False)
        self.windowContainer.pack_start(self.buttonBox)

        self.ics.setNextEnabled(1)

        return self.windowContainer
