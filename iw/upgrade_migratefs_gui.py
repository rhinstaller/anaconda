#
# upgrade_migratefs_gui.py: dialog for migrating filesystems on upgrades
#
# Copyright (C) 2001, 2002  Red Hat, Inc.  All rights reserved.
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
# Author(s): Mike Fulbright <msf@redhat.com>
#

from iw_gui import *
from constants import *
from storage.formats import getFormat
from storage.deviceaction import ActionMigrateFormat
import string
import isys 
import iutil
import gtk

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("anaconda")

class UpgradeMigrateFSWindow (InstallWindow):		
    windowTitle = N_("Migrate File Systems")

    def getNext (self):
        # I don't like this but I also don't see a better way right now
        for (cb, entry) in self.cbs:
            action = self.devicetree.findActions(device=entry,
                                                 type="migrate")
            if cb.get_active():
                if action:
                    # the migrate action has already been scheduled
                    continue

                newfs = getFormat(entry.format.migrationTarget)
                if not newfs:
                    log.warning("failed to get new filesystem type (%s)"
                                % entry.format.migrationTarget)
                    continue
                action = ActionMigrateFormat(entry)
                self.devicetree.registerAction(action)
            elif action:
                self.devicetree.cancelAction(action)

        return None

    def getScreen (self, anaconda):
        self.devicetree = anaconda.storage.devicetree
        self.migent = anaconda.storage.migratableDevices
        
        box = gtk.VBox (False, 5)
        box.set_border_width (5)

	text = (_("This release of %(productName)s supports "
                 "an updated file system, which has several "
                 "benefits over the file system traditionally shipped "
                 "in %(productName)s.  This installation program can migrate "
                 "formatted partitions without data loss.\n\n"
                 "Which of these partitions would you like to migrate?") %
                  {'productName': productName})
        
	label = gtk.Label (text)
        label.set_alignment (0.5, 0.0)
        label.set_size_request(400, -1)
        label.set_line_wrap (True)
        box.pack_start(label, False)

        cbox = gtk.VBox(False, 5)
        self.cbs = []
        for entry in self.migent:
            # don't allow the user to migrate /boot to ext4 (#439944)
            if (getattr(entry.format, "mountpoint", None) == "/boot" and
                not entry.format.migrate and entry.format.type == "ext3"):
                continue
            
            cb = gtk.CheckButton("%s - %s - %s" % (entry.path,
                                                   entry.format.name,
                                                   getattr(entry.format,
                                                           "mountpoint",
                                                           None)))
            cb.set_active(entry.format.migrate)
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
    
                       
