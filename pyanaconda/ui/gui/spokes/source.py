# Installation source spoke classes
#
# Copyright (C) 2011, 2012  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Chris Lumens <clumens@redhat.com>
#                    Martin Sivak <msivak@redhat.com>
#

import gettext
import time
_ = lambda x: gettext.ldgettext("anaconda", x)
N_ = lambda x: x

import logging
log = logging.getLogger("anaconda")

import os.path

from gi.repository import AnacondaWidgets, GLib, Gtk

from pyanaconda.flags import flags
from pyanaconda.image import opticalInstallMedia, potentialHdisoSources
from pyanaconda.ui.gui import GUIObject, communication
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.categories.software import SoftwareCategory
from pyanaconda.ui.gui.utils import enlightbox, gtk_thread_wait
from pyanaconda.iutil import ProxyString, ProxyStringError
from pyanaconda.ui.gui.utils import gtk_call_once
from pyanaconda.threads import threadMgr, AnacondaThread
from pyanaconda.packaging import PayloadError, get_mount_paths, MetadataError
from pyanaconda.constants import DRACUT_ISODIR, ISO_DIR

__all__ = ["SourceSpoke"]

BASEREPO_SETUP_MESSAGE = N_("Setting up installation source...")
METADATA_DOWNLOAD_MESSAGE = N_("Downloading package metadata...")
METADATA_ERROR_MESSAGE = N_("Error downloading package metadata...")

class ProxyDialog(GUIObject):
    builderObjects = ["proxyDialog"]
    mainWidgetName = "proxyDialog"
    uiFile = "spokes/source.glade"

    def on_proxy_cancel_clicked(self, *args):
        self.window.destroy()

    def on_proxy_add_clicked(self, *args):
        # If the user unchecked the proxy entirely, that means they want it
        # disabled.
        if not self._proxyCheck.get_active():
            self.data.method.proxy = ""
            self.window.destroy()
            return

        url = self._proxyURLEntry.get_text()
        if self._authCheck.get_active():
            username = self._proxyUsernameEntry.get_text()
            password = self._proxyPasswordEntry.get_text()
        else:
            username = None
            password = None

        try:
            proxy = ProxyString(url=url, username=username, password=password)
            self.data.method.proxy = proxy.url
        except ProxyStringError as e:
            log.error("Failed to parse proxy for ProxyDialog Add - %s:%s@%s: %s" \
                      % (username, password, url, e))
            # TODO - tell the user they entered an invalid proxy and let them retry
            self.data.method.proxy = ""

        self.window.destroy()

    def on_proxy_enable_toggled(self, button, *args):
        self._proxyInfoBox.set_sensitive(button.get_active())

    def on_proxy_auth_toggled(self, button, *args):
        self._proxyAuthBox.set_sensitive(button.get_active())

    def refresh(self):
        import re

        GUIObject.refresh(self)

        self._proxyCheck = self.builder.get_object("enableProxyCheck")
        self._proxyInfoBox = self.builder.get_object("proxyInfoBox")
        self._authCheck = self.builder.get_object("enableAuthCheck")
        self._proxyAuthBox = self.builder.get_object("proxyAuthBox")

        self._proxyURLEntry = self.builder.get_object("proxyURLEntry")
        self._proxyUsernameEntry = self.builder.get_object("proxyUsernameEntry")
        self._proxyPasswordEntry = self.builder.get_object("proxyPasswordEntry")

        if not self.data.method.proxy:
            self._proxyCheck.set_active(False)
            self.on_proxy_enable_toggled(self._proxyCheck)
            self._authCheck.set_active(False)
            self.on_proxy_auth_toggled(self._authCheck)
            return

        try:
            proxy = ProxyString(self.data.method.proxy)
            if proxy.username:
                self._proxyUsernameEntry.set_text(proxy.username)
            if proxy.password:
                self._proxyPasswordEntry.set_text(proxy.password)
            self._proxyURLEntry.set_text(proxy.noauth_url)
        except ProxyStringError as e:
            log.error("Failed to parse proxy for ProxyDialog.refresh %s: %s" % (self.data.method.proxy, e))
            return

        self._proxyCheck.set_active(True)
        self._authCheck.set_active(bool(proxy.username or proxy.password))
        self.on_proxy_enable_toggled(self._proxyCheck)
        self.on_proxy_auth_toggled(self._authCheck)

    def run(self):
        self.window.run()

