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

import network

from yuminstall import AnacondaYumRepo
import yum.Errors

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

    def _addRepo(self, *args):
        # FIXME: Need to bring up the network
        if not network.hasActiveNetDev():
            self.intf.messageWindow("Need network",
                                    "additional repos can only be configured "
                                    "if you have a network available.",
                                    custom_icon="error")
            return gtk.RESPONSE_CANCEL
        
        (dxml, dialog) = gui.getGladeWidget("addrepo.glade", "addRepoDialog")
        gui.addFrame(dialog)
        dialog.show_all()

        while 1:
            rc = dialog.run()
            if rc == gtk.RESPONSE_CANCEL:
                break
        
            reponame = dxml.get_widget("nameEntry").get_text()
            reponame.strip()
            if len(reponame) == 0:
                self.intf.messageWindow(_("Invalid Repository Name"),
                                        _("You must provide a non-zero length "
                                          "repository name."))
                continue

            repourl = dxml.get_widget("urlEntry").get_text()
            repourl.strip()
            if (len(repourl) == 0 or not
                (repourl.startswith("http://") or
                 repourl.startswith("ftp://"))):
                self.intf.messageWindow(_("Invalid Repository URL"),
                                        _("You must provide an HTTP or FTP "
                                          "URL to a repository."))
                continue

            # FIXME: this is yum specific
            repo = AnacondaYumRepo(uri=repourl, repoid=reponame)
            repo.basecachedir = self.backend.ayum.conf.cachedir
            repo.enable()
            self.backend.ayum.repos.add(repo)

            try:
                self.backend.doRepoSetup(self.anaconda, reponame,
                                         fatalerrors = False)
            except yum.Errors.RepoError, e:
                self.intf.messageWindow(_("Error"),
                      _("Unable to read package metadata from repository.  "
                        "This may be due to a missing repodata directory.  "
                        "Please ensure that your repository has been "
                        "correctly generated.\n\n%s" %(e,)),
                                        type="ok", custom_icon="error")
                self.backend.ayum.repos.delete(reponame)
                continue
            break

        dialog.destroy()
        return rc
            
    def getScreen (self, anaconda):
        self.intf = anaconda.intf
        self.dispatch = anaconda.dispatch
        self.backend = anaconda.backend
        self.anaconda = anaconda

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

        self.xml.get_widget("addRepoButton").connect("clicked", self._addRepo)

        return vbox
