#
# format_gui.py: allows the user to choose which partitions to format
#
# Matt Wilson <msw@redhat.com>
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

from gtk import *
from iw_gui import *
import isys
from translate import _
import gui

class FormatWindow (InstallWindow):
    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)
        ics.setTitle (_("Choose partitions to Format"))
        ics.setNextEnabled (1)
        ics.readHTML ("format")

    def getNext (self):
        for (entry, state) in self.state.items():
            entry.setFormat (state)

    # FormatWindow tag="format"
    def getScreen (self, fsset):
        def toggled (widget, (entry, state)):
            if widget.get_active ():
                state[entry] = 1
            else:
                state[entry] = 0

#        def check (widget, todo):
#            todo.fstab.setBadBlockCheck(widget.get_active ())

        box = GtkVBox (FALSE, 10)

        entries = fsset.formattablePartitions()

	gotOne = 0
        sw = GtkScrolledWindow ()
        sw.set_policy (POLICY_AUTOMATIC, POLICY_AUTOMATIC)
        self.state = {}
        for entry in entries:
            self.state[entry] = entry.getFormat()

	    gotOne = 1
	    checkButton = GtkCheckButton ("%s   %s" % (entry.device,
                                                       entry.mountpoint))
	    checkButton.set_active (self.state[entry])
	    checkButton.connect ("toggled", toggled, (entry, self.state))
	    box.pack_start (checkButton, FALSE, FALSE)

	if not gotOne: return None

        sw.add_with_viewport (box)
        viewport = sw.children()[0]
        viewport.set_shadow_type (SHADOW_ETCHED_IN)
        
        vbox = GtkVBox (FALSE, 10)
        vbox.pack_start (sw, TRUE, TRUE)

#        self.check = GtkCheckButton (_("Check for bad blocks while formatting"))
#        self.check.set_active (self.todo.fstab.getBadBlockCheck())
#        self.check.connect ("toggled", check, self.todo)
#        vbox.pack_start (self.check, FALSE)
        
#        self.check = GtkCheckButton 

	vbox.set_border_width (5)
        return vbox
