# Installation source spoke classes
#
# Copyright (C) 2019 Red Hat, Inc.
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
import os
import signal
import re

from collections import namedtuple
from urllib.parse import urlsplit

from pyanaconda.core import glib, constants
from pyanaconda.core.constants import PAYLOAD_TYPE_DNF, SOURCE_TYPE_HDD, SOURCE_TYPE_URL, \
    SOURCE_TYPE_CDROM, SOURCE_TYPE_NFS, SOURCE_TYPE_HMC, URL_TYPE_BASEURL, URL_TYPE_MIRRORLIST, \
    URL_TYPE_METALINK, SOURCE_TYPE_CLOSEST_MIRROR, SOURCE_TYPE_CDN
from pyanaconda.core.process_watchers import PidWatcher
from pyanaconda.flags import flags
from pyanaconda.core.i18n import _, N_, CN_, C_
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.common.constants.services import SUBSCRIPTION
from pyanaconda.payload.image import find_optical_install_media, find_potential_hdiso_sources, \
    get_hdiso_source_info, get_hdiso_source_description
from pyanaconda.core.payload import ProxyString, ProxyStringError, parse_nfs_url, create_nfs_url
from pyanaconda.core.util import cmp_obj_attrs, id_generator
from pyanaconda.ui.communication import hubQ
from pyanaconda.ui.context import context
from pyanaconda.ui.helpers import InputCheck, InputCheckHandler, SourceSwitchHandler
from pyanaconda.ui.lib.subscription import switch_source
from pyanaconda.ui.gui import GUIObject
from pyanaconda.ui.gui.helpers import GUIDialogInputCheckHandler, GUISpokeInputCheckHandler
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.categories.software import SoftwareCategory
from pyanaconda.ui.gui.utils import blockedHandler, fire_gtk_action, find_first_child
from pyanaconda.ui.gui.utils import gtk_call_once, really_hide, really_show, fancy_set_sensitive, \
    set_password_visibility
from pyanaconda.threading import threadMgr, AnacondaThread
from pyanaconda.payload import utils as payload_utils
from pyanaconda.payload.manager import payloadMgr, PayloadState
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.regexes import REPO_NAME_VALID, URL_PARSE, HOSTNAME_PATTERN_WITHOUT_ANCHORS
from pyanaconda.modules.common.constants.services import NETWORK, STORAGE
from pyanaconda.modules.common.constants.objects import DEVICE_TREE
from pyanaconda.modules.common.structures.storage import DeviceData
from pyanaconda.modules.common.util import is_module_available
from pyanaconda.core.storage import device_matches

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

__all__ = ["SourceSpoke"]

BASEREPO_SETUP_MESSAGE = N_("Setting up installation source...")

# These need to match the IDs in protocolComboBox and repoProtocolComboBox in
# installation_source.glade.
PROTOCOL_HTTP = 'http'
PROTOCOL_HTTPS = 'https'
PROTOCOL_FTP = 'ftp'
PROTOCOL_NFS = 'nfs'
PROTOCOL_FILE = 'file'
PROTOCOL_MIRROR = 'Closest mirror'

# Repo Store Columns
REPO_ENABLED_COL = 0
REPO_NAME_COL = 1
REPO_OBJ = 2

# Additional repo protocol combobox fields
MODEL_ROW_VALUE = 0
MODEL_ROW_NAME = 1

REPO_PROTO = {PROTOCOL_HTTP:  "http://",
              PROTOCOL_HTTPS: "https://",
              PROTOCOL_FTP:   "ftp://",
              PROTOCOL_NFS:   "nfs://",
              PROTOCOL_FILE:  "file://"
              }

CLICK_FOR_DETAILS = N_(' <a href="">Click for details.</a>')


def _validate_proxy(proxy_string, username_set, password_set):
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
    if (proxy_match.group("username") or proxy_match.group("password")) \
       and (username_set or password_set):
        return _("Proxy authentication data duplicated")

    return InputCheck.CHECK_OK


RepoChecks = namedtuple("RepoChecks", ["name_check", "url_check", "proxy_check"])


