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
import copy
from abc import abstractmethod
from contextlib import ExitStack, contextmanager

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.constants import URL_TYPE_BASEURL, REPO_ORIGIN_USER, REPO_ORIGIN_TREEINFO
from pyanaconda.core.i18n import _
from pyanaconda.core.payload import parse_nfs_url, create_nfs_url
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.ui.gui import GUIObject, MainWindow
from pyanaconda.ui.gui.spokes.lib.installation_source_helpers import get_unique_repo_name, \
    ProxyDialog, validate_additional_repositories, get_invalid_repository_message, \
    collect_conflicting_repo_names, generate_repository_description
from pyanaconda.ui.gui.utils import timed_action, blockedHandler as blocked_handler

log = get_module_logger(__name__)

__all__ = ["AdditionalRepositoriesSection"]

# Repo store columns
REPO_COLUMN_ENABLED = 0
REPO_COLUMN_NAME = 1
REPO_COLUMN_DATA = 2
REPO_COLUMN_ACTION = 3

# Editable area for repo configuration
REPO_AREA_EDITABLE = 0
REPO_AREA_UNEDITABLE = 1

# Source action columns.
ACTION_COLUMN_DESCRIPTION = 0
ACTION_COLUMN_VISIBLE = 1

# Source actions - the indexes of source actions
# have to match the indexes of related repo pages.
SOURCE_ACTION_URL = 0
SOURCE_ACTION_NFS = 1
SOURCE_ACTION_OTHER = 2


class RepoConfigurationPage(object):
    """Configuration page of an additional repository."""

    def __init__(self, window, builder):
        """Create a new page.

        :param window: a window with the current spoke
        :param builder: a instance of the Gtk.Builder
        """
        self._window = window
        self._builder = builder
        self._notebook = builder.get_object("repo_config_notebook")
        self._repo_data = RepoConfigurationData()
        self._data_changed = Signal()
        self._monitored_widgets = []

    @property
    @abstractmethod
    def index(self):
        """Index of this page (and the related source action)."""
        return None

    @classmethod
    @abstractmethod
    def match_data(cls, repo_data):
        """Can this page be used to display and edit the specified repository?"""
        return True

    def reset_page(self, repo_data):
        """Refresh the page based on the selected repository.

        :param repo_data: data of the selected repository
        """
        with self._block_changes():
            self._clear_data()

        self._repo_data = repo_data

    def select_page(self, load_data=False):
        """Select this page.

        :param load_data: load the matching repo data
        """
        log.debug("Selecting the '%s' page.", self)

        # Refresh the widgets on this page.
        with self._block_changes():
            self._clear_data()

            if load_data:
                self._load_data()

        # Select this page.
        self._notebook.set_current_page(self.index)

        # Save whatever it is set on the page.
        if not load_data:
            self._on_data_changed()

    @property
    def data_changed(self):
        """The signal that is emitted when the data changes."""
        return self._data_changed

    @timed_action()
    def _on_data_changed(self, *args, **kwargs):
        """Apply the changed data and emit a signal."""
        log.debug("The '%s' repository has changed.", self._repo_data.name)
        self._save_data()
        self._data_changed.emit()

    def _monitor_changes(self, widget, signal_name="changed"):
        """Automatically apply changes of the widget on the data."""
        widget.connect(signal_name, self._on_data_changed)
        self._monitored_widgets.append(widget)

    @contextmanager
    def _block_changes(self):
        """Don't apply changes of the monitored widgets in the current context."""
        with ExitStack() as stack:
            for widget in self._monitored_widgets:
                stack.enter_context(blocked_handler(widget, self._on_data_changed))

            yield

    @abstractmethod
    def _load_data(self):
        """Refresh the data on the page."""
        pass

    def _save_data(self):
        """Load the data from the page."""
        pass

    @abstractmethod
    def _clear_data(self):
        """Clear the data on the page."""
        pass

    def __str__(self):
        """Get the name of the page."""
        return self.__class__.__name__


