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

        if self.anaconda.id.instClass.allowExtraRepos:
            repos = self.xml.get_widget("repoList").get_model()
            for (cb, reponame, repo) in repos:
                if cb:
                    repo.enable()

                    # Setup any repositories that were in the installclass's
                    # default list.
                    self._setupRepo(repo)
                else:
                    repo.disable()

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

    def _setupRepo(self, repo):
        try:
            self.backend.doRepoSetup(self.anaconda, thisrepo = repo.id, fatalerrors = False)
            log.info("added repository %s with with source URL %s" % (repo.name, repo.baseurl[0]))
        except yum.Errors.RepoError, e:
            self.intf.messageWindow(_("Error"),
                  _("Unable to read package metadata from repository.  "
                    "This may be due to a missing repodata directory.  "
                    "Please ensure that your repository has been "
                    "correctly generated.\n\n%s" %(e,)),
                                    type="ok", custom_icon="error")
            self.backend.ayum.repos.delete(repo.id)
            return False

        if not repo.groups_added:
            self.intf.messageWindow(_("Warning"),
                           _("Unable to find a group file for %s.  "
                             "This will prevent manual selection of packages "
                             "from the repository from working") %(repo.id,),
                                    type="warning")

        return True

    def _validURL(self, url):
        return len(url) > 0 and (url.startswith("http://") or
                                 url.startswith("https://") or
                                 url.startswith("ftp://"))

    def _addRepo(self, *args):
        repo = None
        editing = False

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
                editing = True
            else:
                return

        (self.dxml, dialog) = gui.getGladeWidget("addrepo.glade", "addRepoDialog")
        nameEntry = self.dxml.get_widget("nameEntry")
        baseurlButton = self.dxml.get_widget("baseurlButton")
        baseurlEntry = self.dxml.get_widget("baseurlEntry")
        mirrorlistButton = self.dxml.get_widget("mirrorlistButton")
        mirrorlistEntry = self.dxml.get_widget("mirrorlistEntry")
        proxyCheckbox = self.dxml.get_widget("proxyCheckbox")
        proxyEntry = self.dxml.get_widget("proxyEntry")
        proxyTable = self.dxml.get_widget("proxyTable")
        usernameEntry = self.dxml.get_widget("usernameEntry")
        passwordEntry = self.dxml.get_widget("passwordEntry")

        # If we are editing an existing repo, use the existing values to
        # populate the UI.
        # FIXME: this is yum specific
        if editing:
            nameEntry.set_text(repo.name)

            if repo.mirrorlist:
                mirrorlistEntry.set_text(repo.mirrorlist)
                mirrorlistButton.set_active(True)
            else:
                baseurlEntry.set_text(repo.baseurl[0])
                baseurlButton.set_active(True)

            if repo.proxy:
                proxyCheckbox.set_active(True)
                proxyTable.set_sensitive(True)
                proxyEntry.set_text(repo.proxy)
                usernameEntry.set_text(repo.proxy_username)
                passwordEntry.set_text(repo.proxy_password)

        gui.addFrame(dialog)

        # Initialize UI elements that should be sensitive or not.
        self._proxyToggled()
        self._radioChanged()

        proxyCheckbox.connect("toggled", self._proxyToggled)
        baseurlButton.connect("toggled", self._radioChanged)

        lbl = self.dxml.get_widget("descLabel")
        txt = lbl.get_text()
        lbl.set_text(txt %(productName,))

        dialog.show_all()

        while 1:
            rc = dialog.run()
            if rc == gtk.RESPONSE_CANCEL:
                break

            reponame = nameEntry.get_text()
            reponame.strip()
            if len(reponame) == 0:
                self.intf.messageWindow(_("Invalid Repository Name"),
                                        _("You must provide a repository name."))
                continue

            if baseurlButton.get_active():
                repourl = baseurlEntry.get_text()
            else:
                repourl = mirrorlistEntry.get_text()

            repourl.strip()
            if not self._validURL(repourl):
                self.intf.messageWindow(_("Invalid Repository URL"),
                                        _("You must provide an HTTP, HTTPS, "
                                          "or FTP URL to a repository."))
                continue

            proxy = None
            proxy_username = None
            proxy_password = None

            if proxyCheckbox.get_active():
                proxy = proxyEntry.get_text()
                proxy.strip()
                if not self._validURL(proxy):
                    self.intf.messageWindow(_("Invalid Proxy URL"),
                                            _("You must provide an HTTP, HTTPS, "
                                              "or FTP URL to a proxy."))
                    continue

                proxy_username = usernameEntry.get_text()
                proxy_password = passwordEntry.get_text()

            # Don't create a new repo object if we are editing.
            # FIXME: this is yum specific
            if editing:
                if baseurlButton.get_active():
                    repo.baseurl = [repourl]
                else:
                    repo.mirrorlist = repourl

                repo.repoid = reponame.replace(" ", "")
            else:
                repoid = reponame.replace(" ", "")

                if baseurlButton.get_active():
                    repo = AnacondaYumRepo(uri=repourl, repoid=repoid)
                else:
                    repo = AnacondaYumRepo(mirrorlist=repourl, repoid=repoid)

            repo.name = reponame
            repo.basecachedir = self.backend.ayum.conf.cachedir

            if proxy:
                repo.proxy = proxy
                repo.proxy_username = proxy_username
                repo.proxy_password = proxy_password

            repo.enable()

            if editing:
                # Only do this for the real base repo, as that's what will get
                # written out to anaconda-ks.cfg as the method.
                if not repo.addon and not repo.name.startswith("Driver Disk"):
                    self.anaconda.setMethodstr(repourl)

                    # Ideally we should be able to unmount here, but if not
                    # it's probably not a big deal.
                    try:
                        isys.umount(self.backend.ayum.tree)

                        if self.backend.ayum.isodir:
                            isys.umount(self.backend.ayum.isodir)
                    except:
                        pass

                if not self._setupRepo(repo):
                    continue
            else:
                try:
                    self.backend.ayum.repos.add(repo)
                except yum.Errors.DuplicateRepoError, e:
                    self.intf.messageWindow(_("Error"),
                          _("The repository %s has already been added.  Please "
                            "choose a different repository name and "
                            "URL.") % reponame, type="ok", custom_icon="error")
                    continue

                if not self._setupRepo(repo):
                    continue

                s = self.xml.get_widget("repoList").get_model()
                s.append([repo.isEnabled(), repo.name, repo])

            break

        dialog.destroy()
        return rc

    def _radioChanged(self, *args):
        baseurlButton = self.dxml.get_widget("baseurlButton")
        baseurlEntry = self.dxml.get_widget("baseurlEntry")
        mirrorlistEntry = self.dxml.get_widget("mirrorlistEntry")

        active = baseurlButton.get_active()
        baseurlEntry.set_sensitive(active)
        mirrorlistEntry.set_sensitive(not active)

    def _proxyToggled(self, *args):
        table = self.dxml.get_widget("proxyTable")
        checkbox = self.dxml.get_widget("proxyCheckbox")
        table.set_sensitive(checkbox.get_active())

    def _taskToggled(self, data, row, store):
        i = store.get_iter(int(row))
        val = store.get_value(i, 0)
        store.set_value(i, 0, not val)

    def _repoToggled(self, data, row, store):
        i = store.get_iter(int(row))
        val = store.get_value(i, 0)

        if not val and not network.hasActiveNetDev():
            net = NetworkConfigurator(self.anaconda.id.network)
            ret = net.run()
            net.destroy()
            if ret == gtk.RESPONSE_CANCEL:
                return

        store.set_value(i, 0, not val)

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

        if not anaconda.id.instClass.allowExtraRepos:
            vbox.remove(self.xml.get_widget("addRepoBox"))

        self.xml.get_widget("addRepoButton").connect("clicked", self._addRepo)
        self.xml.get_widget("editRepoButton").connect("clicked", self._addRepo, self.rs)

        return vbox
