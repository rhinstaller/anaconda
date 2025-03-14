# Subscription spoke class
#
# Copyright (C) 2020 Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

from enum import IntEnum

from dasbus.typing import unwrap_variant

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.async_utils import async_action_wait
from pyanaconda.core.constants import (
    SECRET_TYPE_HIDDEN,
    SOURCE_TYPES_OVERRIDEN_BY_CDN,
    SUBSCRIPTION_REQUEST_TYPE_ORG_KEY,
    SUBSCRIPTION_REQUEST_TYPE_USERNAME_PASSWORD,
    THREAD_PAYLOAD,
    THREAD_SUBSCRIPTION,
    THREAD_SUBSCRIPTION_SPOKE_INIT,
)
from pyanaconda.core.i18n import CN_, _
from pyanaconda.core.payload import ProxyString, ProxyStringError
from pyanaconda.core.threads import thread_manager
from pyanaconda.flags import flags
from pyanaconda.modules.common.constants.services import NETWORK, SUBSCRIPTION
from pyanaconda.modules.common.errors.subscription import MultipleOrganizationsError
from pyanaconda.modules.common.structures.subscription import (
    OrganizationData,
    SubscriptionRequest,
    SystemPurposeData,
)
from pyanaconda.modules.common.task import async_run_task, sync_run_task
from pyanaconda.modules.common.util import is_module_available
from pyanaconda.ui.categories.software import SoftwareCategory
from pyanaconda.ui.communication import hubQ
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.spokes.lib.subscription import fill_combobox
from pyanaconda.ui.gui.utils import set_password_visibility
from pyanaconda.ui.lib.subscription import (
    SubscriptionPhase,
    check_cdn_is_installation_source,
    org_keys_sufficient,
    register_and_subscribe,
    unregister,
    username_password_sufficient,
)

log = get_module_logger(__name__)

__all__ = ["SubscriptionSpoke"]


# the integers correspond to the order of options
# in the authentication mode combo box
class AuthenticationMethod(IntEnum):
    USERNAME_PASSWORD = 0
    ORG_KEY = 1


