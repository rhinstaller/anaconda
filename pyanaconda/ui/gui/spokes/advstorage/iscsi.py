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
# Red Hat Author(s): Chris Lumens <clumens@redhat.com>
#

from IPy import IP
from collections import namedtuple
from gi.repository import GLib

from pyanaconda import constants
from pyanaconda.threads import threadMgr, AnacondaThread
from pyanaconda.ui.gui import GUIObject
from pyanaconda.ui.gui.utils import escape_markup
from pyanaconda.i18n import _
from pyanaconda import nm

__all__ = ["ISCSIDialog"]

STYLE_NONE = 0
STYLE_CHAP = 1
STYLE_REVERSE_CHAP = 2

Credentials = namedtuple("Credentials", ["style",
                                         "targetIP", "initiator", "username",
                                         "password", "rUsername", "rPassword"])

NodeStoreRow = namedtuple("NodeStoreRow", ["selected", "notLoggedIn", "name", "iface", "portal"])

def discover_no_credentials(builder):
    return Credentials(STYLE_NONE,
                       builder.get_object("targetEntry").get_text(),
                       builder.get_object("initiatorEntry").get_text(),
                       "", "", "", "")

def discover_chap(builder):
    return Credentials(STYLE_CHAP,
                       builder.get_object("targetEntry").get_text(),
                       builder.get_object("initiatorEntry").get_text(),
                       builder.get_object("chapUsernameEntry").get_text(),
                       builder.get_object("chapPasswordEntry").get_text(),
                       "", "")

def discover_reverse_chap(builder):
    return Credentials(STYLE_REVERSE_CHAP,
                       builder.get_object("targetEntry").get_text(),
                       builder.get_object("initiatorEntry").get_text(),
                       builder.get_object("rchapUsernameEntry").get_text(),
                       builder.get_object("rchapPasswordEntry").get_text(),
                       builder.get_object("rchapReverseUsername").get_text(),
                       builder.get_object("rchapReversePassword").get_text())

# This list maps the current page from the authNotebook to a function to grab
# credentials out of the UI.  This works as long as authNotebook keeps the
# filler page at the front.
discoverMap = [discover_no_credentials, discover_chap, discover_reverse_chap]

def login_no_credentials(builder):
    return Credentials(STYLE_NONE,
                       "", "",
                       "", "", "", "")

def login_chap(builder):
    return Credentials(STYLE_CHAP,
                       "", "",
                       builder.get_object("loginChapUsernameEntry").get_text(),
                       builder.get_object("loginChapPasswordEntry").get_text(),
                       "", "")

def login_reverse_chap(builder):
    return Credentials(STYLE_REVERSE_CHAP,
                       "", "",
                       builder.get_object("loginRchapUsernameEntry").get_text(),
                       builder.get_object("loginRchapPasswordEntry").get_text(),
                       builder.get_object("loginRchapReverseUsername").get_text(),
                       builder.get_object("loginRchapReversePassword").get_text())

# And this list maps the current page from the loginAuthNotebook to a function
# to grab credentials out of the UI.  This works as long as loginAuthNotebook
# keeps the filler page at the front, and we check to make sure "Use the
# credentials from discovery" is not selected first.
loginMap = [login_no_credentials, login_chap, login_reverse_chap]

def credentials_valid(credentials):
    if credentials.style == STYLE_NONE:
        return True
    elif credentials.style == STYLE_CHAP:
        return credentials.username.strip() != "" and credentials.password != ""
    elif credentials.style == STYLE_REVERSE_CHAP:
        return credentials.username.strip() != "" and credentials.password != "" and \
               credentials.rUsername.strip() != "" and credentials.rPassword != ""

