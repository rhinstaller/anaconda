#
# task_gui.py: Choose tasks for installation
#
# Copyright (C) 2006, 2007, 2008 Red Hat, Inc.  All rights reserved.
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

import gtk
import gtk.glade
import gobject
import gui
from iw_gui import *
from image import *
from constants import *
import isys

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import network

from yuminstall import AnacondaYumRepo
import yum.Errors

import logging
log = logging.getLogger("anaconda")

def setupRepo(anaconda, repo):
    try:
        anaconda.backend.doRepoSetup(anaconda, thisrepo=repo.id, fatalerrors=False)
        anaconda.backend.doSackSetup(anaconda, thisrepo=repo.id, fatalerrors=False)
        log.info("added repository %s with with source URL %s" % (repo.name, repo.baseurl[0]))
    except yum.Errors.RepoError, e:
        anaconda.intf.messageWindow(_("Error"),
              _("Unable to read package metadata from repository.  "
                "This may be due to a missing repodata directory.  "
                "Please ensure that your repository has been "
                "correctly generated.\n\n%s" %(e,)),
                                type="ok", custom_icon="error")
        anaconda.backend.ayum.repos.delete(repo.id)
        return False

    if not repo.groups_added:
        anaconda.intf.messageWindow(_("Warning"),
                       _("Unable to find a group file for %s.  "
                         "This will prevent manual selection of packages "
                         "from the repository from working") %(repo.name,),
                                type="warning")

    return True

class RepoEditor:
    # Window-level callbacks
    def on_addRepoDialog_destroy(self, widget, *args):
        pass

    def on_cancelButton_clicked(self, widget, *args):
        pass

    def on_okButton_clicked(self, widget, *args):
        pass

    def on_typeComboBox_changed(self, widget, *args):
        if widget.get_active() == -1:
            return

        # When the combo box's value is changed, set the notebook's current
        # page to match.  This requires that the combo box and notebook have
        # the same method types at the same indices (so, HTTP must be the
        # same position on both, etc.).
        self.notebook.set_current_page(widget.get_active())

        if widget.get_active() == 1:
            if self.repo:
                self.proxyCheckbox.set_active(self.repo.proxy is True)
                self.proxyTable.set_sensitive(self.repo.proxy is True)
            else:
                self.proxyCheckbox.set_active(False)
                self.proxyTable.set_sensitive(False)

    # URL-specific callbacks
    def on_proxyCheckbox_toggled(self, widget, *args):
        table = self.dxml.get_widget("proxyTable")
        table.set_sensitive(widget.get_active())

    def on_mirrorlistCheckbox_toggled(self, widget, *args):
        pass

    def __init__(self, anaconda, repoObj):
        self.anaconda = anaconda
        self.backend = self.anaconda.backend
        self.intf = self.anaconda.intf
        self.repo = repoObj

        (self.dxml, self.dialog) = gui.getGladeWidget("addrepo.glade", "addRepoDialog")
        self.dxml.signal_autoconnect(self)

        self.notebook = self.dxml.get_widget("typeNotebook")
        self.nameEntry = self.dxml.get_widget("nameEntry")
        self.typeComboBox = self.dxml.get_widget("typeComboBox")

        self.baseurlEntry = self.dxml.get_widget("baseurlEntry")
        self.mirrorlistCheckbox = self.dxml.get_widget("mirrorlistCheckbox")
        self.proxyCheckbox = self.dxml.get_widget("proxyCheckbox")
        self.proxyEntry = self.dxml.get_widget("proxyEntry")
        self.proxyTable = self.dxml.get_widget("proxyTable")
        self.usernameEntry = self.dxml.get_widget("usernameEntry")
        self.passwordEntry = self.dxml.get_widget("passwordEntry")

        self.nfsServerEntry = self.dxml.get_widget("nfsServerEntry")
        self.nfsPathEntry = self.dxml.get_widget("nfsPathEntry")
        self.nfsOptionsEntry = self.dxml.get_widget("nfsOptionsEntry")

        self.partitionComboBox = self.dxml.get_widget("partitionComboBox")
        self.directoryChooser = self.dxml.get_widget("directoryChooserButton")

        # Remove these until they are actually implemented
        self.typeComboBox.remove_text(3)

    # Given a method string, return the index of the typeComboBox that should
    # be made active in order to match.
    def _methodToIndex(self, method):
        mapping = {"http": 0, "ftp": 0, "https": 0,
                   "cdrom": 1,
                   "nfs": 2}