class SubscriptionSpoke(NormalSpoke):
    """Subscription spoke provides the Connect to Red Hat screen."""
    builderObjects = ["subscription_window"]

    mainWidgetName = "subscription_window"
    uiFile = "spokes/subscription.glade"

    category = SoftwareCategory

    icon = "application-certificate-symbolic"
    title = CN_("GUI|Spoke", "_Connect to Red Hat")

    # main notebook pages
    REGISTRATION_PAGE = 0
    SUBSCRIPTION_STATUS_PAGE = 1

    @staticmethod
    def get_screen_id():
        """Return a unique id of this UI screen."""
        return "subscription-configuration"

    @classmethod
    def should_run(cls, environment, data):
        """The Subscription spoke should run only if the Subscription module is available."""
        return is_module_available(SUBSCRIPTION)

    def __init__(self, *args):
        super().__init__(*args)

        # connect to the Subscription DBus module API
        self._subscription_module = SUBSCRIPTION.get_proxy()

        # connect to the Network DBus module API
        self._network_module = NETWORK.get_proxy()

        # get initial data from the Subscription module
        self._subscription_request = self._get_subscription_request()
        self._system_purpose_data = self._get_system_purpose_data()

        self._authentication_method = AuthenticationMethod.USERNAME_PASSWORD

        self._registration_error = ""
        self._registration_phase = None
        self._registration_controls_enabled = True

        # Red Hat Insights should be enabled by default for non-kickstart installs.
        #
        # For kickstart installations we will use the value from the module, which
        # False by default & can be set to True via the rhsm kickstart command.
        if not flags.automatedInstall:
            self._subscription_module.InsightsEnabled = True

        # previous visit network connectivity tracking
        self._network_connected_previously = False

        # overriden source tracking
        self._overridden_source_type = None

        self._spoke_initialized = False

    # common spoke properties

    @property
    def ready(self):
        """The subscription spoke is ready once the spoke initialization thread finishes.

        The spoke initialization thread waits for the subscription and payload initialization
        threads, to avoid the Subscription spoke being set mandatory in cases
        where the current installation source is the CDN, but payload refresh is still
        running and it might change the installation source to CDROM later on.

        NOTE: We don't actually wait for the spoke initialization thread to finish, we check
              a variable it sets instead. This is due to the thread also sending the hub refresh
              signal, which would trigger a race condition if the hub refresh is processed before
              the spoke initialization thread finishes. Setting the variable and *then* sending
              the hub refresh signal avoids this issue.
        """
        return self._spoke_initialized


    @property
    def status(self):
        # The spoke status message:
        # - shows registration phases when registration + subscription
        #   or unregistration is ongoing
        # - otherwise shows not-registered/registered/error
        return self._get_status_message()

    @property
    def mandatory(self):
        """The subscription spoke is mandatory if Red Hat CDN is set as installation source."""
        return check_cdn_is_installation_source(self.payload)

    @property
    def completed(self):
        return self.subscription_attached

    @property
    def sensitive(self):
        # the Subscription spoke should be always accessible
        return True

    # common spoke methods

    def apply(self):
        log.debug("Subscription GUI: apply() running")
        self._set_data_to_module()

    def refresh(self):
        log.debug("Subscription GUI: refresh() running")
        # update spoke state based on up-to-date data from the Subscription module
        # (this also takes care of updating the two properties holding subscription
        #  request as well as system purpose data)
        self._update_spoke_state()
        # check if network connectivity is available
        # - without network connectivity the spoke is pretty much unusable
        # - also, no need to check if registration/unregistration is in progress
        if not self.registration_phase:
            self._check_connectivity()

    # DBus structure mirrors

    @property
    def subscription_request(self):
        """A mirror of the subscription request from the Subscription DBus module.

        Should be always set and is periodically updated on refresh().

        :return: up to date subscription request
        :rtype: SubscriptionRequest instance
        """
        return self._subscription_request

    @property
    def system_purpose_data(self):
        """A mirror of system purpose data from the Subscription DBus module.

        Should be always set and is periodically updated on refresh().

        :return: up to date system purpose data
        :rtype: SystemPurposeData instance
        """
        return self._system_purpose_data

    # placeholder control

    def enable_http_proxy_password_placeholder(self, show_placeholder):
        """Show a placeholder on the HTTP proxy password field.

        The placeholder notifies the user about HTTP proxy password
        being set in the DBus module.

        The placeholder will be only shown if there is no
        actual text in the entry field.
        """
        if show_placeholder:
            self._http_proxy_password_entry.set_placeholder_text(_("Password set."))
        else:
            self._http_proxy_password_entry.set_placeholder_text("")

    def enable_password_placeholder(self, show_placeholder):
        """Show a placeholder on the red hat account password field.

        The placeholder notifies the user about activation
        key being set in the DBus module.

        The placeholder will be only shown if there is no
        actual text in the entry field.
        """
        if show_placeholder:
            self._password_entry.set_placeholder_text(_("Password set."))
        else:
            self._password_entry.set_placeholder_text("")

    def enable_activation_key_placeholder(self, show_placeholder):
        """Show a placeholder on the activation key field.

        The placeholder notifies the user about activation
        key being set in the DBus module.

        The placeholder will be only shown if there is no
        actual text in the entry field.
        """
        if show_placeholder:
            self._activation_key_entry.set_placeholder_text(_("Activation key set."))
        else:
            self._activation_key_entry.set_placeholder_text("")

    # properties controlling visibility of options that can be hidden

    @property
    def custom_server_hostname_visible(self):
        return self._custom_server_hostname_checkbox.get_active()

    @custom_server_hostname_visible.setter
    def custom_server_hostname_visible(self, visible):
        self._custom_server_hostname_checkbox.set_active(visible)

    @property
    def http_proxy_visible(self):
        return self._http_proxy_checkbox.get_active()

    @http_proxy_visible.setter
    def http_proxy_visible(self, visible):
        self._http_proxy_checkbox.set_active(visible)

    @property
    def custom_rhsm_baseurl_visible(self):
        return self._custom_rhsm_baseurl_checkbox.get_active()

    @custom_rhsm_baseurl_visible.setter
    def custom_rhsm_baseurl_visible(self, visible):
        self._custom_rhsm_baseurl_checkbox.set_active(visible)

    def set_account_visible(self, visible):
        self._account_radio_button.set_active(visible)

    def set_activation_key_visible(self, visible):
        self._activation_key_radio_button.set_active(visible)

    def set_system_purpose_visible(self, visible):
        self._system_purpose_checkbox.set_active(visible)

    def set_options_visible(self, visible):
        self._options_expander.set_expanded(visible)

    # properties - element sensitivity

    def set_registration_controls_sensitive(self, sensitive):
        """Set sensitivity of the registration controls.

        We set these value individually so that the registration status label
        that is between the controls will not become grayed out due to setting
        the top level container insensitive.
        """
        self._registration_grid.set_sensitive(sensitive)
        self._options_expander.set_sensitive(sensitive)
        self._registration_controls_enabled = sensitive
        self._update_registration_state()

    # authentication related signals

    def on_account_radio_button_toggled(self, radio):
        self._account_revealer.set_reveal_child(radio.get_active())
        if radio.get_active():
            self.authentication_method = AuthenticationMethod.USERNAME_PASSWORD

    def on_activation_key_radio_button_toggled(self, radio):
        self._activation_key_revealer.set_reveal_child(radio.get_active())
        if radio.get_active():
            self.authentication_method = AuthenticationMethod.ORG_KEY

    def on_username_entry_changed(self, editable):
        self.subscription_request.account_username = editable.get_text()
        self._update_registration_state()
        # changes to username can invalidate the organization list,
        # so hide it if the username changes
        self._disable_org_selection_for_account()

    def on_password_entry_changed(self, editable):
        entered_text = editable.get_text()
        if entered_text:
            self.enable_password_placeholder(False)
        self.subscription_request.account_password.set_secret(entered_text)
        self._update_registration_state()

    def on_password_icon_clicked(self, entry, icon_pos, event):
        """Called by Gtk callback when the icon of a password entry is clicked."""
        set_password_visibility(entry, not entry.get_visibility())

    def on_password_entry_map(self, entry):
        """Called when a password entry widget is going to be displayed.

        - Without this the password visibility toggle icon would not be shown.
        - The password should be hidden every time the entry widget is displayed
          to avoid showing the password in plain text in case the user previously
          displayed the password and then left the spoke, for example.
        """
        set_password_visibility(entry, False)

    def on_select_organization_combobox_changed(self, combobox):
        log.debug("Subscription GUI: organization selected for account: %s",
                  combobox.get_active_id())
        self.subscription_request.account_organization = combobox.get_active_id()

    def on_organization_entry_changed(self, editable):
        self.subscription_request.organization = editable.get_text()
        self._update_registration_state()

    def on_activation_key_entry_changed(self, editable):
        entered_text = editable.get_text()
        keys = None
        if entered_text:
            self.enable_activation_key_placeholder(False)
            keys = entered_text.split(',')
        # keys == None clears keys in the module, so deleting keys
        # in the keys field will also clear module data on apply()
        self.subscription_request.activation_keys.set_secret(keys)
        self._update_registration_state()

    # system purpose related signals

    def on_system_purpose_checkbox_toggled(self, checkbox):
        active = checkbox.get_active()
        self._system_purpose_revealer.set_reveal_child(active)
        if active:
            # make sure data in the system purpose comboboxes
            # are forwarded to the system purpose data structure
            # in case something was set before they were hidden
            self.on_system_purpose_role_combobox_changed(self._system_purpose_role_combobox)
            self.on_system_purpose_sla_combobox_changed(self._system_purpose_sla_combobox)
            self.on_system_purpose_usage_combobox_changed(self._system_purpose_usage_combobox)
        else:
            # system purpose combo boxes have been hidden, clear the corresponding
            # data from the system purpose data structure, but keep it in the combo boxes
            # in case the user tries to show them again before next spoke entry clears them
            self.system_purpose_data.role = ""
            self.system_purpose_data.sla = ""
            self.system_purpose_data.usage = ""

    def on_system_purpose_role_combobox_changed(self, combobox):
        self.system_purpose_data.role = combobox.get_active_id()

    def on_system_purpose_sla_combobox_changed(self, combobox):
        self.system_purpose_data.sla = combobox.get_active_id()

    def on_system_purpose_usage_combobox_changed(self, combobox):
        self.system_purpose_data.usage = combobox.get_active_id()

    # HTTP proxy signals

    def on_http_proxy_checkbox_toggled(self, checkbox):
        active = checkbox.get_active()
        self._http_proxy_revealer.set_reveal_child(active)
        if active:
            # make sure data in the HTTP proxy entries
            # are forwarded to the subscription request structure
            # in case something was entered before they were hidden
            self.on_http_proxy_location_entry_changed(self._http_proxy_location_entry)
            self.on_http_proxy_username_entry_changed(self._http_proxy_username_entry)
            self.on_http_proxy_password_entry_changed(self._http_proxy_password_entry)
        else:
            # HTTP proxy entries have been hidden, clear the corresponding data from
            # the subscription request structure, but keep it in the entries in case
            # the user tries to show them again before next spoke entry clears them
            self._subscription_request.server_proxy_hostname = ""
            self._subscription_request.server_proxy_port = -1
            self._subscription_request.server_proxy_user = ""
            self._subscription_request.server_proxy_password.set_secret(None)

    def on_http_proxy_location_entry_changed(self, editable):
        # Incorrect hostnames, including empty strings, will
        # throw an exception we need to catch and switch
        # to defaults. This can happen often as the user
        # types the hostname to the field.
        try:
            port = -1  # not set == -1
            proxy_obj = ProxyString(url=editable.get_text())
            hostname = proxy_obj.host
            if proxy_obj.port:
                # the DBus API expects an integer
                port = int(proxy_obj.port)
        except ProxyStringError:
            hostname = ""
        # set the resulting values to the DBus structure
        self.subscription_request.server_proxy_hostname = hostname
        self.subscription_request.server_proxy_port = port

    def on_http_proxy_username_entry_changed(self, editable):
        self.subscription_request.server_proxy_user = editable.get_text()

    def on_http_proxy_password_entry_changed(self, editable):
        password = editable.get_text()
        # if password is set in the field, set it, or set None to clear the password
        self.subscription_request.server_proxy_password.set_secret(password or None)

    # custom server hostname and rhsm baseurl signals

    def on_custom_server_hostname_checkbox_toggled(self, checkbox):
        active = checkbox.get_active()
        self._custom_server_hostname_revealer.set_reveal_child(active)
        if active:
            # make sure data in the server hostname entry
            # is forwarded to the subscription request structure
            # in case something was entered before the entry was
            # hidden
            self.on_custom_server_hostname_entry_changed(self._custom_server_hostname_entry)
        else:
            # the entry was hidden, clear the data from subscription request but
            # keep it in the entry in case user decides to show the entry again
            # before next spoke entry clears it
            self.subscription_request.server_hostname = ""

    def on_custom_server_hostname_entry_changed(self, editable):
        self.subscription_request.server_hostname = editable.get_text()

    def on_custom_rhsm_baseurl_checkbox_toggled(self, checkbox):
        active = checkbox.get_active()
        self._custom_rhsm_baseurl_revealer.set_reveal_child(active)
        if active:
            # make sure data in the rhsm baseurl entry
            # is forwarded to the subscription request structure
            # in case something was entered before the entry was
            # hidden
            self.on_custom_rhsm_baseurl_entry_changed(self._custom_rhsm_baseurl_entry)
        else:
            # the entry was hidden, clear the data from subscription request but
            # keep it in the entry in case user decides to show the entry again
            # before next spoke entry clears it
            self.subscription_request.rhsm_baseurl = ""

    def on_custom_rhsm_baseurl_entry_changed(self, editable):
        self.subscription_request.rhsm_baseurl = editable.get_text()

    # button signals

    def on_register_button_clicked(self, button):
        log.debug("Subscription GUI: register button clicked")
        # hide the passwords during the registration process
        set_password_visibility(self._password_entry, False)
        set_password_visibility(self._http_proxy_password_entry, False)
        self._register()

    def on_unregister_button_clicked(self, button):
        """Handle registration related tasks."""
        log.debug("Subscription GUI: unregister button clicked")
        self._unregister()

    # properties - general properties

    @property
    def registration_phase(self):
        """Reports what phase the registration procedure is in.

        Only valid if a registration thread is running.
        """
        return self._registration_phase

    @registration_phase.setter
    def registration_phase(self, phase):
        self._registration_phase = phase

    @property
    def subscription_attached(self):
        """Was a subscription entitlement successfully attached ?"""
        return self._subscription_module.IsSubscriptionAttached

    @property
    def network_connected(self):
        """Does it look like that we have network connectivity ?

        Network connectivity is required for subscribing a system.
        """
        return self._network_module.Connected

    @property
    def authentication_method(self):
        """Report which authentication method is in use."""
        return self._authentication_method

    @authentication_method.setter
    def authentication_method(self, method):
        self._authentication_method = method
        if method == AuthenticationMethod.USERNAME_PASSWORD:
            self.set_activation_key_visible(False)
            self.set_account_visible(True)
            self.subscription_request.type = SUBSCRIPTION_REQUEST_TYPE_USERNAME_PASSWORD
        elif method == AuthenticationMethod.ORG_KEY:
            self.set_activation_key_visible(True)
            self.set_account_visible(False)
            self.subscription_request.type = SUBSCRIPTION_REQUEST_TYPE_ORG_KEY

    @property
    def options_set(self):
        """Report if at least one option in the Options section has been set."""
        return self.http_proxy_visible or self.custom_server_hostname_visible or \
            self.custom_rhsm_baseurl_visible

    @property
    def registration_error(self):
        return self._registration_error

    @registration_error.setter
    def registration_error(self, error_message):
        self._registration_error = error_message
        # also set the spoke warning banner
        self.show_warning_message(error_message)

    def initialize(self):
        NormalSpoke.initialize(self)
        self.initialize_start()

        # get object references from the builders
        self._main_notebook = self.builder.get_object("main_notebook")

        # * the registration tab  * #

        # container for the main registration controls
        self._registration_grid = self.builder.get_object("registration_grid")

        # authentication
        self._account_radio_button = self.builder.get_object("account_radio_button")
        self._activation_key_radio_button = self.builder.get_object("activation_key_radio_button")

        # authentication - account
        self._account_revealer = self.builder.get_object("account_revealer")
        self._username_entry = self.builder.get_object("username_entry")
        self._password_entry = self.builder.get_object("password_entry")

        # authentication - account - org selection
        self._select_organization_label_revealer = self.builder.get_object(
            "select_organization_label_revealer"
        )
        self._select_organization_combobox_revealer = self.builder.get_object(
            "select_organization_combobox_revealer"
        )
        self._select_organization_combobox = self.builder.get_object(
            "select_organization_combobox"
        )

        # authentication - activation key
        self._activation_key_revealer = self.builder.get_object("activation_key_revealer")
        self._organization_entry = self.builder.get_object("organization_entry")
        self._activation_key_entry = self.builder.get_object("activation_key_entry")

        # system purpose
        self._system_purpose_checkbox = self.builder.get_object("system_purpose_checkbox")
        self._system_purpose_revealer = self.builder.get_object("system_purpose_revealer")
        self._system_purpose_role_combobox = self.builder.get_object(
            "system_purpose_role_combobox"
        )
        self._system_purpose_sla_combobox = self.builder.get_object(
            "system_purpose_sla_combobox"
        )
        self._system_purpose_usage_combobox = self.builder.get_object(
            "system_purpose_usage_combobox"
        )

        # insights
        self._insights_checkbox = self.builder.get_object("insights_checkbox")

        # options expander
        self._options_expander = self.builder.get_object("options_expander")

        # HTTP proxy
        self._http_proxy_checkbox = self.builder.get_object("http_proxy_checkbox")
        self._http_proxy_revealer = self.builder.get_object("http_proxy_revealer")
        self._http_proxy_location_entry = self.builder.get_object("http_proxy_location_entry")
        self._http_proxy_username_entry = self.builder.get_object("http_proxy_username_entry")
        self._http_proxy_password_entry = self.builder.get_object("http_proxy_password_entry")

        # RHSM baseurl
        self._custom_rhsm_baseurl_checkbox = self.builder.get_object(
            "custom_rhsm_baseurl_checkbox"
        )
        self._custom_rhsm_baseurl_revealer = self.builder.get_object(
            "custom_rhsm_baseurl_revealer"
        )
        self._custom_rhsm_baseurl_entry = self.builder.get_object(
            "custom_rhsm_baseurl_entry"
        )

        # server hostname
        self._custom_server_hostname_checkbox = self.builder.get_object(
            "custom_server_hostname_checkbox"
        )
        self._custom_server_hostname_revealer = self.builder.get_object(
            "custom_server_hostname_revealer"
        )
        self._custom_server_hostname_entry = self.builder.get_object(
            "custom_server_hostname_entry"
        )

        # status label
        self._registration_status_label = self.builder.get_object("registration_status_label")

        # register button
        self._register_button = self.builder.get_object("register_button")

        # unregister button
        self._unregister_button = self.builder.get_object("unregister_button")

        # * the subscription status tab * #

        # general status
        self._subscription_status_label = self.builder.get_object("subscription_status_label")
        self._method_status_label = self.builder.get_object("method_status_label")
        self._role_status_label = self.builder.get_object("role_status_label")
        self._sla_status_label = self.builder.get_object("sla_status_label")
        self._usage_status_label = self.builder.get_object("usage_status_label")
        self._insights_status_label = self.builder.get_object("insights_status_label")

        # attached subscriptions
        self._attached_subscriptions_label = self.builder.get_object(
            "attached_subscriptions_label"
        )
        self._subscriptions_listbox = self.builder.get_object("subscriptions_listbox")

        # setup spoke state based on data from the Subscription DBus module
        self._update_spoke_state()

        # start the rest of spoke initialization which might take some time
        # (mainly due to waiting for various initialization threads to finish)
        # in a separate thread
        thread_manager.add_thread(
            name=THREAD_SUBSCRIPTION_SPOKE_INIT,
            target=self._initialize
        )

    def _initialize(self):
        # wait for subscription thread to finish (if any)
        thread_manager.wait(THREAD_SUBSCRIPTION)
        # also wait for the payload thread, which migh still be processing
        # a CDROM source, to avoid the Subscription being mandatory by mistake
        # due to CDN still being default at the time of evaulation
        thread_manager.wait(THREAD_PAYLOAD)

        # update overall state
        self._update_registration_state()
        self._update_subscription_state()

        # we are done, mark the spoke as initialized
        self._spoke_initialized = True

        # Send ready signal to main event loop,
        # which among other things refreshes the hub to make
        # sure the Connect to Red Hat spokes shows up as ready.
        hubQ.send_ready(self.__class__.__name__)

        # report that we are done
        self.initialize_done()

    # private methods

    def _update_spoke_state(self):
        """Setup spoke state based on Subscription DBus module state.

        Subscription DBus module state is represented by the SubscriptionRequest and
        SystemPurposeData DBus structures. We first update their local mirrors from
        the DBus module and then set all the controls in the spoke to values
        represented in the DBus structures.

        NOTE: There are a couple special cases where we need to do some special precessing,
              such as for fields holding sensitive data. If we blindly set those based
              on DBus structure data, we would effectively clear them as the Subscription
              DBus module never returns previously set sensitive data in plain text.

        """
        # start by pulling in fresh data from the Subscription DBus module
        self._subscription_request = self._get_subscription_request()
        self._system_purpose_data = self._get_system_purpose_data()

        # next update the authentication part of the UI
        self._update_authetication_ui()

        # check if system purpose part of the spoke should be visible
        self.set_system_purpose_visible(self.system_purpose_data.check_data_available())

        # NOTE: the fill_combobox() function makes sure to remove old data from the
        #       combo box before filling it

        # role
        fill_combobox(self._system_purpose_role_combobox,
                      self.system_purpose_data.role,
                      self._subscription_module.GetValidRoles())
        # SLA
        fill_combobox(self._system_purpose_sla_combobox,
                      self.system_purpose_data.sla,
                      self._subscription_module.GetValidSLAs())
        # usage
        fill_combobox(self._system_purpose_usage_combobox,
                      self.system_purpose_data.usage,
                      self._subscription_module.GetValidUsageTypes())

        # Insights
        self._insights_checkbox.set_active(self._subscription_module.InsightsEnabled)

        # update the HTTP proxy part of the UI
        self._update_http_proxy_ui()

        # set custom server hostname
        self.custom_server_hostname_visible = bool(self.subscription_request.server_hostname)
        self._custom_server_hostname_entry.set_text(self.subscription_request.server_hostname)

        # set custom rhsm baseurl
        self.custom_rhsm_baseurl_visible = bool(self.subscription_request.rhsm_baseurl)
        self._custom_rhsm_baseurl_entry.set_text(self.subscription_request.rhsm_baseurl)

        # if there is something set in the Options section, expand the expander
        # - this needs to go last, after all the values in option section are set/not set
        if self.options_set:
            self.set_options_visible(True)

        # now that we updated the spoke with fresh data from the module, we can run the
        # general purpose update functions that make sure the two parts of the spoke
        # (the registration part and the subscription part) are both valid
        self._update_registration_state()
        self._update_subscription_state()

    def _update_authetication_ui(self):
        """Update the authentication part of the spoke.

        - SubscriptionRequest always has type set
        - username + password is the default
        For the related password and activation keys entry holding sensitive data
        we need to reconcile the data held in the spoke from previous entry with
        data set in the DBus module previously:
        - data in module and entry empty -> set placeholder
        - data in module and entry populated -> keep text in entry,
          we assume it is the same as what is in module
        - no data in module and entry populated -> clear entry & any placeholders
          (data cleared over DBus API)
        - no data in module and entry empty -> do nothing
        """
        if self.subscription_request.type == SUBSCRIPTION_REQUEST_TYPE_USERNAME_PASSWORD:
            self.authentication_method = AuthenticationMethod.USERNAME_PASSWORD
            self._username_entry.set_text(self.subscription_request.account_username)
            set_in_entry = bool(self._password_entry.get_text())
            set_in_module = self.subscription_request.account_password.type == SECRET_TYPE_HIDDEN
            if set_in_module:
                if not set_in_entry:
                    self.enable_password_placeholder(True)
            else:
                self._password_entry.set_text("")
                self.enable_password_placeholder(False)
        elif self.subscription_request.type == SUBSCRIPTION_REQUEST_TYPE_ORG_KEY:
            self.authentication_method = AuthenticationMethod.ORG_KEY
            self._organization_entry.set_text(self.subscription_request.organization)
            set_in_entry = bool(self._activation_key_entry.get_text())
            set_in_module = self.subscription_request.activation_keys.type == SECRET_TYPE_HIDDEN
            if set_in_module:
                if not set_in_entry:
                    self.enable_activation_key_placeholder(True)
            else:
                self._activation_key_entry.set_text("")
                self.enable_activation_key_placeholder(False)

    def _update_http_proxy_ui(self):
        """Update the HTTP proxy configuration part of the spoke."""
        proxy_hostname = self.subscription_request.server_proxy_hostname
        proxy_port = self.subscription_request.server_proxy_port
        proxy_port_set = proxy_port >= 0
        proxy_username = self.subscription_request.server_proxy_user
        proxy_password_secret = self.subscription_request.server_proxy_password
        proxy_password_set = proxy_password_secret.type == SECRET_TYPE_HIDDEN
        self.http_proxy_visible = proxy_hostname or proxy_username or proxy_password_set
        if proxy_hostname:
            proxy_url = proxy_hostname
            if proxy_port_set:
                proxy_url = "{}:{}".format(proxy_url, proxy_port)
            self._http_proxy_location_entry.set_text(proxy_url)
        # HTTP proxy username
        self._http_proxy_username_entry.set_text(proxy_username)
        # HTTP proxy password
        set_in_entry = bool(self._http_proxy_password_entry.get_text())
        secret_type = self.subscription_request.server_proxy_password.type
        set_in_module = secret_type == SECRET_TYPE_HIDDEN
        if set_in_module:
            if not set_in_entry:
                self.enable_http_proxy_password_placeholder(True)
        else:
            self._http_proxy_password_entry.set_text("")
            self.enable_http_proxy_password_placeholder(False)

    def _set_data_to_module(self):
        """Set system purpose data to the DBus module.

        Called either on apply() or right before a subscription
        attempt.
        """
        self._set_system_purpose_data()
        # Set data about Insights to the DBus module.
        self._set_insights()
        # Set subscription request to the DBus module.
        self._set_subscription_request()

    def _get_system_purpose_data(self):
        """Get SystemPurposeData from the Subscription module."""
        struct = self._subscription_module.SystemPurposeData
        return SystemPurposeData.from_structure(struct)

    def _set_system_purpose_data(self):
        """Set system purpose data to the Subscription DBus module."""
        self._subscription_module.SystemPurposeData = \
            SystemPurposeData.to_structure(self.system_purpose_data)

        # also apply the data (only applies when needed)
        self._apply_system_purpose_data()

    def _apply_system_purpose_data(self):
        """Apply system purpose data to the installation environment.

        Apply system purpose data to the installation environment, provided that:
        - system purpose data has not yet been applied to the system
        or
        - current system purpose data is different from the data last applied to the system

        Due to that we keep a copy of the last applied system purpose data so that we can
        check for difference.

        If the last applied data is the same as current system purpose data, nothing is done.
        """
        log.debug("Subscription GUI: applying system purpose data to installation environment")
        task_path = self._subscription_module.SetSystemPurposeWithTask()
        task_proxy = SUBSCRIPTION.get_proxy(task_path)
        sync_run_task(task_proxy)

    def _get_subscription_request(self):
        """Get SubscriptionRequest from the Subscription module."""
        struct = self._subscription_module.SubscriptionRequest
        return SubscriptionRequest.from_structure(struct)

    def _set_subscription_request(self):
        """Set subscription request to the Subscription DBus module."""
        self._subscription_module.SubscriptionRequest = \
            SubscriptionRequest.to_structure(self.subscription_request)

    def _set_insights(self):
        """Configure Insights in DBus module based on GUI state."""
        self._subscription_module.InsightsEnabled = self._insights_checkbox.get_active()

    def _register(self):
        """Try to register a system."""
        # set the registrastion phase right away to provide immediate feedback once the
        # Register button is clicked
        # - otherwise outdated status text might remain displayed for a while
        #   before the background thread gets going
        # - the stale status text might cause confusion to the users
        self.registration_phase = SubscriptionPhase.REGISTER

        # update data in the Subscription DBUS module
        self._set_data_to_module()

        # disable controls
        self.set_registration_controls_sensitive(False)

        # wait for the previous subscription thread to finish
        thread_manager.wait(THREAD_SUBSCRIPTION)

        # check if the current installation source will be overriden
        # and remember it if it is the case
        source_proxy = self.payload.get_source_proxy()
        source_type = source_proxy.Type
        if source_type in SOURCE_TYPES_OVERRIDEN_BY_CDN:
            self._overridden_source_type = source_type
        else:
            # no override will happen, so clear the variable
            self._overridden_source_type = None

        # try to register
        log.debug("Subscription GUI: attempting to register")
        thread_manager.add_thread(
            name=THREAD_SUBSCRIPTION,
            target=register_and_subscribe,
            kwargs={
                "payload": self.payload,
                "progress_callback": self._subscription_progress_callback,
                "error_callback": self._subscription_error_callback,
                "restart_payload": True
            }
        )

    def _unregister(self):
        """Try to unregister a system."""
        # update data in the Subscription DBUS module
        self._set_data_to_module()

        # disable controls
        self.set_registration_controls_sensitive(False)

        # wait for the previous subscription thread to finish
        thread_manager.wait(THREAD_SUBSCRIPTION)

        # try to unregister
        log.debug("Subscription GUI: attempting to unregister")
        thread_manager.add_thread(
            name=THREAD_SUBSCRIPTION,
            target=unregister,
            kwargs={
                "payload": self.payload,
                "overridden_source_type": self._overridden_source_type,
                "progress_callback": self._subscription_progress_callback,
                "error_callback": self._subscription_error_callback,
                "restart_payload": True
            }
        )

    @async_action_wait
    def _subscription_progress_callback(self, phase):
        """Progress handling for subscription thread.

        Used both for both registration + attaching subscription
        and for unregistration.

        NOTE: Using the @async_action_wait decorator as this is
              called from the subscription thread. We need to do
              that as GTK does bad things if non main threads
              interact with it.
        """
        # clear error message from a previous attempt (if any)
        self.registration_error = ""
        # set registration phase
        self.registration_phase = phase

        # set spoke status according to subscription thread phase
        if phase == SubscriptionPhase.DONE:
            log.debug("Subscription GUI: registration & attach done")
            # we are done, clear the phase
            self.registration_phase = None
            # update registration and subscription parts of the spoke
            self._update_registration_state()
            self._update_subscription_state()
            # enable controls
            self.set_registration_controls_sensitive(True)
            # notify hub
            hubQ.send_ready(self.__class__.__name__)
        else:
            # processing still ongoing, set the phase
            self.registration_phase = phase
            # notify hub
            hubQ.send_ready(self.__class__.__name__)
        # update spoke state
        self._update_registration_state()

    @async_action_wait
    def _subscription_error_callback(self, error):
        log.debug("Subscription GUI: registration & attach failed")
        # store the error message
        self.registration_error = str(error)
        # even if we fail, we are technically done,
        # so clear the phase
        self.registration_phase = None
        # update registration and subscription parts of the spoke
        self._update_registration_state()
        self._update_subscription_state()
        # if the error is an instance of multi-org error,
        # fetch organization list & enable org selection
        # checkbox
        if isinstance(error, MultipleOrganizationsError):
            task_path = self._subscription_module.RetrieveOrganizationsWithTask()
            task_proxy = SUBSCRIPTION.get_proxy(task_path)
            async_run_task(task_proxy, self._process_org_list)
        # re-enable controls, so user can try again
        self.set_registration_controls_sensitive(True)
        # notify hub
        hubQ.send_ready(self.__class__.__name__)

    def _process_org_list(self, task_proxy):
        """Process org listing for account.

        Called as an async callback of the organization listing runtime task.

        :param task_proxy: a task
        """
        # finish the task
        task_proxy.Finish()
        # process the organization list
        org_struct_list = unwrap_variant(task_proxy.GetResult())
        org_list = OrganizationData.from_structure_list(org_struct_list)
        # fill the combobox
        self._select_organization_combobox.remove_all()
        # also add a placeholder and make it the active item so it is visible
        self._select_organization_combobox.append("", _("Not Specified"))
        self._select_organization_combobox.set_active_id("")
        for org in org_list:
            self._select_organization_combobox.append(org.id, org.name)
        # show the combobox
        self._enable_org_selection_for_account()

    def _enable_org_selection_for_account(self):
        self._select_organization_label_revealer.set_reveal_child(True)
        self._select_organization_combobox_revealer.set_reveal_child(True)

    def _disable_org_selection_for_account(self):
        """Disable the org selection combobox.

        And also wipe the last used organization id or else it might be used
        for the next registration attempt with a different username,
        triggering confusing authetication failures.
        """
        self._subscription_request.account_organization = ""
        self._select_organization_label_revealer.set_reveal_child(False)
        self._select_organization_combobox_revealer.set_reveal_child(False)

    def _get_status_message(self):
        """Get status message describing current spoke state.

        The registration phase is taken into account (if any)
        as well as possible error state and subscription
        being or not being attached.

        NOTE: This method is used both for the spoke status message
              as well as for the in-spoke status label.
        """
        phase = self.registration_phase
        if phase:
            if phase == SubscriptionPhase.UNREGISTER:
                return _("Unregistering...")
            elif phase == SubscriptionPhase.REGISTER:
                return _("Registering...")
            elif phase == SubscriptionPhase.ATTACH_SUBSCRIPTION:
                return _("Attaching subscription...")
            elif phase == SubscriptionPhase.DONE:
                return _("Subscription attached.")
        elif self.registration_error:
            return _("Registration failed.")
        elif self.subscription_attached:
            if self._subscription_module.IsRegisteredToSatellite:
                return _("Registered to Satellite.")
            else:
                return _("Registered.")
        else:
            return _("Not registered.")

    @async_action_wait
    def _update_registration_state(self):
        """Update state of the registration related part of the spoke.

        Hopefully this method is not too inefficient as it is running basically
        on every keystroke in the username/password/organization/key entry.
        """
        subscription_attached = self.subscription_attached
        if subscription_attached:
            self._main_notebook.set_current_page(self.SUBSCRIPTION_STATUS_PAGE)
        else:
            self._main_notebook.set_current_page(self.REGISTRATION_PAGE)

        # update registration status label
        self._registration_status_label.set_text(self._get_status_message())

        # update button states
        self._update_register_button_state()
        self._update_unregister_button_state()

    @async_action_wait
    def _update_subscription_state(self):
        """Update state of the subscription related part of the spoke.

        Update state of the part of the spoke, that shows data about the
        currently attached subscriptions.
        """
        # top level status label
        if self._subscription_module.IsRegisteredToSatellite:
            self._subscription_status_label.set_text(
                _("The system is registered to a Satellite instance.")
            )
        else:
            self._subscription_status_label.set_text(
                _("The system is registered.")
            )

        # authentication method
        if self.authentication_method == AuthenticationMethod.USERNAME_PASSWORD:
            method_string = _("Registered with account {}").format(
                self.subscription_request.account_username
            )
        else:  # org + key
            method_string = _("Registered with organization {}").format(
                self.subscription_request.organization
            )
        self._method_status_label.set_text(method_string)

        # final syspurpose data

        # role
        final_role_string = _("Role: {}").format(self.system_purpose_data.role)
        self._role_status_label.set_text(final_role_string)

        # SLA
        final_sla_string = _("SLA: {}").format(self.system_purpose_data.sla)
        self._sla_status_label.set_text(final_sla_string)

        # usage
        final_usage_string = _("Usage: {}").format(self.system_purpose_data.usage)
        self._usage_status_label.set_text(final_usage_string)

        # Insights
        # - this strings are referring to the desired target system state,
        #   the installation environment itself is not expected to be
        #   connected to Insights
        if self._subscription_module.InsightsEnabled:
            insights_string = _("Connected to Red Hat Insights")
        else:
            insights_string = _("Not connected to Red Hat Insights")
        self._insights_status_label.set_text(insights_string)

        subscription_string = _("Subscribed in Simple Content Access mode.")
        self._attached_subscriptions_label.set_text(subscription_string)

    def _check_connectivity(self):
        """Check network connectivity is available.

        Network connectivity is required for using the Subscription spoke
        for obvious reasons (eq. for communication with the remote
        Candlepin instance & CDN).

        If network is already available, this method makes the registration
        controls sensitive and clears any previous connectivity warnings.

        If network is not available it makes the registration controls
        insensitive and displays a warning to the user.
        """
        network_connected = self.network_connected
        if network_connected:
            # make controls sensitive, unless processing is ongoing
            self.set_registration_controls_sensitive(True)
            if not self._network_connected_previously:
                # clear previous connectivity warning
                # - we only do this on connectivity state change so that we don't clear
                #   registration error related warnings
                log.debug("Subscription GUI: clearing connectivity warning")
                self.clear_info()
        else:
            # make controls insensitive
            self.set_registration_controls_sensitive(False)
            # set a warning
            log.debug("Subscription GUI: setting connectivity warning")
            self.show_warning_message(
                _("Please enable network access before connecting to Red Hat.")
            )
        # remember state
        self._network_connected_previously = network_connected

    def _update_register_button_state(self):
        """Update register button state.

        The button is only sensitive if no processing is ongoing
        and we either have enough authentication data to register
        or the system is subscribed, so we can unregister it.
        """
        button_sensitive = False
        if self._registration_controls_enabled:
            # if we are subscribed, we can always unregister
            if self.subscription_attached:
                button_sensitive = True
            # check if credentials are sufficient for registration
            elif self.authentication_method == AuthenticationMethod.USERNAME_PASSWORD:
                button_sensitive = username_password_sufficient(self.subscription_request)
            elif self.authentication_method == AuthenticationMethod.ORG_KEY:
                button_sensitive = org_keys_sufficient(self.subscription_request)
        self._register_button.set_sensitive(button_sensitive)

    def _update_unregister_button_state(self):
        """Update unregister button state.

        Make sure the Unregister button follows status of the
        _registration_controls_enabled variable.
        """
        self._unregister_button.set_sensitive(self._registration_controls_enabled)
