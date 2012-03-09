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
#

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)
N_ = lambda x: x

import os.path

from gi.repository import AnacondaWidgets, GLib, Gtk

from pyanaconda.image import opticalInstallMedia, potentialHdisoSources
from pyanaconda.ui.gui import UIObject
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.categories.software import SoftwareCategory
from pyanaconda.ui.gui.utils import enlightbox, gdk_threaded

__all__ = ["SourceSpoke"]

MOUNTPOINT = "/mnt/install/isodir"

class MediaCheckDialog(UIObject):
    builderObjects = ["mediaCheckDialog"]
    mainWidgetName = "mediaCheckDialog"
    uiFile = "spokes/source.ui"

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
class IsoChooser(UIObject):
    builderObjects = ["isoChooserDialog", "isoFilter"]
    mainWidgetName = "isoChooserDialog"
    uiFile = "spokes/source.ui"

    def refresh(self, currentFile=""):
        UIObject.refresh(self)
        self._chooser = self.builder.get_object("isoChooser")
        self._chooser.connect("current-folder-changed", self.on_folder_changed)
        self._chooser.set_filename(MOUNTPOINT + "/" + currentFile)

    def run(self, dev):
        retval = None

        dev.format.mount(mountpoint=MOUNTPOINT)

        # If any directory was chosen, return that.  Otherwise, return None.
        rc = self.window.run()
        if rc:
            f = self._chooser.get_filename()
            if f:
                retval = f.replace(MOUNTPOINT, "")

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

        if not d.startswith(MOUNTPOINT):
            chooser.set_current_folder(MOUNTPOINT)

