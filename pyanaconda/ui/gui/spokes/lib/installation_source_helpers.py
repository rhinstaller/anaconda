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
from functools import partial

from dasbus.structure import get_fields

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import glib, constants
from pyanaconda.core.constants import REPO_ORIGIN_USER
from pyanaconda.core.i18n import _, N_, C_
from pyanaconda.core.path import join_paths
from pyanaconda.core.payload import ProxyString, ProxyStringError, parse_nfs_url
from pyanaconda.core.process_watchers import PidWatcher
from pyanaconda.core.regexes import URL_PARSE, REPO_NAME_VALID, HOSTNAME_PATTERN_WITHOUT_ANCHORS
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.common.structures.validation import ValidationReport
from pyanaconda.payload import utils as payload_utils
from pyanaconda.ui.gui import GUIObject, really_hide
from pyanaconda.ui.gui.helpers import GUIDialogInputCheckHandler
from pyanaconda.ui.gui.utils import find_first_child, set_password_visibility
from pyanaconda.ui.helpers import InputCheck

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

log = get_module_logger(__name__)

CLICK_FOR_DETAILS = N_(' <a href="">Click for details.</a>')

PROTOCOL_HTTP = 'http'
PROTOCOL_HTTPS = 'https'
PROTOCOL_FTP = 'ftp'
PROTOCOL_NFS = 'nfs'
PROTOCOL_MIRROR = 'Closest mirror'


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


def generate_repository_description(repo_data):
    """Generate a description of a repo configuration data.

    :param RepoConfigurationData repo_data: a repo configuration data
    :return str: a string with the description
    """
    fields = get_fields(RepoConfigurationData)
    attributes = []

    for name, field in fields.items():
        value = field.get_data(repo_data)
        attribute = "{} = {}".format(
            name, repr(value)
        )
        attributes.append(attribute)

    return "\n".join(["{"] + attributes + ["}"])


def validate_additional_repositories(additional_repositories, conflicting_names=None):
    """Validate the configured additional repositories.

    :param [RepoConfigurationData] additional_repositories: a list of repositories
    :param conflicting_names: a list of conflicting repo names or None
    :return ValidationReport: a validation report
    """
    log.debug("Validating additional repositories...")
    report = ValidationReport()

    if not additional_repositories:
        log.debug("Nothing to validate.")
        return report

    # Collect names of validated additional repositories.
    occupied_names = [r.name for r in additional_repositories]
    log.debug("Occupied names: %s", ", ".join(occupied_names))

    # Collect names of possibly conflicting repositories.
    conflicting_names = conflicting_names or []
    log.debug("Conflicting names: %s", ", ".join(conflicting_names))

    # Check additional repositories.
    for repo_data in additional_repositories:
        log.debug("Validating the '%s' repository: %s", repo_data.name, repo_data)

        # Define a an error handler.
        handle_error = partial(_report_invalid_repository, report, repo_data)

        # Check the repo name.
        handle_error(validate_repo_name(
            repo_name=repo_data.name,
            conflicting_names=conflicting_names,
            occupied_names=occupied_names
        ))

        # Don't validate the configuration of system and treeinfo repositories.
        if repo_data.origin != REPO_ORIGIN_USER:
            continue

        # Don't validate the configuration of disabled repositories.
        if not repo_data.enabled:
            continue

        # Check the URL specification.
        handle_error(validate_repo_url(repo_data.url))

        # Check the proxy configuration.
        handle_error(validate_proxy(repo_data.proxy))

    log.debug("The validation has been completed: %s", report)
    return report


def collect_conflicting_repo_names(payload):
    """Collect repo names that could conflict with additional repositories."""
    current_repositories = payload.get_repo_configurations()
    allowed_names = [r.name for r in current_repositories]
    forbidden_names = set(payload.proxy.GetAvailableRepositories())
    return list(forbidden_names - set(allowed_names))


