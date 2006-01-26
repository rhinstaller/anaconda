#
# task_gui.py: Choose tasks for installation
#
# Copyright 2006 Red Hat, Inc.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import gtk
import gtk.glade
import gobject
import gui
from iw_gui import *
from rhpl.translate import _, N_
from constants import productName

grpTaskMap = {"officeCheckbox": ["graphics", "office",
                                 "games", "sound-and-video"],
              "develCheckbox": ["development-libs", "development-tools",
                                "gnome-software-development",
                                "x-software-development"],
              "webCheckbox": ["web-server"],
              "xenCheckbox": ["xen"] }

class TaskWindow(InstallWindow):
    def getNext(self):
        def selgroups(lst):
            map(self.backend.selectGroup, lst)
            
        if self.xml.get_widget("customRadio").get_active():
            self.dispatch.skipStep("group-selection", skip = 0)
        else:
            self.dispatch.skipStep("group-selection", skip = 1)

        for (cb, grps) in grpTaskMap.items():
            if self.xml.get_widget(cb).get_active():
                map(self.backend.selectGroup, grps)                
            else:
                map(self.backend.deselectGroup, grps)

    def groupsInstalled(self, lst):
        # FIXME: yum specific
        rc = False
        for gid in lst:
            g = self.backend.ayum.comps.return_group(gid)
            if g and not g.selected:
                return False
            elif g:
                rc = True
        return rc

    def getScreen (self, intf, backend, dispatch):
        self.intf = intf
        self.dispatch = dispatch
        self.backend = backend

        (self.xml, vbox) = gui.getGladeWidget("tasksel.glade", "taskBox")

        lbl = self.xml.get_widget("mainLabel")
        txt = lbl.get_text()
        lbl.set_text(txt %(productName,))

	custom = not self.dispatch.stepInSkipList("group-selection")
        if custom:
            self.xml.get_widget("customRadio").set_active(True)
        else:
            self.xml.get_widget("customRadio").set_active(False)

        for (cb, grps) in grpTaskMap.items():
            if self.groupsInstalled(grps):
                self.xml.get_widget(cb).set_active(True)
            else:
                self.xml.get_widget(cb).set_active(False)        

        return vbox
