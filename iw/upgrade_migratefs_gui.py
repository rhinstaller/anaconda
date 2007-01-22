#
# upgrade_migratefs_gui.py: dialog for migrating filesystems on upgrades
#
# Mike Fulbright <msf@redhat.com>
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

from iw_gui import *
from rhpl.translate import _, N_
from constants import *
import string
import isys 
import iutil
import upgrade
import rhpl
from fsset import *
import gui
import gtk

class UpgradeMigrateFSWindow (InstallWindow):		
    windowTitle = N_("Migrate File Systems")

    def getNext (self):
        for entry in self.migent:
            if rhpl.getArch() == "ia64" \
                    and entry.getMountPoint() == "/boot/efi":
                continue
            entry.setFormat(0)
            entry.setMigrate(0)
            entry.fsystem = entry.origfsystem

        for (cb, entry) in self.cbs:
            if cb.get_active():
                entry.setFileSystemType(fileSystemTypeGet("ext3"))
                entry.setFormat(0)
                entry.setMigrate(1)
                
        return None

    def getScreen (self, anaconda):
      
        self.fsset = anaconda.id.fsset
        self.migent = self.fsset.getMigratableEntries()
        
        box = gtk.VBox (False, 5)
        box.set_border_width (5)

	text = N_("This release of %s supports "
                 "the ext3 journalling file system.  It has several "
                 "benefits over the ext2 file system traditionally shipped "
                 "in %s.  It is possible to migrate the ext2 "
                 "formatted partitions to ext3 without data loss.\n\n"
                 "Which of these partitions would you like to migrate?" %
                  (productName, productName))
        
	label = gtk.Label (_(text))
        label.set_alignment (0.5, 0.0)
        label.set_size_request(400, -1)
        label.set_line_wrap (True)
        box.pack_start(label, False)

        cbox = gtk.VBox(False, 5)
        self.cbs = []
        for entry in self.migent:
            if rhpl.getArch() == "ia64" \
                    and entry.getMountPoint() == "/boot/efi":
                continue
            if entry.fsystem.getName() != entry.origfsystem.getName():
                migrating = 1
            else:
                migrating = 0
            
            cb = gtk.CheckButton("/dev/%s - %s - %s" % (entry.device.getDevice(),
                                              entry.origfsystem.getName(),
                                              entry.mountpoint))
            cb.set_active(migrating)
            cbox.pack_start(cb, False)

            self.cbs.append((cb, entry))

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        sw.add_with_viewport(cbox)
        sw.set_size_request(-1, 175)
        
        viewport = sw.get_children()[0]
        viewport.set_shadow_type(gtk.SHADOW_IN)
        
        a = gtk.Alignment(0.25, 0.5)
        a.add(sw)

        box.pack_start(a, True)
        
        a = gtk.Alignment(0.5, 0.5)
        a.add(box)
        return a
    
                       