class MediaCheckDialog(GUIObject):
    builderObjects = ["mediaCheckDialog"]
    mainWidgetName = "mediaCheckDialog"
    uiFile = "spokes/source.glade"

    def _checkisoEndsCB(self, pid, status):
        doneButton = self.builder.get_object("doneButton")
        verifyLabel = self.builder.get_object("verifyLabel")

        if status == 0:
            verifyLabel.set_text(_("This media is good to install from."))
        else:
            verifyLabel.set_text(_("This media is not good to install from."))

        self.progressBar.set_fraction(1.0)
        doneButton.set_sensitive(True)
        GLib.spawn_close_pid(pid)

    def _checkisoStdoutWatcher(self, fd, condition):
        if condition == GLib.IOCondition.HUP:
            return False

        channel = GLib.IOChannel(fd)
        line = channel.readline().strip()

        if not line.isdigit():
            return True

        pct = float(line)/100
        if pct > 1.0:
            pct = 1.0

        self.progressBar.set_fraction(pct)
        return True

    def run(self, devicePath):
        self.progressBar = self.builder.get_object("mediaCheck-progressBar")

        (retval, pid, stdin, stdout, stderr) = \
            GLib.spawn_async_with_pipes(None, ["checkisomd5", "--gauge", devicePath], [],
                                        GLib.SpawnFlags.DO_NOT_REAP_CHILD|GLib.SpawnFlags.SEARCH_PATH,
                                        None, None)
        if not retval:
            return

        # This function waits for checkisomd5 to end and then cleans up after it.
        GLib.child_watch_add(pid, self._checkisoEndsCB)

        # This function watches the process's stdout.
        GLib.io_add_watch(stdout, GLib.IOCondition.IN|GLib.IOCondition.HUP, self._checkisoStdoutWatcher)

        self.window.run()

    def on_done_clicked(self, *args):
        self.window.destroy()

# This class is responsible for popping up the dialog that allows the user to
# choose the ISO image they want to use.  We can get away with this instead of
# selecting a directory because we no longer support split media.
#
# Two assumptions about the use of this class:
# (1) This class is responsible for mounting and unmounting the partition
#     containing the ISO images.
# (2) When you call refresh() with a currentFile argument or when you get a
#     result from run(), the file path you use is relative to the root of the
#     mounted partition.  In other words, it will not contain the
#     "/mnt/isodir/install" part.  This is consistent with the rest of anaconda.
class IsoChooser(GUIObject):
    builderObjects = ["isoChooserDialog", "isoFilter"]
    mainWidgetName = "isoChooserDialog"
    uiFile = "spokes/source.glade"

    def refresh(self, currentFile=""):
        GUIObject.refresh(self)
        self._chooser = self.builder.get_object("isoChooser")
        self._chooser.connect("current-folder-changed", self.on_folder_changed)
        self._chooser.set_filename(ISO_DIR + "/" + currentFile)

    def run(self, dev):
        retval = None

        unmount = not dev.format.status
        mounts = get_mount_paths(dev.path)
        # We have to check both ISO_DIR and the DRACUT_ISODIR because we
        # still reference both, even though /mnt/install is a symlink to
        # /run/install.  Finding mount points doesn't handle the symlink
        if ISO_DIR not in mounts and DRACUT_ISODIR not in mounts:
            # We're not mounted to either location, so do the mount
            dev.format.mount(mountpoint=ISO_DIR)

        # If any directory was chosen, return that.  Otherwise, return None.
        rc = self.window.run()
        if rc:
            f = self._chooser.get_filename()
            if f:
                retval = f.replace(ISO_DIR, "")

        if unmount:
            dev.format.unmount()

        self.window.destroy()
        return retval

    # There doesn't appear to be any way to restrict a GtkFileChooser to a
    # given directory (see https://bugzilla.gnome.org/show_bug.cgi?id=155729)
    # so we'll just have to fake it by setting you back to inside the directory
    # should you change out of it.
    def on_folder_changed(self, chooser):
        d = chooser.get_current_folder()
        if not d:
            return

        if not d.startswith(ISO_DIR):
            chooser.set_current_folder(ISO_DIR)