#                   "nfs": 2, "nfsiso": 2,
#                   "hd": 3}

        try:
            return mapping[method.split(':')[0].lower()]
        except:
            return 0

    def _enableRepo(self, repourl):
        # FIXME:  Don't do anything here for now.
        return True

    def _validURL(self, url):
        return len(url) > 0 and (url.startswith("http://") or
                                 url.startswith("https://") or
                                 url.startswith("ftp://"))

    def createDialog(self):
        self.dialog.set_title(_("Edit Repository"))

        if self.repo:
            self.nameEntry.set_text(self.repo.name)
            self.typeComboBox.set_active(self._methodToIndex(self.anaconda.methodstr))

            if not self.anaconda.methodstr or self.anaconda.methodstr.startswith("http") or self.anaconda.methodstr.startswith("ftp"):
                if self.repo.mirrorlist:
                    self.baseurlEntry.set_text(self.repo.mirrorlist)
                    self.mirrorlistCheckbox.set_active(True)
                else:
                    self.baseurlEntry.set_text(self.repo.baseurl[0])
                    self.mirrorlistCheckbox.set_active(False)

                if self.repo.proxy:
                    self.proxyCheckbox.set_active(True)
                    self.proxyTable.set_sensitive(True)
                    self.proxyEntry.set_text(self.repo.proxy)
                    self.usernameEntry.set_text(self.repo.proxy_username)
                    self.passwordEntry.set_text(self.repo.proxy_password)
                else:
                    self.proxyCheckbox.set_active(False)
                    self.proxyTable.set_sensitive(False)
            elif self.anaconda.methodstr.startswith("nfs"):
                (method, server, dir) = self.anaconda.methodstr.split(":")
                self.nfsServerEntry.set_text(server)
                self.nfsPathEntry.set_text(dir)
                self.nfsOptionsEntry.set_text("")
            elif self.anaconda.methodstr.startswith("cdrom:"):
                pass
            elif self.anaconda.methodstr.startswith("hd:"):
                m = self.anaconda.methodstr[3:]
                if m.count(":") == 1:
                    (device, path) = m.split(":")
                    fstype = "auto"
                else:
                    (device, fstype, path) = m.split(":")

                # find device in self.partitionComboBox and select it
                self.directoryChooser.set_current_folder(path)
        else:
            self.typeComboBox.set_active(0)
            self.proxyCheckbox.set_active(False)
            self.proxyTable.set_sensitive(False)

        gui.addFrame(self.dialog)

        lbl = self.dxml.get_widget("descLabel")
        txt = lbl.get_text()
        lbl.set_text(txt)

        self.dialog.show_all()

    def _applyURL(self, repo):
        if self.proxyCheckbox.get_active():
            repo.proxy = self.proxyEntry.get_text()
            repo.proxy.strip()
            if not self._validURL(repo.proxy):
                self.intf.messageWindow(_("Invalid Proxy URL"),
                                        _("You must provide an HTTP, HTTPS, "
                                          "or FTP URL to a proxy."))
                return False

            repo.proxy_username = self.usernameEntry.get_text()
            repo.proxy_password = self.passwordEntry.get_text()

        repourl = self.baseurlEntry.get_text()
        repourl.strip()
        if not self._validURL(repourl):
            self.intf.messageWindow(_("Invalid Repository URL"),
                                    _("You must provide an HTTP, HTTPS, "
                                      "or FTP URL to a repository."))
            return False

        if self.mirrorlistCheckbox.get_active():
            repo.baseurl = []
            repo.mirrorlist = repourl
        else:
            repo.baseurl = [repourl]
            repo.mirrorlist = None

        repo.name = self.nameEntry.get_text()
        repo.basecachedir = self.backend.ayum.conf.cachedir

        if repo.name == "Installation Repo":
            self.anaconda.setMethodstr(repourl)

        return True

    def _applyMedia(self, repo):
        cdr = scanForMedia(self.anaconda.backend.ayum.tree)
        if not cdr:
            self.intf.messageWindow(_("No Media Found"),
                                    _("No installation media was found. "
                                      "Please insert a disc into your drive "
                                      "and try again."))
            return False

        self.anaconda.setMethodstr("cdrom://%s:%s" % (cdr, self.anaconda.backend.ayum.tree))
        self.anaconda.backend.ayum.configBaseURL()
        self.anaconda.backend.ayum.configBaseRepo(replace=True)
        return True

    def _applyNfs(self, repo):
        server = self.nfsServerEntry.get_text()
        server.strip()

        path = self.nfsPathEntry.get_text()
        path.strip()

        if not server or not path:
            self.intf.messageWindow(_("Error"),
                                    _("Please enter an NFS server and path."))
            return False

        self.anaconda.setMethodstr("nfs:%s:%s" % (server, path))

        try:
            self.anaconda.backend.ayum.configBaseURL()
        except SystemError, e:
            self.intf.messageWindow(_("Error Setting Up Repository"),
                _("The following error occurred while setting up the "
                  "installation repository:\n\n%s\n\nPlease provide the "
                  "correct information for installing %s.") % (e, productName))
            return False

        self.anaconda.backend.ayum.configBaseRepo(replace=True)
        return True

    def _applyHd(self, repo):
        return True

    def run(self, createNewRepoObj=False):
        applyFuncs = [ self._applyURL, self._applyMedia, self._applyNfs,
                       self._applyHd ]

        while True:
            rc = self.dialog.run()
            if rc == gtk.RESPONSE_CANCEL:
                break

            reponame = self.nameEntry.get_text()
            reponame.strip()
            if len(reponame) == 0:
                self.intf.messageWindow(_("Invalid Repository Name"),
                                        _("You must provide a repository name."))
                continue

            if createNewRepoObj:
                self.repo = AnacondaYumRepo(repoid=reponame.replace(" ", ""))
            else:
                self.repo.repoid = reponame.replace(" ", "")

            type = self.typeComboBox.get_active()
            if not applyFuncs[type](self.repo):
                continue

            repourl = self.baseurlEntry.get_text()
            repourl.strip()

            if not self._enableRepo(repourl):
                continue

            # this is a bit gross... but we need to make sure that
            # the urls and grabber get set back up based on new urls
            self.repo._grab = None
            self.repo._urls = None

            if not setupRepo(self.anaconda, self.repo):
                continue

            break

        self.dialog.hide()
        return rc

