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

import time

import logging
log = logging.getLogger("anaconda")

import os, signal

from gi.repository import GLib

from pyanaconda.flags import flags
from pyanaconda.i18n import _, N_
from pyanaconda.image import opticalInstallMedia, potentialHdisoSources
from pyanaconda.ui.communication import hubQ
from pyanaconda.ui.gui import GUIObject
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.categories.software import SoftwareCategory
from pyanaconda.ui.gui.utils import enlightbox, gtk_action_wait
from pyanaconda.iutil import ProxyString, ProxyStringError, cmp_obj_attrs
from pyanaconda.ui.gui.utils import gtk_call_once, really_hide, really_show
from pyanaconda.threads import threadMgr, AnacondaThread
from pyanaconda.packaging import PayloadError, MetadataError
from pyanaconda import constants

from blivet.util import get_mount_paths

__all__ = ["SourceSpoke"]

BASEREPO_SETUP_MESSAGE = N_("Setting up installation source...")
METADATA_DOWNLOAD_MESSAGE = N_("Downloading package metadata...")
METADATA_ERROR_MESSAGE = N_("Error downloading package metadata...")

# These need to be in the same order as the items in protocolComboBox in source.glade.
PROTOCOL_HTTP = 0
PROTOCOL_HTTPS = 1
PROTOCOL_FTP = 2
PROTOCOL_NFS = 3
PROTOCOL_MIRROR = 4

# Repo Store Columns
REPO_ENABLED_COL = 0
REPO_NAME_COL = 1
REPO_OBJ = 2

REPO_PROTO = [(0, "http://"), (1, "https://"), (2, "ftp://")]

class ProxyDialog(GUIObject):
    builderObjects = ["proxyDialog"]
    mainWidgetName = "proxyDialog"
    uiFile = "spokes/source.glade"

    def __init__(self, data):
        GUIObject.__init__(self, data)

        self._proxyCheck = self.builder.get_object("enableProxyCheck")
        self._proxyInfoBox = self.builder.get_object("proxyInfoBox")
        self._authCheck = self.builder.get_object("enableAuthCheck")
        self._proxyAuthBox = self.builder.get_object("proxyAuthBox")

        self._proxyURLEntry = self.builder.get_object("proxyURLEntry")
        self._proxyUsernameEntry = self.builder.get_object("proxyUsernameEntry")
        self._proxyPasswordEntry = self.builder.get_object("proxyPasswordEntry")

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
            log.error("Failed to parse proxy for ProxyDialog Add - %s:%s@%s: %s", username, password, url, e)
            # TODO - tell the user they entered an invalid proxy and let them retry
            self.data.method.proxy = ""

        self.window.destroy()

    def on_proxy_enable_toggled(self, button, *args):
        self._proxyInfoBox.set_sensitive(button.get_active())

    def on_proxy_auth_toggled(self, button, *args):
        self._proxyAuthBox.set_sensitive(button.get_active())

    def refresh(self):
        GUIObject.refresh(self)


        if not (hasattr(self.data.method, "proxy") and self.data.method.proxy):
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
            log.error("Failed to parse proxy for ProxyDialog.refresh %s: %s", self.data.method.proxy, e)
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

    def __init__(self, data):
        GUIObject.__init__(self, data)
        self.progressBar = self.builder.get_object("mediaCheck-progressBar")
        self._pid = None

    def _checkisoEndsCB(self, pid, status):
        doneButton = self.builder.get_object("doneButton")
        verifyLabel = self.builder.get_object("verifyLabel")

        if os.WIFSIGNALED(status):
            pass
        elif status == 0:
            verifyLabel.set_text(_("This media is good to install from."))
        else:
            verifyLabel.set_text(_("This media is not good to install from."))

        self.progressBar.set_fraction(1.0)
        doneButton.set_sensitive(True)
        GLib.spawn_close_pid(pid)
        self._pid = None

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
        (retval, self._pid, _stdin, stdout, _stderr) = \
            GLib.spawn_async_with_pipes(None, ["checkisomd5", "--gauge", devicePath], [],
                                        GLib.SpawnFlags.DO_NOT_REAP_CHILD|GLib.SpawnFlags.SEARCH_PATH,
                                        None, None)
        if not retval:
            return

        # This function waits for checkisomd5 to end and then cleans up after it.
        GLib.child_watch_add(self._pid, self._checkisoEndsCB)

        # This function watches the process's stdout.
        GLib.io_add_watch(stdout, GLib.IOCondition.IN|GLib.IOCondition.HUP, self._checkisoStdoutWatcher)

        self.window.run()

    def on_close(self, *args):
        if self._pid:
            os.kill(self._pid, signal.SIGKILL)

        self.window.destroy()

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

    def __init__(self, data):
        GUIObject.__init__(self, data)
        self._chooser = self.builder.get_object("isoChooser")

    # pylint: disable-msg=W0221
    def refresh(self, currentFile=""):
        GUIObject.refresh(self)
        self._chooser.connect("current-folder-changed", self.on_folder_changed)
        self._chooser.set_filename(constants.ISO_DIR + "/" + currentFile)

    def run(self, dev):
        retval = None

        unmount = not dev.format.status
        mounts = get_mount_paths(dev.path)
        # We have to check both ISO_DIR and the DRACUT_ISODIR because we
        # still reference both, even though /mnt/install is a symlink to
        # /run/install.  Finding mount points doesn't handle the symlink
        if constants.ISO_DIR not in mounts and constants.DRACUT_ISODIR not in mounts:
            # We're not mounted to either location, so do the mount
            dev.format.mount(mountpoint=constants.ISO_DIR)

        # If any directory was chosen, return that.  Otherwise, return None.
        rc = self.window.run()
        if rc:
            f = self._chooser.get_filename()
            if f:
                retval = f.replace(constants.ISO_DIR, "")

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

        if not d.startswith(constants.ISO_DIR):
            chooser.set_current_folder(constants.ISO_DIR)