class AdditionalReposDialog(GUIObject):
    builderObjects = ["additionalReposDialog", "peopleRepositories", "peopleRepositoriesFilter"]
    mainWidgetName = "additionalReposDialog"
    uiFile = "spokes/source.glade"

    typingTimeout = 1

    def __init__(self, *args, **kwargs):
        GUIObject.__init__(self, *args, **kwargs)

        self._filterTimer = None
        self._urlTimer = None
        self._timeoutAdd = GLib.timeout_add_seconds
        self._timeoutRemove = GLib.source_remove

        # count the number of times the repository check was started
        # so we allow only the last thread to update the validity and
        # description of the entered repository url
        self._epoch = 0

        # Repository url
        self._repositoryUrl = self.builder.get_object("addRepositoryUrl")
        self._repositoryDesc = self.builder.get_object("addRepositoryDesc")
        self._repositoryIcon = self.builder.get_object("addRepositoryIcon")
        self._repositorySpinner = self.builder.get_object("addRepositorySpinner")
        self._urlGrid = self.builder.get_object("urlGrid")

        # Repository list
        self._peopleRepositories = self.builder.get_object("peopleRepositories")
        self._peopleRepositoriesGrid = self.builder.get_object("peopleRepositoriesGrid")
        self._peopleRepositoriesView = self.builder.get_object("addRepositoryList")
        self._peopleRepositoriesFilter = self.builder.get_object("peopleRepositoriesFilter")
        self._peopleRepositoriesFilterEntry = self.builder.get_object("addRepositoryFilter")
        self._peopleRepositoriesFilterValue = ""

        self._peopleRepositoriesFilter.set_visible_func(self.repoVisible, self)

        # Radio button
        self._sourceSelectionListLabel = self.builder.get_object("listGridLabel")
        self._sourceSelectionList = self.builder.get_object("addRepositorySelectList")
        self._sourceSelectionUrlLabel = self.builder.get_object("urlGridLabel")
        self._sourceSelectionUrl = self.builder.get_object("addRepositorySelectUrl")

    def refresh(self, currentFile=""):
        GUIObject.refresh(self)

    def run(self):
        retval = None

        self._peopleRepositoriesFilter.refilter()
        self._peopleRepositoriesFilterValue = self._peopleRepositoriesFilterEntry.get_text()
        self.on_source_changed()

        self.window.show()
        rc = self.window.run()
        if rc:
            retval = "some value"
        self.window.hide()

        return retval

    def repoVisible(self, model, iter, oself):
        """This method is responsible for people repositories list filtering,
           it returns True only for fields which cointain filterString as a substring"""
        return oself._peopleRepositoriesFilterValue in model[iter][0]

    def on_source_changed(self, w = None):
        """Callbacks which gets called when the radio buttons change.
           It makes proper areas (in)sensitive."""
        sourceArea = self._sourceSelectionList.get_active()

        self._peopleRepositoriesGrid.foreach(lambda w, v: w.set_sensitive(v), sourceArea)
        self._urlGrid.foreach(lambda w, v: w.set_sensitive(v), not sourceArea)

        self._sourceSelectionList.set_sensitive(True)
        self._sourceSelectionListLabel.set_sensitive(True)
        self._sourceSelectionUrl.set_sensitive(True)
        self._sourceSelectionUrlLabel.set_sensitive(True)

    def on_list_title_clicked(self, w, d):
        """Callback that handles clicking on the EventBox around people
           repositories label to mimick the standard radio button label
           behaviour which we had to give up for the sake of design."""
        self._sourceSelectionList.set_active(True)

    def on_url_title_clicked(self, w, d):
        """Callback that handles clicking on the EventBox around repo
           url label to mimick the standard radio button label
           behaviour which we had to give up for the sake of design."""
        self._sourceSelectionUrl.set_active(True)

    def on_url_timeout(self, w):
        """This method starts url checker thread and updates the GUI
           elements like spinner and description to notify the user
           about it."""
        # start resolve thread with epoch info

        self._repositorySpinner.start()
        self._repositoryDesc.set_text(_("Getting info about requested repository"))
        self._repositoryIcon.set_from_stock("XXX_RESOLVING", Gtk.IconSize.MENU)

        return False

    def on_url_changed(self, w):
        """This callback is called when the user changes anything in the url
           text entry field. It resets the typing timer so that url checks
           are not started for every character typed and it also increments
           self._epoch counter to prevent older running url checks from
           updating the dialog with now outdated data."""
        if self._urlTimer:
            # optimistic locking, prevent old, but possibly running threads from updating status
            self._epoch += 1
            self._timeoutRemove(self._urlTimer)

        if self._repositoryUrl.get_text():
            self._urlTimer = self._timeoutAdd(self.typingTimeout, self.on_url_timeout, w)

    def on_url_icon_press(self, w, pos, event):
        """Callback for the delete all icon in url text field."""
        self._repositoryUrl.set_text("")
        self.on_url_changed(w)
        self.repository_status(None, _("enter URL of your desired repository"))

    def repository_status(self, valid, description, epoch = None, still_spinning = False):
        """Helper method to update the icon, spinner and decription text
           around the url text entry."""
        # if an older thread want to update status, do not let him
        if epoch is not None and epoch != self._epoch:
            return

        self._repositoryDesc.set_text(description)

        if valid is None:
            self._repositoryIcon.set_from_stock("XXX_NONE", Gtk.IconSize.MENU)
        elif valid:
            self._repositoryIcon.set_from_stock("gtk-apply", Gtk.IconSize.MENU)
        else:
            self._repositoryIcon.set_from_stock("gtk-error", Gtk.IconSize.MENU)

        if not still_spinning:
            self._repositorySpinner.stop()

    def on_filter_timeout(self, w):
        """Timer callback for delayed filtering of people repositories list."""
        self._peopleRepositoriesFilterValue = w.get_text()
        self._peopleRepositoriesFilter.refilter()
        return False

    def on_filter_changed(self, w):
        """This method is called when user changes something in the people
           repositories field. It resets a timer so the update is not done
           until the user stopped typing for a while."""
        if self._filterTimer:
            self._timeoutRemove(self._filterTimer)

        self._filterTimer = self._timeoutAdd(self.typingTimeout,
                                             self.on_filter_timeout,
                                             self._peopleRepositoriesFilterEntry)

    def on_selection_changed(self, selection):
        """Callback called when user selects something in the people
           repositories list."""
        pass

    def on_filter_icon_press(self, w, pos, event):
        """Callback for delete all icon in the people repositories filter
           text entry."""
        self._peopleRepositoriesFilterEntry.set_text("")
        self.on_filter_timeout(w)