class RepoMethodstrEditor(RepoEditor):
    def __init__(self, anaconda):
        RepoEditor.__init__(self, anaconda, None)

    def createDialog(self):
        RepoEditor.createDialog(self)

        # Hide a bunch of stuff that doesn't apply when we're just prompting
        # for enough information to form a methodstr.
        self.dxml.get_widget("nameLabel").hide()
        self.nameEntry.hide()
        self.mirrorlistCheckbox.hide()
        self.proxyCheckbox.hide()
        self.proxyTable.hide()

    def _applyURL(self):
        repourl = self.baseurlEntry.get_text()
        repourl.strip()
        if not self._validURL(repourl):
            self.intf.messageWindow(_("Invalid Repository URL"),
                                    _("You must provide an HTTP, HTTPS, "
                                      "or FTP URL to a repository."))
            return False

        return repourl

    def _applyMedia(self):
        cdr = scanForMedia(self.anaconda.backend.ayum.tree)
        if not cdr:
            self.intf.messageWindow(_("No Media Found"),
                                    _("No installation media was found. "
                                      "Please insert a disc into your drive "
                                      "and try again."))
            return False

        return "cdrom://%s:%s" % (cdr, self.anaconda.backend.ayum.tree)

    def _applyNfs(self):
        server = self.nfsServerEntry.get_text()
        server.strip()

        path = self.nfsPathEntry.get_text()
        path.strip()

        if not server or not path:
            self.intf.messageWindow(_("Error"),
                                    _("Please enter an NFS server and path."))
            return False

        return "nfs:%s:%s" % (server, path)

    def _applyHd(self):
        return None

    def run(self):
        applyFuncs = [ self._applyURL, self._applyMedia, self._applyNfs,
                       self._applyHd ]

        while True:
            rc = self.dialog.run()
            if rc == gtk.RESPONSE_CANCEL:
                rc = None
                break

            type = self.typeComboBox.get_active()
            retval = applyFuncs[type]()
            if not retval:
                continue

            rc = retval
            break

        self.dialog.hide()
        return rc

class RepoCreator(RepoEditor):
    def __init__(self, anaconda):
        RepoEditor.__init__(self, anaconda, None)

    def createDialog(self):
        RepoEditor.createDialog(self)
        self.dialog.set_title(_("Add Repository"))
    def _enableRepo(self, repourl):
        try:
            self.backend.ayum.repos.add(self.repo)
        except yum.Errors.DuplicateRepoError, e:
            self.intf.messageWindow(_("Error"),
                  _("The repository %s has already been added.  Please "
                    "choose a different repository name and "
                    "URL.") % reponame, type="ok", custom_icon="error")
            return False

        return True

    def run(self, createNewRepoObj=True):
        return RepoEditor.run(self, createNewRepoObj)