def _report_invalid_repository(report, repository, error_message):
    """Report an invalid repository."""
    if not error_message:
        return

    full_message = get_invalid_repository_message(repository.name, error_message)
    report.error_messages.append(full_message)
    log.error(full_message)


def get_invalid_repository_message(repo_name, error_message):
    """Get a full error message with the repository name."""
    return _("The '{}' repository is invalid: {}").format(
        repo_name, error_message
    )


def validate_repo_name(repo_name, conflicting_names=None, occupied_names=None):
    """Validate the given repo name.

    :param str repo_name: a repo name to validate
    :param [str] conflicting_names: a list of conflicting names
    :param [str] occupied_names: a list of occupied names
    :return: an error message or None
    """
    conflicting_names = conflicting_names or []
    occupied_names = occupied_names or []

    # Extend the conflicting names.
    conflicting_names.append(
        constants.BASE_REPO_NAME
    )
    conflicting_names.extend(
        constants.DEFAULT_REPOS
    )

    # Check the repo name.
    if not repo_name:
        return _("Empty repository name")

    if not REPO_NAME_VALID.match(repo_name):
        return _("Invalid repository name")

    if occupied_names.count(repo_name) > 1:
        return _("Duplicate repository names")

    if repo_name in conflicting_names:
        return _("Repository name conflicts with internal repository name")

    return InputCheck.CHECK_OK


def validate_repo_url(url):
    """Validate the given repo URL.

    :param: an URL to validate
    :return: an error message or None
    """
    # There is nothing to validate.
    if not url:
        return _("Empty URL")

    # Don't validate file:.
    if url.startswith("file:"):
        return InputCheck.CHECK_OK

    # Don't validate hd:.
    if url.startswith("hd:"):
        return InputCheck.CHECK_OK

    # Validate an NFS source.
    if url.startswith("nfs:"):
        _options, host, path = parse_nfs_url(url)

        if not host:
            return _("Empty server")

        if not re.match('^' + HOSTNAME_PATTERN_WITHOUT_ANCHORS + '$', host):
            return _("Invalid server")

        if not path:
            return _("Empty path")

        return InputCheck.CHECK_OK

    # Validate an URL source.
    if any(url.startswith(p) for p in ["http:", "https:", "ftp:"]):
        if not re.match(URL_PARSE, url):
            return _("Invalid URL")

        return InputCheck.CHECK_OK

    # The protocol seems to be unsupported.
    return _("Invalid protocol")


def validate_proxy(proxy_string, authentication=True):
    """Validate a proxy string and return an input code usable by InputCheck

    :param str proxy_string: the proxy URL string
    :param bool authentication: can the URL contain authentication data?
    :return: an error message or None
    """
    # Nothing to check.
    if not proxy_string:
        return InputCheck.CHECK_OK

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

    # Check if authentication data can be specified in the URL.
    if not authentication and (proxy_match.group("username") or proxy_match.group("password")):
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

        authentication = self._is_username_set() or self._is_password_set()
        return validate_proxy(proxy_string, authentication=not authentication)

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
    """The dialog for checking media."""

    builderObjects = ["mediaCheckDialog"]
    mainWidgetName = "mediaCheckDialog"
    uiFile = "spokes/lib/installation_source_helpers.glade"

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
        pct = min(pct, 1.0)

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

    def __init__(self, data, current_file=None):
        super().__init__(data)
        self._current_file = current_file or ""
        self._chooser = self.builder.get_object("isoChooserDialog")
        self._chooser.connect("current-folder-changed", self.on_folder_changed)
        self._chooser.set_filename(join_paths(constants.ISO_DIR, self._current_file))

        # Hide the places sidebar, since it makes no sense in this context
        # This is discouraged, but the alternative suggested is to reinvent the
        # wheel. See also https://bugzilla.gnome.org/show_bug.cgi?id=751730
        places_sidebar = find_first_child(self._chooser,
                                          lambda x: isinstance(x, Gtk.PlacesSidebar))
        if places_sidebar:
            really_hide(places_sidebar)

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
