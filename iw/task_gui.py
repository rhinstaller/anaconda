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
from rhpl.translate import _, N_
from constants import productName
import isys

from netconfig_dialog import NetworkConfigurator
import network

from yuminstall import AnacondaYumRepo
import yum.Errors

import logging
log = logging.getLogger("anaconda")

def setupRepo(anaconda, repo):
    try:
        anaconda.backend.doRepoSetup(anaconda, thisrepo = repo.id, fatalerrors = False)
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
    def __init__(self, anaconda, repoObj):
        self.anaconda = anaconda
        self.backend = self.anaconda.backend
        self.intf = self.anaconda.intf
        self.repo = repoObj

        (self.dxml, self.dialog) = gui.getGladeWidget("addrepo.glade", "addRepoDialog")
        self.nameEntry = self.dxml.get_widget("nameEntry")
        self.baseurlButton = self.dxml.get_widget("baseurlButton")
        self.baseurlEntry = self.dxml.get_widget("baseurlEntry")
        self.mirrorlistButton = self.dxml.get_widget("mirrorlistButton")
        self.mirrorlistEntry = self.dxml.get_widget("mirrorlistEntry")
        self.proxyCheckbox = self.dxml.get_widget("proxyCheckbox")
        self.proxyEntry = self.dxml.get_widget("proxyEntry")
        self.proxyTable = self.dxml.get_widget("proxyTable")
        self.usernameEntry = self.dxml.get_widget("usernameEntry")
        self.passwordEntry = self.dxml.get_widget("passwordEntry")

        self.dialog.set_title(_("Edit Repository"))

    def _enableRepo(self, repourl):
        # Only do this for the real base repo, as that's what will get
        # written out to anaconda-ks.cfg as the method.
        if not self.repo.addon and not self.repo.name.startswith("Driver Disk"):
            self.anaconda.setMethodstr(repourl)

            # Ideally we should be able to unmount here, but if not
            # it's probably not a big deal.
            try:
                isys.umount(self.backend.ayum.tree)

                if self.backend.ayum.isodir:
                    isys.umount(self.backend.ayum.isodir)
            except:
                pass

        return True

    def _proxyToggled(self, *args):
        self.proxyTable.set_sensitive(self.proxyCheckbox.get_active())

    def _radioChanged(self, *args):
        active = self.baseurlButton.get_active()
        self.baseurlEntry.set_sensitive(active)
        self.mirrorlistEntry.set_sensitive(not active)

    def _validURL(self, url):
        return len(url) > 0 and (url.startswith("http://") or
                                 url.startswith("https://") or
                                 url.startswith("ftp://"))

    def createDialog(self):
        if self.repo:
            self.nameEntry.set_text(self.repo.name)

            if self.repo.mirrorlist:
                self.mirrorlistEntry.set_text(self.repo.mirrorlist)
                self.mirrorlistButton.set_active(True)
            else:
                self.baseurlEntry.set_text(self.repo.baseurl[0])
                self.baseurlButton.set_active(True)

            if self.repo.proxy:
                self.proxyCheckbox.set_active(True)
                self.proxyTable.set_sensitive(True)
                self.proxyEntry.set_text(self.repo.proxy)
                self.usernameEntry.set_text(self.repo.proxy_username)
                self.passwordEntry.set_text(self.repo.proxy_password)

        gui.addFrame(self.dialog)

        # Initialize UI elements that should be sensitive or not.
        self._proxyToggled()
        self._radioChanged()

        self.proxyCheckbox.connect("toggled", self._proxyToggled)
        self.baseurlButton.connect("toggled", self._radioChanged)

        lbl = self.dxml.get_widget("descLabel")
        txt = lbl.get_text()
        lbl.set_text(txt)

        self.dialog.show_all()

    def run(self, createNewRepoObj=False):
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

            proxy = None
            proxy_username = None
            proxy_password = None

            if self.proxyCheckbox.get_active():
                proxy = self.proxyEntry.get_text()
                proxy.strip()
                if not self._validURL(proxy):
                    self.intf.messageWindow(_("Invalid Proxy URL"),
                                            _("You must provide an HTTP, HTTPS, "
                                              "or FTP URL to a proxy."))
                    continue

                proxy_username = self.usernameEntry.get_text()
                proxy_password = self.passwordEntry.get_text()

            if createNewRepoObj:
                self.repo = AnacondaYumRepo(repoid=reponame.replace(" ", ""))
            else:
                self.repo.repoid = reponame.replace(" ", "")

            if self.baseurlButton.get_active():
                repourl = self.baseurlEntry.get_text()
            else:
                repourl = self.mirrorlistEntry.get_text()

            repourl.strip()
            if not self._validURL(repourl):
                self.intf.messageWindow(_("Invalid Repository URL"),
                                        _("You must provide an HTTP, HTTPS, "
                                          "or FTP URL to a repository."))
                continue

            if self.baseurlButton.get_active():
                self.repo.baseurl = [repourl]
            else:
                self.repo.mirrorlist = repourl

            self.repo.name = reponame
            self.repo.basecachedir = self.backend.ayum.conf.cachedir

            if proxy:
                self.repo.proxy = proxy
                self.repo.proxy_username = proxy_username
                self.repo.proxy_password = proxy_password

                self.repo.enable()

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

class RepoCreator(RepoEditor):
    def __init__(self, anaconda):
        RepoEditor.__init__(self, anaconda, None)

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
            net = NetworkConfigurator(self.anaconda.id.network)
            ret = net.run()
            net.destroy()
            if ret == gtk.RESPONSE_CANCEL:
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
            net = NetworkConfigurator(self.anaconda.id.network)
            ret = net.run()
            net.destroy()
            if ret == gtk.RESPONSE_CANCEL:
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

    def _repoToggled(self, button, row, store):
        i = store.get_iter(int(row))
        wasChecked = store.get_value(i, 0)
        repo = store.get_value(i, 2)

        # The base repositories can never be disabled, but they can be edited.
        if wasChecked and not repo.addon:
            button.set_active(True)
            return

        if not wasChecked:
            if not network.hasActiveNetDev():
                net = NetworkConfigurator(self.anaconda.id.network)
                ret = net.run()
                net.destroy()
                if ret == gtk.RESPONSE_CANCEL:
                    return

            repo.enable()
            if not setupRepo(self.anaconda, repo):
                return
        else:
            repo.disable()

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
