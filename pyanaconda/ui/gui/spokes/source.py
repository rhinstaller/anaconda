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

import time
import threading

import logging
log = logging.getLogger("anaconda")

import os, signal, re
from collections import namedtuple
from urllib.parse import urlsplit

import gi
gi.require_version("GLib", "2.0")
gi.require_version("Gtk", "3.0")

from gi.repository import GLib, Gtk

from pyanaconda.flags import flags
from pyanaconda.i18n import _, N_, CN_
from pyanaconda.image import opticalInstallMedia, potentialHdisoSources
from pyanaconda.ui.communication import hubQ
from pyanaconda.ui.helpers import InputCheck, InputCheckHandler
from pyanaconda.ui.gui import GUIObject
from pyanaconda.ui.gui.helpers import GUIDialogInputCheckHandler, GUISpokeInputCheckHandler
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.categories.software import SoftwareCategory
from pyanaconda.ui.gui.utils import blockedHandler, fire_gtk_action, find_first_child
from pyanaconda.iutil import ProxyString, ProxyStringError, cmp_obj_attrs
from pyanaconda.ui.gui.utils import gtk_call_once, really_hide, really_show, fancy_set_sensitive
from pyanaconda.threads import threadMgr, AnacondaThread
from pyanaconda.packaging import PackagePayload, payloadMgr
from pyanaconda.regexes import REPO_NAME_VALID, URL_PARSE, HOSTNAME_PATTERN_WITHOUT_ANCHORS
from pyanaconda import constants
from pyanaconda import nm
from pyanaconda.iutil import id_generator

from blivet.util import get_mount_device, get_mount_paths

__all__ = ["SourceSpoke"]

BASEREPO_SETUP_MESSAGE = N_("Setting up installation source...")

# These need to match the IDs in protocolComboBox and repoProtocolComboBox in source.glade.
PROTOCOL_HTTP = 'http'
PROTOCOL_HTTPS = 'https'
PROTOCOL_FTP = 'ftp'
PROTOCOL_NFS = 'nfs'
PROTOCOL_MIRROR = 'Closest mirror'

# Repo Store Columns
REPO_ENABLED_COL = 0
REPO_NAME_COL = 1
REPO_OBJ = 2

REPO_PROTO = {PROTOCOL_HTTP:  "http://",
              PROTOCOL_HTTPS: "https://",
              PROTOCOL_FTP:   "ftp://",
              PROTOCOL_NFS:   "nfs://"
              }

CLICK_FOR_DETAILS = N_(' <a href="">Click for details.</a>')

def _validateProxy(proxy_string, username_set, password_set):
    """Validate a proxy string and return an input code usable by InputCheck

       :param str proxy_string: the proxy URL string
       :param bool username_set: Whether a username has been specified external to the URL
       :param bool password_set: Whether a password has been speicifed external to the URL
    """
    proxy_match = URL_PARSE.match(proxy_string)
    if not proxy_match:
        return _("Invalid proxy URL")

    # Ensure the protocol is something that makes sense
    protocol = proxy_match.group("protocol")
    if protocol and protocol not in ('http://', 'https://', 'ftp://'):
        return _("Invalid proxy protocol: %s") % protocol

    # Path and anything after makes no sense for a proxy URL
    # Allow '/' as a path so you can use http://proxy.example.com:8080/
    if (proxy_match.group("path") and proxy_match.group("path") != "/") \
            or proxy_match.group("query") or proxy_match.group("fragment"):
        return _("Extra characters in proxy URL")

    # Check if if authentication data is both in the URL and specified externally
    if (proxy_match.group("username") or proxy_match.group("password")) and (username_set or password_set):
        return _("Proxy authentication data duplicated")

    return InputCheck.CHECK_OK

RepoChecks = namedtuple("RepoChecks", ["name_check", "url_check", "proxy_check"])