class URLPage(RepoConfigurationPage):
    """Configuration page of a URL repository."""

    def __init__(self, *args, **kwargs):
        """Create a new page."""
        super().__init__(*args, **kwargs)
        self._proxy = ""

        self._url_entry = self._builder.get_object("repo_url_entry")
        self._type_combo_box = self._builder.get_object("repo_url_type_combo_box")
        self._proxy_button = self._builder.get_object("repo_url_proxy_button")

        # Handle additional logic in widgets.
        self._url_entry.connect("changed", self._on_url_entry_changed)
        self._proxy_button.connect("clicked", self._on_proxy_button_clicked)

        # Automatically apply changes in the widgets.
        self._monitor_changes(self._url_entry)
        self._monitor_changes(self._type_combo_box)

    @property
    def index(self):
        """Index of this page (and the related source action)."""
        return SOURCE_ACTION_URL

    @classmethod
    def match_data(cls, repo_data):
        """Can this page be used to display and edit the specified repository?"""
        # System and treeinfo repositories shouldn't be editable.
        if repo_data.origin != REPO_ORIGIN_USER:
            return False

        # Use this page for new repositories.
        if not repo_data.url:
            return True

        # Match repositories with http, https and ftp protocols.
        return any(map(repo_data.url.startswith, ("http:", "https:", "ftp:")))

    def _load_data(self):
        """Refresh the data on the page."""
        self._url_entry.set_text(self._repo_data.url)
        self._type_combo_box.set_active_id(self._repo_data.type)
        self._proxy = self._repo_data.proxy

    def _save_data(self):
        """Load the data from the page."""
        self._repo_data.url = self._url_entry.get_text()
        self._repo_data.type = self._type_combo_box.get_active_id()
        self._repo_data.proxy = self._proxy

    def _clear_data(self):
        """Clear the data on the page."""
        self._url_entry.set_text("")
        self._type_combo_box.set_active_id(URL_TYPE_BASEURL)
        self._proxy = ""

    def _on_url_entry_changed(self, *args, **kwargs):
        """The URL has changed."""
        # Reset the sensitivity of the combo box.
        self._type_combo_box.set_sensitive(True)
        url = self._url_entry.get_text()

        if not url.startswith("ftp:"):
            return

        #  Only BASEURL is supported for FTP repositories.
        self._type_combo_box.set_active_id(URL_TYPE_BASEURL)
        self._type_combo_box.set_sensitive(False)

    def _on_proxy_button_clicked(self, *args, **kwargs):
        """The proxy reconfiguration has been requested."""
        dialog = ProxyDialog(proxy_url=self._proxy, data=None)
        main_window = MainWindow.get()

        with main_window.enlightbox(dialog.window):
            dialog.refresh()
            dialog.run()

        self._proxy = dialog.proxy_url
        self._on_data_changed()


class NFSPage(RepoConfigurationPage):
    """Configuration page of an NFS repository."""

    def __init__(self, *args, **kwargs):
        """Create a new page."""
        super().__init__(*args, **kwargs)
        self._server_entry = self._builder.get_object("repo_nfs_server_entry")
        self._path_entry = self._builder.get_object("repo_nfs_path_entry")
        self._opts_entry = self._builder.get_object("repo_nfs_options_entry")

        # Automatically apply changes in these widgets.
        self._monitor_changes(self._server_entry)
        self._monitor_changes(self._path_entry)
        self._monitor_changes(self._opts_entry)

    @property
    def index(self):
        """Index of this page (and the related source action)."""
        return SOURCE_ACTION_NFS

    @classmethod
    def match_data(cls, repo_data):
        """Can this page be used to display and edit the specified repository?"""
        # System and treeinfo repositories shouldn't be editable.
        if repo_data.origin != REPO_ORIGIN_USER:
            return False

        # Match only repositories with the nfs protocol.
        return repo_data.url.startswith("nfs:")

    def _load_data(self):
        """Refresh the data on the page."""
        options, host, path = parse_nfs_url(self._repo_data.url)
        self._server_entry.set_text(host)
        self._path_entry.set_text(path)
        self._opts_entry.set_text(options)

    def _save_data(self):
        """Load the data from the page."""
        self._repo_data.url = self._get_nfs_url()
        self._repo_data.type = URL_TYPE_BASEURL
        self._repo_data.proxy = ""

    def _clear_data(self):
        """Clear the data on the page."""
        self._server_entry.set_text("")
        self._path_entry.set_text("")
        self._opts_entry.set_text("")

    def _get_nfs_url(self):
        """Generate the URL of the NFS source."""
        host = self._server_entry.get_text()
        path = self._path_entry.get_text()
        options = self._opts_entry.get_text()
        return create_nfs_url(host, path, options) or "nfs:"


