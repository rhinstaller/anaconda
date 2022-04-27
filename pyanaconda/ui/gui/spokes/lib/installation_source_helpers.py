#
# Copyright (C) 2022  Red Hat, Inc.
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
import os
import re
import signal

from collections import namedtuple

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import glib, constants
from pyanaconda.core.i18n import _, N_
from pyanaconda.core.payload import ProxyString, ProxyStringError
from pyanaconda.core.process_watchers import PidWatcher
from pyanaconda.core.regexes import URL_PARSE
from pyanaconda.payload import utils as payload_utils
from pyanaconda.ui.gui import GUIObject, really_hide
from pyanaconda.ui.gui.helpers import GUIDialogInputCheckHandler
from pyanaconda.ui.gui.utils import find_first_child
from pyanaconda.ui.helpers import InputCheck

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

log = get_module_logger(__name__)

BASEREPO_SETUP_MESSAGE = N_("Setting up installation source...")
CLICK_FOR_DETAILS = N_(' <a href="">Click for details.</a>')

PROTOCOL_HTTP = 'http'
PROTOCOL_HTTPS = 'https'
PROTOCOL_FTP = 'ftp'
PROTOCOL_NFS = 'nfs'
PROTOCOL_FILE = 'file'
PROTOCOL_MIRROR = 'Closest mirror'

REPO_PROTO = {
    PROTOCOL_HTTP:  "http://",
    PROTOCOL_HTTPS: "https://",
    PROTOCOL_FTP:   "ftp://",
    PROTOCOL_NFS:   "nfs://",
    PROTOCOL_FILE:  "file://"
}

RepoChecks = namedtuple("RepoChecks", ["name_check", "url_check", "proxy_check"])


def get_unique_repo_name(existing_names=None):
    """Return a unique repo name.

    The returned name will be 1 greater than any other entry in the store
    with a _%d at the end of it.

    :param [str] existing_names: a list of existing names
    :returns: a unique repo name
    """
    existing_names = existing_names or []
    name = "New_Repository"

    # Does this name exist in the store? If not, return it.
    if name not in existing_names:
        return name

    # If the name already ends with a _\d+ it needs to be stripped.
    match = re.match(r"(.*)_\d+$", name)
    if match:
        name = match.group(1)

    # Find all of the names with _\d+ at the end
    name_re = re.compile(r"(" + re.escape(name) + r")_(\d+)")
    matches = tuple(map(name_re.match, existing_names))
    matches = [int(m.group(2)) for m in matches if m is not None]

    # Get the highest number, add 1, append to name
    highest_index = max(matches) if matches else 0
    return name + ("_%d" % (highest_index + 1))


def validate_proxy(proxy_string, username_set, password_set):
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


class ProxyDialog(GUIObject, GUIDialogInputCheckHandler):
    """The dialog for configuring proxy settings."""

    builderObjects = ["proxyDialog"]
    mainWidgetName = "proxyDialog"
    uiFile = "spokes/lib/installation_source_helpers.glade"

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

        return validate_proxy(proxy_string, self._is_username_set(), self._is_password_set())

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
    """The dialog for checking media."""

    builderObjects = ["mediaCheckDialog"]
    mainWidgetName = "mediaCheckDialog"
    uiFile = "spokes/lib/installation_source_helpers.glade"

    def __init__(self, data):
        super().__init__(data)
        self.progressBar = self.builder.get_object("mediaCheck-progressBar")
        self._pid = None

    def _check_iso_ends_cb(self, pid, status):
        verify_label = self.builder.get_object("verifyLabel")

        if os.WIFSIGNALED(status):
            pass
        elif status == 0:
            verify_label.set_text(_("This media is good to install from."))
        else:
            verify_label.set_text(_("This media is not good to install from."))

        self.progressBar.set_fraction(1.0)
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

        self.progressBar.set_fraction(pct)
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

        self.window.destroy()


class IsoChooser(GUIObject):
    """The dialog for choosing an ISO.

    This class is responsible for popping up the dialog that allows the user to
    choose the ISO image they want to use.  We can get away with this instead of
    selecting a directory because we no longer support split media.

    Two assumptions about the use of this class:
    (1) This class is responsible for mounting and unmounting the partition
        containing the ISO images.
    (2) When you call refresh() with a currentFile argument or when you get a
        result from run(), the file path you use is relative to the root of the
        mounted partition.  In other words, it will not contain the
        "/mnt/isodir/install" part.  This is consistent with the rest of anaconda.
    """

    builderObjects = ["isoChooserDialog", "isoFilter"]
    mainWidgetName = "isoChooserDialog"
    uiFile = "spokes/lib/installation_source_helpers.glade"

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