class ProxyDialog(GUIObject, GUIDialogInputCheckHandler):
    builderObjects = ["proxyDialog"]
    mainWidgetName = "proxyDialog"
    uiFile = "spokes/source.glade"

    def __init__(self, data, proxy_url):
        GUIObject.__init__(self, data)

        self._proxyOkButton = self.builder.get_object("proxyOkButton")
        GUIDialogInputCheckHandler.__init__(self, self._proxyOkButton)

        self.proxyUrl = proxy_url
        self._proxyCheck = self.builder.get_object("enableProxyCheck")
        self._proxyInfoBox = self.builder.get_object("proxyInfoBox")
        self._authCheck = self.builder.get_object("enableAuthCheck")
        self._proxyAuthBox = self.builder.get_object("proxyAuthBox")

        self._proxyURLEntry = self.builder.get_object("proxyURLEntry")
        self._proxyUsernameEntry = self.builder.get_object("proxyUsernameEntry")
        self._proxyPasswordEntry = self.builder.get_object("proxyPasswordEntry")

        self._proxyValidate = self.add_check(self._proxyURLEntry, self._checkProxyURL)
        self._proxyValidate.update_check_status()

    def _checkProxyURL(self, inputcheck):
        proxy_string = self.get_input(inputcheck.input_obj)

        # Don't set an error icon on empty input, but still consider it an error
        if not proxy_string:
            return InputCheck.CHECK_SILENT

        username_set = self._proxyUsernameEntry.is_sensitive() and self._proxyUsernameEntry.get_text()
        password_set = self._proxyPasswordEntry.is_sensitive() and self._proxyPasswordEntry.get_text()

        return _validateProxy(proxy_string, username_set, password_set)

    # Update the proxy validation check on username and password changes to catch
    # changes in duplicated authentication data
    def on_proxyUsernameEntry_changed(self, entry, user_data=None):
        self._proxyValidate.update_check_status()

    def on_proxyPasswordEntry_changed(self, entry, user_data=None):
        self._proxyValidate.update_check_status()

    def on_proxy_enable_toggled(self, button, *args):
        self._proxyInfoBox.set_sensitive(button.get_active())

        if button.get_active():
            self.set_status(self._proxyValidate)
        else:
            self._proxyOkButton.set_sensitive(True)

    def on_proxy_auth_toggled(self, button, *args):
        self._proxyAuthBox.set_sensitive(button.get_active())
        self._proxyValidate.update_check_status()

    def refresh(self):
        GUIObject.refresh(self)

        if not self.proxyUrl:
            self._proxyCheck.set_active(False)
            self.on_proxy_enable_toggled(self._proxyCheck)
            self._authCheck.set_active(False)
            self.on_proxy_auth_toggled(self._authCheck)
            return

        try:
            proxy = ProxyString(self.proxyUrl)
            if proxy.username:
                self._proxyUsernameEntry.set_text(proxy.username)
            if proxy.password:
                self._proxyPasswordEntry.set_text(proxy.password)
            self._proxyURLEntry.set_text(proxy.noauth_url)
        except ProxyStringError as e:
            log.error("Failed to parse proxy for ProxyDialog.refresh %s: %s", self.proxyUrl, e)
            return

        self._proxyCheck.set_active(True)
        self._authCheck.set_active(bool(proxy.username or proxy.password))
        self.on_proxy_enable_toggled(self._proxyCheck)
        self.on_proxy_auth_toggled(self._authCheck)

    def run(self):
        while True:
            response = self.window.run()

            if response == 1:
                if self.on_ok_clicked():
                    # Ok clicked with valid input, save the proxy data
                    if self._proxyCheck.get_active():
                        url = self._proxyURLEntry.get_text()

                        if self._authCheck.get_active():
                            username = self._proxyUsernameEntry.get_text()
                            password = self._proxyPasswordEntry.get_text()
                        else:
                            username = None
                            password = None

                        proxy = ProxyString(url=url, username=username, password=password)
                        self.proxyUrl = proxy.url
                    else:
                        self.proxyUrl = ""
                    break
                else:
                    # Ok clicked with invalid input, keep running the dialog
                    continue
            else:
                # Cancel or Esc, just exit
                break

        self.window.destroy()

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
        self._chooser = self.builder.get_object("isoChooserDialog")

        # Hide the places sidebar, since it makes no sense in this context
        # This is discouraged, but the alternative suggested is to reinvent the
        # wheel. See also https://bugzilla.gnome.org/show_bug.cgi?id=751730
        places_sidebar = find_first_child(self._chooser, lambda x: isinstance(x, Gtk.PlacesSidebar))
        if places_sidebar:
            really_hide(places_sidebar)

    # pylint: disable=arguments-differ
    def refresh(self, currentFile=""):
        GUIObject.refresh(self)
        self._chooser.connect("current-folder-changed", self.on_folder_changed)
        self._chooser.set_filename(constants.ISO_DIR + "/" + currentFile)

    def run(self, dev):
        retval = None

        unmount = not dev.format.status
        mounts = get_mount_paths(dev.path)
        mountpoint = None
        # We have to check both ISO_DIR and the DRACUT_ISODIR because we
        # still reference both, even though /mnt/install is a symlink to
        # /run/install.  Finding mount points doesn't handle the symlink
        if constants.ISO_DIR not in mounts and constants.DRACUT_ISODIR not in mounts:
            # We're not mounted to either location, so do the mount
            mountpoint = constants.ISO_DIR
            dev.format.mount(mountpoint=mountpoint)

        # If any directory was chosen, return that.  Otherwise, return None.
        rc = self.window.run()
        if rc == Gtk.ResponseType.OK:
            f = self._chooser.get_filename()
            if f:
                retval = f.replace(constants.ISO_DIR, "")

        if unmount:
            dev.format.unmount(mountpoint=mountpoint)

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