class OtherPage(RepoConfigurationPage):
    """Configuration page of another repository."""

    def __init__(self, *args, **kwargs):
        """Create a new page."""
        super().__init__(*args, **kwargs)
        self._url_entry = self._builder.get_object("repo_other_url_entry")

    @property
    def index(self):
        """Index of a source action."""
        return SOURCE_ACTION_OTHER

    @classmethod
    def match_data(cls, repo_data):
        """Can this page be used to display the specified repository?"""
        return True

    def _load_data(self):
        """Refresh the data on the page."""
        self._url_entry.set_text(self._repo_data.url)

    def _clear_data(self):
        """Clear the data on the page."""
        self._url_entry.set_text("")


class AdditionalRepositoriesSection(GUIObject):
    """Representation of a widget for additional repositories."""

    builderObjects = [
        "repo_store",
        "repo_source_action_store",
        "repo_source_action_filter",
        "repo_label_size_group",
        "additional_repos_expander",
    ]
    uiFile = "spokes/lib/additional_repositories.glade"

    def __init__(self, data, payload, window):
        """Create the section."""
        super().__init__(data)
        self.payload = payload
        self._window = window
        self._original_repositories = []

        # Grab the UI elements.
        self._repo_store = self.builder.get_object("repo_store")
        self._repo_selection = self.builder.get_object("repo_selection")
        self._repo_area_notebook = self.builder.get_object("repo_area_notebook")
        self._repo_name_entry = self.builder.get_object("repo_name_entry")
        self._source_combo_box = self.builder.get_object("repo_source_combo_box")
        self._label_size_group = self.builder.get_object("repo_label_size_group")
        self._remove_button = self.builder.get_object("remove_button")

        # Define the repo pages and monitor changes.
        self._repo_pages = [
            URLPage(self.window, self.builder),
            NFSPage(self.window, self.builder),
            OtherPage(self.window, self.builder),
        ]

        for page in self._repo_pages:
            page.data_changed.connect(self.validate)

        # Filter source actions.
        self._repo_source_action_filter = self.builder.get_object("repo_source_action_filter")
        self._repo_source_action_filter.set_visible_column(ACTION_COLUMN_VISIBLE)

    @property
    def widget(self):
        """The top-level widget that can be included into a spoke."""
        return self.builder.get_object("additional_repos_expander")

    @property
    def window(self):
        """A spoke window that contains this widget."""
        return self._window

    @property
    def _repositories(self):
        """List of configured additional repositories.

        :return [RepoConfigurationData]: a list of repositories
        """
        return [row[REPO_COLUMN_DATA] for row in self._repo_store]

    def clear(self):
        """Clear the repo store."""
        self._repo_store.clear()

    def refresh(self):
        """Refresh the section."""
        self._refresh_size_group(self._label_size_group)
        self._populate_repo_store()

    @staticmethod
    def _refresh_size_group(size_group):
        """Force the recalculation of the size group.

        The size group should handle this automatically,
        but for some reason, it doesn't work.
        """
        widgets = size_group.get_widgets()
        max_width = max(w.get_allocation().width for w in widgets)

        for widget in widgets:
            widget.set_size_request(max_width, -1)

    def _populate_repo_store(self):
        """Populate the list of additional repositories."""
        log.debug("Populating the repo store")

        # Clear the repo store.
        self._repo_store.clear()

        # Hide the editable area by default.
        self._set_repo_area_editable(False)

        # Get the list of additional repositories.
        repositories = self.payload.get_repo_configurations()
        self._original_repositories = copy.deepcopy(repositories)

        if not repositories:
            return

        # Add the repositories to the repo store.
        for repo_data in repositories:
            self._add_repo_row(repo_data)

        # Select the first one.
        self._repo_selection.select_path(0)

        # Trigger the validation.
        self.validate()

    def _add_repo_row(self, repo_data: RepoConfigurationData):
        """Add a row with an additional repository to the repo store."""
        log.debug(
            "Add the '%s' repository:\n%s",
            repo_data.name, generate_repository_description(repo_data)
        )
        return self._repo_store.append([
            repo_data.enabled,
            repo_data.name,
            repo_data,
            self._match_source_action(repo_data),
        ])

    def _match_source_action(self, repo_data):
        """Find the best source action for the specified repository."""
        for page in self._repo_pages:
            if page.match_data(repo_data):
                return page.index

        return SOURCE_ACTION_OTHER

    def on_repos_reset_clicked(self, button):
        """Revert to the default list of additional repositories."""
        self._populate_repo_store()

    def on_repo_store_changed(self, *args, **kwargs):
        """A row in the repo store has been inserted or deleted."""
        log.debug("The repo store has changed.")
        self._set_repo_area_editable(self._get_selected_repo_row())

    def _set_repo_area_editable(self, editable):
        """Hide the editable area for the repo configuration if necessary."""
        index = REPO_AREA_EDITABLE if editable else REPO_AREA_UNEDITABLE
        self._repo_area_notebook.set_current_page(index)

    def on_repo_add_clicked(self, button):
        """Add a new additional repository."""
        # Generate a unique repo name.
        existing_names = [r.name for r in self._repositories]
        generated_name = get_unique_repo_name(existing_names)

        # Create a new repo data.
        repo_data = RepoConfigurationData()
        repo_data.name = generated_name

        # Add the repository to the repo store.
        itr = self._add_repo_row(repo_data)

        # Select this repository.
        self._repo_selection.select_iter(itr)

        # The new repository is obviously not configured,
        # so don't validate it yet!

    def on_repo_enable_toggled(self, renderer, path):
        """Enable/disable the selected additional repository."""
        repo_row = self._repo_store[path]
        repo_data = repo_row[REPO_COLUMN_DATA]

        repo_data.enabled = not repo_data.enabled
        repo_row[REPO_COLUMN_ENABLED] = repo_data.enabled

        log.debug("The '%s' repo enabled has changed: %s", repo_data.name, repo_data.enabled)
        self.validate()

    def on_repo_name_entry_changed(self, entry):
        """The name of the additional repository has changed."""
        repo_row = self._get_selected_repo_row()

        if not repo_row:
            return

        repo_data = repo_row[REPO_COLUMN_DATA]
        previous_name = repo_data.name

        repo_data.name = self._repo_name_entry.get_text().strip()
        repo_row[REPO_COLUMN_NAME] = repo_data.name

        log.debug("The '%s' repo name has changed: %s", previous_name, repo_data.name)
        self.validate()

    def _get_selected_repo_row(self):
        """Return a selected repo row or None."""
        itr = self._repo_selection.get_selected()[1]

        if not itr:
            return None

        return self._repo_store[itr]

    def on_repo_remove_clicked(self, button):
        """Remove the selected additional repository"""
        itr = self._repo_selection.get_selected()[1]

        if not itr:
            return

        self._repo_store.remove(itr)
        self.validate()

    def remove_treeinfo_repositories(self):
        """Remove repositories loaded from the .treeinfo file."""
        if not len(self._repo_store) > 0:
            return

        log.debug("Removing treeinfo repositories...")
        itr = self._repo_store.get_iter_first()

        while itr:
            repo_row = self._repo_store[itr]
            repo_data = repo_row[REPO_COLUMN_DATA]

            # Remove a treeinfo repository. The iterator will be moved
            # to the next item or invalidated. Set it to None in that
            # case to stop the iteration.
            if repo_data.origin == REPO_ORIGIN_TREEINFO:
                log.debug("Removing the '%s' repository.", repo_data.name)
                valid_itr = self._repo_store.remove(itr)
                itr = itr if valid_itr else None
                continue

            itr = self._repo_store.iter_next(itr)

        self.validate()

    def on_repo_selection_changed(self, *args):
        """Show data of the selected additional repository."""
        # Get the selected row and relevant data.
        repo_row = self._get_selected_repo_row()
        self._set_repo_area_editable(repo_row)

        if not repo_row:
            return

        repo_data = repo_row[REPO_COLUMN_DATA]
        log.debug("The repo selection has changed: %s", repo_data.name)

        # Show the editable area and reset its widgets.
        self._repo_name_entry.set_sensitive(True)
        self._source_combo_box.set_sensitive(True)
        self._remove_button.set_sensitive(True)

        for page in self._repo_pages:
            page.reset_page(repo_data)

        # Set the repo name without triggering the validation.
        with blocked_handler(self._repo_name_entry, self.on_repo_name_entry_changed):
            self._repo_name_entry.set_text(repo_data.name)

        # Set up a repo page and a source action.
        source_action = repo_row[REPO_COLUMN_ACTION]
        self._select_source_action(source_action)
        self._select_repo_page(source_action, load_data=True)

        # Don't allow to rename and remove treeinfo repositories.
        is_sensitive = repo_data.origin != REPO_ORIGIN_TREEINFO
        self._repo_name_entry.set_sensitive(is_sensitive)
        self._remove_button.set_sensitive(is_sensitive)

    def _select_repo_page(self, index, load_data=False):
        """Select a repo page specified by the index."""
        page = self._repo_pages[index]
        page.select_page(load_data=load_data)

    def _select_source_action(self, index):
        """Select a source action specified by the index."""
        # Make sure that the 'OTHER' action is visible only
        # if it is a default action of the selected repo.
        is_visible = index == SOURCE_ACTION_OTHER
        actions = self._repo_source_action_filter.get_model()
        actions[SOURCE_ACTION_OTHER][ACTION_COLUMN_VISIBLE] = is_visible

        # Re-filter the combo box options.
        self._repo_source_action_filter.refilter()

        # Set up the source action.
        self._source_combo_box.set_active(index)

        # Don't allow to change the 'OTHER' source action.
        is_sensitive = index != SOURCE_ACTION_OTHER
        self._source_combo_box.set_sensitive(is_sensitive)

    def on_repo_source_action_changed(self, *args):
        """Show a repo page based on the selected source action."""
        repo_row = self._get_selected_repo_row()
        source_action = self._source_combo_box.get_active()

        if not repo_row or source_action < 0:
            return

        log.debug("The source action has changed: %s", source_action)
        repo_row[REPO_COLUMN_ACTION] = source_action

        self._select_repo_page(source_action)

    def validate(self):
        """Validate the additional repositories.

        :return: True if the repositories are valid, otherwise False
        """
        self.clear_info()

        # Validate the repo configuration data.
        conflicting_names = collect_conflicting_repo_names(self.payload)
        report = validate_additional_repositories(self._repositories, conflicting_names)

        # Validate the expected repo configuration data.
        self._validate_expected_protocols(report)

        if report.error_messages:
            self.set_warning(report.error_messages[0])

        return report.is_valid()

    def _validate_expected_protocols(self, report):
        """Validate expected protocols of additional repositories.

        Make sure that the repository matches the selected source action.
        Otherwise, it means that the repository doesn't use a protocol
        that is valid for that type of source action.
        """
        for row in self._repo_store:
            repo_data = row[REPO_COLUMN_DATA]
            source_action = row[REPO_COLUMN_ACTION]

            if source_action != self._match_source_action(repo_data):
                error_message = get_invalid_repository_message(
                    repo_data.name, _("Invalid protocol")
                )
                report.error_messages.append(error_message)

    def apply(self):
        """Apply the additional repositories.

        :return: True if the repositories has changed, otherwise False
        """
        old_repositories = self._original_repositories
        new_repositories = self._repositories

        if RepoConfigurationData.to_structure_list(old_repositories) == \
                RepoConfigurationData.to_structure_list(new_repositories):
            log.debug("The additional repositories haven't changed.")
            return False

        log.debug(
            "The additional repositories has changed:\n%s",
            "\n".join(map(generate_repository_description, new_repositories))
        )

        self.payload.set_repo_configurations(new_repositories)
        return True