class ProxyDialog(GUIObject, GUIDialogInputCheckHandler):
    builderObjects = ["proxyDialog"]
    mainWidgetName = "proxyDialog"
    uiFile = "spokes/installation_source.glade"

    def __init__(self, data, proxy_url):
        GUIObject.__init__(self, data)

        self._proxy_ok_button = self.builder.get_object("proxyOkButton")
        GUIDialogInputCheckHandler.__init__(self, self._proxy_ok_button)

        self.proxy_url = proxy_url
        self._proxy_check = self.builder.get_object("enableProxyCheck")
        self._proxy_info_box = self.builder.get_object("proxyInfoBox")
        self._auth_check = self.builder.get_object("enableAuthCheck")
        self._proxy_auth_box = self.builder.get_object("proxyAuthBox")

        self._proxy_url_entry = self.builder.get_object("proxyURLEntry")
        self._proxy_username_entry = self.builder.get_object("proxyUsernameEntry")
        self._proxy_password_entry = self.builder.get_object("proxyPasswordEntry")

        self._proxy_validate = self.add_check(self._proxy_url_entry, self._check_proxy_url)
        self._proxy_validate.update_check_status()

    def _check_proxy_url(self, inputcheck):
        proxy_string = self.get_input(inputcheck.input_obj)

        # Don't set an error icon on empty input, but still consider it an error
        if not proxy_string:
            return InputCheck.CHECK_SILENT

        return _validate_proxy(proxy_string, self._is_username_set(), self._is_password_set())

    def _is_username_set(self):
        return self._proxy_username_entry.is_sensitive() and self._proxy_username_entry.get_text()

    def _is_password_set(self):
        return self._proxy_password_entry.is_sensitive() and self._proxy_password_entry.get_text()

    # Update the proxy validation check on username and password changes to catch
    # changes in duplicated authentication data
    def on_proxyUsernameEntry_changed(self, entry, user_data=None):
        self._proxy_validate.update_check_status()

    def on_proxyPasswordEntry_changed(self, entry, user_data=None):
        self._proxy_validate.update_check_status()

    def on_proxy_enable_toggled(self, button, *args):
        self._proxy_info_box.set_sensitive(button.get_active())

        if button.get_active():
            self.set_status(self._proxy_validate)
        else:
            self._proxy_ok_button.set_sensitive(True)

    def on_proxy_auth_toggled(self, button, *args):
        self._proxy_auth_box.set_sensitive(button.get_active())
        self._proxy_validate.update_check_status()

    def on_password_icon_clicked(self, entry, icon_pos, event):
        """Called by Gtk callback when the icon of a password entry is clicked."""
        set_password_visibility(entry, not entry.get_visibility())

    def on_password_entry_map(self, entry):
        """Called when a proxy password entry widget is going to be displayed.
        - Without this the password visibility toggle icon would not be shown.
        - The password should be hidden every time the entry widget is displayed
          to avoid showing the password in plain text in case the user previously
          displayed the password and then closed the dialog.
        """
        set_password_visibility(entry, False)

    def refresh(self):
        GUIObject.refresh(self)

        if not self.proxy_url:
            self._proxy_check.set_active(False)
            self.on_proxy_enable_toggled(self._proxy_check)
            self._auth_check.set_active(False)
            self.on_proxy_auth_toggled(self._auth_check)
            return

        try:
            proxy = ProxyString(self.proxy_url)
            if proxy.username:
                self._proxy_username_entry.set_text(proxy.username)
            if proxy.password:
                self._proxy_password_entry.set_text(proxy.password)
            self._proxy_url_entry.set_text(proxy.noauth_url)
        except ProxyStringError as e:
            log.error("Failed to parse proxy for ProxyDialog.refresh %s: %s", self.proxy_url, e)
            return

        self._proxy_check.set_active(True)
        self._auth_check.set_active(bool(proxy.username or proxy.password))
        self.on_proxy_enable_toggled(self._proxy_check)
        self.on_proxy_auth_toggled(self._auth_check)

    def run(self):
        while True:
            response = self.window.run()

            if response == 1:
                if self.on_ok_clicked():
                    # Ok clicked with valid input, save the proxy data
                    if self._proxy_check.get_active():
                        url = self._proxy_url_entry.get_text()

                        if self._auth_check.get_active():
                            username = self._proxy_username_entry.get_text()
                            password = self._proxy_password_entry.get_text()
                        else:
                            username = None
                            password = None

                        proxy = ProxyString(url=url, username=username, password=password)
                        self.proxy_url = proxy.url
                    else:
                        self.proxy_url = ""
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
    uiFile = "spokes/installation_source.glade"
    TRANSLATION_CONTEXT = "GUI|Software Source|Media Check Dialog"

    def __init__(self, data):
        super().__init__(data)
        self.progress_bar = self.builder.get_object("mediaCheck-progressBar")
        self.close_button = self.builder.get_object("closeActionButton")
        self.verify_progress_label = self.builder.get_object("verifyProgressLabel")
        self.verify_result_label = self.builder.get_object("verifyResultLabel")
        self.verify_result_icon = self.builder.get_object("verifyResultIcon")
        self._pid = None

    def _check_iso_ends_cb(self, pid, status):
        if os.WIFSIGNALED(status):
            pass
        elif status == 0:
            self.set_state_ok()
        else:
            self.set_state_bad()

        self.progress_bar.set_fraction(1.0)
        glib.spawn_close_pid(pid)
        self._pid = None

    def _check_iso_stdout_watcher(self, fd, condition):
        if condition == glib.IOCondition.HUP:
            return False

        channel = glib.IOChannel(fd)
        line = channel.readline().strip()

        if not line.isdigit():
            return True

        pct = float(line)/100
        if pct > 1.0:
            pct = 1.0

        self.progress_bar.set_fraction(pct)
        return True

    def run(self, device_path):
        (retval, self._pid, _stdin, stdout, _stderr) = \
            glib.spawn_async_with_pipes(None, ["checkisomd5", "--gauge", device_path], [],
                                        glib.SpawnFlags.DO_NOT_REAP_CHILD |
                                        glib.SpawnFlags.SEARCH_PATH,
                                        None, None)
        if not retval:
            return

        # This function waits for checkisomd5 to end and then cleans up after it.
        PidWatcher().watch_process(self._pid, self._check_iso_ends_cb)

        # This function watches the process's stdout.
        glib.io_add_watch(stdout,
                          glib.IOCondition.IN | glib.IOCondition.HUP,
                          self._check_iso_stdout_watcher)

        self.window.run()

    def on_close(self, *args):
        if self._pid:
            os.kill(self._pid, signal.SIGKILL)

        self.set_state_processing()

        self.window.destroy()

    def set_state_processing(self):
        self.close_button.set_label(C_(
            "GUI|Software Source|Media Check Dialog",
            "Cancel"
        ))
        self.verify_progress_label.set_text(C_(
            "GUI|Software Source|Media Check Dialog",
            "Verifying media, please wait..."
        ))
        self.verify_result_label.set_text("")
        self.verify_result_icon.set_visible(False)

    def set_state_ok(self):
        self.close_button.set_label(C_(
            "GUI|Software Source|Media Check Dialog",
            "OK"
        ))
        self.verify_progress_label.set_text(C_(
            "GUI|Software Source|Media Check Dialog",
            "Verification finished."
        ))
        self.verify_result_label.set_text(C_(
            "GUI|Software Source|Media Check Dialog",
            "This media is good to install from."
        ))
        self.verify_result_icon.set_visible(True)
        self.verify_result_icon.set_from_icon_name("emblem-default-symbolic", Gtk.IconSize.DIALOG)

    def set_state_bad(self):
        self.close_button.set_label(C_(
            "GUI|Software Source|Media Check Dialog",
            "OK"
        ))
        self.verify_progress_label.set_text(C_(
            "GUI|Software Source|Media Check Dialog",
            "Verification finished."
        ))
        self.verify_result_label.set_text(C_(
            "GUI|Software Source|Media Check Dialog",
            "This media is not good to install from."
        ))
        self.verify_result_icon.set_visible(True)
        self.verify_result_icon.set_from_icon_name("dialog-warning-symbolic", Gtk.IconSize.DIALOG)


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
    uiFile = "spokes/installation_source.glade"

    def __init__(self, data):
        super().__init__(data)
        self._chooser = self.builder.get_object("isoChooserDialog")

        # Hide the places sidebar, since it makes no sense in this context
        # This is discouraged, but the alternative suggested is to reinvent the
        # wheel. See also https://bugzilla.gnome.org/show_bug.cgi?id=751730
        places_sidebar = find_first_child(self._chooser,
                                          lambda x: isinstance(x, Gtk.PlacesSidebar))
        if places_sidebar:
            really_hide(places_sidebar)

    # pylint: disable=arguments-differ
    def refresh(self, currentFile=""):
        super().refresh()
        self._chooser.connect("current-folder-changed", self.on_folder_changed)
        self._chooser.set_filename(constants.ISO_DIR + "/" + currentFile)

    def run(self, device_name):
        retval = None
        device_path = payload_utils.get_device_path(device_name)

        # FIXME: Use a unique mount point.
        mounts = payload_utils.get_mount_paths(device_path)
        mountpoint = None
        # We have to check both ISO_DIR and the DRACUT_ISODIR because we
        # still reference both, even though /mnt/install is a symlink to
        # /run/install.  Finding mount points doesn't handle the symlink
        if constants.ISO_DIR not in mounts and constants.DRACUT_ISODIR not in mounts:
            # We're not mounted to either location, so do the mount
            mountpoint = constants.ISO_DIR
            payload_utils.mount_device(device_name, mountpoint)

        # If any directory was chosen, return that.  Otherwise, return None.
        rc = self.window.run()
        if rc == Gtk.ResponseType.OK:
            f = self._chooser.get_filename()
            if f:
                retval = f.replace(constants.ISO_DIR, "")

        if not mounts:
            payload_utils.unmount_device(device_name, mountpoint)

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


