# Installation source spoke classes
#
# Copyright (C) 2011  Red Hat, Inc.
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

from gi.repository import Gtk, AnacondaWidgets

from pyanaconda.image import opticalInstallMedia, potentialHdisoSources
from pyanaconda.ui.gui import UIObject
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.categories.software import SoftwareCategory

__all__ = ["SourceSpoke"]

MOUNTPOINT = "/mnt/install/isodir"

class MediaCheckDialog(UIObject):
    builderObjects = ["mediaCheckDialog"]
    mainWidgetName = "mediaCheckDialog"
    uiFile = "spokes/source.ui"

    def _update_progress_bar(self, offset, total):
        fract = offset/total
        if fract > 1.0:
            fract = 1.0

        self.progressBar.set_fraction(fract)

    def run(self, devicePath):
        self.progressBar = self.builder.get_object("mediaCheck-progressBar")

        rc = self.window.run()
        self.window.destroy()

    def on_cancel_clicked(self, *args):
        print "CANCELING"

class IsoDirChooser(UIObject):
    builderObjects = ["isoDirChooserDialog"]
    mainWidgetName = "isoDirChooserDialog"
    uiFile = "spokes/source.ui"

    def setup(self, currentDir=""):
        UIObject.setup(self)
        self._chooser = self.builder.get_object("isoDirChooser")
        self._chooser.set_uri("file://" + MOUNTPOINT + currentDir)

    def run(self, dev):
        retval = None

        dev.format.mount(mountpoint=MOUNTPOINT)

        # If any directory was chosen, return that.  Otherwise, return None.
        rc = self.window.run()
        if rc:
            uri = self._chooser.get_uri()
            if uri:
                retval = uri.replace("file://" + MOUNTPOINT, "")

            if retval == "":
                retval = "/"

        dev.format.unmount()

        self.window.destroy()
        return retval

    # There doesn't appear to be any way to restrict a GtkFileChooser to a
    # given directory (see https://bugzilla.gnome.org/show_bug.cgi?id=155729)
    # so we'll just have to fake it by setting you back to inside the directory
    # should you change out of it.
    def on_folder_changed(self, chooser):
        d = chooser.get_uri()
        if not d:
            return

        # Strip off "file://"
        d = d[7:]
        if not d.startswith(MOUNTPOINT):
            chooser.set_uri("file://" + MOUNTPOINT)