class SourceSpoke(NormalSpoke):
    builderObjects = ["isoChooser", "isoFilter", "partitionStore", "sourceWindow", "dirImage"]
    mainWidgetName = "sourceWindow"
    uiFile = "spokes/source.ui"

    category = SoftwareCategory

    icon = "media-optical-symbolic"
    title = N_("INSTALL SOURCE")

    def __init__(self, *args, **kwargs):
        NormalSpoke.__init__(self, *args, **kwargs)
        self._currentIsoFile = None
        self._ready = False

    def apply(self):
        if self._autodetectButton.get_active():
            dev = self._get_selected_media()
            if not dev:
                return

            self.data.method.method = "cdrom"
        elif self._isoButton.get_active():
            # If the user didn't select a partition (not sure how that would
            # happen) or didn't choose a directory (more likely), then return
            # as if they never did anything.
            part = self._get_selected_partition()
            if not part or not self._currentIsoFile:
                return

            self.data.method.method = "harddrive"
            self.data.method.partition = part.name
            self.data.method.dir = self._currentIsoFile
        elif self._mirror_active():
            pass
        elif self._http_active() or self._ftp_active():
            url = self._urlEntry.get_text().strip()

            # If the user didn't fill in the URL entry, just return as if they
            # selected nothing.
            if url == "":
                return

            self.data.method.method = "url"
            self.data.method.url = url

            # Make sure the URL starts with the protocol.  yum will want that
            # to know how to fetch, and the refresh method needs that to know
            # which element of the combo to default to should this spoke be
            # revisited.
            if self._ftp_active() and not self.data.method.url.startswith("ftp://"):
                self.data.method.url = "ftp://" + self.data.method.url
            elif self._protocolComboBox.get_active() == 0 and not self.data.method.url.startswith("http://"):
                self.data.method.url = "http://" + self.data.method.url
            elif self._protocolComboBox.get_active() == 1 and not self.data.method.url.startswith("https://"):
                self.data.method.url = "https://" + self.data.method.url
        elif self._nfs_active():
            url = self._urlEntry.get_text().strip()

            # If the user didn't fill in the URL entry, just return as if
            # they selected nothing.
            if url == "":
                return

            self.data.method.method = "nfs"
            (self.data.method.server, self.data.method.dir) = url.split(":", 2)
            self.data.method.opts = self.builder.get_object("nfsOptsEntry").get_text() or ""

    @property
    def completed(self):
        return self.status and self.status != _("Nothing selected")

    @property
    def ready(self):
        # By default, the source spoke is not ready.  We have to wait until
        # storageInitialize is done to know whether or not there's local
        # devices potentially holding install media.
        return self._ready

    @property
    def status(self):
        if self.data.method.method == "url":
            if len(self.data.method.url) > 42:
                return self.data.method.url[:30] + "..." + self.data.method.url[-12:]
            else:
                return self.data.method.url
        elif self.data.method.method == "nfs":
            return _("NFS server %s") % self.data.method.server
        elif self.data.method.method == "cdrom":
            return _("CD/DVD drive")
        elif self.data.method.method == "harddrive":
            return os.path.basename(self._currentIsoFile)
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

        self._verifyIsoButton = self.builder.get_object("verifyIsoButton")

    def initialize(self):
        from pyanaconda.threads import threadMgr
        from pyanaconda.ui.gui.utils import setViewportBackground
        from threading import Thread

        NormalSpoke.initialize(self)

        self._grabObjects()

        # I shouldn't have to do this outside GtkBuilder, but it really doesn't
        # want to let me pass in user data.
        self._autodetectButton.connect("toggled", self.on_source_toggled, self._autodetectBox)
        self._isoButton.connect("toggled", self.on_source_toggled, self._isoBox)
        self._networkButton.connect("toggled", self.on_source_toggled, self._networkBox)

        viewport = self.builder.get_object("autodetectViewport")
        setViewportBackground(viewport)

        threadMgr.add(Thread(name="AnaSourceWatcher", target=self._initialize))

    def _initialize(self):
        from pyanaconda.threads import threadMgr

        storageThread = threadMgr.get("AnaStorageThread")
        if storageThread:
            storageThread.join()

        added = False
        cdrom = None
        chosen = False

        with gdk_threaded():
            # If we've previously set up to use a CD/DVD method, the media has
            # already been mounted by payload.setup.  We can't try to mount it
            # again.  So just use what we already know to create the selector.
            # Otherwise, check to see if there's anything available.
            if self.data.method.method == "cdrom":
                cdrom = self.payload.install_device
                chosen = True
            else:
                cdrom = opticalInstallMedia(self.devicetree, mountpoint=MOUNTPOINT)

            if cdrom:
                selector = AnacondaWidgets.DiskOverview(cdrom.format.label or "", "drive-removable-media", "")
                selector.path = cdrom.path
                selector.set_chosen(chosen)
                self._autodetectMediaBox.pack_start(selector, False, False, 0)
                added = True

            # These UI elements default to not being showable.  If optical install
            # media were found, mark them to be shown.
            if added:
                self._autodetectBox.set_no_show_all(False)
                self._autodetectButton.set_no_show_all(False)

            # Find all hard drive partitions that could hold an ISO and add each
            # to the diskStore.
            store = self.builder.get_object("partitionStore")

            added = False
            for dev in potentialHdisoSources(self.devicetree):
                store.append([dev, "%s (%s MB)" % (self._sanitize_model(dev.disk.model), int(dev.size))])
                added = True

            # Again, only display these widgets if an HDISO source was found.
            if added:
                self._isoBox.set_no_show_all(False)
                self._isoButton.set_no_show_all(False)
                combo = self.builder.get_object("isoPartitionCombo")
                combo.set_active(0)

            # Add the mirror manager URL in as the default for HTTP and HTTPS.
            # We'll override this later in the refresh() method, if they've already
            # provided a URL.
            # FIXME

            self._ready = True
            self.selector.set_sensitive(True)

    def refresh(self):
        NormalSpoke.refresh(self)

        # We default to the mirror list, and then if the method tells us
        # something different later, we can change it.
        self._protocolComboBox.set_active(0)
        self._urlEntry.set_sensitive(False)

        # Set up the default state of UI elements.
        if self.data.method.method == "url":
            self._networkButton.set_active(True)

            proto = self.data.method.url
            if proto.startswith("http:"):
                self._protocolComboBox.set_active(0)
                l = 7
            elif proto.startswith("https:"):
                self._protocolComboBox.set_active(1)
                l = 8
            elif proto.startswith("ftp:"):
                self._protocolComboBox.set_active(2)
                l = 6

            self._urlEntry.set_sensitive(True)
            self._urlEntry.set_text(proto[l:])
        elif self.data.method.method == "nfs":
            self._networkButton.set_active(True)
            self._protocolComboBox.set_active(3)

            self._urlEntry.set_text("%s:%s" % (self.data.method.server, self.data.method.dir))
            self.builder.get_object("nfsOptsEntry").set_text(self.data.method.opts or "")
        elif self.data.method.method == "harddrive":
            self._isoButton.set_active(True)

            self._isoChooserButton.set_label(os.path.basename(self.data.method.dir))
            self._isoChooserButton.set_use_underline(False)
        else:
            # No method was given in advance, so now we need to make a sensible
            # guess.  Go with autodetected media if that was provided, and then
            # fall back to a URL.
            if not self._autodetectButton.get_no_show_all():
                self._autodetectButton.set_active(True)
            else:
                self._networkButton.set_active(True)

        # Then, some widgets get enabled/disabled/greyed out depending on
        # how others are set up.  We can use the signal handlers to handle
        # that condition here too.
        self.on_protocol_changed(self._protocolComboBox)

    def _mirror_active(self):
        return self._protocolComboBox.get_active_text().startswith("Closest")

    def _http_active(self):
        return self._protocolComboBox.get_active_text().startswith("http")

    def _ftp_active(self):
        return self._protocolComboBox.get_active_text().startswith("ftp")

    def _nfs_active(self):
        return self._protocolComboBox.get_active_text().startswith("nfs")

    def _get_selected_media(self):
        dev = None
        for child in self._autodetectMediaBox.get_children():
            if child.get_chosen():
                dev = child.path
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
        # FIXME:  this doesn't do anything
        pass

    def on_verify_iso_clicked(self, button):
        p = self._get_selected_partition()
        f = self._currentIsoFile

        if not p or not f:
            return

        dialog = MediaCheckDialog(self.data)
        with enlightbox(self.window, dialog.window):
            dev = self.devicetree.getDeviceByName(dev)
            dev.format.mount(mountpoint=MOUNTPOINT)
            dialog.run(MOUNTPOINT + "/" + f)
            dev.format.unmount()

    def on_verify_media_clicked(self, button):
        dev = self._get_selected_media()

        if not dev:
            return

        dialog = MediaCheckDialog(self.data)
        with enlightbox(self.window, dialog.window):
            dialog.run(dev)

    def on_protocol_changed(self, combo):
        proxyButton = self.builder.get_object("proxyButton")
        nfsOptsBox = self.builder.get_object("nfsOptsBox")

        # Only allow the URL entry to be used if we're using an HTTP/FTP
        # method that's not the mirror list.
        self._urlEntry.set_sensitive(self._http_active() or self._ftp_active())

        # Only allow the proxy button to be clicked if a proxy makes sense for
        # the currently selected protocol.
        proxyButton.set_sensitive(self._http_active())
        nfsOptsBox.set_visible(self._nfs_active())
