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

class TaskWindow(InstallWindow):
    def getNext(self):
        if self.xml.get_widget("customRadio").get_active():
            self.dispatch.skipStep("group-selection", skip = 0)
        else:
            self.dispatch.skipStep("group-selection", skip = 1)

        for (txt, grps) in self.tasks:
            if not self.taskcbs.has_key(txt):
                continue
            cb = self.taskcbs[txt]
            if cb.get_active():
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

    def groupsExist(self, lst):
        # FIXME: yum specific
        for gid in lst:
            g = self.backend.ayum.comps.return_group(gid)
            if not g:
                return False
        return True

    def getScreen (self, anaconda):
        self.intf = anaconda.intf
        self.dispatch = anaconda.dispatch
        self.backend = anaconda.backend

        self.tasks = anaconda.id.instClass.tasks
        self.taskcbs = {}

        (self.xml, vbox) = gui.getGladeWidget("tasksel.glade", "taskBox")

        lbl = self.xml.get_widget("mainLabel")
        txt = lbl.get_text()
        lbl.set_text(txt %(productName,))

	custom = not self.dispatch.stepInSkipList("group-selection")
        if custom:
            self.xml.get_widget("customRadio").set_active(True)
        else:
            self.xml.get_widget("customRadio").set_active(False)

        found = False
        for (txt, grps) in self.tasks:
            if not self.groupsExist(grps):
                continue
            found = True
            cb = gtk.CheckButton(_(txt))
            self.xml.get_widget("cbVBox").pack_start(cb)
            if self.groupsInstalled(grps):
                cb.set_active(True)
            self.taskcbs[txt] = cb

        if not found:
            self.xml.get_widget("mainLabel").hide()
            self.xml.get_widget("cbVBox").hide()

        return vbox