class SourceSpoke(NormalSpoke):
    builderObjects = ["isoDirChooser", "isoFileFilter", "partitionStore", "sourceWindow", "dirImage"]
    mainWidgetName = "sourceWindow"
    uiFile = "spokes/source.ui"

    category = SoftwareCategory

    icon = "media-optical-symbolic"
    title = "INSTALL SOURCE"

    def apply(self):
        if self._autodetectButton.get_active():
            pass
        elif self._isoButton.get_active():
            # If the user didn't select a partition (not sure how that would
            # happen) or didn't choose a directory (more likely), then return
            # as if they never did anything.
            part = self._get_selected_partition()
            if not part or not self._isoDirChooserButton.get_label().startswith("/"):
                return

            self.data.method.method = "harddrive"
            self.data.method.partition = part.name
            self.data.method.dir = self._isoDirChooserButton.get_label()
        elif self._http_active(self._protocolComboBox) or self._ftp_active(self._protocolComboBox):
            url = self._urlEntry.get_text().strip()

            # If the user didn't fill in the URL entry, just return as if they
            # selected nothing.
            if url == "":
                return

            self.data.method.method = "url"
            self.data.method.url = url

            # Make sure the URL starts with the protocol.  yum will want that
            # to know how to fetch, and the setup method needs that to know
            # which element of the combo to default to should this spoke be
            # revisited.
            if self._ftp_active(self._protocolComboBox) and not self.data.method.url.startswith("ftp://"):
                self.data.method.url = "ftp://" + self.data.method.url
            elif self._protocolComboBox.get_active() == 0 and not self.data.method.url.startswith("http://"):
                self.data.method.url = "http://" + self.data.method.url
            elif self._protocolComboBox.get_active() == 1 and not self.data.method.url.startswith("https://"):
                self.data.method.url = "https://" + self.data.method.url
        elif self._nfs_active(self._protocolComboBox):
            url = self._urlEntry.get_text().strip()

            # If the user didn't fill in the URL entry, just return as if
            # they selected nothing.
            if url == "":
                return

            self.data.method.method = "nfs"
            (self.data.method.server, self.data.method.dir) = url.split(":", 2)
            self.data.method.opts = self.builder.get_object("nfsOptsEntry").get_text() or ""

    @property
    def status(self):
        if self.data.method.method == "url":
            if len(self.data.method.url) > 30:
                return self.data.method.url[:30] + "..."
            else:
                return self.data.method.url[:30]
        elif self.data.method.method == "nfs":
            return "NFS server %s" % self.data.method.server
        elif self.data.method.method == "cdrom":
            return "CD/DVD drive"
        elif self.data.method.method == "harddrive":
            return self._sanitize_model(self._get_selected_partition().disk.model)
        else:
            return "Nothing selected"

    def _grabObjects(self):
        self._autodetectButton = self.builder.get_object("autodetectRadioButton")
        self._autodetectBox = self.builder.get_object("autodetectBox")
        self._isoButton = self.builder.get_object("isoRadioButton")
        self._isoBox = self.builder.get_object("isoBox")
        self._networkButton = self.builder.get_object("networkRadioButton")
        self._networkBox = self.builder.get_object("networkBox")

        self._urlEntry = self.builder.get_object("urlEntry")
        self._protocolComboBox = self.builder.get_object("protocolComboBox")
        self._isoDirChooserButton = self.builder.get_object("isoDirChooserButton")

    def populate(self):
        NormalSpoke.populate(self)

        self._grabObjects()

        # I shouldn't have to do this outside GtkBuilder, but it really doesn't
        # want to let me pass in user data.
        self._autodetectButton.connect("toggled", self.on_source_toggled, self._autodetectBox)
        self._isoButton.connect("toggled", self.on_source_toggled, self._isoBox)
        self._networkButton.connect("toggled",self.on_source_toggled, self._networkBox)

        # If we found any optical install media, display a selector for each
        # of those.
        added = False
        for cdrom in opticalInstallMedia(self.devicetree, mountpoint=MOUNTPOINT):
            selector = AnacondaWidgets.DiskSelector(cdrom.format.label, "drive-harddisk", "")
            self._autodetectBox.add(selector)
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
        # We'll override this later in the setup() method, if they've already
        # provided a URL.
        # FIXME

    def setup(self):
        NormalSpoke.setup(self)

        # Just set the protocol combo to a default of HTTP.  We'll set it to
        # the right value later on, depending on the method.
        self._protocolComboBox.set_active(0)

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

            self._urlEntry.set_text(proto[l:])
        elif self.data.method.method == "nfs":
            self._networkButton.set_active(True)
            self._protocolComboBox.set_active(3)

            self._urlEntry.set_text("%s:%s" % (self.data.method.server, self.data.method.dir))
            self.builder.get_object("nfsOptsEntry").set_text(self.data.method.opts or "")
        elif self.data.method.method == "harddrive":
            self._isoButton.set_active(True)

            self._isoDirChooserButton.set_label(self.data.method.dir)
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

    def _http_active(self, combo):
        return combo.get_active() in [0, 1]

    def _ftp_active(self, combo):
        return combo.get_active() == 2

    def _nfs_active(self, combo):
        return combo.get_active() == 3

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
        dialog = IsoDirChooser(self.data)

        # If the chooser has been selected once before, the button will have a
        # label with the selected directory in it, not the default of "Select..."
        # so we need to pass that in to have it set as the default directory.
        if self._isoDirChooserButton.get_label().startswith("/"):
            dialog.setup(currentDir=self._isoDirChooserButton.get_label())
        else:
            dialog.setup()

        d = dialog.run(self._get_selected_partition())

        if d:
            button.set_label(d)

    def on_proxy_clicked(self, button):
        # FIXME:  this doesn't do anything
        pass

    def on_verify_iso_clicked(self, button, chooser):
        # FIXME:  this doesn't do anything
        pass

    def on_verify_media_clicked(self, button):
        # FIXME:  this doesn't do anything
        pass

    def on_protocol_changed(self, combo):
        proxyButton = self.builder.get_object("proxyButton")
        nfsOptsBox = self.builder.get_object("nfsOptsBox")

        # Only allow the proxy button to be clicked if a proxy makes sense for
        # the currently selected protocol.
        proxyButton.set_sensitive(self._http_active(combo))
        nfsOptsBox.set_visible(self._nfs_active(combo))

    def on_back_clicked(self, window):
        self.window.hide()
        Gtk.main_quit()
