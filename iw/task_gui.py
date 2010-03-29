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
import gzip
from iw_gui import *
from image import *
from constants import *
import isys
import shutil

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import network
import iutil

from yuminstall import AnacondaYumRepo
import urlgrabber.grabber
import yum.Errors

import logging
log = logging.getLogger("anaconda")

def setupRepo(anaconda, repo):
    if repo.needsNetwork() and not network.hasActiveNetDev():
        if not anaconda.intf.enableNetwork():
            return False
        urlgrabber.grabber.reset_curl_obj()
    try:
        anaconda.backend.doRepoSetup(anaconda, thisrepo=repo.id, fatalerrors=False)
        anaconda.backend.doSackSetup(anaconda, thisrepo=repo.id, fatalerrors=False)
        log.info("added (UI) repository %s with source URL %s, id:%s" % (repo.name, repo.mirrorlist or repo.baseurl, repo.id))
    except (IOError, yum.Errors.RepoError) as e:
        anaconda.intf.messageWindow(_("Error"),
              _("Unable to read package metadata from repository.  "
                "This may be due to a missing repodata directory.  "
                "Please ensure that your repository has been "
                "correctly generated.\n\n%s" % str(e)),
                                type="ok", custom_icon="error")
        repo.disable()
        repo.close()
        anaconda.backend.ayum.repos.delete(repo.id)
        return False

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

        self.dialog.set_title(_("Edit Repository"))

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

    def _addAndEnableRepo(self, repo):
        try:
            self.backend.ayum.repos.add(repo)
        except yum.Errors.DuplicateRepoError, e:
            self.intf.messageWindow(_("Error"),
                  _("The repository %s has already been added.  Please "
                    "choose a different repository name and "
                    "URL.") % self.repo.name, type="ok", custom_icon="error")
            return False

        repo.enable()
        return True

    def _validURL(self, url):
        return len(url) > 0 and (url.startswith("http://") or
                                 url.startswith("https://") or
                                 url.startswith("ftp://"))

    def createDialog(self):

        if self.repo:
            self.nameEntry.set_text(self.repo.name)
            if self.repo.anacondaBaseURLs:
                url = self.repo.anacondaBaseURLs[0]
            else:
                url = ''
            self.typeComboBox.set_active(self._methodToIndex(url))

            if not url or url.startswith("http") or url.startswith("ftp"):
                if self.repo.mirrorlist:
                    self.baseurlEntry.set_text(self.repo.mirrorlist)
                    self.mirrorlistCheckbox.set_active(True)
                else:
                    self.baseurlEntry.set_text(url)

                    self.mirrorlistCheckbox.set_active(False)

                if self.repo.proxy:
                    self.proxyCheckbox.set_active(True)
                    self.proxyTable.set_sensitive(True)
                    self.proxyEntry.set_text(self.repo.proxy)
                    self.usernameEntry.set_text(self.repo.proxy_username or '')
                    self.passwordEntry.set_text(self.repo.proxy_password or '')
                else:
                    self.proxyCheckbox.set_active(False)
                    self.proxyTable.set_sensitive(False)
            elif url.startswith("nfs"):
                (opts, server, path) = iutil.parseNfsUrl(url)
                self.nfsServerEntry.set_text(server)
                self.nfsPathEntry.set_text(path)
                self.nfsOptionsEntry.set_text(opts)
            elif url.startswith("cdrom:"):
                pass
            elif url.startswith("hd:"):
                m = url[3:]
                if m.count(":") == 1:
                    (device, path) = m.split(":")
                    fstype = "auto"
                else:
                    (device, fstype, path) = m.split(":")

                # find device in self.partitionComboBox and select it
                self.directoryChooser.set_current_folder("%s%s" % (self.anaconda.backend.ayum.isodir, path))
            else:
                self.baseurlEntry.set_text(url)

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
            proxy = self.proxyEntry.get_text()
            proxy.strip()

            if not self._validURL(proxy):
                self.intf.messageWindow(_("Invalid Proxy URL"),
                                        _("You must provide an HTTP, HTTPS, "
                                          "or FTP URL to a proxy."))
                return False

            repo.proxy = proxy
            # with empty string yum would create invalid proxy string
            repo.proxy_username = self.usernameEntry.get_text() or None
            repo.proxy_password = self.passwordEntry.get_text() or None

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
        repo.anacondaBaseURLs = repo.baseurl

        repo.name = self.nameEntry.get_text()

        return True

    def _applyMedia(self, repo):
        # FIXME works only if storage has detected format of cdrom drive
        ayum = self.anaconda.backend.ayum
        cdr = scanForMedia(ayum.tree, self.anaconda.storage)
        if not cdr:
            self.intf.messageWindow(_("No Media Found"),
                                    _("No installation media was found. "
                                      "Please insert a disc into your drive "
                                      "and try again."))
            return False

        log.info("found installation media on %s" % cdr)
        repo.name = self.nameEntry.get_text()
        repo.anacondaBaseURLs = ["cdrom://%s:%s" % (cdr, self.anaconda.backend.ayum.tree)]
        repo.baseurl = "file://%s" % ayum.tree
        ayum.mediagrabber = ayum.mediaHandler
        self.anaconda.mediaDevice = cdr
        ayum.currentMedia = 1
        repo.mediaid = getMediaId(ayum.tree)
        log.info("set mediaid of repo %s to: %s" % (repo.name, repo.mediaid))

        return True

    def _applyNfs(self, repo):
        server = self.nfsServerEntry.get_text()
        server.strip()

        path = self.nfsPathEntry.get_text()
        path.strip()

        options = self.nfsOptionsEntry.get_text()
        options.strip()

        repo.name = self.nameEntry.get_text()

        if not server or not path:
            self.intf.messageWindow(_("Error"),
                                    _("Please enter an NFS server and path."))
            return False

        if not network.hasActiveNetDev():
            if not self.anaconda.intf.enableNetwork():
                self.intf.messageWindow(_("No Network Available"),
                    _("Some of your software repositories require "
                      "networking, but there was an error enabling the "
                      "network on your system."))
                return False
            urlgrabber.grabber.reset_curl_obj()

        import tempfile
        dest = tempfile.mkdtemp("", repo.name.replace(" ", ""), "/mnt")

        try:
            isys.mount("%s:%s" % (server, path), dest, "nfs", options=options)
        except Exception as e:
            self.intf.messageWindow(_("Error Setting Up Repository"),
                _("The following error occurred while setting up the "
                  "repository:\n\n%s") % e)
            return False

        repo.baseurl = "file://%s" % dest
        repo.anacondaBaseURLs = ["nfs:%s:%s:%s" % (options,server,path)]
        return True

    def _applyHd(self, repo):
        return True

    def run(self):
        applyFuncs = [ self._applyURL, self._applyMedia, self._applyNfs,
                       self._applyHd ]

        while True:
            rc = self.dialog.run()
            if rc in [gtk.RESPONSE_CANCEL, gtk.RESPONSE_DELETE_EVENT]:
                break

            reponame = self.nameEntry.get_text()
            reponame.strip()
            if len(reponame) == 0:
                self.intf.messageWindow(_("Invalid Repository Name"),
                                        _("You must provide a repository name."))
                continue

            # Always create a new repo object here instead of attempting to
            # somehow expire the metadata and refetch.  We'll just have to make
            # sure that if we're just editing the repo, we grab all the
            # attributes from the old one before deleting it.
            if self.repo:
                # use temporary id so that we don't get Duplicate Repo error
                # when adding
                newRepoObj = AnacondaYumRepo("UIedited_%s" %
                                             self.anaconda.backend.ayum.repoIDcounter.next())
                newRepoObj.cost = self.repo.cost
                removeOld = True
            else:
                newRepoObj = AnacondaYumRepo(reponame.replace(" ", ""))
                removeOld = False

            # corresponds to self.repos.setCacheDir in AnacondaYum.doConfigSetup
            newRepoObj.basecachedir = self.anaconda.backend.ayum.conf.cachedir

            type = self.typeComboBox.get_active()
            if not applyFuncs[type](newRepoObj) or not self._addAndEnableRepo(newRepoObj) or not \
                   setupRepo(self.anaconda, newRepoObj):
                continue

            if removeOld:
                try:
                    os.unlink("%s/cachecookie" % self.repo.cachedir)
                    os.unlink("%s/repomd.xml" % self.repo.cachedir)
                except:
                    pass

                self.repo.disable()
                self.repo.close()
                self.anaconda.backend.ayum.repos.delete(self.repo.id)
                log.info("deleted (UI) repository %s with source URL %s, id:%s"
                         % (self.repo.name, self.repo.mirrorlist or self.repo.baseurl, self.repo.id))
                try:
                    shutil.rmtree(self.repo.cachedir)
                except Exception as e:
                    log.warning("error removing cachedir for %s: %s" %(self.repo, e))
                    pass

            if (newRepoObj.enablegroups or 
                (removeOld and self.repo.enablegroups)):
                # update groups information
                try:
                    self.anaconda.backend.ayum.doGroupSetup()
                except Exception as e:
                    log.debug("unable to reset group information after UI repo edit: %s"
                              % e)
                else:
                    log.info("group information reset after UI repo edit")

            self.repo = newRepoObj
            break

        self.dialog.hide()
        return rc

