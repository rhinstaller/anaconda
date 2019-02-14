# iSCSI configuration dialog
#
# Copyright (C) 2013  Red Hat, Inc.
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

from collections import namedtuple

from pyanaconda.modules.common.errors.configuration import StorageDiscoveryError
from pyanaconda.modules.common.structures.iscsi import Credentials, Target
from pyanaconda.modules.storage.iscsi.discover import ISCSIDiscoverTask, ISCSILoginTask
from pyanaconda.ui.gui import GUIObject
from pyanaconda.ui.gui.utils import escape_markup
from pyanaconda.storage.utils import try_populate_devicetree
from pyanaconda.core.i18n import _
from pyanaconda.core.regexes import ISCSI_IQN_NAME_REGEX, ISCSI_EUI_NAME_REGEX
from pyanaconda.network import check_ip_address

from blivet.iscsi import iscsi

__all__ = ["ISCSIDialog"]

STYLE_NONE = 0
STYLE_CHAP = 1
STYLE_REVERSE_CHAP = 2

NodeStoreRow = namedtuple("NodeStoreRow", ["selected", "notLoggedIn", "name", "iface", "portal"])


class ISCSIDialog(GUIObject):
    """
       .. inheritance-diagram:: ISCSIDialog
          :parts: 3
    """
    builderObjects = ["iscsiDialog", "nodeStore", "nodeStoreFiltered"]
    mainWidgetName = "iscsiDialog"
    uiFile = "spokes/advstorage/iscsi.glade"

    def __init__(self, data, storage):
        super().__init__(data)
        self._storage = storage
        self._discovered_nodes = []
        self._update_devicetree = False

        self._authTypeCombo = self.builder.get_object("authTypeCombo")
        self._authNotebook = self.builder.get_object("authNotebook")
        self._iscsiNotebook = self.builder.get_object("iscsiNotebook")
        self._loginButton = self.builder.get_object("loginButton")
        self._retryLoginButton = self.builder.get_object("retryLoginButton")
        self._loginAuthTypeCombo = self.builder.get_object("loginAuthTypeCombo")
        self._loginAuthNotebook = self.builder.get_object("loginAuthNotebook")
        self._loginGrid = self.builder.get_object("loginGrid")
        self._loginConditionNotebook = self.builder.get_object("loginConditionNotebook")
        self._configureGrid = self.builder.get_object("configureGrid")
        self._conditionNotebook = self.builder.get_object("conditionNotebook")
        self._bindCheckbox = self.builder.get_object("bindCheckbutton")
        self._startButton = self.builder.get_object("startButton")
        self._okButton = self.builder.get_object("okButton")
        self._cancelButton = self.builder.get_object("cancelButton")
        self._retryButton = self.builder.get_object("retryButton")
        self._initiatorEntry = self.builder.get_object("initiatorEntry")
        self._store = self.builder.get_object("nodeStore")
        self._storeFilter = self.builder.get_object("nodeStoreFiltered")
        self._discoverySpinner = self.builder.get_object("waitSpinner")
        self._discoveryErrorLabel = self.builder.get_object("discoveryErrorLabel")
        self._discoveredLabel = self.builder.get_object("discoveredLabel")
        self._loginSpinner = self.builder.get_object("loginSpinner")
        self._loginErrorLabel = self.builder.get_object("loginErrorLabel")

    def refresh(self):
        self._bindCheckbox.set_active(bool(iscsi.ifaces))
        self._bindCheckbox.set_sensitive(iscsi.mode == "none")
        self._authTypeCombo.set_active(0)
        self._startButton.set_sensitive(True)
        self._loginAuthTypeCombo.set_active(0)
        self._storeFilter.set_visible_column(1)
        self._initiatorEntry.set_text(iscsi.initiator)
        self._initiatorEntry.set_sensitive(not iscsi.initiator_set)

    def run(self):
        rc = self.window.run()
        self.window.destroy()

        if self._update_devicetree:
            try_populate_devicetree(self._storage.devicetree)

        return rc

    ##
    ## DISCOVERY
    ##

    def on_auth_type_changed(self, widget, *args):
        """Validate the credentials.

        When we change the notebook, we also need to reverify the credentials
        in order to set the Start button sensitivity.
        """
        self._authNotebook.set_current_page(widget.get_active())
        self.on_discover_field_changed()

    def on_discover_field_changed(self, *args):
        """Validate the discover fields.

        When the initiator name, ip address, and any auth fields are filled in
        valid, only then should the Start button be made sensitive.
        """
        style = self._authNotebook.get_current_page()
        target = self._get_target()
        credentials = self._get_discover_credentials(style)

        self._startButton.set_sensitive(
            self._is_target_valid(target)
            and self._are_credentials_valid(style, credentials)
        )

    def on_start_clicked(self, *args):
        """Start the discovery task."""
        # First update widgets.
        self._startButton.hide()
        self._cancelButton.set_sensitive(False)
        self._okButton.set_sensitive(False)
        self._conditionNotebook.set_current_page(1)
        self._set_configure_sensitive(False)
        self._initiatorEntry.set_sensitive(False)

        # Get the node discovery credentials.
        style = self._authNotebook.get_current_page()
        target = self._get_target()
        credentials = self._get_discover_credentials(style)

        self._discoveredLabel.set_markup(_(
            "The following nodes were discovered using the iSCSI initiator "
            "<b>%(initiatorName)s</b> using the target IP address "
            "<b>%(targetAddress)s</b>.  Please select which nodes you "
            "wish to log into:") %
            {
                "initiatorName": escape_markup(target.initiator),
                "targetAddress": escape_markup(target.ip_address)
            }
        )

        # Get the discovery task.
        task = ISCSIDiscoverTask(target, credentials)

        # Start the discovery.
        task.stopped_signal.connect(lambda: self.process_discovery_result(task))
        task.start()

        self._discoverySpinner.start()

    def process_discovery_result(self, task):
        """Process the result of the task.

        :param task: a task
        """
        # Stop the spinner.
        self._discoverySpinner.stop()
        self._cancelButton.set_sensitive(True)

        try:
            # Finish the task
            nodes = task.finish()
        except StorageDiscoveryError as e:
            # Discovery has failed, show the error.
            self._set_configure_sensitive(True)
            self._discoveryErrorLabel.set_text(str(e))
            self._conditionNotebook.set_current_page(2)
        else:
            # Discovery succeeded.
            # Populate the node store.
            self._discovered_nodes = nodes

            for node in nodes:
                interface = iscsi.ifaces.get(node.iface, node.iface)
                portal = "%s:%s" % (node.address, node.port)
                self._store.append([False, True, node.name, interface, portal])

            # We should select the first node by default.
            self._store[0][0] = True

            # Kick the user on over to that subscreen.
            self._iscsiNotebook.set_current_page(1)

            # If some form of login credentials were used for discovery,
            # default to using the same for login.
            if self._authTypeCombo.get_active() != 0:
                self._loginAuthTypeCombo.set_active(3)

    def _get_text(self, name):
        """Get the content of the text entry.

        :param name: a name of the widget
        :return: a content of the widget
        """
        return self.builder.get_object(name).get_text()

    def _get_target(self):
        """Get the target for the discovery

        :return: an instance of Target
        """
        target = Target()
        target.initiator = self._get_text("initiatorEntry")
        target.ip_address = self._get_text("targetEntry")
        target.bind = self._bindCheckbox.get_active()
        return target

    def _is_target_valid(self, target):
        """Is the target valid?

        iSCSI Naming Standards: RFC 3720 and RFC 3721
        Name should either match IQN format or EUI format.

        :param target: an instance of Target
        :return: True if valid, otherwise False
        """
        if not check_ip_address(target.ip_address):
            return False

        return bool(
            ISCSI_IQN_NAME_REGEX.match(target.initiator.strip())
            or ISCSI_EUI_NAME_REGEX.match(target.initiator.strip())
        )

    def _get_discover_credentials(self, style):
        """Get credentials for the discovery.

        The current page from the authNotebook defines how to grab credentials
        out of the UI. This works as long as authNotebook keeps the filler page
        at the front.

        :param style: an id of the discovery style
        :return: an instance of Credentials
        """
        # No credentials.
        credentials = Credentials()

        # CHAP
        if style is STYLE_CHAP:
            credentials.username = self._get_text("chapUsernameEntry")
            credentials.password = self._get_text("chapPasswordEntry")

        # Reverse CHAP.
        if style is STYLE_REVERSE_CHAP:
            credentials.username = self._get_text("rchapUsernameEntry")
            credentials.password = self._get_text("rchapPasswordEntry")
            credentials.reverse_username = self._get_text("rchapReverseUsername")
            credentials.reverse_password = self._get_text("rchapReversePassword")

        return credentials

    def _are_credentials_valid(self, style, credentials):
        """Are the credentials valid?

        :param style: an id of the login style
        :param credentials: an instance of Credentials
        :return: True if valid, otherwise False
        """
        if style is STYLE_NONE:
            return True

        if style is STYLE_CHAP:
            return credentials.username.strip() != "" \
                   and credentials.password != ""

        elif style is STYLE_REVERSE_CHAP:
            return credentials.username.strip() != "" \
                   and credentials.password != "" \
                   and credentials.reverse_username.strip() != "" \
                   and credentials.reverse_password != ""

    def _set_configure_sensitive(self, sensitivity):
        """Set the sensitivity of the configuration."""
        for child in self._configureGrid.get_children():
            if child == self._initiatorEntry:
                self._initiatorEntry.set_sensitive(not iscsi.initiator_set)
            elif child == self._bindCheckbox:
                self._bindCheckbox.set_sensitive(sensitivity and iscsi.mode == "none")
            elif child != self._conditionNotebook:
                child.set_sensitive(sensitivity)

    ##
    ## LOGGING IN
    ##

    def on_login_type_changed(self, widget, *args):
        """Validate the credentials.

        When we change the notebook, we also need to reverify the credentials
        in order to set the Log In button sensitivity.
        """
        self._loginAuthNotebook.set_current_page(widget.get_active())
        self.on_login_field_changed()

    def on_login_field_changed(self, *args):
        """Validate the login fields."""
        style, credentials = self._get_login_style_and_credentials()
        sensitive = self._are_credentials_valid(style, credentials)
        self._loginButton.set_sensitive(sensitive)

    def on_row_toggled(self, button, path):
        """Mark the row as selected."""
        if not path:
            return

        # Then, go back and mark just this row as selected.
        itr = self._storeFilter.get_iter(path)
        itr = self._storeFilter.convert_iter_to_child_iter(itr)
        self._store[itr][0] = not self._store[itr][0]

    def on_discover_entry_activated(self, *args):
        """Retry discovery.

        When an entry is activated in the discovery view, push either the
        start or retry discovery button.
        """
        current_page = self._conditionNotebook.get_current_page()
        if current_page == 0:
            self._startButton.clicked()
        elif current_page == 2:
            self._retryButton.clicked()

    def on_login_entry_activated(self, *args):
        """Retry login.

        When an entry or a row in the tree view is activated on the login view,
        push the login or retry button
        """
        current_page = self._loginConditionNotebook.get_current_page()
        if current_page == 0:
            self._loginButton.clicked()
        elif current_page == 1:
            self._retryLoginButton.clicked()

    def on_login_clicked(self, *args):
        """Start the login task."""
        row = self._find_row_for_login()

        # Skip, if there is nothing to do.
        if not row:
            return

        # First update widgets.
        self._set_login_sensitive(False)
        self._okButton.set_sensitive(False)
        self._cancelButton.set_sensitive(False)
        self._loginButton.set_sensitive(False)
        self._loginConditionNotebook.set_current_page(0)

        # Get data.
        target = self._get_target()
        node = self._find_node_for_row(row)
        style, credentials = self._get_login_style_and_credentials()

        # Get the login task.
        task = ISCSILoginTask(target, credentials, node)
        task.stopped_signal.connect(lambda: self.process_login_result(task, row))

        # Start the login.
        task.run()

        self._loginSpinner.start()
        self._loginSpinner.show()

    def process_login_result(self, task, row):
        """Process the result of the login task.

        :param task: a task
        :param row: a row in UI
        """
        # Stop the spinner.
        self._loginSpinner.stop()
        self._loginSpinner.hide()

        try:
            # Finish the task
            task.finish()
        except StorageDiscoveryError as e:
            # Login has failed, show the error.
            self._loginErrorLabel.set_text(str(e))

            self._set_login_sensitive(True)
            self._loginButton.set_sensitive(True)
            self._cancelButton.set_sensitive(True)
            self._loginConditionNotebook.set_current_page(1)
        else:
            # Login succeeded.
            self._update_devicetree = True

            # Update the row.
            row[1] = False

            # Are there more rows for login? Run again.
            if self._find_row_for_login():
                self.on_login_clicked()
                return

            # Are there more rows to select? Continue.
            if self._select_row_for_login():
                self._set_login_sensitive(True)
                self._okButton.set_sensitive(True)
                self._cancelButton.set_sensitive(False)
                self._loginButton.set_sensitive(True)
                self._loginConditionNotebook.set_current_page(0)
                return

            # There is nothing else to do. Quit.
            self.window.response(1)

    def _get_login_style_and_credentials(self):
        """Get style and credentials for login.

        :return: a tuple with a style and a credentials
        """
        if self._loginAuthNotebook.get_current_page() == 3:
            style = self._authNotebook.get_current_page()
            credentials = self._get_discover_credentials(style)
        else:
            style = self._loginAuthNotebook.get_current_page()
            credentials = self._get_login_credentials(style)

        return style, credentials

    def _get_login_credentials(self, style):
        """Get credentials for the login.

        The current page from the loginAuthNotebook defines how to grab credentials
        out of the UI. This works as long as loginAuthNotebook keeps the filler page
        at the front, and we check to make sure "Use the credentials from discovery"
        is not selected first.

        :param style: an id of the login style
        :return: an instance of Credentials
        """
        # No credentials.
        credentials = Credentials()

        # CHAP
        if style is STYLE_CHAP:
            credentials.username = self._get_text("loginChapUsernameEntry")
            credentials.password = self._get_text("loginChapPasswordEntry")

        # Reverse CHAP.
        if style is STYLE_REVERSE_CHAP:
            credentials.username = self._get_text("loginRchapUsernameEntry")
            credentials.password = self._get_text("loginRchapPasswordEntry")
            credentials.reverse_username = self._get_text("loginRchapReverseUsername")
            credentials.reverse_password = self._get_text("loginRchapReversePassword")

        return credentials

    def _find_row_for_login(self):
        """Find a row for login.

        Find a row that we can use to run a login task.

        :return: a row in UI
        """
        for row in self._store:
            obj = NodeStoreRow(*row)
            if obj.selected and obj.notLoggedIn:
                return row

        return None

    def _find_node_for_row(self, row):
        """Find a node for the given row.

        Find a node for the given row in UI.

        :param row: a row in UI
        :return: a discovered node
        """
        obj = NodeStoreRow(*row)
        for node in self._discovered_nodes:
            if node.name == obj.name and obj.portal == "%s:%s" % (node.address, node.port):
                return node

        return None

    def _select_row_for_login(self):
        """Select the first row we could use for login.

        :return: True if a row was selected, otherwise False
        """
        for row in self._store:
            if row[1]:
                row[0] = True
                return True

        return False

    def _set_login_sensitive(self, sensitivity):
        """Set the sensitivity of the login configuration."""
        for child in self._loginGrid.get_children():
            if child != self._loginConditionNotebook:
                child.set_sensitive(sensitivity)