class SourceSpoke(NormalSpoke):
    builderObjects = ["isoChooser", "isoFilter", "partitionStore", "sourceWindow", "dirImage", "repoStore"]
    mainWidgetName = "sourceWindow"
    uiFile = "spokes/source.glade"

    category = SoftwareCategory

    icon = "media-optical-symbolic"
    title = N_("_INSTALLATION SOURCE")

    def __init__(self, *args, **kwargs):
        NormalSpoke.__init__(self, *args, **kwargs)
        self._currentIsoFile = None
        self._ready = False
        self._error = False
        self._proxyChange = False
        self._cdrom = None

    def apply(self):
        # If askmethod was provided on the command line, entering the source
        # spoke wipes that out.
        if flags.askmethod:
            flags.askmethod = False

        threadMgr.add(AnacondaThread(name=constants.THREAD_PAYLOAD_MD, target=self.getRepoMetadata))
        self.clear_info()

    def _method_changed(self):
        """ Check to see if the install method has changed.

            :returns: True if it changed, False if not
            :rtype: bool
        """
        import copy

        old_source = copy.copy(self.data.method)

        if self._autodetectButton.get_active():
            if not self._cdrom:
                return False

            self.data.method.method = "cdrom"
            self.payload.install_device = self._cdrom
            if old_source.method == "cdrom":
                # XXX maybe we should always redo it for cdrom in case they
                #     switched disks
                return False
        elif self._isoButton.get_active():
            # If the user didn't select a partition (not sure how that would
            # happen) or didn't choose a directory (more likely), then return
            # as if they never did anything.
            part = self._get_selected_partition()
            if not part or not self._currentIsoFile:
                return False

            self.data.method.method = "harddrive"
            self.data.method.partition = part.name
            # The / gets stripped off by payload.ISOImage
            self.data.method.dir = "/" + self._currentIsoFile
            if (old_source.method == "harddrive" and
                old_source.partition == self.data.method.partition and
                old_source.dir == self.data.method.dir):
                return False

            # Make sure anaconda doesn't touch this device.
            part.protected = True
            self.storage.config.protectedDevSpecs.append(part.name)
        elif self._mirror_active():
            # this preserves the url for later editing
            self.data.method.method = None
            if not old_source.method and self.payload.baseRepo and \
               not self._proxyChange:
                return False
        elif self._http_active() or self._ftp_active():
            url = self._urlEntry.get_text().strip()
            mirrorlist = False

            # If the user didn't fill in the URL entry, just return as if they
            # selected nothing.
            if url == "":
                return False

            # Make sure the URL starts with the protocol.  yum will want that
            # to know how to fetch, and the refresh method needs that to know
            # which element of the combo to default to should this spoke be
            # revisited.
            if self._ftp_active() and not url.startswith("ftp://"):
                url = "ftp://" + url
            elif self._protocolComboBox.get_active() == PROTOCOL_HTTP and not url.startswith("http://"):
                url = "http://" + url
                mirrorlist = self._mirrorlistCheckbox.get_active()
            elif self._protocolComboBox.get_active() == PROTOCOL_HTTPS and not url.startswith("https://"):
                url = "https://" + url
                mirrorlist = self._mirrorlistCheckbox.get_active()

            if old_source.method == "url" and not self._proxyChange and \
               ((not mirrorlist and old_source.url == url) or \
                (mirrorlist and old_source.mirrorlist == url)):
                return False

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
                return False

            self.data.method.method = "nfs"
            try:
                (self.data.method.server, self.data.method.dir) = url.split(":", 2)
            except ValueError as e:
                log.error("ValueError: %s", e)
                gtk_call_once(self.set_warning, _("Failed to set up installation source; check the repo url"))
                self._error = True
                return

            self.data.method.opts = self.builder.get_object("nfsOptsEntry").get_text() or ""

            if (old_source.method == "nfs" and
                old_source.server == self.data.method.server and
                old_source.dir == self.data.method.dir and
                old_source.opts == self.data.method.opts):
                return False

        # If the user moved from an HDISO method to some other, we need to
        # clear the protected bit on that device.
        if old_source.method == "harddrive" and old_source.partition:
            if old_source.partition in self.storage.config.protectedDevSpecs:
                self.storage.config.protectedDevSpecs.remove(old_source.partition)

            dev = self.storage.devicetree.getDeviceByName(old_source.partition)
            if dev:
                dev.protected = False

        return True

    def getRepoMetadata(self):
        hubQ.send_not_ready("SoftwareSelectionSpoke")
        hubQ.send_not_ready(self.__class__.__name__)
        hubQ.send_message(self.__class__.__name__, _(BASEREPO_SETUP_MESSAGE))
        # this sleep is lame, but without it the message above doesn't seem
        # to get processed by the hub in time, and is never shown.
        # FIXME this should get removed when we figure out how to ensure
        # that the message takes effect on the hub before we try to mount
        # a bad NFS server.
        time.sleep(1)
        try:
            self.payload.updateBaseRepo(fallback=False, checkmount=False)
        except (OSError, PayloadError) as e:
            log.error("PayloadError: %s", e)
            self._error = True
            hubQ.send_message(self.__class__.__name__, _("Failed to set up installation source"))
            if not (hasattr(self.data.method, "proxy") and self.data.method.proxy):
                gtk_call_once(self.set_warning, _("Failed to set up installation source; check the repo url"))
            else:
                gtk_call_once(self.set_warning, _("Failed to set up installation source; check the repo url and proxy settings"))
        else:
            self._error = False
            hubQ.send_message(self.__class__.__name__, _(METADATA_DOWNLOAD_MESSAGE))
            self.payload.gatherRepoMetadata()
            self.payload.release()
            if not self.payload.baseRepo:
                hubQ.send_message(self.__class__.__name__, _(METADATA_ERROR_MESSAGE))
                hubQ.send_ready(self.__class__.__name__, False)
                self._error = True
                gtk_call_once(self.set_warning, _("Failed to set up installation source; check the repo url"))
            else:
                try:
                    # Grabbing the list of groups could potentially take a long time the
                    # first time (yum does a lot of magic property stuff, some of which
                    # involves side effects like network access) so go ahead and grab
                    # them now. These are properties with side-effects, just accessing
                    # them will trigger yum.
                    # pylint: disable-msg=W0104
                    self.payload.environments
                    # pylint: disable-msg=W0104
                    self.payload.groups
                except MetadataError:
                    hubQ.send_message("SoftwareSelectionSpoke",
                                      _("No installation source available"))
                else:
                    hubQ.send_ready("SoftwareSelectionSpoke", False)
        finally:
            hubQ.send_ready(self.__class__.__name__, False)

    @property
    def changed(self):
        method_changed = self._method_changed()
        update_payload_repos = self._update_payload_repos()
        return method_changed or update_payload_repos

    @property
    def completed(self):
        if flags.automatedInstall and (not self.data.method.method or not self.payload.baseRepo):
            return False
        else:
            return not self._error and self.ready and (self.data.method.method or self.payload.baseRepo)

    @property
    def mandatory(self):
        return True

    @property
    def ready(self):
        return (self._ready and
                not threadMgr.get(constants.THREAD_PAYLOAD_MD) and
                not threadMgr.get(constants.THREAD_SOFTWARE_WATCHER) and
                not threadMgr.get(constants.THREAD_CHECK_SOFTWARE))

    @property
    def status(self):
        if threadMgr.get(constants.THREAD_CHECK_SOFTWARE):
            return _("Checking software dependencies...")
        elif not self.ready:
            return _(BASEREPO_SETUP_MESSAGE)
        elif self._error or not self.payload.baseRepo:
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
        self._autodetectDeviceLabel = self.builder.get_object("autodetectDeviceLabel")
        self._autodetectLabel = self.builder.get_object("autodetectLabel")
        self._isoButton = self.builder.get_object("isoRadioButton")
        self._isoBox = self.builder.get_object("isoBox")
        self._networkButton = self.builder.get_object("networkRadioButton")
        self._networkBox = self.builder.get_object("networkBox")

        self._urlEntry = self.builder.get_object("urlEntry")
        self._protocolComboBox = self.builder.get_object("protocolComboBox")
        self._isoChooserButton = self.builder.get_object("isoChooserButton")

        self._mirrorlistCheckbox = self.builder.get_object("mirrorlistCheckbox")

        self._noUpdatesCheckbox = self.builder.get_object("noUpdatesCheckbox")
        self._noUpdatesCheckbox.get_children()[0].set_line_wrap(True)

        self._verifyIsoButton = self.builder.get_object("verifyIsoButton")

        # addon repo objects
        self._repoEntryBox = self.builder.get_object("repoEntryBox")
        self._repoStore = self.builder.get_object("repoStore")
        self._repoSelection = self.builder.get_object("repoSelection")
        self._repoNameEntry = self.builder.get_object("repoNameEntry")
        self._repoProtocolComboBox = self.builder.get_object("repoProtocolComboBox")
        self._repoUrlEntry = self.builder.get_object("repoUrlEntry")
        self._repoMirrorlistCheckbox = self.builder.get_object("repoMirrorlistCheckbox")
        self._repoProxyUrlEntry = self.builder.get_object("repoProxyUrlEntry")
        self._repoProxyUsernameEntry = self.builder.get_object("repoProxyUsernameEntry")
        self._repoProxyPasswordEntry = self.builder.get_object("repoProxyPasswordEntry")

        # updates option container
        self._updatesBox = self.builder.get_object("updatesBox")

        self._proxyButton = self.builder.get_object("proxyButton")
        self._nfsOptsBox = self.builder.get_object("nfsOptsBox")

    def initialize(self):
        NormalSpoke.initialize(self)

        self._grabObjects()

        # I shouldn't have to do this outside GtkBuilder, but it really doesn't
        # want to let me pass in user data.
        self._autodetectButton.connect("toggled", self.on_source_toggled, self._autodetectBox)
        self._isoButton.connect("toggled", self.on_source_toggled, self._isoBox)
        self._networkButton.connect("toggled", self.on_source_toggled, self._networkBox)

        # Show or hide the updates option based on the installclass
        if self.instclass.installUpdates:
            really_show(self._updatesBox)
        else:
            really_hide(self._updatesBox)

        threadMgr.add(AnacondaThread(name=constants.THREAD_SOURCE_WATCHER, target=self._initialize))

    def _initialize(self):
        hubQ.send_message(self.__class__.__name__, _("Probing storage..."))

        threadMgr.wait(constants.THREAD_STORAGE)

        hubQ.send_message(self.__class__.__name__, _(METADATA_DOWNLOAD_MESSAGE))

        threadMgr.wait(constants.THREAD_PAYLOAD)

        added = False

        # If there's no fallback mirror to use, we should just disable that option
        # in the UI.
        if not self.payload.mirrorEnabled:
            self._protocolComboBox.remove(PROTOCOL_MIRROR)

        # If we've previously set up to use a CD/DVD method, the media has
        # already been mounted by payload.setup.  We can't try to mount it
        # again.  So just use what we already know to create the selector.
        # Otherwise, check to see if there's anything available.
        if self.data.method.method == "cdrom":
            self._cdrom = self.payload.install_device
        elif not flags.automatedInstall:
            self._cdrom = opticalInstallMedia(self.storage.devicetree)

        if self._cdrom:
            @gtk_action_wait
            def gtk_action_1():
                self._autodetectDeviceLabel.set_text(_("Device: %s") % self._cdrom.name)
                self._autodetectLabel.set_text(_("Label: %s") % (getattr(self._cdrom.format, "label", "") or ""))

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

        self._reset_repoStore()

        self._ready = True
        hubQ.send_ready(self.__class__.__name__, False)

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
            # path model size format type uuid of format
            dev_info = { "model" : self._sanitize_model(dev.disk.model),
                         "path"  : dev.path,
                         "size"  : dev.size,
                         "format": dev.format.name or "",
                         "label" : dev.format.label or dev.format.uuid or ""
                       }
            store.append([dev, "%(model)s %(path)s (%(size)s MB) %(format)s %(label)s" % dev_info])
            if self.data.method.method == "harddrive" and self.data.method.partition in [dev.path, dev.name]:
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
        self._protocolComboBox.set_active(PROTOCOL_MIRROR)
        self._urlEntry.set_sensitive(False)

        # Set up the default state of UI elements.
        if self.data.method.method == "url":
            self._networkButton.set_active(True)

            proto = self.data.method.url or self.data.method.mirrorlist
            if proto.startswith("http:"):
                self._protocolComboBox.set_active(PROTOCOL_HTTP)
                l = 7
            elif proto.startswith("https:"):
                self._protocolComboBox.set_active(PROTOCOL_HTTPS)
                l = 8
            elif proto.startswith("ftp:"):
                self._protocolComboBox.set_active(PROTOCOL_FTP)
                l = 6
            else:
                self._protocolComboBox.set_active(PROTOCOL_HTTP)
                l = 0

            self._urlEntry.set_sensitive(True)
            self._urlEntry.set_text(proto[l:])
            self._mirrorlistCheckbox.set_active(bool(self.data.method.mirrorlist))
        elif self.data.method.method == "nfs":
            self._networkButton.set_active(True)
            self._protocolComboBox.set_active(PROTOCOL_NFS)

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
                self.data.method.method = "cdrom"
            else:
                self._networkButton.set_active(True)
                self.data.method.method = "url"

        self._noUpdatesCheckbox.set_active(not self.payload.isRepoEnabled("updates"))

        # Setup the addon repos
        self._reset_repoStore()

        # Then, some widgets get enabled/disabled/greyed out depending on
        # how others are set up.  We can use the signal handlers to handle
        # that condition here too.
        self.on_protocol_changed(self._protocolComboBox)

    @property
    def showable(self):
        return not flags.livecdInstall and not self.data.method.method == "liveimg"

    def _mirror_active(self):
        return self._protocolComboBox.get_active() == PROTOCOL_MIRROR

    def _http_active(self):
        return self._protocolComboBox.get_active() in [PROTOCOL_HTTP, PROTOCOL_HTTPS]

    def _ftp_active(self):
        return self._protocolComboBox.get_active() == PROTOCOL_FTP

    def _nfs_active(self):
        return self._protocolComboBox.get_active() == PROTOCOL_NFS

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

        if button is self._networkButton:
            # setup updates check box based on protocol chosen
            self._protocolComboBox.emit("changed")
        else:
            # just make updates check box sensitive and unchecked by default
            self._noUpdatesCheckbox.set_active(False)
            self._updatesBox.set_sensitive(True)

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
        if not hasattr(self.data.method, "proxy"):
            old_proxy = None
        else:
            old_proxy = self.data.method.proxy

        dialog = ProxyDialog(self.data)
        with enlightbox(self.window, dialog.window):
            dialog.refresh()
            dialog.run()
        self._proxyChange = old_proxy != self.data.method.proxy

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
            if constants.ISO_DIR not in mounts and constants.DRACUT_ISODIR not in mounts:
                # We're not mounted to either location, so do the mount
                p.format.mount(mountpoint=constants.ISO_DIR)
            dialog.run(constants.ISO_DIR + "/" + f)
            if unmount:
                p.format.unmount()

    def on_verify_media_clicked(self, button):
        if not self._cdrom:
            return

        dialog = MediaCheckDialog(self.data)
        with enlightbox(self.window, dialog.window):
            dialog.run("/dev/" + self._cdrom.name)

    def on_protocol_changed(self, combo):
        # Only allow the URL entry to be used if we're using an HTTP/FTP
        # method that's not the mirror list, or an NFS method.
        self._urlEntry.set_sensitive(self._http_active() or self._ftp_active() or self._nfs_active())

        # Only allow thse widgets to be shown if it makes sense for the
        # the currently selected protocol.
        self._proxyButton.set_sensitive(self._http_active() or self._mirror_active())
        self._nfsOptsBox.set_visible(self._nfs_active())
        self._mirrorlistCheckbox.set_visible(self._http_active())

        # We only know how to enable updates if the default mirror is used.
        # don't disable updates by default
        self._noUpdatesCheckbox.set_active(not self._mirror_active())
        self._updatesBox.set_sensitive(self._mirror_active())

    def _update_payload_repos(self):
        """ Change the packaging repos to match the new edits

            This will add new repos to the addon repo list, remove
            ones that were removed and update any changes made to
            existing ones.

            :returns: True if any repo was changed, added or removed
            :rtype: bool
        """
        REPO_ATTRS=("name", "baseurl", "mirrorlist", "proxy", "enabled")
        changed = False
        for repo in [r[REPO_OBJ] for r in self._repoStore]:
            orig_repo = self.payload.getAddOnRepo(repo.orig_name)
            if not orig_repo:
                # TODO: Need an API to do this w/o touching yum (not addRepo)
                self.payload.data.repo.dataList().append(repo)
                changed = True
            elif not cmp_obj_attrs(orig_repo, repo, REPO_ATTRS):
                for attr in REPO_ATTRS:
                    setattr(orig_repo, attr, getattr(repo, attr))
                changed = True

        # Remove repos from payload that were removed in the UI
        ui_repo_names = [r[REPO_OBJ].name for r in self._repoStore]
        for repo_name in self.payload.addOns:
            if repo_name not in ui_repo_names:
                repo = self.payload.getAddOnRepo(repo_name)
                # TODO: Need an API to do this w/o touching yum (not addRepo)
                self.payload.data.repo.dataList().remove(repo)
                changed = True

        return changed

    def _reset_repoStore(self):
        """ Reset the list of repos to the default list and select first entry

            Populate it with all the addon repos from payload.getAddOns
            If there are none, clear the repo entry fields
        """
        self._repoStore.clear()
        repos = self.payload.addOns
        log.debug("Setting up repos: %s", repos)
        for name in repos:
            if name in [constants.BASE_REPO_NAME, "updates"]:
                continue

            repo = self.payload.getAddOnRepo(name)
            ks_repo = self.data.RepoData(name=repo.name,
                                         baseurl=repo.baseurl,
                                         mirrorlist=repo.mirrorlist,
                                         proxy=repo.proxy,
                                         enabled=repo.enabled)
            # Track the original name, user may change .name
            ks_repo.orig_name = name
            self._repoStore.append([self.payload.isRepoEnabled(name),
                                    ks_repo.name,
                                    ks_repo])

        if len(self._repoStore) > 0:
            self._repoSelection.select_path(0)
        else:
            self._clear_repo_info()
            self._repoEntryBox.set_sensitive(False)


    def on_repoSelection_changed(self, *args):
        """ Called when the selection changed.

            Update the repo text boxes with the current information
        """
        itr = self._repoSelection.get_selected()[1]
        if not itr:
            return
        self._update_repo_info(self._repoStore[itr][REPO_OBJ])

    def on_repoEnable_toggled(self, renderer, path):
        """ Called when the repo Enable checkbox is clicked
        """
        enabled = not self._repoStore[path][REPO_ENABLED_COL]
        self._repoStore[path][REPO_ENABLED_COL] = enabled
        self._repoStore[path][REPO_OBJ].enabled = enabled

    def _clear_repo_info(self):
        """ Clear the text from the repo entry fields

            and reset the checkbox and combobox.
        """
        self._repoNameEntry.set_text("")
        self._repoMirrorlistCheckbox.handler_block_by_func(self.on_repoMirrorlistCheckbox_toggled)
        self._repoMirrorlistCheckbox.set_active(False)
        self._repoMirrorlistCheckbox.handler_unblock_by_func(self.on_repoMirrorlistCheckbox_toggled)
        self._repoUrlEntry.set_text("")
        self._repoProtocolComboBox.set_active(0)
        self._repoProxyUrlEntry.set_text("")
        self._repoProxyUsernameEntry.set_text("")
        self._repoProxyPasswordEntry.set_text("")

    def _update_repo_info(self, repo):
        """ Update the text boxes with data from repo

            :param repo: kickstart repository object
            :type repo: RepoData
        """
        self._repoNameEntry.set_text(repo.name)

        self._repoMirrorlistCheckbox.handler_block_by_func(self.on_repoMirrorlistCheckbox_toggled)
        if repo.mirrorlist:
            url = repo.mirrorlist
            self._repoMirrorlistCheckbox.set_active(True)
        else:
            url = repo.baseurl
            self._repoMirrorlistCheckbox.set_active(False)
        self._repoMirrorlistCheckbox.handler_unblock_by_func(self.on_repoMirrorlistCheckbox_toggled)

        if url:
            for idx, proto in REPO_PROTO:
                if url.startswith(proto):
                    self._repoProtocolComboBox.set_active(idx)
                    self._repoUrlEntry.set_text(url[len(proto):])
                    break
            else:
                # Unknown protocol, just set the url then
                self._repoUrlEntry.set_text(url)
        else:
            self._repoUrlEntry.set_text("")

        if not repo.proxy:
            self._repoProxyUrlEntry.set_text("")
            self._repoProxyUsernameEntry.set_text("")
            self._repoProxyPasswordEntry.set_text("")
        else:
            try:
                proxy = ProxyString(repo.proxy)
                if proxy.username:
                    self._repoProxyUsernameEntry.set_text(proxy.username)
                if proxy.password:
                    self._repoProxyPasswordEntry.set_text(proxy.password)
                self._repoProxyUrlEntry.set_text(proxy.noauth_url)
            except ProxyStringError as e:
                log.error("Failed to parse proxy for repo %s: %s", repo.name, e)
                return

    def on_noUpdatesCheckbox_toggled(self, *args):
        """ Toggle the enable state of the updates repo

            Before final release this will also toggle the updates-testing repo
        """
        if self._noUpdatesCheckbox.get_active():
            self.payload.disableRepo("updates")
            if not constants.isFinal:
                self.payload.disableRepo("updates-testing")
        else:
            self.payload.enableRepo("updates")
            if not constants.isFinal:
                self.payload.enableRepo("updates-testing")

    def on_addRepo_clicked(self, button):
        """ Add a new repository
        """
        repo = self.data.RepoData(name="New Repository")
        repo.ks_repo = True
        repo.orig_name = ""
        itr = self._repoStore.append([True, repo.name, repo])
        self._repoSelection.select_iter(itr)
        self._repoEntryBox.set_sensitive(True)


    def on_removeRepo_clicked(self, button):
        """ Remove the selected repository
        """
        itr = self._repoSelection.get_selected()[1]
        if not itr:
            return
        self._repoStore.remove(itr)
        if len(self._repoStore) == 0:
            self._clear_repo_info()
            self._repoEntryBox.set_sensitive(False)

    def on_resetRepos_clicked(self, button):
        """ Revert to the default list of repositories
        """
        self._reset_repoStore()

    def on_repoNameEntry_changed(self, entry):
        """ repo name changed
        """
        itr = self._repoSelection.get_selected()[1]
        if not itr:
            return
        repo = self._repoStore[itr][REPO_OBJ]

        name = self._repoNameEntry.get_text().strip()
        self._repoStore.set_value(itr, REPO_NAME_COL, name)
        repo.name = name

    def on_repoUrl_changed(self, *args):
        """ proxy url or protocol changed
        """
        itr = self._repoSelection.get_selected()[1]
        if not itr:
            return
        repo = self._repoStore[itr][REPO_OBJ]
        idx = self._repoProtocolComboBox.get_active()
        proto = REPO_PROTO[idx][1]
        url = self._repoUrlEntry.get_text().strip()
        if self._repoMirrorlistCheckbox.get_active():
            repo.mirorlist = proto + url
        else:
            repo.baseurl = proto + url

    def on_repoMirrorlistCheckbox_toggled(self, *args):
        """ mirror state changed
        """
        itr = self._repoSelection.get_selected()[1]
        if not itr:
            return
        repo = self._repoStore[itr][REPO_OBJ]

        # This is called by set_active so only swap if there is something
        # in the variable.
        if self._repoMirrorlistCheckbox.get_active() and repo.baseurl:
            repo.mirrorlist = repo.baseurl
            repo.baseurl = ""
        elif repo.mirrorlist:
            repo.baseurl = repo.mirrorlist
            repo.mirrorlist = ""

    def on_repoProxy_changed(self, *args):
        """ Update the selected repo's proxy settings
        """
        itr = self._repoSelection.get_selected()[1]
        if not itr:
            return
        repo = self._repoStore[itr][REPO_OBJ]

        url = self._repoProxyUrlEntry.get_text().strip()
        username = self._repoProxyUsernameEntry.get_text().strip() or None
        password = self._repoProxyPasswordEntry.get_text().strip() or None

        try:
            proxy = ProxyString(url=url, username=username, password=password)
            repo.proxy = proxy.url
        except ProxyStringError as e:
            log.error("Failed to parse proxy - %s:%s@%s: %s", username, password, url, e)