class RepoMethodstrEditor(RepoEditor):
    def __init__(self, anaconda, methodstr):
        # Create temporary repo to store methodstr needed for
        # createDialog parent method.
        temprepo = AnacondaYumRepo("UITmpMethodstrRepo")
        temprepo.name = "Installation Repo"
        temprepo.anacondaBaseURLs = [methodstr]
        RepoEditor.__init__(self, anaconda, temprepo)

    def createDialog(self):
        RepoEditor.createDialog(self)

        # Hide a bunch of stuff that doesn't apply when we're just prompting
        # for enough information to form a methodstr.
        self.nameEntry.set_sensitive(False)
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
        cdr = scanForMedia(self.anaconda.backend.ayum.tree, self.anaconda.storage)
        if not cdr:
            self.intf.messageWindow(_("No Media Found"),
                                    _("No installation media was found. "
                                      "Please insert a disc into your drive "
                                      "and try again."))
            return False

        self.anaconda.backend.ayum.mediagrabber = self.anaconda.backend.ayum.mediaHandler
        self.anaconda.backend.ayum.anaconda.mediaDevice = cdr
        self.anaconda.backend.ayum.currentMedia = 1
        log.info("found installation media on %s" % cdr)
        return "cdrom://%s:%s" % (cdr, self.anaconda.backend.ayum.tree)

    def _applyNfs(self):
        server = self.nfsServerEntry.get_text()
        server.strip()

        path = self.nfsPathEntry.get_text()
        path.strip()

        options = self.nfsOptionsEntry.get_text()
        options.strip()

        if not server or not path:
            self.intf.messageWindow(_("Error"),
                                    _("Please enter an NFS server and path."))
            return False

        return "nfs:%s:%s:%s" % (options, server, path)

    def _applyHd(self):
        return None

    def run(self):
        applyFuncs = [ self._applyURL, self._applyMedia, self._applyNfs,
                       self._applyHd ]

        while True:
            rc = self.dialog.run()
            if rc in [gtk.RESPONSE_CANCEL, gtk.RESPONSE_DELETE_EVENT]:
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
        self.dialog.set_title(_("Add Repository"))

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
        for (cb, task, grps) in filter(lambda x: not x[0], tasks):
            map(lambda g: setattr(self.backend.ayum.comps.return_group(g),
                                  "default", False), grps)
        for (cb, task, grps) in filter(lambda x: x[0], tasks):
            map(lambda g: setattr(self.backend.ayum.comps.return_group(g),
                                  "default", True), grps)

    def _editRepo(self, *args):
        repo = None

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

        if repo.needsNetwork() and not network.hasActiveNetDev():
            if not self.anaconda.intf.enableNetwork():
                return gtk.RESPONSE_CANCEL

            urlgrabber.grabber.reset_curl_obj()

        dialog = RepoEditor(self.anaconda, repo)
        dialog.createDialog()
        dialog.run()

        model.set_value(iter, 0, dialog.repo.isEnabled())
        model.set_value(iter, 1, dialog.repo.name)
        model.set_value(iter, 2, dialog.repo)

    def _addRepo(self, *args):
        dialog = RepoCreator(self.anaconda)
        dialog.createDialog()
        if dialog.run() in [gtk.RESPONSE_CANCEL, gtk.RESPONSE_DELETE_EVENT]:
            return gtk.RESPONSE_CANCEL

        s = self.xml.get_widget("repoList").get_model()
        s.append([dialog.repo.isEnabled(), dialog.repo.name, dialog.repo])

    def _taskToggled(self, button, path, store):
        # First, untoggle everything in the store.
        for row in store:
            row[0] = False

        # Then, enable the one that was clicked.
        store[path][0] = True

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
            if repo.needsNetwork() and not network.hasActiveNetDev():
                if not self.anaconda.intf.enableNetwork():
                    return

                urlgrabber.grabber.reset_curl_obj()

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
        cbr.set_radio(True)
        cbr.connect("toggled", self._taskToggled, store)

        col = gtk.TreeViewColumn('', cbr, active = 0)
        tl.append_column(col)

        col = gtk.TreeViewColumn('Text', gtk.CellRendererText(), text = 1)
        col.set_clickable(False)
        tl.append_column(col)

        anyEnabled = False

        for (txt, grps) in self.tasks:
            if not self.backend.groupListExists(grps):
                continue

            enabled = self.backend.groupListDefault(grps)
            store.append([not anyEnabled and enabled, _(txt), grps])

            if enabled:
                anyEnabled = True

        return tl

    def __sortRepos(self, store, aIter, bIter):
        aStr = store.get_value(aIter, 1)
        bStr = store.get_value(bIter, 1)

        if aStr == "Installation Repo":
            return -1
        elif bStr == "Installation Repo":
            return 1
        elif aStr < bStr or bStr is None:
            return -1
        elif aStr > bStr or aStr is None:
            return 1
        else:
            return aStr == bStr

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

        store.set_sort_column_id(1, gtk.SORT_ASCENDING)
        store.set_sort_func(1, self.__sortRepos)

        return tl

    def getScreen (self, anaconda):
        self.intf = anaconda.intf
        self.dispatch = anaconda.dispatch
        self.backend = anaconda.backend
        self.anaconda = anaconda

        self.tasks = anaconda.instClass.tasks
        self.repos = anaconda.backend.ayum.repos

        (self.xml, vbox) = gui.getGladeWidget("tasksel.glade", "taskBox")

        lbl = self.xml.get_widget("mainLabel")
        if anaconda.instClass.description:
            lbl.set_text(_(anaconda.instClass.description))
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