class TaskWindow(InstallWindow):
    def getNext(self):
        if not self._anyRepoEnabled():
            self.anaconda.intf.messageWindow(_("No Software Repos Enabled"),
                _("You must have at least one software repository enabled to "
                  "continue installation."))
            raise gui.StayOnScreen

        if self.xml.get_widget("customRadio").get_active():
            self.dispatch.skipStep("group-selection", skip = 0)
        else:
            self.dispatch.skipStep("group-selection", skip = 1)

        tasks = self.xml.get_widget("taskList").get_model()
        for (cb, task, grps) in tasks:
            if cb:
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

    def _editRepo(self, *args):
        repo = None

        if not network.hasActiveNetDev():
            if not self.anaconda.intf.enableNetwork(self.anaconda):
                return gtk.RESPONSE_CANCEL

        # If we were passed an extra argument, it's the repo store and we
        # are editing an existing repo as opposed to adding a new one.
        if len(args) > 1:
            (model, iter) = args[1].get_selection().get_selected()
            if iter:
                repo = model.get_value(iter, 2)
            else:
                return
        else:
            return

        dialog = RepoEditor(self.anaconda, repo)
        dialog.createDialog()
        dialog.run()

    def _addRepo(self, *args):
        if not network.hasActiveNetDev():
            if not self.anaconda.intf.enableNetwork(self.anaconda):
                return gtk.RESPONSE_CANCEL

        dialog = RepoCreator(self.anaconda)
        dialog.createDialog()
        if dialog.run() == gtk.RESPONSE_CANCEL:
            return gtk.RESPONSE_CANCEL

        s = self.xml.get_widget("repoList").get_model()
        s.append([dialog.repo.isEnabled(), dialog.repo.name, dialog.repo])

    def _taskToggled(self, button, row, store):
        i = store.get_iter(int(row))
        val = store.get_value(i, 0)
        store.set_value(i, 0, not val)

    def _anyRepoEnabled(self):
        model = self.rs.get_model()
        iter = model.get_iter_first()

        while True:
            if model.get_value(iter, 0):
                return True

            iter = model.iter_next(iter)
            if not iter:
                return False

        return False

    def _repoToggled(self, button, row, store):
        i = store.get_iter(int(row))
        wasChecked = store.get_value(i, 0)
        repo = store.get_value(i, 2)

        if not wasChecked:
            if not network.hasActiveNetDev():
                if not self.anaconda.intf.enableNetwork(self.anaconda):
                    return

            repo.enable()
            if not setupRepo(self.anaconda, repo):
                return
        else:
            repo.disable()
            repo.close()

        store.set_value(i, 0, not wasChecked)

    def _createTaskStore(self):
        store = gtk.ListStore(gobject.TYPE_BOOLEAN,
                              gobject.TYPE_STRING,
                              gobject.TYPE_PYOBJECT)
        tl = self.xml.get_widget("taskList")
        tl.set_model(store)

        cbr = gtk.CellRendererToggle()
        col = gtk.TreeViewColumn('', cbr, active = 0)
        cbr.connect("toggled", self._taskToggled, store)
        tl.append_column(col)

        col = gtk.TreeViewColumn('Text', gtk.CellRendererText(), text = 1)
        col.set_clickable(False)
        tl.append_column(col)

        for (txt, grps) in self.tasks:
            if not self.groupsExist(grps):
                continue
            store.append([self.groupsInstalled(grps), _(txt), grps])

        return tl

    def _createRepoStore(self):
        store = gtk.ListStore(gobject.TYPE_BOOLEAN,
                              gobject.TYPE_STRING,
                              gobject.TYPE_PYOBJECT)
        store.set_sort_column_id(1, gtk.SORT_ASCENDING)

        tl = self.xml.get_widget("repoList")
        tl.set_model(store)

        cbr = gtk.CellRendererToggle()
        col = gtk.TreeViewColumn('', cbr, active = 0)
        cbr.connect("toggled", self._repoToggled, store)
        tl.append_column(col)

        col = gtk.TreeViewColumn('Text', gtk.CellRendererText(), text = 1)
        col.set_clickable(False)
        tl.append_column(col)

        for (reponame, repo) in self.repos.repos.items():
            store.append([repo.isEnabled(), repo.name, repo])

        return tl

    def getScreen (self, anaconda):
        self.intf = anaconda.intf
        self.dispatch = anaconda.dispatch
        self.backend = anaconda.backend
        self.anaconda = anaconda

        self.tasks = anaconda.id.instClass.tasks
        self.repos = anaconda.backend.ayum.repos

        (self.xml, vbox) = gui.getGladeWidget("tasksel.glade", "taskBox")

        lbl = self.xml.get_widget("mainLabel")
        if anaconda.id.instClass.description:
            lbl.set_text(_(anaconda.id.instClass.description))
        else:
            txt = lbl.get_text()
            lbl.set_text(txt %(productName,))

        custom = not self.dispatch.stepInSkipList("group-selection")
        if custom:
            self.xml.get_widget("customRadio").set_active(True)
        else:
            self.xml.get_widget("customRadio").set_active(False)

        self.ts = self._createTaskStore()
        self.rs = self._createRepoStore()

        if len(self.ts.get_model()) == 0:
            self.xml.get_widget("cbVBox").hide()
            self.xml.get_widget("mainLabel").hide()

        self.xml.get_widget("addRepoButton").connect("clicked", self._addRepo)
        self.xml.get_widget("editRepoButton").connect("clicked", self._editRepo, self.rs)

        return vbox