class SourceSpoke(NormalSpoke, GUISpokeInputCheckHandler, SourceSwitchHandler):
    """
       .. inheritance-diagram:: SourceSpoke
          :parts: 3
    """
    builderObjects = ["isoChooser", "isoFilter", "partitionStore", "sourceWindow",
                      "dirImage", "repoStore"]
    mainWidgetName = "sourceWindow"
    uiFile = "spokes/installation_source.glade"
    category = SoftwareCategory

    icon = "media-optical-symbolic"
    title = CN_("GUI|Spoke", "_Installation Source")

    @staticmethod
    def get_screen_id():
        """Return a unique id of this UI screen."""
        return "software-source-configuration"

    @classmethod
    def should_run(cls, environment, data):
        """Don't run for any non-package payload."""
        if not NormalSpoke.should_run(environment, data):
            return False

        return context.payload_type == PAYLOAD_TYPE_DNF

    def __init__(self, *args, **kwargs):
        NormalSpoke.__init__(self, *args, **kwargs)
        GUISpokeInputCheckHandler.__init__(self)
        SourceSwitchHandler.__init__(self)

        self._current_iso_file = None
        self._ready = False
        self._error = False
        self._error_msg = ""
        self._proxy_url = ""
        self._proxy_change = False
        self._updates_change = False
        self._cdrom = None
        self._repo_counter = id_generator()

        self._repo_checks = {}
        self._repo_store_lock = threading.Lock()

        self._network_module = NETWORK.get_proxy()
        self._device_tree = STORAGE.get_proxy(DEVICE_TREE)

        # connect to the Subscription module, if possible
        self._subscription_module = None
        if is_module_available(SUBSCRIPTION):
            self._subscription_module = SUBSCRIPTION.get_proxy()

    def apply(self):
        source_changed = self._update_payload_source()
        repo_changed = self._update_payload_repos()
        source_proxy = self.payload.get_source_proxy()
        cdn_source = source_proxy.Type == SOURCE_TYPE_CDN
        # If CDN is the current installation source but no subscription is
        # attached there is no need to refresh the installation source,
        # as without the subscription tokens the refresh would fail anyway.
        if cdn_source and not self.subscribed:
            log.debug("CDN source but no subscription attached - skipping payload restart.")
        elif source_changed or repo_changed or self._error:
            payloadMgr.restart_thread(self.payload, checkmount=False)
        else:
            log.debug("Nothing has changed - skipping payload restart.")

        self.clear_info()

    def _update_payload_source(self):
        """ Check to see if the install method has changed.

            :returns: True if it changed, False if not
            :rtype: bool
        """
        source_proxy = self.payload.get_source_proxy()
        source_type = source_proxy.Type

        if self._cdn_button.get_active():
            if source_type == SOURCE_TYPE_CDN:
                return False
            switch_source(self.payload, SOURCE_TYPE_CDN)
        elif self._autodetect_button.get_active():
            if not self._cdrom:
                return False

            if source_type == SOURCE_TYPE_CDROM:
                # XXX maybe we should always redo it for cdrom in case they
                # switched disks
                return False

            self.set_source_cdrom()
        elif self._hmc_button.get_active():
            if source_type == SOURCE_TYPE_HMC:
                return False

            self.set_source_hmc()
        elif self._iso_button.get_active():
            # If the user didn't select a partition (not sure how that would
            # happen) or didn't choose a directory (more likely), then return
            # as if they never did anything.
            partition = self._get_selected_partition()
            if not partition or not self._current_iso_file:
                return False

            if source_type == SOURCE_TYPE_HDD \
                    and payload_utils.resolve_device(source_proxy.Partition) == partition \
                    and source_proxy.Directory in [self._current_iso_file, "/" + self._current_iso_file]:
                return False

            self.set_source_hdd_iso(partition, "/" + self._current_iso_file)
        elif self._mirror_active():
            if source_type == SOURCE_TYPE_CLOSEST_MIRROR \
                    and self.payload.base_repo \
                    and not self._proxy_change \
                    and not self._updates_change:
                return False

            self.set_source_closest_mirror()
        elif self._ftp_active():
            url = self._url_entry.get_text().strip()
            # If the user didn't fill in the URL entry, just return as if they
            # selected nothing.
            if url == "":
                return False

            # Make sure the URL starts with the protocol.  dnf will want that
            # to know how to fetch, and the refresh method needs that to know
            # which element of the combo to default to should this spoke be
            # revisited.
            if not url.startswith("ftp://"):
                url = "ftp://" + url

            if source_type == SOURCE_TYPE_URL and not self._proxy_change:
                repo_configuration = RepoConfigurationData.from_structure(
                    source_proxy.RepoConfiguration
                )

                if repo_configuration.url == url:
                    return False

            self.set_source_url(url, proxy=self._proxy_url)
        elif self._http_active():
            url = self._url_entry.get_text().strip()
            # If the user didn't fill in the URL entry, just return as if they
            # selected nothing.
            if url == "":
                return False

            # Make sure the URL starts with the protocol.  dnf will want that
            # to know how to fetch, and the refresh method needs that to know
            # which element of the combo to default to should this spoke be
            # revisited.
            elif (self._protocol_combo_box.get_active_id() == PROTOCOL_HTTP
                  and not url.startswith("http://")):
                url = "http://" + url
            elif (self._protocol_combo_box.get_active_id() == PROTOCOL_HTTPS
                  and not url.startswith("https://")):
                url = "https://" + url

            url_type = self._url_type_combo_box.get_active_id()

            if source_type == SOURCE_TYPE_URL and not self._proxy_change:
                repo_configuration = RepoConfigurationData.from_structure(
                    source_proxy.RepoConfiguration
                )

                if repo_configuration.url == url \
                        and repo_configuration.type == url_type:
                    return False

            self.set_source_url(url, url_type, proxy=self._proxy_url)
        elif self._nfs_active():
            url = self._url_entry.get_text().strip()
            opts = self.builder.get_object("nfsOptsEntry").get_text() or ""

            if url == "":
                return False

            try:
                server, directory = url.split(":", 2)
            except ValueError as e:
                log.error("ValueError: %s", e)
                self._error = True
                self._error_msg = _("Failed to set up installation source; check the repo url")
                return

            if source_type == SOURCE_TYPE_NFS \
                    and source_proxy.URL == create_nfs_url(server, directory, opts):
                return False

            self.set_source_nfs(server, directory, opts)

        self._proxy_change = False
        self._updates_change = False

        return True

    def _update_file_protocol(self, ksrepo):
        """Show file protocol for repositories that already have it. Remove it when unselected."""
        if ksrepo.baseurl and ksrepo.baseurl.startswith(REPO_PROTO[PROTOCOL_FILE]):
            self._set_file_protocol_to_repo_combobox()
            self._repo_protocol_combo_box.set_sensitive(False)
        else:
            self._remove_file_protocol_from_repo_combobox()
            self._repo_protocol_combo_box.set_sensitive(True)

    def _set_file_protocol_to_repo_combobox(self):
        # file protocol will be always the last one
        model = self._repo_protocol_combo_box.get_model()
        row = self._get_protocol_row(PROTOCOL_FILE)

        if row is None:
            model.append([REPO_PROTO[PROTOCOL_FILE], PROTOCOL_FILE])

        self._protocol_combo_box.set_active_id(PROTOCOL_FILE)

    def _remove_file_protocol_from_repo_combobox(self):
        model = self._repo_protocol_combo_box.get_model()
        row = self._get_protocol_row(PROTOCOL_FILE)

        if row:
            model.remove(row.iter)

    def _get_protocol_row(self, protocol):
        model = self._repo_protocol_combo_box.get_model()

        for row in model:
            if row[MODEL_ROW_NAME] == protocol:
                return row

        return None

    @property
    def completed(self):
        """ WARNING: This can be called before _initialize is done, make sure that it
            doesn't access things that are not setup (eg. payload.*) until it is ready
        """
        source_proxy = self.payload.get_source_proxy()
        if source_proxy.Type == SOURCE_TYPE_CDN:
            return True
        elif flags.automatedInstall and self.ready and not self.payload.base_repo:
            return False

        return not self._error and self.ready and self.payload.is_complete()

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
    def subscribed(self):
        """Report if the system is currently subscribed.

        NOTE: This will be always False when the Subscription
              module is not available.

        :return: True if subscribed, False otherwise
        :rtype: bool
        """
        subscribed = False
        if self._subscription_module:
            subscribed = self._subscription_module.IsSubscriptionAttached
        return subscribed

    @property
    def registered_to_satellite(self):
        """Report if the system is registered to a Satellite instance.

        NOTE: This will be always False when the Subscription
              module is not available.

        :return: True if registered to Satellite, False otherwise
        :rtype: bool
        """
        registered_to_satellite = False
        if self._subscription_module:
            registered_to_satellite = self._subscription_module.IsRegisteredToSatellite
        return registered_to_satellite

    @property
    def status(self):
        # When CDN is selected as installation source and system
        # is not yet subscribed, the automatic repo refresh will
        # fail. This is expected as CDN can't be used until the
        # system has been registered. So prevent the error
        # message and show CDN is used instead. If CDN still
        # fails after registration, the regular error message
        # will be displayed.
        source_proxy = self.payload.get_source_proxy()
        cdn_source = source_proxy.Type == SOURCE_TYPE_CDN
        if cdn_source:
            if self.registered_to_satellite:
                # override the regular CDN source name to make it clear Satellite
                # provided repositories are being used
                return _("Satellite")
            else:
                source_proxy = self.payload.get_source_proxy()
                return source_proxy.Description
        elif threadMgr.get(constants.THREAD_CHECK_SOFTWARE):
            return _("Checking software dependencies...")
        elif not self.ready:
            return _(BASEREPO_SETUP_MESSAGE)
        elif not self.payload.base_repo:
            return _("Error setting up base repository")
        elif self._error:
            return _("Error setting up software source")
        elif not self.payload.is_complete():
            return _("Nothing selected")
        else:
            source_proxy = self.payload.get_source_proxy()
            return source_proxy.Description

    def _get_device_name(self, device_spec):
        devices = device_matches(device_spec)

        if not devices:
            log.warning("Device for installation from HDD can't be found!")
            return ""
        elif len(devices) > 1:
            log.warning("More than one device is found for HDD installation!")

        return devices[0]

    def _grab_objects(self):
        self._autodetect_button = self.builder.get_object("autodetectRadioButton")
        self._autodetect_box = self.builder.get_object("autodetectBox")
        self._autodetect_device_label = self.builder.get_object("autodetectDeviceLabel")
        self._autodetect_label = self.builder.get_object("autodetectLabel")
        self._cdn_button = self.builder.get_object("cdnRadioButton")
        self._hmc_button = self.builder.get_object("hmcRadioButton")
        self._iso_button = self.builder.get_object("isoRadioButton")
        self._iso_box = self.builder.get_object("isoBox")
        self._network_button = self.builder.get_object("networkRadioButton")
        self._network_box = self.builder.get_object("networkBox")

        self._url_entry = self.builder.get_object("urlEntry")
        self._protocol_combo_box = self.builder.get_object("protocolComboBox")
        self._iso_chooser_button = self.builder.get_object("isoChooserButton")

        # Attach a validator to the URL entry. Start it as disabled, and it will be
        # enabled/disabled as entry sensitivity is enabled/disabled.
        self._url_check = self.add_check(self._url_entry, self._check_url_entry)
        self._url_check.enabled = False

        self._url_type_combo_box = self.builder.get_object("urlTypeComboBox")
        self._url_type_label = self.builder.get_object("urlTypeLabel")

        self._updates_radio_button = self.builder.get_object("updatesRadioButton")

        self._verify_iso_button = self.builder.get_object("verifyIsoButton")

        # addon repo objects
        self._repo_entry_box = self.builder.get_object("repoEntryBox")
        self._repo_store = self.builder.get_object("repoStore")
        self._repo_selection = self.builder.get_object("repoSelection")
        self._repo_name_entry = self.builder.get_object("repoNameEntry")
        self._repo_protocol_combo_box = self.builder.get_object("repoProtocolComboBox")
        self._repo_url_entry = self.builder.get_object("repoUrlEntry")
        self._repo_url_type_combo_box = self.builder.get_object("repoUrlTypeComboBox")

        self._repo_proxy_url_entry = self.builder.get_object("repoProxyUrlEntry")
        self._repo_proxy_username_entry = self.builder.get_object("repoProxyUsernameEntry")
        self._repo_proxy_password_entry = self.builder.get_object("repoProxyPasswordEntry")
        self._repo_view = self.builder.get_object("repoTreeView")
        self._repo_remove_button = self.builder.get_object("removeButton")

        # Create a check for duplicate repo ids
        # Call InputCheckHandler directly since this check operates on rows of a TreeModel
        # instead of GtkEntry inputs. Updating the check is handled by the signal handlers
        # connected to repoStore.
        self._duplicate_repo_check = InputCheckHandler.add_check(self, self._repo_store,
                                                                 self._check_duplicate_repos)

        # Create a dictionary for the checks on fields in individual repos
        # These checks will be added and removed as repos are added and removed from repoStore
        self._repo_checks = {}

        # updates option container
        self._updates_box = self.builder.get_object("updatesBox")

        self._proxy_button = self.builder.get_object("proxyButton")
        self._nfs_opts_box = self.builder.get_object("nfsOptsBox")

        # Connect scroll events on the viewport with focus events on the box
        main_viewport = self.builder.get_object("mainViewport")
        main_box = self.builder.get_object("mainBox")
        main_box.set_focus_vadjustment(Gtk.Scrollable.get_vadjustment(main_viewport))

    def initialize(self):
        NormalSpoke.initialize(self)
        self.initialize_start()

        self._grab_objects()
        self._initialize_closest_mirror()

        # I shouldn't have to do this outside GtkBuilder, but it really doesn't
        # want to let me pass in user data.
        # See also: https://bugzilla.gnome.org/show_bug.cgi?id=727919
        self._autodetect_button.connect("toggled", self.on_source_toggled, self._autodetect_box)
        self._cdn_button.connect("toggled", self.on_source_toggled, None)
        self._hmc_button.connect("toggled", self.on_source_toggled, None)
        self._iso_button.connect("toggled", self.on_source_toggled, self._iso_box)
        self._network_button.connect("toggled", self.on_source_toggled, self._network_box)
        self._network_button.connect("toggled", self._update_url_entry_check)

        # Show or hide the updates option based on the configuration
        if conf.payload.updates_repositories:
            really_show(self._updates_box)
        else:
            really_hide(self._updates_box)

        # Register listeners for payload events
        payloadMgr.add_listener(PayloadState.STARTED, self._payload_refresh)
        payloadMgr.add_listener(PayloadState.WAITING_STORAGE, self._probing_storage)
        payloadMgr.add_listener(PayloadState.DOWNLOADING_PKG_METADATA,
                                self._downloading_package_md)
        payloadMgr.add_listener(PayloadState.DOWNLOADING_GROUP_METADATA,
                                self._downloading_group_md)
        payloadMgr.add_listener(PayloadState.FINISHED, self._payload_finished)
        payloadMgr.add_listener(PayloadState.ERROR, self._payload_error)
        payloadMgr.add_listener(PayloadState.PAYLOAD_THREAD_TERMINATED, self._check_ready)

        # Start the thread last so that we are sure initialize_done() is really called only
        # after all initialization has been done.
        threadMgr.add(AnacondaThread(name=constants.THREAD_SOURCE_WATCHER,
                                     target=self._initialize))

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
        hubQ.send_ready("SoftwareSelectionSpoke")
        self._ready = True
        hubQ.send_ready(self.__class__.__name__)

    def _payload_error(self):
        self._error = True
        hubQ.send_message(self.__class__.__name__, payloadMgr.error)

        self._error_msg = _("Failed to set up installation source; "
                            "check the repo url and proxy settings.")

        if self.payload.verbose_errors:
            self._error_msg += _(CLICK_FOR_DETAILS)

        self._ready = True
        hubQ.send_ready(self.__class__.__name__)

    def _check_ready(self):
        # (re)check if the spoke is now ready
        #
        # This is used to clear spoke access in cases where the payload thread
        # reports and error while still running - yet we gate spoke access on the
        # payload thread *not* running.
        # So we listen to a notification from a different thread telling us
        # that the payload thread has terminated and then re-check the condition.
        hubQ.send_ready(self.__class__.__name__)

    def _initialize_closest_mirror(self):
        # If there's no fallback mirror to use, we should just disable that option
        # in the UI.
        if not conf.payload.enable_closest_mirror:
            model = self._protocol_combo_box.get_model()
            itr = model.get_iter_first()
            while itr and model[itr][self._protocol_combo_box.get_id_column()] != PROTOCOL_MIRROR:
                itr = model.iter_next(itr)

            if itr:
                model.remove(itr)

    def _initialize(self):
        threadMgr.wait(constants.THREAD_PAYLOAD)

        # If there is the Subscriptiopn DBus module, make the CDN radio button visible
        if self._subscription_module:
            gtk_call_once(self._cdn_button.set_no_show_all, False)

        # Get the current source.
        source_proxy = self.payload.get_source_proxy()
        source_type = source_proxy.Type

        # If we've previously set up to use a CD/DVD method, the media has
        # already been mounted by payload.setup.  We can't try to mount it
        # again.  So just use what we already know to create the selector.
        # Otherwise, check to see if there's anything available.
        if source_type == SOURCE_TYPE_CDROM:
            self._cdrom = source_proxy.DeviceName
        elif not flags.automatedInstall:
            self._cdrom = find_optical_install_media()

        if self._cdrom:
            self._show_autodetect_box_with_device(self._cdrom)

        if source_type == SOURCE_TYPE_HDD:
            self._current_iso_file = source_proxy.GetIsoPath() or None

            if not self._current_iso_file:
                # Installation from an expanded install tree
                device_spec = source_proxy.Partition
                device_name = self._get_device_name(device_spec)
                self._show_autodetect_box(device_name, device_spec)

        # Enable the SE/HMC option.
        if self.payload.source_type == SOURCE_TYPE_HMC:
            gtk_call_once(self._hmc_button.set_no_show_all, False)

        # Add the mirror manager URL in as the default for HTTP and HTTPS.
        # We'll override this later in the refresh() method, if they've already
        # provided a URL.
        # FIXME

        gtk_call_once(self._reset_repo_store)

        self._ready = True
        # Wait to make sure the other threads are done before sending ready, otherwise
        # the spoke may not be set sensitive by _handleCompleteness in the hub.
        while not self.ready:
            time.sleep(1)
        hubQ.send_ready(self.__class__.__name__)

        # report that the source spoke has been initialized
        self.initialize_done()

    def _show_autodetect_box_with_device(self, device_name):
        device_data = DeviceData.from_structure(
            self._device_tree.GetDeviceData(device_name)
        )
        device_label = device_data.attrs.get("label", "")
        self._show_autodetect_box(device_name, device_label)

    def _show_autodetect_box(self, device_name, device_label):
        fire_gtk_action(self._autodetect_device_label.set_text, _("Device: %s") % device_name)
        fire_gtk_action(self._autodetect_label.set_text, _("Label: %s") % device_label)

        gtk_call_once(self._autodetect_box.set_no_show_all, False)
        gtk_call_once(self._autodetect_button.set_no_show_all, False)

    def refresh(self):
        NormalSpoke.refresh(self)

        # Find all hard drive partitions that could hold an ISO and add each
        # to the partitionStore.  This has to be done here because if the user
        # has done partitioning first, they may have blown away partitions
        # found during _initialize on the partitioning spoke.
        store = self.builder.get_object("partitionStore")
        store.clear()

        added = False
        idx = 0

        active_idx = 0
        active_name = None

        source_proxy = self.payload.get_source_proxy()
        source_type = source_proxy.Type

        if source_type == SOURCE_TYPE_HDD:
            device_spec = source_proxy.Partition
            active_name = self._get_device_name(device_spec)

        for device_name in find_potential_hdiso_sources():
            device_info = get_hdiso_source_info(self._device_tree, device_name)

            # With the label in here, the combo box can appear really long thus pushing
            # the "pick an image" and the "verify" buttons off the screen.
            if device_info["label"] != "":
                device_info["label"] = "\n" + device_info["label"]

            device_desc = get_hdiso_source_description(device_info)
            store.append([device_name, device_desc])

            if device_name == active_name:
                active_idx = idx

            added = True
            idx += 1

        # Again, only display these widgets if an HDISO source was found.
        self._iso_box.set_no_show_all(not added)
        self._iso_box.set_visible(added)
        self._iso_button.set_no_show_all(not added)
        self._iso_button.set_visible(added)

        if added:
            combo = self.builder.get_object("isoPartitionCombo")
            combo.set_active(active_idx)

        # We defaults and if the method tells us something different later, we can change it.
        self._protocol_combo_box.set_active_id(PROTOCOL_MIRROR)
        self._url_type_combo_box.set_active_id(URL_TYPE_BASEURL)

        if source_type == SOURCE_TYPE_CDN:
            self._cdn_button.set_active(True)
        elif source_type == SOURCE_TYPE_URL:
            self._network_button.set_active(True)

            # Get the current configuration.
            repo_configuration = RepoConfigurationData.from_structure(
                source_proxy.RepoConfiguration
            )

            proto = repo_configuration.url
            if proto.startswith("http:"):
                self._protocol_combo_box.set_active_id(PROTOCOL_HTTP)
                length = 7
            elif proto.startswith("https:"):
                self._protocol_combo_box.set_active_id(PROTOCOL_HTTPS)
                length = 8
            elif proto.startswith("ftp:"):
                self._protocol_combo_box.set_active_id(PROTOCOL_FTP)
                length = 6
            else:
                self._protocol_combo_box.set_active_id(PROTOCOL_HTTP)
                length = 0

            self._url_entry.set_text(proto[length:])
            self._update_url_entry_check()
            self._url_type_combo_box.set_active_id(repo_configuration.type)
            self._proxy_url = repo_configuration.proxy
        elif source_type == SOURCE_TYPE_NFS:
            self._network_button.set_active(True)
            self._protocol_combo_box.set_active_id(PROTOCOL_NFS)

            # Get the current URL.
            options, host, path = parse_nfs_url(source_proxy.URL)

            self._url_entry.set_text("{}:{}".format(host, path))
            self._update_url_entry_check()
            self.builder.get_object("nfsOptsEntry").set_text(options or "")
        elif source_type == SOURCE_TYPE_HDD:
            if not self._current_iso_file:
                self._autodetect_button.set_active(True)
            else:
                self._iso_button.set_active(True)
                self._verify_iso_button.set_sensitive(True)

                if self._current_iso_file:
                    self._iso_chooser_button.set_label(os.path.basename(self._current_iso_file))
                else:
                    self._iso_chooser_button.set_label("")
                self._iso_chooser_button.set_use_underline(False)
        elif source_type == SOURCE_TYPE_HMC:
            self._hmc_button.set_active(True)
        elif source_type == SOURCE_TYPE_CDROM:
            # Go with autodetected media if that was provided,
            # otherwise fall back to the closest mirror.
            if not self._autodetect_button.get_no_show_all():
                self._autodetect_button.set_active(True)
            else:
                self._network_button.set_active(True)
        elif source_type == SOURCE_TYPE_CLOSEST_MIRROR:
            self._network_button.set_active(True)
        else:
            ValueError("Unsupported source type: '{}'".format(source_type))

        self._setup_updates()

        # Setup the addon repos
        self._reset_repo_store()

        # Some widgets get enabled/disabled/greyed out depending on
        # how others are set up.  We can use the signal handlers to handle
        # that condition here too. Start at the innermost pieces and work
        # outwards

        # First check the protocol combo in the network box
        self._on_protocol_changed()

        # Then simulate changes for the radio buttons, which may override the
        # sensitivities set for the network box.
        #
        # Whichever radio button is selected should have gotten a signal
        # already, but the ones that are not selected need a signal in order
        # to disable the related box.
        self._on_source_toggled(self._autodetect_button, self._autodetect_box)
        self._on_source_toggled(self._hmc_button, None)
        self._on_source_toggled(self._iso_button, self._iso_box)
        self._on_source_toggled(self._network_button, self._network_box)

        if not self._network_module.Connected:
            self._network_button.set_sensitive(False)
            self._network_box.set_sensitive(False)

            self.clear_info()
            self.set_warning(_("You need to configure the network to use a network "
                               "installation source."))
        else:
            if self._error:
                self.clear_info()
                self.set_error(self._error_msg)

            # network button could be deativated from last visit
            self._network_button.set_sensitive(True)

        # Update the URL entry validation now that we're done messing with sensitivites
        self._update_url_entry_check()

        # If subscription module is available we might need to refresh the label
        # of the CDN/Satellite radio button, so that it properly describes what is providing
        # the repositories available after registration.
        #
        # For registration to Red Hat hosted infrastructure (also called Hosted Candlepin) the
        # global Red Hat CDN efficiently provides quick access to the repositories to customers
        # across the world over the public Internet.
        #
        # If registered to a customer Satellite instance, it is the Satellite instance itself that
        # provides the software repositories.
        #
        # This is an important distinction as Satellite instances are often used in environments
        # not connected to the public Internet, so seeing the installation source being provided
        # by Red Hat CDN which the machine might not be able to reach could be very confusing.
        if self._subscription_module:
            if self.registered_to_satellite:
                self._cdn_button.set_label(C_("GUI|Software Source", "_Satellite"))
            else:
                self._cdn_button.set_label(C_("GUI|Software Source", "Red Hat _CDN"))

    def _setup_updates(self):
        """ Setup the state of the No Updates checkbox.

            If closest mirror is not selected, check it.
            If closest mirror is selected, and "updates" repo is enabled,
            uncheck it.
        """
        self._updates_box.set_sensitive(self._mirror_active())
        active = self._mirror_active() and self.payload.is_repo_enabled("updates")
        self._updates_radio_button.set_active(active)

    def _mirror_active(self):
        return self._protocol_combo_box.get_active_id() == PROTOCOL_MIRROR and \
            self._network_button.get_active()

    def _http_active(self):
        return self._protocol_combo_box.get_active_id() in (
            PROTOCOL_HTTP,
            PROTOCOL_HTTPS,
            PROTOCOL_MIRROR
        )

    def _ftp_active(self):
        return self._protocol_combo_box.get_active_id() == PROTOCOL_FTP

    def _nfs_active(self):
        return self._protocol_combo_box.get_active_id() == PROTOCOL_NFS

    def _get_selected_partition(self):
        """Get a name of the selected partition."""
        store = self.builder.get_object("partitionStore")
        combo = self.builder.get_object("isoPartitionCombo")

        selected = combo.get_active()
        if selected == -1:
            return None
        else:
            return store[selected][0]

    # Input checks

    # This method is shared by the checks on urlEntry and repoUrlEntry
    def _check_url(self, inputcheck, combo):
        # Network is not up, don't check urls.
        if not self._network_module.Connected:
            return InputCheck.CHECK_OK

        # If combo is not set inputcheck holds repo
        is_additional_repo = combo is None
        if is_additional_repo:
            # Input object contains repository name
            repo = self._get_repo_by_id(inputcheck.input_obj)
            if repo.mirrorlist:
                url = repo.mirrorlist
            elif repo.metalink:
                url = repo.metalink
            else:
                url = repo.baseurl
            protocol = urlsplit(url)[0]
            # remove protocol part ("http://", "https://", "nfs://"...)
            url_string = url.strip()[len(protocol + "://"):]
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
            # by _remove_url_prefix. If there's still one there, it's wrong.
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

    def _check_url_entry(self, inputcheck):
        return self._check_url(inputcheck, self._protocol_combo_box)

    def _check_repo_url(self, inputcheck):
        return self._check_url(inputcheck, None)

    # Update the check on urlEntry when the sensitity or selected protocol changes
    def _update_url_entry_check(self, *args):
        self._url_check.enabled = self._url_entry.is_sensitive()
        self._url_check.update_check_status()

        # Force a status update to clear any disabled errors
        self.set_status(self._url_check)

    def _check_duplicate_repos(self, inputcheck):
        repo_names = [r[REPO_OBJ].name for r in inputcheck.input_obj]
        if len(repo_names) != len(frozenset(repo_names)):
            return _("Duplicate repository names.")
        return InputCheck.CHECK_OK

    def _check_repo_name(self, inputcheck):
        # Input object is name of the repository
        repo_name = self._get_repo_by_id(inputcheck.input_obj).name

        if not repo_name:
            return _("Empty repository name")

        if not REPO_NAME_VALID.match(repo_name):
            return _("Invalid repository name")

        cnames = [constants.BASE_REPO_NAME] + constants.DEFAULT_REPOS + \
                 [r for r in self.payload.repos if r not in self.payload.addons]
        if repo_name in cnames:
            return _("Repository name conflicts with internal repository name.")

        return InputCheck.CHECK_OK

    def _check_repo_proxy(self, inputcheck):
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

        return _validate_proxy(proxy_obj.noauth_url, proxy_obj.username, proxy_obj.password)

    # Signal handlers.
    def on_source_toggled(self, button, relatedBox):
        # When a radio button is clicked, this handler gets called for both
        # the newly enabled button as well as the previously enabled (now
        # disabled) button.
        self._on_source_toggled(button, relatedBox)
        self._remove_treeinfo_repositories()

    def _on_source_toggled(self, button, relatedBox):
        enabled = button.get_active()

        if relatedBox:
            relatedBox.set_sensitive(enabled)

        self._setup_updates()

    def on_back_clicked(self, button):
        """If any input validation checks failed, keep the user on the screen.
           Otherwise, do the usual thing."""

        # Check repositories on bad url
        for repo in self._repo_store:
            self._repo_checks[repo[REPO_OBJ].repo_id].url_check.update_check_status()

        failed_check = next(self.failed_checks, None)

        # If the failed check is the duplicate repo check, focus the repo TreeView
        if failed_check == self._duplicate_repo_check:
            self._repo_view.grab_focus()
            return
        # If the failed check is on one of the repo fields, select the repo in the
        # TreeView and focus the field
        elif failed_check in (checks.name_check for checks in self._repo_checks.values()):
            self._repo_selection.select_path(failed_check.data.get_path())
            self._repo_name_entry.grab_focus()
            return
        elif failed_check in (checks.url_check for checks in self._repo_checks.values()):
            self._repo_selection.select_path(failed_check.data.get_path())
            self._repo_url_entry.grab_focus()
            return
        elif failed_check in (checks.proxy_check for checks in self._repo_checks.values()):
            self._repo_selection.select_path(failed_check.data.get_path())
            self._repo_proxy_url_entry.grab_focus()
            return
        # Otherwise let GUISpokeInputCheckHandler figure out what to focus
        elif not self.can_go_back_focus_if_not():
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
        if self._current_iso_file:
            dialog.refresh(currentFile=self._current_iso_file)
        else:
            dialog.refresh()

        with self.main_window.enlightbox(dialog.window):
            iso_file = dialog.run(self._get_selected_partition())

        if iso_file and iso_file.endswith(".iso"):
            self._current_iso_file = iso_file
            button.set_label(os.path.basename(iso_file))
            button.set_use_underline(False)
            self._verify_iso_button.set_sensitive(True)
            self._remove_treeinfo_repositories()

    def on_proxy_clicked(self, button):
        dialog = ProxyDialog(self.data, self._proxy_url)
        with self.main_window.enlightbox(dialog.window):
            dialog.refresh()
            dialog.run()

        if self._proxy_url != dialog.proxy_url:
            self._proxy_change = True
            self._proxy_url = dialog.proxy_url

    def on_verify_iso_clicked(self, button):
        partition = self._get_selected_partition()
        iso_file = self._current_iso_file

        if not partition or not iso_file:
            return

        dialog = MediaCheckDialog(self.data)
        with self.main_window.enlightbox(dialog.window):
            path = payload_utils.get_device_path(partition)

            # FIXME: Use a unique mount point.
            mounts = payload_utils.get_mount_paths(path)
            mountpoint = None
            # We have to check both ISO_DIR and the DRACUT_ISODIR because we
            # still reference both, even though /mnt/install is a symlink to
            # /run/install.  Finding mount points doesn't handle the symlink
            if constants.ISO_DIR not in mounts and constants.DRACUT_ISODIR not in mounts:
                # We're not mounted to either location, so do the mount
                mountpoint = constants.ISO_DIR
                payload_utils.mount_device(partition, mountpoint)
            dialog.run(constants.ISO_DIR + "/" + iso_file)

            if not mounts:
                payload_utils.unmount_device(partition, mountpoint)

    def on_verify_media_clicked(self, button):
        if not self._cdrom:
            return

        dialog = MediaCheckDialog(self.data)
        with self.main_window.enlightbox(dialog.window):
            dialog.run("/dev/" + self._cdrom)

    def on_protocol_changed(self, combo):
        self._on_protocol_changed()
        self._remove_treeinfo_repositories()

    def _on_protocol_changed(self):
        # Only allow the URL entry to be used if we're using an HTTP/FTP
        # method that's not the mirror list, or an NFS method.
        self._url_entry.set_sensitive(self._http_active() or self._ftp_active() or
                                      self._nfs_active())

        # Only allow these widgets to be shown if it makes sense for the
        # the currently selected protocol.
        self._proxy_button.set_sensitive(self._http_active() or self._mirror_active())
        self._nfs_opts_box.set_visible(self._nfs_active())
        self._url_type_combo_box.set_visible(self._http_active())
        self._url_type_label.set_visible(self._http_active())
        self._setup_updates()

        # Any changes to the protocol combo box also need to update the checks.
        # Emitting the urlEntry 'changed' signal will see if the entered URL
        # contains the protocol that's just been selected and strip it if so;
        # _update_url_entry_check() does the other validity checks.
        self._on_urlEtry_changed(self._url_entry)
        self._update_url_entry_check()

    def _update_payload_repos(self):
        """ Change the payload repos to match the new edits

            This will add new repos to the addon repo list, remove
            ones that were removed and update any changes made to
            existing ones.

            :returns: True if any repo was changed, added or removed
            :rtype: bool
        """
        REPO_ATTRS = ("name", "baseurl", "mirrorlist", "metalink", "proxy", "enabled")
        changed = False

        with self._repo_store_lock:
            ui_orig_names = [r[REPO_OBJ].orig_name for r in self._repo_store]

            # Remove repos from payload that were removed in the UI
            for repo_name in [r for r in self.payload.addons if r not in ui_orig_names]:
                repo = self.payload.get_addon_repo(repo_name)
                # TODO: Need an API to do this w/o touching dnf (not add_repo)
                # FIXME: Is this still needed for dnf?
                self.payload.data.repo.dataList().remove(repo)
                changed = True

            addon_repos = [(r[REPO_OBJ], self.payload.get_addon_repo(r[REPO_OBJ].orig_name))
                           for r in self._repo_store]
            for repo, orig_repo in addon_repos:
                if not orig_repo:
                    # TODO: Need an API to do this w/o touching dnf (not add_repo)
                    # FIXME: Is this still needed for dnf?
                    self.payload.data.repo.dataList().append(repo)
                    changed = True
                elif not cmp_obj_attrs(orig_repo, repo, REPO_ATTRS):
                    for attr in REPO_ATTRS:
                        setattr(orig_repo, attr, getattr(repo, attr))
                    changed = True

        return changed

    def _reset_repo_store(self):
        """ Reset the list of repos.

            Populate the list with all the addon repos from payload.addons.

            If the list has no element, clear the repo entry fields.
        """

        log.debug("Clearing checks in source spoke")

        # Remove the repo checks
        for checks in self._repo_checks.values():
            self.remove_check(checks.name_check)
            self.remove_check(checks.url_check)
            self.remove_check(checks.proxy_check)
        self._repo_checks = {}

        with self._repo_store_lock:
            self._repo_store.clear()
            repos = self.payload.addons
            log.debug("Setting up repos: %s", repos)
            for name in repos:
                repo = self.payload.get_addon_repo(name)
                ks_repo = self.data.RepoData.create_copy(repo)
                # Track the original name, user may change .name
                ks_repo.orig_name = name
                # Add addon repository id for identification
                ks_repo.repo_id = next(self._repo_counter)
                self._repo_store.append([self.payload.is_repo_enabled(name),
                                        ks_repo.name,
                                        ks_repo])

        if len(self._repo_store) > 0:
            self._repo_selection.select_path(0)
        else:
            self._clear_repo_info()
            self._repo_entry_box.set_sensitive(False)

    def _unique_repo_name(self, name):
        """ Return a unique variation of the name if it already
            exists in the repo store.

            :param str name: Name to check
            :returns: name or name with _%d appended

            The returned name will be 1 greater than any other entry in the store
            with a _%d at the end of it.
        """
        # Does this name exist in the store? If not, return it.
        if not any(r[REPO_NAME_COL] == name for r in self._repo_store):
            return name

        # If the name already ends with a _\d+ it needs to be stripped.
        match = re.match(r"(.*)_\d+$", name)
        if match:
            name = match.group(1)

        # Find all of the names with _\d+ at the end
        name_re = re.compile(r"("+re.escape(name)+r")_(\d+)")
        matches = (name_re.match(r[REPO_NAME_COL]) for r in self._repo_store)
        matches = [int(m.group(2)) for m in matches if m is not None]

        # Get the highest number, add 1, append to name
        highest_index = max(matches) if matches else 0
        return name + ("_%d" % (highest_index + 1))

    def _get_repo_by_id(self, repo_id):
        """ Return a repository by given name
        """
        for repo in self._repo_store:
            if repo[REPO_OBJ].repo_id == repo_id:
                return repo[REPO_OBJ]
        return None

    def on_repoSelection_changed(self, *args):
        """ Called when the selection changed.

            Update the repo text boxes with the current information
        """
        itr = self._repo_selection.get_selected()[1]
        if not itr:
            return

        repo = self._repo_store[itr][REPO_OBJ]
        self._update_repo_info(repo)

    def on_repoEnable_toggled(self, renderer, path):
        """ Called when the repo Enable checkbox is clicked
        """
        enabled = not self._repo_store[path][REPO_ENABLED_COL]
        self._set_repo_enabled(path, enabled)

    def _set_repo_enabled(self, repo_model_path, enabled):
        self._repo_store[repo_model_path][REPO_ENABLED_COL] = enabled
        self._repo_store[repo_model_path][REPO_OBJ].enabled = enabled

    def _remove_treeinfo_repositories(self):
        """Disable all repositories loaded from the .treeinfo file"""
        removal_repo_list = []

        for repo_item in self._repo_store:
            if repo_item[REPO_OBJ].treeinfo_origin:
                removal_repo_list.append(repo_item.path)

        # Using reverse order to ensure that the previous repositories
        # will not be removed before _remove_repository(), otherwise it
        # will get a wrong index to use after the first loop.
        removal_repo_list.reverse()

        for path in removal_repo_list:
            self._remove_repository(path)

    def _clear_repo_info(self):
        """ Clear the text from the repo entry fields

            and reset the checkbox and combobox.
        """
        self._repo_name_entry.set_text("")

        with blockedHandler(self._repo_url_type_combo_box, self.on_repo_url_type_changed):
            self._repo_url_type_combo_box.set_active_id(URL_TYPE_BASEURL)

        self._repo_url_entry.set_text("")
        self._repo_protocol_combo_box.set_active(0)
        self._repo_proxy_url_entry.set_text("")
        self._repo_proxy_username_entry.set_text("")
        self._repo_proxy_password_entry.set_text("")

    def _update_repo_info(self, repo):
        """ Update the text boxes with data from repo

            :param repo: kickstart repository object
            :type repo: RepoData
        """
        self._repo_name_entry.set_text(repo.name)

        with blockedHandler(self._repo_url_type_combo_box, self.on_repo_url_type_changed):
            if repo.mirrorlist:
                url = repo.mirrorlist
                self._repo_url_type_combo_box.set_active_id(URL_TYPE_MIRRORLIST)
            elif repo.metalink:
                url = repo.metalink
                self._repo_url_type_combo_box.set_active_id(URL_TYPE_METALINK)
            else:
                url = repo.baseurl
                self._repo_url_type_combo_box.set_active_id(URL_TYPE_BASEURL)

        if url:
            for idx, proto in REPO_PROTO.items():
                if url.startswith(proto):
                    self._repo_protocol_combo_box.set_active_id(idx)
                    self._repo_url_entry.set_text(url[len(proto):])
                    break
            else:
                # Unknown protocol, just set the url then
                self._repo_url_entry.set_text(url)
        else:
            self._repo_url_entry.set_text("")

        if not repo.proxy:
            self._repo_proxy_url_entry.set_text("")
            self._repo_proxy_username_entry.set_text("")
            self._repo_proxy_password_entry.set_text("")
        else:
            try:
                proxy = ProxyString(repo.proxy)
                if proxy.username:
                    self._repo_proxy_username_entry.set_text(proxy.username)
                if proxy.password:
                    self._repo_proxy_password_entry.set_text(proxy.password)
                self._repo_proxy_url_entry.set_text(proxy.noauth_url)
            except ProxyStringError as e:
                log.error("Failed to parse proxy for repo %s: %s", repo.name, e)

        self._configure_treeinfo_repo(repo.treeinfo_origin)

    def _configure_treeinfo_repo(self, is_treeinfo_repository):
        self._repo_remove_button.set_sensitive(not is_treeinfo_repository)
        self._repo_entry_box.set_sensitive(not is_treeinfo_repository)

    def _remove_url_prefix(self, editable, combo, handler):
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
        self._on_urlEtry_changed(editable)
        self._remove_treeinfo_repositories()

    def _on_urlEtry_changed(self, editable):
        self._remove_url_prefix(editable, self._protocol_combo_box, self.on_urlEntry_changed)

    def on_updatesRadioButton_toggled(self, button):
        """Toggle the enable state of the updates repo."""
        active = self._updates_radio_button.get_active()
        self.payload.set_updates_enabled(active)

        # Refresh the metadata using the new set of repos
        self._updates_change = True

    def on_addRepo_clicked(self, button):
        """ Add a new repository
        """
        name = self._unique_repo_name("New_Repository")
        repo = self.data.RepoData(name=name)
        repo.ks_repo = True
        repo.orig_name = ""
        # Set addon repo id and increment counter
        repo.repo_id = next(self._repo_counter)

        itr = self._repo_store.append([True, repo.name, repo])
        self._repo_selection.select_iter(itr)
        self._repo_entry_box.set_sensitive(True)

    def on_removeRepo_clicked(self, button):
        """Remove the selected repository"""
        self._remove_repository()

    def _remove_repository(self, repo_model_path=None):
        """Remove repository on repo_model_path or current selection.

        If repo_model_path is not specified then current selection will be used.

        :param repo_model_path: repo_model_path of what we can remove or None
        :type repo_model_path: repo_store repo_model_path
        """
        if repo_model_path is not None:
            itr = self._repo_store[repo_model_path].iter
        else:
            itr = self._repo_selection.get_selected()[1]

        if not itr:
            return

        # Remove the input validation checks for this repo
        repo = self._repo_store[itr][REPO_OBJ]
        # avoid crash when the source is changed because of initialization
        if repo.repo_id in self._repo_checks:
            self.remove_check(self._repo_checks[repo.repo_id].name_check)
            self.remove_check(self._repo_checks[repo.repo_id].url_check)
            self.remove_check(self._repo_checks[repo.repo_id].proxy_check)
            del self._repo_checks[repo.repo_id]

        self._repo_store.remove(itr)
        if len(self._repo_store) == 0:
            self._clear_repo_info()
            self._repo_entry_box.set_sensitive(False)

    def on_resetRepos_clicked(self, button):
        """ Revert to the default list of repositories
        """
        self._reset_repo_store()

    def on_repoNameEntry_changed(self, entry):
        """ repo name changed
        """
        itr = self._repo_selection.get_selected()[1]
        if not itr:
            return
        repo = self._repo_store[itr][REPO_OBJ]
        name = self._repo_name_entry.get_text().strip()

        repo.name = name
        self._repo_store.set_value(itr, REPO_NAME_COL, name)
        # do not update check status if check are not yet set up
        # (populationg/refreshing the spoke)
        if repo.repo_id in self._repo_checks:
            self._repo_checks[repo.repo_id].name_check.update_check_status()

    def on_repoUrl_changed(self, editable, data=None):
        """ proxy url or protocol changed
        """
        itr = self._repo_selection.get_selected()[1]
        if not itr:
            return
        repo = self._repo_store[itr][REPO_OBJ]
        combo_protocol = self._repo_protocol_combo_box.get_active_id()

        # not user editable protocol (e.g. file://) was selected on the old repo and
        # removed when repo line changed
        if not combo_protocol:
            return

        url_prefix = REPO_PROTO[combo_protocol]
        url = self._repo_url_entry.get_text().strip()

        if combo_protocol in (PROTOCOL_HTTP, PROTOCOL_HTTPS):
            url_type = self._repo_url_type_combo_box.get_active_id()
            repo.baseurl = repo.mirrorlist = repo.metalink = ""
            if url_type == URL_TYPE_MIRRORLIST:
                repo.mirrorlist = url_prefix + url
            elif url_type == URL_TYPE_METALINK:
                repo.metalink = url_prefix + url
            else:
                repo.baseurl = url_prefix + url
        else:
            repo.baseurl = url_prefix + url

        # do not update check status if check are not yet set up
        # (populationg/refreshing the spoke)
        if repo.repo_id in self._repo_checks:
            self._repo_checks[repo.repo_id].url_check.update_check_status()

        # Check for and remove a URL prefix that matches the protocol dropdown
        self._remove_url_prefix(editable, self._repo_protocol_combo_box, self.on_repoUrl_changed)

    def on_repo_url_type_changed(self, *args):
        self._repo_url_entry.emit("changed")

    def on_repoProxy_changed(self, *args):
        """ Update the selected repo's proxy settings
        """
        itr = self._repo_selection.get_selected()[1]
        if not itr:
            return
        repo = self._repo_store[itr][REPO_OBJ]

        url = self._repo_proxy_url_entry.get_text().strip()
        username = self._repo_proxy_username_entry.get_text().strip() or None
        password = self._repo_proxy_password_entry.get_text().strip() or None

        # do not update check status if checks are not yet set up
        # (populating/refreshing the spoke)
        if repo.repo_id in self._repo_checks:
            self._repo_checks[repo.repo_id].proxy_check.update_check_status()

        try:
            if username and password:
                proxy = ProxyString(url=url, username=username, password=password)
            else:
                proxy = ProxyString(url=url)
            repo.proxy = proxy.url
        except ProxyStringError as e:
            log.error("Failed to parse proxy - %s:%s@%s: %s", username, password, url, e)

    def on_repoProxyPassword_icon_clicked(self, entry, icon_pos, event):
        """Called by Gtk callback when the icon of a password entry is clicked."""
        set_password_visibility(entry, not entry.get_visibility())

    def on_repoProxyPassword_entry_map(self, entry):
        """Called when a repo proxy password entry widget is going to be displayed.
        - Without this the password visibility toggle icon would not be shown.
        - The password should be hidden every time the entry widget is displayed
          to avoid showing the password in plain text in case the user previously
          displayed the password and then closed the dialog.
        """
        set_password_visibility(entry, False)

    def on_repoStore_row_changed(self, model, path, itr, user_data=None):
        self._duplicate_repo_check.update_check_status()

        repo = model[itr][REPO_OBJ]
        self._update_file_protocol(repo)

    def on_repoStore_row_deleted(self, model, path, user_data=None):
        self._duplicate_repo_check.update_check_status()

    def on_repoStore_row_inserted(self, model, path, itr, user_data=None):
        self._duplicate_repo_check.update_check_status()

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
        self._repo_checks[repo.repo_id] = \
            RepoChecks(InputCheckHandler.add_check(self,
                                                   repo.repo_id,
                                                   self._check_repo_name,
                                                   Gtk.TreeRowReference.new(model, path)),
                       InputCheckHandler.add_check(self,
                                                   repo.repo_id,
                                                   self._check_repo_url,
                                                   Gtk.TreeRowReference.new(model, path)),
                       InputCheckHandler.add_check(self,
                                                   repo.repo_id,
                                                   self._check_repo_proxy,
                                                   Gtk.TreeRowReference.new(model, path)))

    def on_repoProtocolComboBox_changed(self, combobox, user_data=None):
        # Set the url type and proxy fields sensitivity depending on whether NFS was selected
        protocol = self._repo_protocol_combo_box.get_active_id()

        can_have_proxy = protocol in (PROTOCOL_HTTP, PROTOCOL_HTTPS, PROTOCOL_FTP,
                                      PROTOCOL_MIRROR)
        fancy_set_sensitive(self._repo_proxy_url_entry, can_have_proxy)
        fancy_set_sensitive(self._repo_proxy_username_entry, can_have_proxy)
        fancy_set_sensitive(self._repo_proxy_password_entry, can_have_proxy)

        can_have_mirror = protocol in (PROTOCOL_HTTP, PROTOCOL_HTTPS)
        fancy_set_sensitive(self._repo_url_type_combo_box, can_have_mirror)

        can_be_edited = protocol != PROTOCOL_FILE
        fancy_set_sensitive(self._repo_url_entry, can_be_edited)

        # Re-run the proxy check
        itr = self._repo_selection.get_selected()[1]
        if itr:
            repo = self._repo_store[itr][REPO_OBJ]
            # do not update check status if check are not yet set up
            # (populationg/refreshing the spoke)
            if repo.repo_id in self._repo_checks:
                self._repo_checks[repo.repo_id].proxy_check.update_check_status()

        # Run the URL entry handler too as it might be needed
        self._repo_url_entry.emit("changed")