class SourceSpoke(NormalSpoke, GUISpokeInputCheckHandler):
    """
       .. inheritance-diagram:: SourceSpoke
          :parts: 3
    """
    builderObjects = ["isoChooser", "isoFilter", "partitionStore", "sourceWindow", "dirImage", "repoStore"]
    mainWidgetName = "sourceWindow"
    uiFile = "spokes/source.glade"
    helpFile = "SourceSpoke.xml"

    category = SoftwareCategory

    icon = "media-optical-symbolic"
    title = CN_("GUI|Spoke", "_INSTALLATION SOURCE")

    def __init__(self, *args, **kwargs):
        NormalSpoke.__init__(self, *args, **kwargs)
        GUISpokeInputCheckHandler.__init__(self)
        self._currentIsoFile = None
        self._ready = False
        self._error = False
        self._error_msg = ""
        self._proxyUrl = ""
        self._proxyChange = False
        self._updatesChange = False
        self._cdrom = None
        self._repo_counter = id_generator()

        self._repoChecks = {}
        self._repoStore_lock = threading.Lock()

    def apply(self):
        # If askmethod was provided on the command line, entering the source
        # spoke wipes that out.
        if flags.askmethod:
            flags.askmethod = False

        payloadMgr.restartThread(self.storage, self.data, self.payload, self.instclass,
                checkmount=False)
        self.clear_info()

    def _method_changed(self):
        """ Check to see if the install method has changed.

            :returns: True if it changed, False if not
            :rtype: bool
        """
        import copy

        old_source = copy.deepcopy(self.data.method)

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
                self.storage.devicetree.resolve_device(old_source.partition) == part and
                old_source.dir in [self._currentIsoFile, "/" + self._currentIsoFile]):
                return False

            # Make sure anaconda doesn't touch this device.
            part.protected = True
            self.storage.config.protected_dev_specs.append(part.name)
        elif self._mirror_active():
            # this preserves the url for later editing
            self.data.method.method = None
            self.data.method.proxy = self._proxyUrl
            if not old_source.method and self.payload.baseRepo and \
               not self._proxyChange and not self._updatesChange:
                return False
        elif self._http_active() or self._ftp_active():
            url = self._urlEntry.get_text().strip()
            mirrorlist = False

            # If the user didn't fill in the URL entry, just return as if they
            # selected nothing.
            if url == "":
                return False

            # Make sure the URL starts with the protocol.  dnf will want that
            # to know how to fetch, and the refresh method needs that to know
            # which element of the combo to default to should this spoke be
            # revisited.
            if self._ftp_active() and not url.startswith("ftp://"):
                url = "ftp://" + url
            elif self._protocolComboBox.get_active_id() == PROTOCOL_HTTP and not url.startswith("http://"):
                url = "http://" + url
                mirrorlist = self._mirrorlistCheckbox.get_active()
            elif self._protocolComboBox.get_active_id() == PROTOCOL_HTTPS and not url.startswith("https://"):
                url = "https://" + url
                mirrorlist = self._mirrorlistCheckbox.get_active()

            if old_source.method == "url" and not self._proxyChange and \
               ((not mirrorlist and old_source.url == url) or \
                (mirrorlist and old_source.mirrorlist == url)):
                return False

            self.data.method.method = "url"
            self.data.method.proxy = self._proxyUrl
            if mirrorlist:
                self.data.method.mirrorlist = url
                self.data.method.url = ""
            else:
                self.data.method.url = url
                self.data.method.mirrorlist = ""
        elif self._nfs_active():
            url = self._urlEntry.get_text().strip()

            if url == "":
                return False

            self.data.method.method = "nfs"
            try:
                (self.data.method.server, self.data.method.dir) = url.split(":", 2)
            except ValueError as e:
                log.error("ValueError: %s", e)
                self._error = True
                self._error_msg = _("Failed to set up installation source; check the repo url")
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
            if not self._isoButton.get_active():
                # Only clear this if iso isn't selected
                self._currentIsoFile = None
                self._isoChooserButton.set_label(self._origIsoChooserButton)
                self._isoChooserButton.set_use_underline(True)

            if old_source.partition in self.storage.config.protected_dev_specs:
                self.storage.config.protected_dev_specs.remove(old_source.partition)

            dev = self.storage.devicetree.get_device_by_name(old_source.partition)
            if dev:
                dev.protected = False

        self._proxyChange = False
        self._updatesChange = False

        return True

    @property
    def changed(self):
        method_changed = self._method_changed()
        update_payload_repos = self._update_payload_repos()
        return method_changed or update_payload_repos or self._error

    @property
    def completed(self):
        """ WARNING: This can be called before _initialize is done, make sure that it
            doesn't access things that are not setup (eg. payload.*) until it is ready
        """
        if flags.automatedInstall and self.ready and not self.payload.baseRepo:
            return False
        else:
            return not self._error and self.ready and (self.data.method.method or self.payload.baseRepo)

    @property
    def mandatory(self):
        return True

    @property
    def ready(self):
        return (self._ready and
                not threadMgr.get(constants.THREAD_PAYLOAD) and
                not threadMgr.get(constants.THREAD_SOFTWARE_WATCHER) and
                not threadMgr.get(constants.THREAD_CHECK_SOFTWARE))

    @property
    def status(self):
        if threadMgr.get(constants.THREAD_CHECK_SOFTWARE):
            return _("Checking software dependencies...")
        elif not self.ready:
            return _(BASEREPO_SETUP_MESSAGE)
        elif not self.payload.baseRepo:
            return _("Error setting up base repository")
        elif self._error:
            return _("Error setting up software source")
        elif self.data.method.method == "url":
            return self.data.method.url or self.data.method.mirrorlist
        elif self.data.method.method == "nfs":
            return _("NFS server %s") % self.data.method.server
        elif self.data.method.method == "cdrom":
            return _("Local media")
        elif self.data.method.method == "harddrive":
            if not self._currentIsoFile:
                return _("Error setting up ISO file")
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
        self._origIsoChooserButton = self._isoChooserButton.get_label()

        # Attach a validator to the URL entry. Start it as disabled, and it will be
        # enabled/disabled as entry sensitivity is enabled/disabled.
        self._urlCheck = self.add_check(self._urlEntry, self._checkURLEntry)
        self._urlCheck.enabled = False

        self._mirrorlistCheckbox = self.builder.get_object("mirrorlistCheckbox")

        self._noUpdatesCheckbox = self.builder.get_object("noUpdatesCheckbox")

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
        self._repoView = self.builder.get_object("repoTreeView")

        # Create a check for duplicate repo ids
        # Call InputCheckHandler directly since this check operates on rows of a TreeModel
        # instead of GtkEntry inputs. Updating the check is handled by the signal handlers
        # connected to repoStore.
        self._duplicateRepoCheck = InputCheckHandler.add_check(self, self._repoStore,
                                                               self._checkDuplicateRepos)

        # Create a dictionary for the checks on fields in individual repos
        # These checks will be added and removed as repos are added and removed from repoStore
        self._repoChecks = {}

        # updates option container
        self._updatesBox = self.builder.get_object("updatesBox")

        self._proxyButton = self.builder.get_object("proxyButton")
        self._nfsOptsBox = self.builder.get_object("nfsOptsBox")

        # Connect scroll events on the viewport with focus events on the box
        mainViewport = self.builder.get_object("mainViewport")
        mainBox = self.builder.get_object("mainBox")
        mainBox.set_focus_vadjustment(mainViewport.get_vadjustment())

    def initialize(self):
        NormalSpoke.initialize(self)

        self._grabObjects()

        # I shouldn't have to do this outside GtkBuilder, but it really doesn't
        # want to let me pass in user data.
        # See also: https://bugzilla.gnome.org/show_bug.cgi?id=727919
        self._autodetectButton.connect("toggled", self.on_source_toggled, self._autodetectBox)
        self._isoButton.connect("toggled", self.on_source_toggled, self._isoBox)
        self._networkButton.connect("toggled", self.on_source_toggled, self._networkBox)
        self._networkButton.connect("toggled", self._updateURLEntryCheck)

        # Show or hide the updates option based on the installclass
        if self.instclass.installUpdates:
            really_show(self._updatesBox)
        else:
            really_hide(self._updatesBox)

        self._repoNameWarningBox = self.builder.get_object("repoNameWarningBox")
        self._repoNameWarningLabel = self.builder.get_object("repoNameWarningLabel")

        threadMgr.add(AnacondaThread(name=constants.THREAD_SOURCE_WATCHER, target=self._initialize))

        # Register listeners for payload events
        payloadMgr.addListener(payloadMgr.STATE_START, self._payload_refresh)
        payloadMgr.addListener(payloadMgr.STATE_STORAGE, self._probing_storage)
        payloadMgr.addListener(payloadMgr.STATE_PACKAGE_MD, self._downloading_package_md)
        payloadMgr.addListener(payloadMgr.STATE_GROUP_MD, self._downloading_group_md)
        payloadMgr.addListener(payloadMgr.STATE_FINISHED, self._payload_finished)
        payloadMgr.addListener(payloadMgr.STATE_ERROR, self._payload_error)

    def _payload_refresh(self):
        hubQ.send_not_ready("SoftwareSelectionSpoke")
        hubQ.send_not_ready(self.__class__.__name__)
        hubQ.send_message(self.__class__.__name__, _(BASEREPO_SETUP_MESSAGE))

        # this sleep is lame, but without it the message above doesn't seem
        # to get processed by the hub in time, and is never shown.
        # FIXME this should get removed when we figure out how to ensure
        # that the message takes effect on the hub before we try to mount
        # a bad NFS server.
        time.sleep(1)

    def _probing_storage(self):
        hubQ.send_message(self.__class__.__name__, _(constants.PAYLOAD_STATUS_PROBING_STORAGE))

    def _downloading_package_md(self):
        # Reset the error state from previous payloads
        self._error = False
        self._error_msg = ""

        hubQ.send_message(self.__class__.__name__, _(constants.PAYLOAD_STATUS_PACKAGE_MD))

    def _downloading_group_md(self):
        hubQ.send_message(self.__class__.__name__, _(constants.PAYLOAD_STATUS_GROUP_MD))

    def _payload_finished(self):
        hubQ.send_ready("SoftwareSelectionSpoke", False)
        hubQ.send_ready(self.__class__.__name__, False)

    def _payload_error(self):
        self._error = True
        hubQ.send_message(self.__class__.__name__, payloadMgr.error)
        if not (hasattr(self.data.method, "proxy") and self.data.method.proxy):
            self._error_msg = _("Failed to set up installation source; check the repo url.")
        else:
            self._error_msg = _("Failed to set up installation source; check the repo url and proxy settings.")
        if self.payload.verbose_errors:
            self._error_msg += _(CLICK_FOR_DETAILS)

        hubQ.send_ready(self.__class__.__name__, False)

    def _initialize(self):
        threadMgr.wait(constants.THREAD_PAYLOAD)

        added = False

        # If there's no fallback mirror to use, we should just disable that option
        # in the UI.
        if not self.payload.mirrorEnabled:
            model = self._protocolComboBox.get_model()
            itr = model.get_iter_first()
            while itr and model[itr][self._protocolComboBox.get_id_column()] != PROTOCOL_MIRROR:
                itr = model.iter_next(itr)

            if itr:
                model.remove(itr)

        # If we've previously set up to use a CD/DVD method, the media has
        # already been mounted by payload.setup.  We can't try to mount it
        # again.  So just use what we already know to create the selector.
        # Otherwise, check to see if there's anything available.
        if self.data.method.method == "cdrom":
            self._cdrom = self.payload.install_device
        elif not flags.automatedInstall:
            self._cdrom = opticalInstallMedia(self.storage.devicetree)

        if self._cdrom:
            fire_gtk_action(self._autodetectDeviceLabel.set_text, _("Device: %s") % self._cdrom.name)
            fire_gtk_action(self._autodetectLabel.set_text, _("Label: %s") % (getattr(self._cdrom.format, "label", "") or ""))
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
        # Wait to make sure the other threads are done before sending ready, otherwise
        # the spoke may not be set sensitive by _handleCompleteness in the hub.
        while not self.ready:
            time.sleep(1)
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

        if self.data.method.method == "harddrive":
            methodDev = self.storage.devicetree.resolve_device(self.data.method.partition)

        for dev in potentialHdisoSources(self.storage.devicetree):
            # path model size format type uuid of format
            dev_info = {"model" : self._sanitize_model(dev.disk.model or ""),
                        "path"  : dev.path,
                        "size"  : dev.size,
                        "format": dev.format.name or "",
                        "label" : dev.format.label or dev.format.uuid or ""
                       }

            # With the label in here, the combo box can appear really long thus pushing the "pick an image"
            # and the "verify" buttons off the screen.
            if dev_info["label"] != "":
                dev_info["label"] = "\n" + dev_info["label"]

            store.append([dev, "%(model)s %(path)s (%(size)s) %(format)s %(label)s" % dev_info])
            if self.data.method.method == "harddrive" and dev == methodDev:
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
        self._protocolComboBox.set_active_id(PROTOCOL_MIRROR)

        if self.data.method.method == "url":
            self._networkButton.set_active(True)

            proto = self.data.method.url or self.data.method.mirrorlist
            if proto.startswith("http:"):
                self._protocolComboBox.set_active_id(PROTOCOL_HTTP)
                l = 7
            elif proto.startswith("https:"):
                self._protocolComboBox.set_active_id(PROTOCOL_HTTPS)
                l = 8
            elif proto.startswith("ftp:"):
                self._protocolComboBox.set_active_id(PROTOCOL_FTP)
                l = 6
            else:
                self._protocolComboBox.set_active_id(PROTOCOL_HTTP)
                l = 0

            self._urlEntry.set_text(proto[l:])
            self._updateURLEntryCheck()
            self._mirrorlistCheckbox.set_active(bool(self.data.method.mirrorlist))
            self._proxyUrl = self.data.method.proxy
        elif self.data.method.method == "nfs":
            self._networkButton.set_active(True)
            self._protocolComboBox.set_active_id(PROTOCOL_NFS)

            self._urlEntry.set_text("%s:%s" % (self.data.method.server, self.data.method.dir))
            self._updateURLEntryCheck()
            self.builder.get_object("nfsOptsEntry").set_text(self.data.method.opts or "")
        elif self.data.method.method == "harddrive":
            self._isoButton.set_active(True)
            self._verifyIsoButton.set_sensitive(True)

            if self._currentIsoFile:
                self._isoChooserButton.set_label(os.path.basename(self._currentIsoFile))
            else:
                self._isoChooserButton.set_label("")
            self._isoChooserButton.set_use_underline(False)
        else:
            # No method was given in advance, so now we need to make a sensible
            # guess.  Go with autodetected media if that was provided, and then
            # fall back to closest mirror.
            if not self._autodetectButton.get_no_show_all():
                self._autodetectButton.set_active(True)
                self.data.method.method = "cdrom"
            else:
                self._networkButton.set_active(True)
                self.data.method.method = None
                self._proxyUrl = self.data.method.proxy

        self._setup_no_updates()

        # Setup the addon repos
        self._reset_repoStore()

        # Some widgets get enabled/disabled/greyed out depending on
        # how others are set up.  We can use the signal handlers to handle
        # that condition here too. Start at the innermost pieces and work
        # outwards

        # First check the protocol combo in the network box
        self.on_protocol_changed(self._protocolComboBox)

        # Then simulate changes for the radio buttons, which may override the
        # sensitivities set for the network box.
        #
        # Whichever radio button is selected should have gotten a signal
        # already, but the ones that are not selected need a signal in order
        # to disable the related box.
        self.on_source_toggled(self._autodetectButton, self._autodetectBox)
        self.on_source_toggled(self._isoButton, self._isoBox)
        self.on_source_toggled(self._networkButton, self._networkBox)

        # Lastly, if the stage2 image is mounted from an HDISO source, there's
        # really no way we can tear down that source to allow the user to
        # change it.  Thus, this entire portion of the spoke should be
        # insensitive.
        if self.data.method.method == "harddrive" and \
           get_mount_device(constants.DRACUT_ISODIR) == get_mount_device(constants.DRACUT_REPODIR):
            for widget in [self._autodetectButton, self._autodetectBox, self._isoButton,
                           self._isoBox, self._networkButton, self._networkBox]:
                widget.set_sensitive(False)
                widget.set_tooltip_text(_("The installation source is in use by the installer and cannot be changed."))

        if not nm.nm_is_connected():
            self._networkButton.set_sensitive(False)
            self._networkBox.set_sensitive(False)

            self.clear_info()
            self.set_warning(_("You need to configure the network to use a network installation source."))
        else:
            if self._error:
                self.clear_info()
                self.set_error(self._error_msg)

            # network button could be deativated from last visit
            self._networkButton.set_sensitive(True)

        # Update the URL entry validation now that we're done messing with sensitivites
        self._updateURLEntryCheck()

    def _setup_no_updates(self):
        """ Setup the state of the No Updates checkbox.

            If closest mirror is not selected, check it.
            If closest mirror is selected, and "updates" repo is enabled,
            uncheck it.
        """
        self._updatesBox.set_sensitive(self._mirror_active())
        active = not self._mirror_active() or not self.payload.isRepoEnabled("updates")
        self._noUpdatesCheckbox.set_active(active)

    @property
    def showable(self):
        return isinstance(self.payload, PackagePayload)

    def _mirror_active(self):
        return self._protocolComboBox.get_active_id() == PROTOCOL_MIRROR

    def _http_active(self):
        return self._protocolComboBox.get_active_id() in [PROTOCOL_HTTP, PROTOCOL_HTTPS]

    def _ftp_active(self):
        return self._protocolComboBox.get_active_id() == PROTOCOL_FTP

    def _nfs_active(self):
        return self._protocolComboBox.get_active_id() == PROTOCOL_NFS

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

    # Input checks

    # This method is shared by the checks on urlEntry and repoUrlEntry
    def _checkURL(self, inputcheck, combo):
        # Network is not up, don't check urls.
        if not nm.nm_is_connected():
            return InputCheck.CHECK_OK

        # If combo is not set inputcheck holds repo
        is_additional_repo = combo is None
        if is_additional_repo:
            # Input object contains repository name
            repo = self._get_repo_by_id(inputcheck.input_obj)
            protocol = urlsplit(repo.baseurl)[0] # extract protocol part (http, https, nfs...)
            if repo.mirrorlist:
                url_string = repo.mirrorlist.strip()[len(protocol) + 3:] # +3 for "://" part
            else:
                url_string = repo.baseurl.strip()[len(protocol) + 3:] # +3 for "://" part
        else:
            url_string = self.get_input(inputcheck.input_obj).strip()
            protocol = combo.get_active_id()

        # If this is HTTP/HTTPS/FTP, use the URL_PARSE regex
        if protocol in (PROTOCOL_HTTP, PROTOCOL_HTTPS, PROTOCOL_FTP):
            if not url_string:
                if is_additional_repo and repo.name:
                    return _("Repository %s has empty url") % repo.name
                else:
                    return _("URL is empty")

            m = URL_PARSE.match(url_string)
            if not m:
                if is_additional_repo and repo.name:
                    return _("Repository %s has invalid url") % repo.name
                else:
                    return _("Invalid URL")

            # Matching protocols in the URL should already have been removed
            # by _removeUrlPrefix. If there's still one there, it's wrong.
            url_protocol = m.group('protocol')
            if url_protocol:
                if is_additional_repo and repo.name:
                    return _("Repository %s does not match selected protocol") % repo.name
                else:
                    return _("Protocol in URL does not match selected protocol")
        elif protocol == PROTOCOL_NFS:
            if not url_string:
                if is_additional_repo and repo.name:
                    return _("Repository %s has empty NFS server") % repo.name
                else:
                    return _("NFS server is empty")

            # Make sure the part before the colon looks like a hostname,
            # and that the path is not empty
            host, _colon, path = url_string.partition(':')

            if not re.match('^' + HOSTNAME_PATTERN_WITHOUT_ANCHORS + '$', host):
                if is_additional_repo and repo.name:
                    return _("Repository %s has invalid host name") % repo.name
                else:
                    return _("Invalid host name")

            if not path:
                if is_additional_repo and repo.name:
                    return _("Repository %s required remote directory") % repo.name
                else:
                    return _("Remote directory is required")

        return InputCheck.CHECK_OK

    def _checkURLEntry(self, inputcheck):
        return self._checkURL(inputcheck, self._protocolComboBox)

    def _checkRepoURL(self, inputcheck):
        return self._checkURL(inputcheck, None)

    # Update the check on urlEntry when the sensitity or selected protocol changes
    def _updateURLEntryCheck(self, *args):
        self._urlCheck.enabled = self._urlEntry.is_sensitive()
        self._urlCheck.update_check_status()

        # Force a status update to clear any disabled errors
        self.set_status(self._urlCheck)

    def _checkDuplicateRepos(self, inputcheck):
        repo_names = [r[REPO_OBJ].name for r in inputcheck.input_obj]
        if len(repo_names) != len(frozenset(repo_names)):
            return _("Duplicate repository names.")
        return InputCheck.CHECK_OK

    def _checkRepoName(self, inputcheck):
        # Input object is name of the repository
        repo_name = self._get_repo_by_id(inputcheck.input_obj).name

        if not repo_name:
            return _("Empty repository name")

        if not REPO_NAME_VALID.match(repo_name):
            return _("Invalid repository name")

        cnames = [constants.BASE_REPO_NAME] + \
                 self.payload.DEFAULT_REPOS + \
                 [r for r in self.payload.repos if r not in self.payload.addOns]
        if repo_name in cnames:
            return _("Repository name conflicts with internal repository name.")

        return InputCheck.CHECK_OK

    def _checkRepoProxy(self, inputcheck):
        # Input object contains repo name
        repo = self._get_repo_by_id(inputcheck.input_obj)
        # If nfs is selected as the protocol, skip the proxy check
        if repo.baseurl.startswith(PROTOCOL_NFS):
            return InputCheck.CHECK_OK

        if not repo.proxy:
            return InputCheck.CHECK_OK

        # Empty proxies are OK, as long as the username and password are empty too
        proxy_obj = ProxyString(repo.proxy)
        if not (repo.proxy or proxy_obj.username or proxy_obj.password):
            return InputCheck.CHECK_OK

        return _validateProxy(proxy_obj.noauth_url, proxy_obj.username, proxy_obj.password)

    # Signal handlers.
    def on_source_toggled(self, button, relatedBox):
        # When a radio button is clicked, this handler gets called for both
        # the newly enabled button as well as the previously enabled (now
        # disabled) button.
        enabled = button.get_active()
        relatedBox.set_sensitive(enabled)
        self._setup_no_updates()

    def on_back_clicked(self, button):
        """If any input validation checks failed, keep the user on the screen.
           Otherwise, do the usual thing."""

        # Check repositories on bad url
        for repo in self._repoStore:
            self._repoChecks[repo[REPO_OBJ].repo_id].url_check.update_check_status()

        failed_check = next(self.failed_checks, None)

        # If the failed check is the duplicate repo check, focus the repo TreeView
        if failed_check == self._duplicateRepoCheck:
            self._repoView.grab_focus()
            return
        # If the failed check is on one of the repo fields, select the repo in the
        # TreeView and focus the field
        elif failed_check in (checks.name_check for checks in self._repoChecks.values()):
            self._repoSelection.select_path(failed_check.data.get_path())
            self._repoNameEntry.grab_focus()
            return
        elif failed_check in (checks.url_check for checks in self._repoChecks.values()):
            self._repoSelection.select_path(failed_check.data.get_path())
            self._repoUrlEntry.grab_focus()
            return
        elif failed_check in (checks.proxy_check for checks in self._repoChecks.values()):
            self._repoSelection.select_path(failed_check.data.get_path())
            self._repoProxyUrlEntry.grab_focus()
            return
        # Otherwise let GUISpokeInputCheckHandler figure out what to focus
        elif not GUISpokeInputCheckHandler.on_back_clicked(self, button):
            return

        self.clear_info()
        NormalSpoke.on_back_clicked(self, button)

    def on_info_bar_clicked(self, *args):
        log.debug("info bar clicked: %s (%s)", self._error, args)
        if not self.payload.verbose_errors:
            return

        dlg = Gtk.MessageDialog(flags=Gtk.DialogFlags.MODAL,
                                message_type=Gtk.MessageType.ERROR,
                                buttons=Gtk.ButtonsType.CLOSE,
                                message_format="\n".join(self.payload.verbose_errors))
        dlg.set_decorated(False)

        with self.main_window.enlightbox(dlg):
            dlg.run()
            dlg.destroy()

    def on_chooser_clicked(self, button):
        dialog = IsoChooser(self.data)

        # If the chooser has been run once before, we should make it default to
        # the previously selected file.
        if self._currentIsoFile:
            dialog.refresh(currentFile=self._currentIsoFile)
        else:
            dialog.refresh()

        with self.main_window.enlightbox(dialog.window):
            f = dialog.run(self._get_selected_partition())

        if f and f.endswith(".iso"):
            self._currentIsoFile = f
            button.set_label(os.path.basename(f))
            button.set_use_underline(False)
            self._verifyIsoButton.set_sensitive(True)

    def on_proxy_clicked(self, button):
        dialog = ProxyDialog(self.data, self._proxyUrl)
        with self.main_window.enlightbox(dialog.window):
            dialog.refresh()
            dialog.run()

        if self._proxyUrl != dialog.proxyUrl:
            self._proxyChange = True
            self._proxyUrl = dialog.proxyUrl

    def on_verify_iso_clicked(self, button):
        p = self._get_selected_partition()
        f = self._currentIsoFile

        if not p or not f:
            return

        dialog = MediaCheckDialog(self.data)
        with self.main_window.enlightbox(dialog.window):
            unmount = not p.format.status
            mounts = get_mount_paths(p.path)
            mountpoint = None
            # We have to check both ISO_DIR and the DRACUT_ISODIR because we
            # still reference both, even though /mnt/install is a symlink to
            # /run/install.  Finding mount points doesn't handle the symlink
            if constants.ISO_DIR not in mounts and constants.DRACUT_ISODIR not in mounts:
                # We're not mounted to either location, so do the mount
                mountpoint = constants.ISO_DIR
                p.format.mount(mountpoint=mountpoint)
            dialog.run(constants.ISO_DIR + "/" + f)
            if unmount:
                p.format.unmount(mountpoint=mountpoint)

    def on_verify_media_clicked(self, button):
        if not self._cdrom:
            return

        dialog = MediaCheckDialog(self.data)
        with self.main_window.enlightbox(dialog.window):
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
        self._setup_no_updates()

        # Any changes to the protocol combo box also need to update the checks.
        # Emitting the urlEntry 'changed' signal will see if the entered URL
        # contains the protocol that's just been selected and strip it if so;
        # _updateURLEntryCheck() does the other validity checks.
        self._urlEntry.emit("changed")
        self._updateURLEntryCheck()

    def _update_payload_repos(self):
        """ Change the packaging repos to match the new edits

            This will add new repos to the addon repo list, remove
            ones that were removed and update any changes made to
            existing ones.

            :returns: True if any repo was changed, added or removed
            :rtype: bool
        """
        REPO_ATTRS = ("name", "baseurl", "mirrorlist", "proxy", "enabled")
        changed = False

        with self._repoStore_lock:
            ui_orig_names = [r[REPO_OBJ].orig_name for r in self._repoStore]

            # Remove repos from payload that were removed in the UI
            for repo_name in [r for r in self.payload.addOns if r not in ui_orig_names]:
                repo = self.payload.getAddOnRepo(repo_name)
                # TODO: Need an API to do this w/o touching dnf (not addRepo)
                # FIXME: Is this still needed for dnf?
                self.payload.data.repo.dataList().remove(repo)
                changed = True

            for repo, orig_repo in [(r[REPO_OBJ], self.payload.getAddOnRepo(r[REPO_OBJ].orig_name)) for r in self._repoStore]:
                if not orig_repo:
                    # TODO: Need an API to do this w/o touching dnf (not addRepo)
                    # FIXME: Is this still needed for dnf?
                    self.payload.data.repo.dataList().append(repo)
                    changed = True
                elif not cmp_obj_attrs(orig_repo, repo, REPO_ATTRS):
                    for attr in REPO_ATTRS:
                        setattr(orig_repo, attr, getattr(repo, attr))
                    changed = True

        return changed

    def _reset_repoStore(self):
        """ Reset the list of repos.

            Populate the list with all the addon repos from payload.addOns.

            If the list has no element, clear the repo entry fields.
        """

        log.debug("Clearing checks in source spoke")

        # Remove the repo checks
        for checks in self._repoChecks.values():
            self.remove_check(checks.name_check)
            self.remove_check(checks.url_check)
            self.remove_check(checks.proxy_check)
        self._repoChecks = {}

        with self._repoStore_lock:
            self._repoStore.clear()
            repos = self.payload.addOns
            log.debug("Setting up repos: %s", repos)
            for name in repos:
                repo = self.payload.getAddOnRepo(name)
                ks_repo = self.data.RepoData(name=repo.name,
                                             baseurl=repo.baseurl,
                                             mirrorlist=repo.mirrorlist,
                                             proxy=repo.proxy,
                                             enabled=repo.enabled)
                # Track the original name, user may change .name
                ks_repo.orig_name = name
                # Add addon repository id for identification
                ks_repo.repo_id = next(self._repo_counter)
                self._repoStore.append([self.payload.isRepoEnabled(name),
                                        ks_repo.name,
                                        ks_repo])

        if len(self._repoStore) > 0:
            self._repoSelection.select_path(0)
        else:
            self._clear_repo_info()
            self._repoEntryBox.set_sensitive(False)

    def _unique_repo_name(self, name):
        """ Return a unique variation of the name if it already
            exists in the repo store.

            :param str name: Name to check
            :returns: name or name with _%d appended

            The returned name will be 1 greater than any other entry in the store
            with a _%d at the end of it.
        """
        # Does this name exist in the store? If not, return it.
        if not any(r[REPO_NAME_COL] == name for r in self._repoStore):
            return name

        # If the name already ends with a _\d+ it needs to be stripped.
        match = re.match(r"(.*)_\d+$", name)
        if match:
            name = match.group(1)

        # Find all of the names with _\d+ at the end
        name_re = re.compile(r"("+re.escape(name)+r")_(\d+)")
        matches = (name_re.match(r[REPO_NAME_COL]) for r in self._repoStore)
        matches = [int(m.group(2)) for m in matches if m is not None]

        # Get the highest number, add 1, append to name
        highest_index = max(matches) if matches else 0
        return name + ("_%d" % (highest_index + 1))

    def _get_repo_by_id(self, repo_id):
        """ Return a repository by given name
        """
        for repo in self._repoStore:
            if repo[REPO_OBJ].repo_id == repo_id:
                return repo[REPO_OBJ]
        return None

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

        with blockedHandler(self._repoMirrorlistCheckbox, self.on_repoMirrorlistCheckbox_toggled):
            self._repoMirrorlistCheckbox.set_active(False)

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

        with blockedHandler(self._repoMirrorlistCheckbox, self.on_repoMirrorlistCheckbox_toggled):
            if repo.mirrorlist:
                url = repo.mirrorlist
                self._repoMirrorlistCheckbox.set_active(True)
            else:
                url = repo.baseurl
                self._repoMirrorlistCheckbox.set_active(False)

        if url:
            for idx, proto in REPO_PROTO.items():
                if url.startswith(proto):
                    self._repoProtocolComboBox.set_active_id(idx)
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

    def _removeUrlPrefix(self, editable, combo, handler):
        # If there is a protocol in the URL, and the protocol matches the
        # combo box, just remove it. This makes it more convenient to paste
        # in URLs. It'll probably freak out people who are typing out http://
        # in the box themselves, but why would you do that?  Don't do that.

        combo_protocol = combo.get_active_id()
        if combo_protocol in (PROTOCOL_HTTP, PROTOCOL_HTTPS, PROTOCOL_FTP):
            url_string = editable.get_text()
            m = URL_PARSE.match(url_string)
            if m:
                url_protocol = m.group('protocol')
                if (url_protocol == 'http://' and combo_protocol == PROTOCOL_HTTP) or \
                        (url_protocol == 'https://' and combo_protocol == PROTOCOL_HTTPS) or \
                        (url_protocol == 'ftp://' and combo_protocol == PROTOCOL_FTP):
                    # URL protocol matches. Block the changed signal and remove it
                    with blockedHandler(editable, handler):
                        editable.set_text(url_string[len(url_protocol):])

    def on_urlEntry_changed(self, editable, data=None):
        # Check for and remove a URL prefix that matches the protocol dropdown
        self._removeUrlPrefix(editable, self._protocolComboBox, self.on_urlEntry_changed)

    def on_noUpdatesCheckbox_toggled(self, *args):
        """ Toggle the enable state of the updates repo

            Before final release this will also toggle the updates-testing repo
        """
        if self._noUpdatesCheckbox.get_active():
            self.payload.setUpdatesEnabled(False)
        else:
            self.payload.setUpdatesEnabled(True)

        # Refresh the metadata using the new set of repos
        self._updatesChange = True

    def on_addRepo_clicked(self, button):
        """ Add a new repository
        """
        name = self._unique_repo_name("New_Repository")
        repo = self.data.RepoData(name=name)
        repo.ks_repo = True
        repo.orig_name = ""
        # Set addon repo id and increment counter
        repo.repo_id = next(self._repo_counter)

        itr = self._repoStore.append([True, repo.name, repo])
        self._repoSelection.select_iter(itr)
        self._repoEntryBox.set_sensitive(True)

    def on_removeRepo_clicked(self, button):
        """ Remove the selected repository
        """
        itr = self._repoSelection.get_selected()[1]
        if not itr:
            return

        # Remove the input validation checks for this repo
        repo = self._repoStore[itr][REPO_OBJ]
        self.remove_check(self._repoChecks[repo.repo_id].name_check)
        self.remove_check(self._repoChecks[repo.repo_id].url_check)
        self.remove_check(self._repoChecks[repo.repo_id].proxy_check)
        del self._repoChecks[repo.repo_id]

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

        repo.name = name
        self._repoStore.set_value(itr, REPO_NAME_COL, name)
        # do not update check status if check are not yet set up
        # (populationg/refreshing the spoke)
        if repo.repo_id in self._repoChecks:
            self._repoChecks[repo.repo_id].name_check.update_check_status()

    def on_repoUrl_changed(self, editable, data=None):
        """ proxy url or protocol changed
        """
        itr = self._repoSelection.get_selected()[1]
        if not itr:
            return
        repo = self._repoStore[itr][REPO_OBJ]
        idx = self._repoProtocolComboBox.get_active_id()
        proto = REPO_PROTO[idx]
        url = self._repoUrlEntry.get_text().strip()
        if self._repoMirrorlistCheckbox.get_active():
            repo.mirorlist = proto + url
        else:
            repo.baseurl = proto + url

        # do not update check status if check are not yet set up
        # (populationg/refreshing the spoke)
        if repo.repo_id in self._repoChecks:
            self._repoChecks[repo.repo_id].url_check.update_check_status()

        # Check for and remove a URL prefix that matches the protocol dropdown
        self._removeUrlPrefix(editable, self._repoProtocolComboBox, self.on_repoUrl_changed)

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

        # do not update check status if checks are not yet set up
        # (populating/refreshing the spoke)
        if repo.name in self._repoChecks:
            self._repoChecks[repo.repo_id].proxy_check.update_check_status()

        try:
            if username and password:
                proxy = ProxyString(url=url, username=username, password=password)
            else:
                proxy = ProxyString(url=url)
            repo.proxy = proxy.url
        except ProxyStringError as e:
            log.error("Failed to parse proxy - %s:%s@%s: %s", username, password, url, e)

    def on_repoStore_row_changed(self, model, path, itr, user_data=None):
        self._duplicateRepoCheck.update_check_status()

    def on_repoStore_row_deleted(self, model, path, user_data=None):
        self._duplicateRepoCheck.update_check_status()

    def on_repoStore_row_inserted(self, model, path, itr, user_data=None):
        self._duplicateRepoCheck.update_check_status()

        repo = model[itr][REPO_OBJ]

        # Add checks for the repo fields
        # Use InputCheckHandler.add_check instead of GUISpokeInputCheckHandler.add_check since
        # the input fields are used by every repo, so the changed signal handler is shared by
        # more than one check and needs to update only the active one.

        # It would be nice if we could store itr as the means of accessing this row later,
        # and GtkListStore sets GTK_TREE_MODEL_ITERS_PERSIST which is supposed to let us
        # do something like that, but as part of a grand practical joke the iter passed in
        # to this method is different from the iter used everywhere else, and is useless
        # once this method returns. Instead, create a TreeRowReference and work backwards
        # from that using paths any time we need to reference the store.
        self._repoChecks[repo.repo_id] = RepoChecks(InputCheckHandler.add_check(self,
                                                                             repo.repo_id,
                                                                             self._checkRepoName,
                                                                             Gtk.TreeRowReference.new(model, path)),
                                                 InputCheckHandler.add_check(self,
                                                                             repo.repo_id,
                                                                             self._checkRepoURL,
                                                                             Gtk.TreeRowReference.new(model, path)),
                                                 InputCheckHandler.add_check(self,
                                                                             repo.repo_id,
                                                                             self._checkRepoProxy,
                                                                             Gtk.TreeRowReference.new(model, path)))

    def on_repoProtocolComboBox_changed(self, combobox, user_data=None):
        # Set the mirrorlist and proxy fields sensitivity depending on whether NFS was selected
        sensitive = not(self._repoProtocolComboBox.get_active_id() == PROTOCOL_NFS)
        fancy_set_sensitive(self._repoMirrorlistCheckbox, sensitive)
        fancy_set_sensitive(self._repoProxyUrlEntry, sensitive)
        fancy_set_sensitive(self._repoProxyUsernameEntry, sensitive)
        fancy_set_sensitive(self._repoProxyPasswordEntry, sensitive)

        # Re-run the proxy check
        itr = self._repoSelection.get_selected()[1]
        if itr:
            repo = self._repoStore[itr][REPO_OBJ]
            self._repoChecks[repo.repo_id].proxy_check.update_check_status()

        # Run the URL entry handler too as it might be needed
        self._repoUrlEntry.emit("changed")