class ISCSIDialog(GUIObject):
    builderObjects = ["iscsiDialog", "nodeStore", "nodeStoreFiltered"]
    mainWidgetName = "iscsiDialog"
    uiFile = "spokes/advstorage/iscsi.glade"

    def __init__(self, data, storage):
        GUIObject.__init__(self, data)
        self.storage = storage
        self.iscsi = self.storage.iscsi()

        self._discoveryError = None
        self._loginError = False

        self._discoveredNodes = []
        self._update_devicetree = False

        self._authTypeCombo = self.builder.get_object("authTypeCombo")
        self._authNotebook = self.builder.get_object("authNotebook")
        self._iscsiNotebook = self.builder.get_object("iscsiNotebook")

        self._loginButton = self.builder.get_object("loginButton")
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

        self._initiatorEntry = self.builder.get_object("initiatorEntry")

        self._store = self.builder.get_object("nodeStore")
        self._storeFilter = self.builder.get_object("nodeStoreFiltered")

    def refresh(self):
        self._bindCheckbox.set_active(bool(self.iscsi.ifaces))
        self._bindCheckbox.set_sensitive(self.iscsi.mode == "none")

        self._authTypeCombo.set_active(0)
        self._startButton.set_sensitive(True)

        self._loginAuthTypeCombo.set_active(0)

        self._storeFilter.set_visible_column(1)

        self._initiatorEntry.set_text(self.iscsi.initiator)
        self._initiatorEntry.set_sensitive(not self.iscsi.initiatorSet)

    @property
    def selectedNames(self):
        return [itr[2] for itr in self._store if itr[0]]

    def run(self):
        rc = self.window.run()
        self.window.destroy()
        # We need to call this to get the device nodes to show up
        # in our devicetree.
        if self._update_devicetree:
            self.storage.devicetree.populate()
        return rc

    ##
    ## DISCOVERY
    ##

    def on_auth_type_changed(self, widget, *args):
        self._authNotebook.set_current_page(widget.get_active())

        # When we change the notebook, we also need to reverify the credentials
        # in order to set the Start button sensitivity.
        self.on_discover_field_changed()

    def _discover(self, credentials, bind):
        # This needs to be in its own thread, not marked with gtk_action_* because it's
        # called from on_start_clicked, which is in the GTK main loop.  Those decorators
        # won't do anything special in that case.
        if not self.iscsi.initiatorSet:
            self.iscsi.initiator = credentials.initiator

        # interfaces created here affect nodes that iscsi.discover would return
        if self.iscsi.mode == "none" and not bind:
            self.iscsi.delete_interfaces()
        elif (self.iscsi.mode == "bind"
              or self.iscsi.mode == "none" and bind):
            activated = set(nm.nm_activated_devices())
            created = set(self.iscsi.ifaces.values())
            self.iscsi.create_interfaces(activated - created)

        try:
            self._discoveredNodes = self.iscsi.discover(credentials.targetIP,
                                                        username=credentials.username,
                                                        password=credentials.password,
                                                        r_username=credentials.rUsername,
                                                        r_password=credentials.rPassword)
        except IOError as e:
            self._discoveryError = str(e)
            return

        if len(self._discoveredNodes) == 0:
            self._discoveryError = "No nodes discovered."

    def _check_discover(self, *args):
        if threadMgr.get(constants.THREAD_ISCSI_DISCOVER):
            return True

        # When iscsi discovery is done, update the UI.  We don't need to worry
        # about the user escaping from the dialog because all the buttons are
        # marked insensitive.
        spinner = self.builder.get_object("waitSpinner")
        spinner.stop()

        if self._discoveryError:
            # Failure.  Display some error message and leave the user on the
            # dialog to try again.
            self.builder.get_object("discoveryErrorLabel").set_text(self._discoveryError)
            self._discoveryError = None
            self._conditionNotebook.set_current_page(2)
            self._set_configure_sensitive(True)
        else:
            # Success.  Now populate the node store and kick the user on over to
            # that subscreen.
            self._add_nodes(self._discoveredNodes)
            self._iscsiNotebook.set_current_page(1)

            # If some form of login credentials were used for discovery,
            # default to using the same for login.
            if self._authTypeCombo.get_active() != 0:
                self._loginAuthTypeCombo.set_active(3)

        # We always want to enable this button, in case the user's had enough.
        self._cancelButton.set_sensitive(True)
        return False

    def _set_configure_sensitive(self, sensitivity):
        for child in self._configureGrid.get_children():
            if child == self._initiatorEntry:
                self._initiatorEntry.set_sensitive(not self.iscsi.initiatorSet)
            elif child == self._bindCheckbox:
                self._bindCheckbox.set_sensitive(sensitivity and self.iscsi.mode == "none")
            elif child != self._conditionNotebook:
                child.set_sensitive(sensitivity)

    def on_start_clicked(self, *args):
        # First, update some widgets to not be usable while discovery happens.
        self._startButton.hide()
        self._cancelButton.set_sensitive(False)
        self._okButton.set_sensitive(False)

        self._conditionNotebook.set_current_page(1)
        self._set_configure_sensitive(False)
        self._initiatorEntry.set_sensitive(False)

        # Now get the node discovery credentials.
        credentials = discoverMap[self._authNotebook.get_current_page()](self.builder)

        discoveredLabelText = _("The following nodes were discovered using the iSCSI initiator "\
                                "<b>%(initiatorName)s</b> using the target IP address "\
                                "<b>%(targetAddress)s</b>.  Please select which nodes you "\
                                "wish to log into:") % \
                                {"initiatorName": escape_markup(credentials.initiator),
                                 "targetAddress": escape_markup(credentials.targetIP)}

        discoveredLabel = self.builder.get_object("discoveredLabel")
        discoveredLabel.set_markup(discoveredLabelText)

        bind = self._bindCheckbox.get_active()

        spinner = self.builder.get_object("waitSpinner")
        spinner.start()

        threadMgr.add(AnacondaThread(name=constants.THREAD_ISCSI_DISCOVER, target=self._discover,
                                     args=(credentials, bind)))
        GLib.timeout_add(250, self._check_discover)

    # When the initiator name, ip address, and any auth fields are filled in
    # valid, only then should the Start button be made sensitive.
    def _target_ip_valid(self):
        widget = self.builder.get_object("targetEntry")
        text = widget.get_text()

        try:
            IP(text)
            return True
        except ValueError:
            return False

    def _initiator_name_valid(self):
        widget = self.builder.get_object("initiatorEntry")
        text = widget.get_text()

        stripped = text.strip()
        #iSCSI Naming Standards: RFC 3720 and RFC 3721
        return "." in stripped

    def on_discover_field_changed(self, *args):
        # Make up a credentials object so we can test if it's valid.
        credentials = discoverMap[self._authNotebook.get_current_page()](self.builder)
        sensitive = self._target_ip_valid() and self._initiator_name_valid() and credentials_valid(credentials)
        self._startButton.set_sensitive(sensitive)

    ##
    ## LOGGING IN
    ##

    def _add_nodes(self, nodes):
        for node in nodes:
            iface =  self.iscsi.ifaces.get(node.iface, node.iface)
            portal = "%s:%s" % (node.address, node.port)
            self._store.append([False, True, node.name, iface, portal])

        # We should select the first node by default.
        self._store[0][0] = True

    def on_login_type_changed(self, widget, *args):
        self._loginAuthNotebook.set_current_page(widget.get_active())

        # When we change the notebook, we also need to reverify the credentials
        # in order to set the Log In button sensitivity.
        self.on_login_field_changed()

    def on_row_toggled(self, button, path):
        if not path:
            return

        # Then, go back and mark just this row as selected.
        itr = self._storeFilter.get_iter(path)
        itr = self._storeFilter.convert_iter_to_child_iter(itr)
        self._store[itr][0] = not self._store[itr][0]

    def _login(self, credentials):
        for row in self._store:
            obj = NodeStoreRow(*row)

            if not obj.selected:
                continue

            for node in self._discoveredNodes:
                if obj.notLoggedIn and node.name == obj.name \
                   and obj.portal == "%s:%s" % (node.address, node.port):
                    # when binding interfaces match also interface
                    if self.iscsi.ifaces and \
                       obj.iface != self.iscsi.ifaces[node.iface]:
                        continue
                    (rc, msg) = self.iscsi.log_into_node(node,
                                                         username=credentials.username,
                                                         password=credentials.password,
                                                         r_username=credentials.rUsername,
                                                         r_password=credentials.rPassword)
                    if not rc:
                        self._loginError = msg
                        return

                    self._update_devicetree = True
                    row[1] = False

    def _check_login(self, *args):
        if threadMgr.get(constants.THREAD_ISCSI_LOGIN):
            return True

        spinner = self.builder.get_object("loginSpinner")
        spinner.stop()
        spinner.hide()

        if self._loginError:
            self.builder.get_object("loginErrorLabel").set_text(self._loginError)
            self._loginError = None
            self._loginConditionNotebook.set_current_page(1)
            self._cancelButton.set_sensitive(True)
            self._loginButton.set_sensitive(True)
        else:
            anyLeft = False

            self._loginConditionNotebook.set_current_page(0)

            # Select the now-first target for the user in case they want to
            # log into another one.
            for row in self._store:
                if row[1]:
                    row[0] = True
                    anyLeft = True

                    # And make the login button sensitive if there are any more
                    # nodes to login to.
                    self._loginButton.set_sensitive(True)
                    break

            self._okButton.set_sensitive(True)

            # Once a node has been logged into, it doesn't make much sense to let
            # the user cancel.  Cancel what, exactly?
            self._cancelButton.set_sensitive(False)

            if not anyLeft:
                self.window.response(1)

        self._set_login_sensitive(True)
        return False

    def _set_login_sensitive(self, sensitivity):
        for child in self._loginGrid.get_children():
            if child != self._loginConditionNotebook:
                child.set_sensitive(sensitivity)

    def on_login_clicked(self, *args):
        # Make the buttons UI while we work.
        self._okButton.set_sensitive(False)
        self._cancelButton.set_sensitive(False)
        self._loginButton.set_sensitive(False)

        self._loginConditionNotebook.set_current_page(0)
        self._set_login_sensitive(False)

        spinner = self.builder.get_object("loginSpinner")
        spinner.start()
        spinner.set_visible(True)
        spinner.show()

        # Are we reusing the credentials from the discovery step?  If so, grab them
        # out of the UI again here.  They should still be there.
        page = self._loginAuthNotebook.get_current_page()
        if page == 3:
            credentials = discoverMap[self._authNotebook.get_current_page()](self.builder)
        else:
            credentials = loginMap[page](self.builder)

        threadMgr.add(AnacondaThread(name=constants.THREAD_ISCSI_LOGIN, target=self._login,
                                     args=(credentials,)))
        GLib.timeout_add(250, self._check_login)

    def on_login_field_changed(self, *args):
        # Make up a credentials object so we can test if it's valid.
        page = self._loginAuthNotebook.get_current_page()
        if page == 3:
            credentials = discoverMap[self._authNotebook.get_current_page()](self.builder)
        else:
            credentials = loginMap[page](self.builder)

        self._loginButton.set_sensitive(credentials_valid(credentials))