class SourceSpoke(NormalSpoke):
    builderObjects = ["isoChooser", "isoFilter", "partitionStore", "sourceWindow", "dirImage"]
    mainWidgetName = "sourceWindow"
    uiFile = "spokes/source.glade"

    category = SoftwareCategory

    icon = "media-optical-symbolic"
    title = N_("INSTALLATION SOURCE")

    def __init__(self, *args, **kwargs):
        NormalSpoke.__init__(self, *args, **kwargs)
        self._currentIsoFile = None
        self._ready = False
        self._error = False

    def apply(self):
        import copy

        old_source = copy.copy(self.data.method)

        if self._autodetectButton.get_active():
            dev = self._get_selected_media()
            if not dev:
                return

            self.data.method.method = "cdrom"
            self.payload.install_device = dev
            if old_source.method == "cdrom":
                # XXX maybe we should always redo it for cdrom in case they
                #     switched disks
                return
        elif self._isoButton.get_active():
            # If the user didn't select a partition (not sure how that would
            # happen) or didn't choose a directory (more likely), then return
            # as if they never did anything.
            part = self._get_selected_partition()
            if not part or not self._currentIsoFile:
                return

            self.data.method.method = "harddrive"
            self.data.method.partition = part.name
            # The / gets stripped off by payload.ISOImage
            self.data.method.dir = "/" + self._currentIsoFile
            if (old_source.method == "harddrive" and
                old_source.partition == self.data.method.partition and
                old_source.dir == self.data.method.dir):
                return

            # Make sure anaconda doesn't touch this device.
            part.protected = True
            self.storage.config.protectedDevSpecs.append(part.name)
        elif self._mirror_active():
            # this preserves the url for later editing
            self.data.method.method = None
            if not old_source.method:
                return
        elif self._http_active() or self._ftp_active():
            url = self._urlEntry.get_text().strip()
            mirrorlist = False

            # If the user didn't fill in the URL entry, just return as if they
            # selected nothing.
            if url == "":
                return

            # Make sure the URL starts with the protocol.  yum will want that
            # to know how to fetch, and the refresh method needs that to know
            # which element of the combo to default to should this spoke be
            # revisited.
            if self._ftp_active() and not url.startswith("ftp://"):
                url = "ftp://" + url
            elif self._protocolComboBox.get_active() == 1 and not url.startswith("http://"):
                url = "http://" + url
                mirrorlist = self._mirrorlistCheckbox.get_active()
            elif self._protocolComboBox.get_active() == 2 and not url.startswith("https://"):
                url = "https://" + url
                mirrorlist = self._mirrorlistCheckbox.get_active()

            if old_source.method == "url" and \
               ((not mirrorlist and old_source.url == url) or \
                (mirrorlist and old_source.mirrorlist == url)):
                return

            self.data.method.method = "url"
            if mirrorlist:
                self.data.method.mirrorlist = url
                self.data.method.url = ""
            else:
                self.data.method.url = url
                self.data.method.mirrorlist = ""
        elif self._nfs_active():
            url = self._urlEntry.get_text().strip()

            # If the user didn't fill in the URL entry, or it does not contain
            # a ':' (so, no host/directory split), just return as if they
            # selected nothing.
            if url == "" or not ':' in url:
                return

            self.data.method.method = "nfs"
            (self.data.method.server, self.data.method.dir) = url.split(":", 2)
            self.data.method.opts = self.builder.get_object("nfsOptsEntry").get_text() or ""

            if (old_source.method == "nfs" and
                old_source.server == self.data.method.server and
                old_source.dir == self.data.method.dir and
                old_source.opts == self.data.method.opts):
                return

        # If the user moved from an HDISO method to some other, we need to
        # clear the protected bit on that device.
        if old_source.method == "harddrive" and old_source.partition:
            if old_source.partition in self.storage.config.protectedDevSpecs:
                self.storage.config.protectedDevSpecs.remove(old_source.partition)

            dev = self.storage.devicetree.getDeviceByName(old_source.partition)
            if dev:
                dev.protected = False

        threadMgr.add(AnacondaThread(name="AnaPayloadMDThread",
                                     target=self.getRepoMetadata))
        self.clear_info()

    def getRepoMetadata(self):
        communication.send_not_ready("SoftwareSelectionSpoke")
        communication.send_not_ready(self.__class__.__name__)
        communication.send_message(self.__class__.__name__,
                                   _(BASEREPO_SETUP_MESSAGE))
        # this sleep is lame, but without it the message above doesn't seem
        # to get processed by the hub in time, and is never shown.
        # FIXME this should get removed when we figure out how to ensure
        # that the message takes effect on the hub before we try to mount
        # a bad NFS server.
        time.sleep(1)
        try:
            self.payload.updateBaseRepo(fallback=False, checkmount=False)
        except PayloadError as e:
            log.error("PayloadError: %s" % (e,))
            self._error = True
            communication.send_message(self.__class__.__name__,
                                       _("Failed to set up install source"))
            if not self.data.method.proxy:
                gtk_call_once(self.set_warning, _("Failed to set up install source, check the repo url"))
            else:
                gtk_call_once(self.set_warning, _("Failed to set up install source, check the repo url and proxy settings"))
        else:
            self._error = False
            communication.send_message(self.__class__.__name__,
                                       _(METADATA_DOWNLOAD_MESSAGE))
            self.payload.gatherRepoMetadata()
            self.payload.release()
            if not self.payload.baseRepo:
                communication.send_message(self.__class__.__name__,
                                           _(METADATA_ERROR_MESSAGE))
                communication.send_ready(self.__class__.__name__)
                self._error = True
                gtk_call_once(self.set_warning, _("Failed to set up install source, check the repo url"))
            else:
                try:
                    # Grabbing the list of groups could potentially take a long time the
                    # first time (yum does a lot of magic property stuff, some of which
                    # involves side effects like network access) so go ahead and grab
                    # them now. These are properties with side-effects, just accessing
                    # them will trigger yum.
                    e = self.payload.environments
                    g = self.payload.groups
                except MetadataError:
                    communication.send_message("SoftwareSelectionSpoke",
                                               _("No installation source available"))
                else:
                    communication.send_ready("SoftwareSelectionSpoke")
        finally:
            communication.send_ready(self.__class__.__name__)

    @property
    def completed(self):
        return not self._error and self.status and self.status != _("Nothing selected")

    @property
    def ready(self):
        from pyanaconda.threads import threadMgr
        # By default, the source spoke is not ready.  We have to wait until
        # storageInitialize is done to know whether or not there's local
        # devices potentially holding install media.
        return (self._ready and not threadMgr.get("AnaPayloadMDThread") and
                not threadMgr.get("AnaCheckSoftwareThread"))

    @property
    def status(self):
        from pyanaconda.threads import threadMgr
        if threadMgr.get("AnaCheckSoftwareThread"):
            return _("Checking software dependencies...")
        elif not self.ready:
            return _("Not ready")
        elif self._error:
            return _("Error setting up software source")
        elif self.data.method.method == "url":
            return self.data.method.url or self.data.method.mirrorlist
        elif self.data.method.method == "nfs":
            return _("NFS server %s") % self.data.method.server
        elif self.data.method.method == "cdrom":
            return _("CD/DVD drive")
        elif self.data.method.method == "harddrive":
            if not self._currentIsoFile:
                return _("Error setting up software source")
            return os.path.basename(self._currentIsoFile)
        elif self.payload.baseRepo:
            return _("Closest mirror")
        else:
            return _("Nothing selected")

    def _grabObjects(self):
        self._autodetectButton = self.builder.get_object("autodetectRadioButton")
        self._autodetectBox = self.builder.get_object("autodetectBox")
        self._autodetectMediaBox = self.builder.get_object("autodetectMediaBox")
        self._isoButton = self.builder.get_object("isoRadioButton")
        self._isoBox = self.builder.get_object("isoBox")
        self._networkButton = self.builder.get_object("networkRadioButton")
        self._networkBox = self.builder.get_object("networkBox")

        self._urlEntry = self.builder.get_object("urlEntry")
        self._protocolComboBox = self.builder.get_object("protocolComboBox")
        self._isoChooserButton = self.builder.get_object("isoChooserButton")

        self._mirrorlistCheckbox = self.builder.get_object("mirrorlistCheckbox")

        self._verifyIsoButton = self.builder.get_object("verifyIsoButton")

    def initialize(self):
        from pyanaconda.threads import threadMgr, AnacondaThread
        from pyanaconda.ui.gui.utils import setViewportBackground

        NormalSpoke.initialize(self)

        self._grabObjects()

        # I shouldn't have to do this outside GtkBuilder, but it really doesn't
        # want to let me pass in user data.
        self._autodetectButton.connect("toggled", self.on_source_toggled, self._autodetectBox)
        self._isoButton.connect("toggled", self.on_source_toggled, self._isoBox)
        self._networkButton.connect("toggled", self.on_source_toggled, self._networkBox)

        viewport = self.builder.get_object("autodetectViewport")
        setViewportBackground(viewport)

        threadMgr.add(AnacondaThread(name="AnaSourceWatcher", target=self._initialize))

    def _initialize(self):
        from pyanaconda.threads import threadMgr

        communication.send_message(self.__class__.__name__, _("Probing storage..."))

        storageThread = threadMgr.get("AnaStorageThread")
        if storageThread:
            storageThread.join()

        communication.send_message(self.__class__.__name__, _(METADATA_DOWNLOAD_MESSAGE))

        payloadThread = threadMgr.get("AnaPayloadThread")
        if payloadThread:
            payloadThread.join()

        added = False
        cdrom = None
        chosen = False

        # If we've previously set up to use a CD/DVD method, the media has
        # already been mounted by payload.setup.  We can't try to mount it
        # again.  So just use what we already know to create the selector.
        # Otherwise, check to see if there's anything available.
        if self.data.method.method == "cdrom":
            cdrom = self.payload.install_device
            chosen = True
        else:
            cdrom = opticalInstallMedia(self.storage.devicetree)

        if cdrom:
            @gtk_thread_wait
            def gtk_action_1():
                selector = AnacondaWidgets.DiskOverview(cdrom.format.label or "", "drive-removable-media", "")
                selector.path = cdrom.path
                selector.set_chosen(chosen)
                self._autodetectMediaBox.pack_start(selector, False, False, 0)

            gtk_action_1()
            added = True

        if self.data.method.method == "harddrive":
            self._currentIsoFile = self.payload.ISOImage

        # These UI elements default to not being showable.  If optical install
        # media were found, mark them to be shown.
        if added:
            gtk_call_once(self._autodetectBox.set_no_show_all, False)
            gtk_call_once(self._autodetectButton.set_no_show_all, False)

        # Add the mirror manager URL in as the default for HTTP and HTTPS.
        # We'll override this later in the refresh() method, if they've already
        # provided a URL.
        # FIXME

        self._ready = True
        communication.send_ready(self.__class__.__name__)

    def refresh(self):
        NormalSpoke.refresh(self)

        # Find all hard drive partitions that could hold an ISO and add each
        # to the partitionStore.  This has to be done here because if the user
        # has done partitioning first, they may have blown away partitions
        # found during _initialize on the partitioning spoke.
        store = self.builder.get_object("partitionStore")
        store.clear()

        added = False
        active = 0
        idx = 0
        for dev in potentialHdisoSources(self.storage.devicetree):
            store.append([dev, "%s (%s MB)" % (self._sanitize_model(dev.disk.model), int(dev.size))])
            if dev.name == self.data.method.partition:
                active = idx
            added = True
            idx += 1

        # Again, only display these widgets if an HDISO source was found.
        self._isoBox.set_no_show_all(not added)
        self._isoBox.set_visible(added)
        self._isoButton.set_no_show_all(not added)
        self._isoButton.set_visible(added)

        if added:
            combo = self.builder.get_object("isoPartitionCombo")
            combo.set_active(active)

        # We default to the mirror list, and then if the method tells us
        # something different later, we can change it.
        self._protocolComboBox.set_active(0)
        self._urlEntry.set_sensitive(False)

        # Set up the default state of UI elements.
        if self.data.method.method == "url":
            self._networkButton.set_active(True)

            proto = self.data.method.url or self.data.method.mirrorlist
            if proto.startswith("http:"):
                self._protocolComboBox.set_active(1)
                l = 7
            elif proto.startswith("https:"):
                self._protocolComboBox.set_active(2)
                l = 8
            elif proto.startswith("ftp:"):
                self._protocolComboBox.set_active(3)
                l = 6

            self._urlEntry.set_sensitive(True)
            self._urlEntry.set_text(proto[l:])
            self._mirrorlistCheckbox.set_active(bool(self.data.method.mirrorlist))
        elif self.data.method.method == "nfs":
            self._networkButton.set_active(True)
            self._protocolComboBox.set_active(4)

            self._urlEntry.set_text("%s:%s" % (self.data.method.server, self.data.method.dir))
            self._urlEntry.set_sensitive(True)
            self.builder.get_object("nfsOptsEntry").set_text(self.data.method.opts or "")
        elif self.data.method.method == "harddrive":
            self._isoButton.set_active(True)
            self._isoBox.set_sensitive(True)
            self._verifyIsoButton.set_sensitive(True)

            if self._currentIsoFile:
                self._isoChooserButton.set_label(os.path.basename(self._currentIsoFile))
            else:
                self._isoChooserButton.set_label("")
            self._isoChooserButton.set_use_underline(False)
        else:
            # No method was given in advance, so now we need to make a sensible
            # guess.  Go with autodetected media if that was provided, and then
            # fall back to a URL.
            if not self._autodetectButton.get_no_show_all():
                self._autodetectButton.set_active(True)
            else:
                self._networkButton.set_active(True)

        # TODO: handle noUpdatesCheckbox

        # Then, some widgets get enabled/disabled/greyed out depending on
        # how others are set up.  We can use the signal handlers to handle
        # that condition here too.
        self.on_protocol_changed(self._protocolComboBox)

    @property
    def showable(self):
        return not flags.livecdInstall

    def _mirror_active(self):
        return self._protocolComboBox.get_active() == 0

    def _http_active(self):
        return self._protocolComboBox.get_active() in [1, 2]

    def _ftp_active(self):
        return self._protocolComboBox.get_active() == 3

    def _nfs_active(self):
        return self._protocolComboBox.get_active() == 4

    def _get_selected_media(self):
        dev = None
        for child in self._autodetectMediaBox.get_children():
            if child.get_chosen():
                dev = child
                break

        return dev

    def _get_selected_partition(self):
        store = self.builder.get_object("partitionStore")
        combo = self.builder.get_object("isoPartitionCombo")

        selected = combo.get_active()
        if selected == -1:
            return None
        else:
            return store[selected][0]

    def _sanitize_model(self, model):
        return model.replace("_", " ")

    # Signal handlers.
    def on_source_toggled(self, button, relatedBox):
        # When a radio button is clicked, this handler gets called for both
        # the newly enabled button as well as the previously enabled (now
        # disabled) button.
        enabled = button.get_active()
        relatedBox.set_sensitive(enabled)

    def on_chooser_clicked(self, button):
        dialog = IsoChooser(self.data)

        with enlightbox(self.window, dialog.window):
            # If the chooser has been run one before, we should make it default to
            # the previously selected file.
            if self._currentIsoFile:
                dialog.refresh(currentFile=self._currentIsoFile)
            else:
                dialog.refresh()

            f = dialog.run(self._get_selected_partition())

            if f:
                self._currentIsoFile = f
                button.set_label(os.path.basename(f))
                button.set_use_underline(False)
                self._verifyIsoButton.set_sensitive(True)

    def on_proxy_clicked(self, button):
        dialog = ProxyDialog(self.data)
        with enlightbox(self.window, dialog.window):
            dialog.refresh()
            dialog.run()

    def on_verify_iso_clicked(self, button):
        p = self._get_selected_partition()
        f = self._currentIsoFile

        if not p or not f:
            return

        dialog = MediaCheckDialog(self.data)
        with enlightbox(self.window, dialog.window):
            unmount = not p.format.status
            mounts = get_mount_paths(p.path)
            # We have to check both ISO_DIR and the DRACUT_ISODIR because we
            # still reference both, even though /mnt/install is a symlink to
            # /run/install.  Finding mount points doesn't handle the symlink
            if ISO_DIR not in mounts and DRACUT_ISODIR not in mounts:
                # We're not mounted to either location, so do the mount
                p.format.mount(mountpoint=ISO_DIR)
            dialog.run(ISO_DIR + "/" + f)
            if unmount:
                p.format.unmount()

    def on_verify_media_clicked(self, button):
        dev = self._get_selected_media()

        if not dev:
            return

        dialog = MediaCheckDialog(self.data)
        with enlightbox(self.window, dialog.window):
            dialog.run(dev.path)

    def on_protocol_changed(self, combo):
        proxyButton = self.builder.get_object("proxyButton")
        nfsOptsBox = self.builder.get_object("nfsOptsBox")

        # Only allow the URL entry to be used if we're using an HTTP/FTP
        # method that's not the mirror list, or an NFS method.
        self._urlEntry.set_sensitive(self._http_active() or self._ftp_active() or self._nfs_active())

        # Only allow thse widgets to be shown if it makes sense for the
        # the currently selected protocol.
        proxyButton.set_sensitive(self._http_active() or self._mirror_active())
        nfsOptsBox.set_visible(self._nfs_active())
        self._mirrorlistCheckbox.set_visible(self._http_active())
