# system purpose spoke class
#
# Copyright (C) 2018 Red Hat, Inc.
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
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Pango", "1.0")

from gi.repository import Gtk, Pango

from pyanaconda.threading import threadMgr, AnacondaThread
from pyanaconda.flags import flags
from pyanaconda import subscription

from pyanaconda.core.i18n import _, CN_
from pyanaconda.core.constants import RHSM_AUTH_USERNAME_PASSWORD, RHSM_AUTH_ORG_KEY, RHSM_AUTH_NOT_SELECTED, \
        THREAD_SUBSCRIPTION, INSTALLATION_METHODS_OVERRIDEN_BY_CDN
from pyanaconda.core.util import ProxyString
from pyanaconda.core.async_utils import async_action_wait

from pyanaconda.modules.common.constants.services import SUBSCRIPTION, NETWORK, PAYLOAD
from pyanaconda.modules.common.task import sync_run_task

from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.categories.system import SystemCategory
from pyanaconda.ui.communication import hubQ

from enum import IntEnum

# the integers correspond to the order of options
# in the authentication mode combo box
class AuthenticationMethod(IntEnum):
    USERNAME_PASSWORD = 0
    ORG_KEY = 1

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

__all__ = ["SubscriptionSpoke"]


class SubscriptionSpoke(NormalSpoke):
    """
       .. inheritance-diagram:: SubscriptionSpoke
          :parts: 3
    """
    builderObjects = ["subscription_window"]

    mainWidgetName = "subscription_window"
    uiFile = "spokes/subscription.glade"
    help_id = "SubscriptionSpoke"

    category = SystemCategory

    icon = "application-certificate-symbolic"
    #icon = "subscription-manager"
    title = CN_("GUI|Spoke", "_Connect to Red Hat")

    # main notebook pages
    REGISTRATION_PAGE = 0
    SUBSCRIPTION_STATUS_PAGE = 1

    def __init__(self, *args):
        NormalSpoke.__init__(self, *args)

        # connect to the Subscription DBus module API
        self._subscription_module = SUBSCRIPTION.get_observer()
        self._subscription_module.connect()

        # connect to the Network DBus module API
        self._network_module = NETWORK.get_observer()
        self._network_module.connect()

        # connect to the Payload DBus module API
        self._payload_module = PAYLOAD.get_observer()
        self._payload_module.connect()

        self._authentication_method = AuthenticationMethod.USERNAME_PASSWORD

        self._registration_error = ""
        self._registration_phase = None
        self._registration_controls_enabled = True

        self._initial_activation_key_set = False

        # previous visit network connectivity tracking
        self._network_connected_previously = False

        # overridden installation source method tracking
        self._overridden_method = None

    def initialize(self):
        NormalSpoke.initialize(self)
        self.initialize_start()

        # get object references from the builders
        self._main_notebook = self.builder.get_object("main_notebook")

        ## the registration tab ##

        # container for the main registration controls
        self._registration_grid = self.builder.get_object("registration_grid")

        # authentication
        self._account_radio_button = self.builder.get_object("account_radio_button")
        self._activation_key_radio_button = self.builder.get_object("activation_key_radio_button")

        # authentication - account
        self._account_revealer = self.builder.get_object("account_revealer")
        self._username_entry = self.builder.get_object("username_entry")
        self._password_entry = self.builder.get_object("password_entry")

        # authentication - activation key
        self._activation_key_revealer = self.builder.get_object("activation_key_revealer")
        self._organization_entry = self.builder.get_object("organization_entry")
        self._activation_key_entry = self.builder.get_object("activation_key_entry")

        # system purpose
        self._system_purpose_checkbox = self.builder.get_object("system_purpose_checkbox")
        self._system_purpose_revealer = self.builder.get_object("system_purpose_revealer")
        self._system_purpose_role_combobox = self.builder.get_object("system_purpose_role_combobox")
        self._system_purpose_sla_combobox = self.builder.get_object("system_purpose_sla_combobox")
        self._system_purpose_usage_combobox = self.builder.get_object("system_purpose_usage_combobox")

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
        self._custom_rhsm_baseurl_checkbox = self.builder.get_object("custom_rhsm_baseurl_checkbox")
        self._custom_rhsm_baseurl_revealer = self.builder.get_object("custom_rhsm_baseurl_revealer")
        self._custom_rhsm_baseurl_entry = self.builder.get_object("custom_rhsm_baseurl_entry")

        # server hostname
        self._custom_server_hostname_checkbox = self.builder.get_object("custom_server_hostname_checkbox")
        self._custom_server_hostname_revealer = self.builder.get_object("custom_server_hostname_revealer")
        self._custom_server_hostname_entry = self.builder.get_object("custom_server_hostname_entry")

        # status label
        self._registration_status_label = self.builder.get_object("registration_status_label")

        # register button
        self._register_button = self.builder.get_object("register_button")

        ## the subscription status tab ##

        # general status
        self._method_status_label = self.builder.get_object("method_status_label")
        self._role_status_label = self.builder.get_object("role_status_label")
        self._sla_status_label = self.builder.get_object("sla_status_label")
        self._usage_status_label = self.builder.get_object("usage_status_label")
        self._insights_status_label = self.builder.get_object("insights_status_label")

        # attached subscriptions
        self._attached_subscriptions_label = self.builder.get_object("attached_subscriptions_label")
        self._subscriptions_listbox = self.builder.get_object("subscriptions_listbox")

        # unregister button
        self._unregister_revealer = self.builder.get_object("unregister_revealer")
        self._unregister_button = self.builder.get_object("unregister_button")


        # setup spoke state based on Subscription DBus module state

        # check if HTTP proxy data has been set
        proxy_hostname = self._subscription_module.proxy.ServerProxyHostname
        proxy_port = self._subscription_module.proxy.ServerProxyPort
        proxy_port_set = proxy_port >= 0
        proxy_username = self._subscription_module.proxy.ServerProxyUser
        proxy_password_set = self._subscription_module.proxy.ServerProxyPasswordSet
        if proxy_hostname or proxy_username or proxy_password_set:
            if proxy_hostname:
                proxy_url = proxy_hostname
                if proxy_port_set:
                    proxy_url = "{}:{}".format(proxy_url, proxy_port)
                self.http_proxy_location = proxy_url
            self.http_proxy_username = proxy_username
            self.show_http_proxy_password_placeholder = proxy_password_set

        # check if custom server hostname has been set
        custom_server_hostname = self._subscription_module.proxy.ServerHostname
        if custom_server_hostname:
            # set the server hostname combo box content
            self._custom_server_hostname_checkbox.set_active(True)
            # make the custom hostname entry visible
            self.custom_server_hostname_visible = True
            # set the custom server hostname string to the entry
            self.custom_server_hostname = custom_server_hostname

        # rhsm baseurl
        custom_rhsm_baseurl = self._subscription_module.proxy.RHSMBaseurl
        if custom_rhsm_baseurl:
            # check the RHSM baseurl checkbox
            self._custom_rhsm_baseurl_checkbox.set_active(True)
            # make the RHSM baseurl entry field visible
            self.custom_rhsm_baseurl_visible = True
            # set the custom RHSM baseurl to the entry
            self.custom_rhsm_baseurl = custom_rhsm_baseurl

        # authentication method
        auth_method = self._subscription_module.proxy.AuthenticationMethod
        if auth_method == RHSM_AUTH_USERNAME_PASSWORD:
            self.authentication_method = AuthenticationMethod.USERNAME_PASSWORD
            self._account_radio_button.set_active(True)
        elif auth_method == RHSM_AUTH_ORG_KEY:
            self.authentication_method = AuthenticationMethod.ORG_KEY
            self._activation_key_radio_button.set_active(True)
            self.organization = self._subscription_module.proxy.Organization
            if self.activation_key_set:
                self.show_activation_key_placeholder = True
        elif auth_method == RHSM_AUTH_NOT_SELECTED:
            # configure based on GUI state
            if self._account_radio_button.get_active():
                self.authentication_method = AuthenticationMethod.USERNAME_PASSWORD
            else:
                self.authentication_method = AuthenticationMethod.ORG_KEY
        else:
            log.warning("Unknown authentication method: %s", auth_method)

        # check if some System Purpose data has been set
        if self._subscription_module.proxy.IsSystemPurposeSet:
            # check the "Set System Purpose" checkbox
            self._system_purpose_checkbox.set_active(True)
            # make the System Purpose combo boxes visible
            self.system_purpose_visible = True

        # role
        self._fill_combobox(self._system_purpose_role_combobox,
                            self._subscription_module.proxy.Role,
                            self._subscription_module.proxy.ValidRoles)
        # SLA
        self._fill_combobox(self._system_purpose_sla_combobox,
                            self._subscription_module.proxy.SLA,
                            self._subscription_module.proxy.ValidSLAs)
        # usage
        self._fill_combobox(self._system_purpose_usage_combobox,
                            self._subscription_module.proxy.Usage,
                            self._subscription_module.proxy.ValidUsageTypes)


        # Insights
        # If we have a kickstart, use the value from the module, otherwise keep the
        # default from the GUI in place.
        if flags.automatedInstall:
            self._insights_checkbox.set_active(self._subscription_module.proxy.InsightsEnabled)

        # if there is something set in the Options section, expand the expander
        if self.options_set:
            self.options_visible = True

        # wait for subscription thread to finish (if any)
        threadMgr.wait(THREAD_SUBSCRIPTION)

        # update overall state
        self._update_registration_state()
        self._update_subscription_state()

        # Send ready signal to main event loop
        hubQ.send_ready(self.__class__.__name__, False)

        # report that we are done
        self.initialize_done()

    def _get_status_message(self):
        """Get status message describing current spoke state.

        The registration phase is taken into account (if any)
        as well as possible error state and subscription
        being or not being attached.
        """
        phase = self.registration_phase
        if phase:
            if phase == subscription.SubscriptionPhase.UNREGISTER:
                return _("Unregistering...")
            elif phase == subscription.SubscriptionPhase.REGISTER:
                return _("Registering...")
            elif phase == subscription.SubscriptionPhase.ATTACH:
                return _("Attaching subscription...")
            elif phase == subscription.SubscriptionPhase.DONE:
                return _("Subscription attached.")
        elif self.registration_error:
            return _("Registration failed.")
        elif self.subscription_attached:
            return _("Registered.")
        else:
            return _("Not registered.")

    def _restart_payload(self):
        log.debug("Subscription GUI: restarting payload thread")
        from pyanaconda.payload import payloadMgr
        payloadMgr.restartThread(self.storage, self.data, self.payload, self.instclass,
                                 fallback=False, checkmount=False, onlyOnChange=False)

    @async_action_wait
    def _subscription_progress_callback(self, phase):
        # clear error message from a previous attempt (if any)
        self.registration_error = ""
        # set registration phase
        self.registration_phase = phase

        # set spoke status according to subscription thread phase
        if phase == subscription.SubscriptionPhase.DONE:
            log.debug("Subscription GUI: registration & attach done")
            # we are done, clear the phase
            self.registration_phase = None
            # check if an installation method is set that the
            # Red Hat CDN should override
            method_set = self.data.method.method is not None

            can_override_method = self.data.method.method in INSTALLATION_METHODS_OVERRIDEN_BY_CDN
            if method_set and can_override_method:
                log.debug("Subscription GUI: Overriding installation method %s by Red Hat CDN",
                          self.data.method.method)
                # remember what method we have overridden
                self._overridden_method = self.data.method.method
                # override it
                self.data.method.method = None
            # set CDN as installation source
            self._payload_module.proxy.SetRedHatCDNEnabled(True)
            # restart payload
            self._restart_payload()
            # refresh subscription state
            self._update_subscription_state()
            # enable controls
            self.set_registration_controls_sensitive(True)
            # notify hub
            hubQ.send_ready(self.__class__.__name__, False)
        else:
            # processing still ongoing, set the phase
            self.registration_phase = phase
            # notify hub
            hubQ.send_ready(self.__class__.__name__, False)
        # update spoke state
        self._update_registration_state()

    @async_action_wait
    def _subscription_error_callback(self, error_message):
        log.debug("Subscription GUI: registration & attach failed")
        # store the error message
        self.registration_error = error_message
        # even if we fail, we are technically done,
        # so clear the phase
        self.registration_phase = None
        # restart payload
        self._restart_payload()
        # update spoke state
        self._update_registration_state()
        # re-enable controls, so user can try again
        self.set_registration_controls_sensitive(True)
        # notify hub
        hubQ.send_ready(self.__class__.__name__, False)

    def _fill_combobox(self, combobox, user_provided_value, valid_values):
        """Fill the given combobox with data based on current value & valid values.

        Please note that it is possible that the list box will be empty if no
        list of valid values are available and the user has not supplied any value
        via kickstart or the DBUS API.

        :param combobox: the combobox to fill
        :param user_provided_value: the value provided by the user (if any)
        :type user_provided_value: str or None
        :param list valid_values: list of known valid values
        """
        preselected_value_list = self._handle_user_provided_value(user_provided_value,
                                                                  valid_values)

        # add the "Not Specified" option as the first item
        # - otherwise the user would not be able to unselect option clicked previously
        #   or selected via kickstart
        # - set the active id to this value by default

        active_id = ""
        combobox.append("", _("Not Specified"))

        if preselected_value_list:
            for value, display_string, preselected in preselected_value_list:
                combobox.append(value, display_string)
                # the value has been preselected, set the active id accordingly
                if preselected:
                    active_id = value

        # set the active id (what item should be selected in the combobox)
        combobox.set_active_id(active_id)

    def _handle_user_provided_value(self, user_provided_value, valid_values):
        """Handle user provided value (if any) based on list of valid values.

        There are three possible outcomes:
        - the value matches one of the valid values, so we preselect the valid value
        - the value does not match a valid value, so we append a custom value
          to the list and preselect it
        - the user provided value is not available (empty string), no matching will be done
          and no value will be preselected

        :param str user_provided_value: a value provided by user
        :param list valid_values: a list of valid values
        :returns: list of values with one value preselected
        :rtype: list of (str, str, bool) tuples in (<value>, <display string>, <is_preselected>) format
        """
        preselected_value_list = []
        value_matched = False
        for valid_value in valid_values:
            preselect = False
            if user_provided_value and not value_matched:
                if user_provided_value == valid_value:
                    preselect = True
                    value_matched = True
            preselected_value_list.append((valid_value, valid_value, preselect))
        # check if the user provided value matched a valid value
        if user_provided_value and not value_matched:
            # user provided value did not match any valid value,
            # add it as a custom value to the list and preselect it
            other_value_string = _("Other ({})").format(user_provided_value)
            preselected_value_list.append((user_provided_value, other_value_string, True))
        return preselected_value_list

    # Signal handlers

    def on_http_proxy_checkbox_toggled(self, checkbox):
        self.http_proxy_visible = checkbox.get_active()

    def on_custom_server_hostname_checkbox_toggled(self, checkbox):
        self.custom_server_hostname_visible = checkbox.get_active()

    def on_custom_rhsm_baseurl_checkbox_toggled(self, checkbox):
        self.custom_rhsm_baseurl_visible = checkbox.get_active()

    def on_account_radio_button_toggled(self, radio):
        if radio.get_active():
            self.authentication_method = AuthenticationMethod.USERNAME_PASSWORD

    def on_activation_key_radio_button_toggled(self, radio):
        if radio.get_active():
            self.authentication_method = AuthenticationMethod.ORG_KEY

    def on_auth_entry_changed(self, editable):
        """This signal is triggered change in any authetication entry.

        If the username, password, organization or activation key text entry
        content changes, this signal will emitted.
        """
        self._update_registration_state()

    def on_activation_key_entry_changed(self, editable):
        entered_text = editable.get_text()
        if entered_text:
            self.show_activation_key_placeholder = False

    def on_system_purpose_checkbox_toggled(self, checkbox):
        self.system_purpose_visible = checkbox.get_active()

    def on_register_button_clicked(self, button):
        log.debug("Subscription GUI: register button clicked")
        self._register()

    def on_unregister_button_clicked(self, button):
        """Handle registration related tasks."""
        log.debug("Subscription GUI: unregister button clicked")
        self._unregister()

    def refresh(self):
        self._update_registration_state()
        self._update_subscription_state()
        # no need to check connectivity if registration
        # process is ongoing
        if not self.registration_phase:
            self._check_connectivity()

    # properties - visibility of options that can be hidden

    @property
    def custom_server_hostname_visible(self):
        return self._custom_server_hostname_revealer.get_reveal_child()

    @custom_server_hostname_visible.setter
    def custom_server_hostname_visible(self, visible):
        self._custom_server_hostname_revealer.set_reveal_child(visible)

    @property
    def http_proxy_visible(self):
        return self._http_proxy_revealer.get_reveal_child()

    @http_proxy_visible.setter
    def http_proxy_visible(self, visible):
        self._http_proxy_revealer.set_reveal_child(visible)

    @property
    def custom_rhsm_baseurl_visible(self):
        return self._custom_rhsm_baseurl_revealer.get_reveal_child()

    @custom_rhsm_baseurl_visible.setter
    def custom_rhsm_baseurl_visible(self, visible):
        self._custom_rhsm_baseurl_revealer.set_reveal_child(visible)

    @property
    def account_visible(self):
        return self._account_revealer.get_reveal_child()

    @account_visible.setter
    def account_visible(self, visible):
        self._account_revealer.set_reveal_child(visible)

    @property
    def activation_key_visible(self):
        return self._activation_key_revealer.get_reveal_child()

    @activation_key_visible.setter
    def activation_key_visible(self, visible):
        self._activation_key_revealer.set_reveal_child(visible)

    @property
    def system_purpose_visible(self):
        return self._system_purpose_revealer.get_reveal_child()

    @system_purpose_visible.setter
    def system_purpose_visible(self, visible):
        self._system_purpose_revealer.set_reveal_child(visible)

    @property
    def options_visible(self):
        return self._options_expander.get_expanded()

    @options_visible.setter
    def options_visible(self, visible):
        self._options_expander.set_expanded(visible)

    # properties - element sensitivity

    def set_registration_controls_sensitive(self, sensitive, include_register_button=True):
        """Set sensitivity of the registration controls.

        We set these value individually so that the registration status label
        that is between the controls will not become grayed out due to setting
        the top level container insensitive.
        """
        self._registration_grid.set_sensitive(sensitive)
        self._options_expander.set_sensitive(sensitive)
        self._registration_controls_enabled = sensitive
        self._update_registration_state()

    # properties - mirroring entries

    @property
    def custom_server_hostname(self):
        return self._custom_server_hostname_entry.get_text()

    @custom_server_hostname.setter
    def custom_server_hostname(self, hostname):
        self._custom_server_hostname_entry.set_text(hostname)

    @property
    def custom_server_hostname_set(self):
        # even if custom server hostname is set, this can be overridden by the server combobox
        return self._custom_server_hostname_checkbox.get_active()

    @property
    def http_proxy_location(self):
        return self._http_proxy_location_entry.get_text()

    @http_proxy_location.setter
    def http_proxy_location(self, location):
        self._http_proxy_location_entry.set_text(location)

    @property
    def http_proxy_username(self):
        return self._http_proxy_username_entry.get_text()

    @http_proxy_username.setter
    def http_proxy_username(self, username):
        self._http_proxy_username_entry.set_text(username)

    @property
    def http_proxy_password(self):
        return self._http_proxy_password_entry.get_text()

    @http_proxy_password.setter
    def http_proxy_password(self, password):
        self._http_proxy_password_entry.set_text(password)

    @property
    def http_proxy_password_set(self):
        """Report if the HTTP proxy password has been set.

        We need this separate property, because the
        Subscription DBUS module API on purpose does
        not provide the plaintext of the HTTP proxy password
        once it has been set. Therefore we only know
        a password has been set via kickstart or
        the DBUS API, but can't get its plaintext.

        Thus we have this property to check if a HTTP proxy
        password has been set.
        """
        return self.http_proxy_password or self._subscription_module.proxy.ServerProxyPasswordSet

    @property
    def show_http_proxy_password_placeholder(self):
        """Show a placeholder on the HTTP proxy password field.

        The placeholder notifies the user about HTTP proxy password
        being set in the DBus module.

        The placeholder will be only shown if there is no
        actual text in the entry field.
        """
        return bool(self._http_proxy_password_entry.get_placeholder_text())

    @show_http_proxy_password_placeholder.setter
    def show_http_proxy_password_placeholder(self, show_placeholder):
        if show_placeholder:
            self._http_proxy_password_entry.set_placeholder_text(_("Password set."))
        else:
            self._http_proxy_password_entry.set_placeholder_text("")

    @property
    def http_proxy_set(self):
        # we consider the HTTP proxy data as set only if the corresponding checkbox is checked
        return self._http_proxy_checkbox.get_active()

    @property
    def custom_rhsm_baseurl(self):
        return self._custom_rhsm_baseurl_entry.get_text()

    @custom_rhsm_baseurl.setter
    def custom_rhsm_baseurl(self, baseurl):
        self._custom_rhsm_baseurl_entry.set_text(baseurl)

    @property
    def custom_rhsm_baseurl_set(self):
        # we consider the custom RHSM baseurl as set only if the corresponding checkbox is checked
        return self._custom_rhsm_baseurl_checkbox.get_active()

    @property
    def username(self):
        """Red Hat account login."""
        return self._username_entry.get_text()

    @property
    def password(self):
        """Red Hat account password."""
        return self._password_entry.get_text()

    @property
    def organization(self):
        """Organization name."""
        return self._organization_entry.get_text()

    @organization.setter
    def organization(self, organization):
        self._organization_entry.set_text(organization)

    @property
    def activation_keys(self):
        """Activation keys.

        :return: list of activation keys
        :rtype: list of str
        """
        return self._activation_key_entry.get_text().split(',')

    @activation_keys.setter
    def activation_keys(self, activation_keys):
        """Set activation keys.

        :param activation_keys: activation keys
        :type activation_keys: list of str
        """
        self._activation_key_entry.set_text(",".join(activation_keys))

    @property
    def activation_key_set(self):
        """Report if at least one activation key has been set.

        We need this separate property, because the
        Subscription DBUS module API on purpose does
        not provide the plaintext of the activation key
        once it has been set. Therefore we only know
        an activation key has been set via kickstart or
        the DBUS API, but can't get its plaintext.

        Thus we have this property to check if an activation
        key has been set.
        """
        return self.activation_keys or self._subscription_module.proxy.IsActivationKeySet

    @property
    def show_activation_key_placeholder(self):
        """Show a placeholder on the activation key field.

        The placeholder notifies the user about activation
        key being set in the DBus module.

        The placeholder will be only shown if there is no
        actual text in the entry field.
        """
        return bool(self._activation_key_entry.get_placeholder_text())

    @show_activation_key_placeholder.setter
    def show_activation_key_placeholder(self, show_placeholder):
        if show_placeholder:
            self._activation_key_entry.set_placeholder_text(_("Activation key set."))
        else:
            self._activation_key_entry.set_placeholder_text("")

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
        return self._subscription_module.proxy.IsSubscriptionAttached

    @property
    def network_connected(self):
        """Does it look like that we have network connectivity ?

        Network connectivity is required for subscribing a system.
        """
        return self._network_module.proxy.Connected

    @property
    def authentication_method(self):
        """Report which authentication method is in use."""
        return self._authentication_method

    @authentication_method.setter
    def authentication_method(self, method):
        self._authentication_method = method
        # set visibility of activation key
        if method == AuthenticationMethod.USERNAME_PASSWORD:
            self.activation_key_visible = False
            self.account_visible = True
        elif method == AuthenticationMethod.ORG_KEY:
            self.activation_key_visible = True
            self.account_visible = False
        else:
            log.warning("Unknown authentication method: %s", method)

    @property
    def options_set(self):
        """Report if at least one option in the Options section has been set."""
        return self.http_proxy_set or self.custom_server_hostname_set or self.custom_rhsm_baseurl_set


    @property
    def registration_error(self):
        return self._registration_error

    @registration_error.setter
    def registration_error(self, error_message):
        self._registration_error = error_message
        # also set the spoke warning banner
        self.show_warning_message(error_message)

    @property
    def ready(self):
        """The subscription spoke is always ready."""
        return True

    @property
    def status(self):
        return self._get_status_message()

    @property
    def mandatory(self):
        """The subscription spoke is mandatory if Red Hat CDN is set as installation source."""
        return self._payload_module.proxy.RedHatCDNEnabled

    def apply(self):
        log.debug("Subscription GUI: apply(): running")
        # Set System Purpose data to the Subscription DBus module,
        # it makes sense to send the rest only right before a
        # registration attempt.
        self._set_system_purpose_data_to_subscription_module()

    @property
    def completed(self):
        return self.subscription_attached

    @property
    def sensitive(self):
        # the system purpose spoke should be always accessible
        return True

    def _check_connectivity(self):
        """Check network connectivity is available."""
        network_connected = self.network_connected
        if network_connected:
            # make controls sensitive, unless processing is ongoing
            self.set_registration_controls_sensitive(True)
            if not self._network_connected_previously:
                # clear previous warning
                # - we only do this on connectivity state change so that we don't clear
                #   registration error related warnings
                log.debug("Subscription GUI: clearing connectivity warning")
                self.clear_info()
        else:
            # make controls insensitive
            self.set_registration_controls_sensitive(False)
            # set a warning
            log.debug("Subscription GUI: setting connectivity warning")
            self.show_warning_message(_("Please enable network access before connecting to Red Hat."))
        # remember state
        self._network_connected_previously = network_connected

    def _update_register_button_state(self):
        """Update register button state."""
        if self._registration_controls_enabled:
            # check if credentials are sufficient for registration
            if self.authentication_method == AuthenticationMethod.USERNAME_PASSWORD:
                if self.username and self.password:
                    button_sensitive = True
                else:
                    button_sensitive = False
            elif self.authentication_method == AuthenticationMethod.ORG_KEY:
                if self.organization and self.activation_key_set:
                    button_sensitive = True
                else:
                    button_sensitive = False
            self._register_button.set_sensitive(button_sensitive)
        else:
            self._register_button.set_sensitive(False)

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

        # update registration button state
        self._update_register_button_state()

    def _update_subscription_state(self):
        """Update state of the subscription related part of the spoke.

        Update state of the part of the spoke, that shows data about the
        currently attached subscriptions.
        """
        log.debug("UPDATE SUBSCRIPTION STATE RUNNING")
        # authentication method
        if self.authentication_method == AuthenticationMethod.USERNAME_PASSWORD:
            method_string = _("Registered with account {}").format(self.username)
        else:  # org + key
            method_string = _("Registered with organization {}").format(self.organization)
        self._method_status_label.set_text(method_string)
        # final role
        final_role_string = _("Role: {}").format(self._subscription_module.proxy.Role)
        self._role_status_label.set_text(final_role_string)
        # final SLA
        final_sla_string = _("SLA: {}").format(self._subscription_module.proxy.SLA)
        self._sla_status_label.set_text(final_sla_string)
        # final usage
        final_usage_string = ("Usage: {}").format(self._subscription_module.proxy.Usage)
        self._usage_status_label.set_text(final_usage_string)
        # Insights
        # - this strings are referring to the desired target system state,
        #   the installation environment itself is not expected to be
        #   connected to Insights
        if self._subscription_module.proxy.InsightsEnabled:
            insights_string = _("Connected to Red Hat Insights")
        else:
            insights_string = _("Not connected to Red Hat Insights")
        self._insights_status_label.set_text(insights_string)
        # attached subscriptions
        attached_subscriptions = self._subscription_module.proxy.AttachedSubscriptions
        log.debug("GUI ATTACHED SUBSCRIPTIONS")
        log.debug(self._subscription_module.proxy.AttachedSubscriptions)
        log.debug(attached_subscriptions)
        log.debug(len(attached_subscriptions))

        subscription_count = len(attached_subscriptions)

        if subscription_count == 0:
            subscription_string = _("No subscriptions are attached to the system")
        elif subscription_count == 1:
            subscription_string = _("1 subscription attached to the system")
        else:
            subscription_string = _("{} subscriptions attached to the system").format(subscription_count)

        self._attached_subscriptions_label.set_text(subscription_string)
        # populate the attached subscriptions listbox
        self._populate_attached_subscriptions_listbox(attached_subscriptions)

    def _populate_attached_subscriptions_listbox(self, attached_subscriptions):
        """Populate the attached subscription listbox with delegates.

        Unfortunately it does not seem to be possible to create delegate templates
        that could be reused for each data item in the listbox via Glade, so
        we need to construct them imperatively via Python GTK API.
        """
        log.debug("Subscription GUI: populating attached subscriptions listbox")

        # start by making sure the listbox is empty
        def clear_listbox(listbox):
            for child in listbox.get_children():
                listbox.remove(child)
                del(child)

        clear_listbox(self._subscriptions_listbox)

        # add one delegate per attached subscription
        delegate_index = 0
        for sdict in attached_subscriptions:
            self._add_attached_subscription_delegate(sdict, delegate_index)
            delegate_index = delegate_index + 1

        # Make sure the delegates are actually visible after the listbox has been cleared.
        # Without show_all() nowthing would be visible past first clear.
        self._subscriptions_listbox.show_all()

        log.debug("Subscription GUI: attached subscriptions listbox has been populated")

    def _add_attached_subscription_delegate(self, sdict, delegate_index):
        log.debug("Subscription GUI: adding subscription to listbox: %s", sdict["name"])
        # if we are not the first delegate, we should pre-pend a spacer, so that the
        # actual delegates are nicely delimitted
        if delegate_index != 0:
            row = Gtk.ListBoxRow()
            row.set_name("subscriptions_listbox_row_spacer")
            row.set_margin_top(4)
            self._subscriptions_listbox.insert(row, -1)

        # construct delegate
        row = Gtk.ListBoxRow()
        # set a name so that the ListBoxRow instance can be styled via CSS
        row.set_name("subscriptions_listbox_row")

        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        main_vbox.set_margin_top(12)
        main_vbox.set_margin_bottom(12)

        name_label = Gtk.Label(label='<span size="x-large">{}</span>'.format(sdict["name"]),
                     use_markup=True, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR,
                     hexpand=True, xalign=0, yalign=0.5)
        name_label.set_margin_start(12)
        name_label.set_margin_bottom(12)

        # create the first details grid
        details_grid_1 = Gtk.Grid()
        details_grid_1.set_column_spacing(12)
        details_grid_1.set_row_spacing(12)
 
        # first column
        service_level_label = Gtk.Label(label="<b>{}</b>".format(_("Service level")),
                                        use_markup=True, xalign=0)
        service_level_status_label = Gtk.Label(label=sdict["service_level"])
        sku_label = Gtk.Label(label="<b>{}</b>".format(_("SKU")),
                              use_markup=True, xalign=0)
        sku_status_label = Gtk.Label(label=sdict["sku"], xalign=0)
        contract_label = Gtk.Label(label="<b>{}</b>".format(_("Contract")),
                                   use_markup=True, xalign=0)
        contract_status_label = Gtk.Label(label=sdict["contract"], xalign=0)

        # add first column to the grid
        details_grid_1.attach(service_level_label, 0, 0, 1, 1)
        details_grid_1.attach(service_level_status_label, 1, 0, 1, 1)
        details_grid_1.attach(sku_label, 0, 1, 1, 1)
        details_grid_1.attach(sku_status_label, 1, 1, 1, 1)
        details_grid_1.attach(contract_label, 0, 2, 1, 1)
        details_grid_1.attach(contract_status_label, 1, 2, 1, 1)

        # second column
        start_date_label = Gtk.Label(label="<b>{}</b>".format(_("Start date")),
                                     use_markup=True, xalign=0)
        start_date_status_label = Gtk.Label(label=sdict["start_date"], xalign=0)
        end_date_label = Gtk.Label(label="<b>{}</b>".format(_("End date")),
                                   use_markup=True, xalign=0)
        end_date_status_label = Gtk.Label(label=sdict["end_date"], xalign=0)
        entitlements_label = Gtk.Label(label="<b>{}</b>".format(_("Entitlements")),
                                       use_markup=True, xalign=0)
        entitlement_string = _("{} consumed").format(sdict["consumed_entitlement_count"])
        entitlements_status_label = Gtk.Label(label=entitlement_string, xalign=0)

        # create the second details grid
        details_grid_2 = Gtk.Grid()
        details_grid_2.set_column_spacing(12)
        details_grid_2.set_row_spacing(12)

        # add second column to the grid
        details_grid_2.attach(start_date_label, 0, 0, 1, 1)
        details_grid_2.attach(start_date_status_label, 1, 0, 1, 1)
        details_grid_2.attach(end_date_label, 0, 1, 1, 1)
        details_grid_2.attach(end_date_status_label, 1, 1, 1, 1)
        details_grid_2.attach(entitlements_label, 0, 2, 1, 1)
        details_grid_2.attach(entitlements_status_label, 1, 2, 1, 1)

        details_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        details_hbox.pack_start(details_grid_1, True, True, 12)
        details_hbox.pack_start(details_grid_2, True, True, 0)

        main_vbox.pack_start(name_label, True, True, 0)
        main_vbox.pack_start(details_hbox, True, True, 0)

        row.add(main_vbox)

        # append delegate to listbox
        self._subscriptions_listbox.insert(row, -1)

    def _set_system_purpose_data_to_subscription_module(self):
        """Set system purpose data to the Subscription DBus module.

        This is separate from the general purpose set data method
        as we should always set syspurpose data on spoke exit yet
        the general function runs only before registration attempts.

        If system purpose data was only set on registration attempt,
        we would break the backwards compatiblity assumption that
        one should be able to set system purpose data without
        registration.

        So we have this syspurpose specific method that is called on
        apply & before registration attempts.
        """
        log.debug("Subscription GUI: setting System Purpose data to Subscription DBUS module")
        self._subscription_module.proxy.SetRole(self._system_purpose_role_combobox.get_active_id())
        self._subscription_module.proxy.SetSLA(self._system_purpose_sla_combobox.get_active_id())
        self._subscription_module.proxy.SetUsage(self._system_purpose_usage_combobox.get_active_id())

    def _set_data_to_subscription_module(self):
        """Apply authentication data on the DBUS module.

        NOTE: We do not have to handle System Purpose and
              Insights here as both are set immediately
              when interacted with in the GUI.
        """
        log.debug("Subscription GUI: setting data to Subscription DBUS module")

        # authentication data - only set the currently selected authentication method
        # & only if not already registered.
        if not self.subscription_attached:
            if self.authentication_method == AuthenticationMethod.USERNAME_PASSWORD:
                self._subscription_module.proxy.SetAccountUsername(self.username)
                self._subscription_module.proxy.SetAccountPassword(self.password)
            elif self.authentication_method == AuthenticationMethod.ORG_KEY:
                self._subscription_module.proxy.SetOrganization(self.organization)
                # Prevent the kickstart set activation key from being overwritten by
                # empty value from the GUI by checking if there is a placeholder set
                # for the activation key field. If there is a placeholder, it means
                # a key has been set in the DBus module and not yet overwritten
                # by the user.
                if not self.show_activation_key_placeholder:
                    self._subscription_module.proxy.SetActivationKeys(self.activation_keys)

        # set current authentication method
        self._subscription_module.proxy.SetAuthenticationMethod(self.authentication_method)

        # Insights
        self._subscription_module.proxy.SetInsightsEnabled(self._insights_checkbox.get_active())

        # HTTP proxy
        hostname = ""
        port = -1
        username = ""
        password = ""
        # We set actual HTTP proxy data only if the proxy checkbox is set
        # and some valid loking data has been entered. Otherwise we set
        # empty values, which are either a no-op or clear previous input.
        if self.http_proxy_set and self.http_proxy_location:
            # gather data
            proxy_obj = ProxyString(url=self.http_proxy_location)
            hostname = proxy_obj.host
            port = proxy_obj.port
            if port:
                # the DBus API expects an integer
                port = int(port)
            else:
                # if no port is specified, set the value to -1
                port = -1
            username = self.http_proxy_username
            password = self.http_proxy_password

        # set proxy values to module/clear previous values
        self._subscription_module.proxy.SetServerProxy(hostname, port, username, password)

        # custom URL
        self._subscription_module.proxy.SetServerHostname(self.custom_server_hostname)

        # custom RHSM baseurl
        self._subscription_module.proxy.SetRHSMBaseurl(self.custom_rhsm_baseurl)

    def _register(self):
        """Try to register a system."""
        # update data in the Subscription DBUS module
        self._set_system_purpose_data_to_subscription_module()
        self._set_data_to_subscription_module()

        # disable controls
        self.set_registration_controls_sensitive(False)

        # try to register
        log.debug("Subscription GUI: attempting to register")
        threadMgr.add(AnacondaThread(name=THREAD_SUBSCRIPTION,
                                     target=subscription.subscribe,
                                     args=(self._subscription_progress_callback,
                                           self._subscription_error_callback)))

    def _unregister(self):
        """Try to unregister a system."""
        # update data in the Subscription DBUS module
        self._set_data_to_subscription_module()

        # try to unregister
        # - the unregister operation seems to be fast & we need to stay in the spoke
        #   anyway, so we don't run unregister in a thread
        log.debug("Subscription GUI: attempting to unregister")
        task_path = self._subscription_module.proxy.UnregisterWithTask()
        task_proxy = SUBSCRIPTION.get_proxy(task_path)
        sync_run_task(task_proxy)
        error = task_proxy.Error
        if error:
            log.debug("Subscription GUI: unregistration failed: %s", error)
            self.registration_error = error
        else:
            log.debug("Subscription GUI: unregistration succeeded")
            # success, clear any previous errors
            self.registration_error = ""
            # disable CDN usage, as we can no longer use it without registration
            self._payload_module.proxy.SetRedHatCDNEnabled(False)
            # if a URL has been set previously, switch method back to "url"
            if hasattr(self.data.method, "url") and self.data.method.url:
                log.debug("Subscription GUI: switching source back to URL")
                self.data.method.method = "url"
            # check for overridden methods as well
            elif self._overridden_method:
                self.data.method.method = self._overridden_method
                # clear overridden method tracking
                self._overridden_method = None
            # update subscription status tab
            self._update_registration_state()

        # restart the payload
        self._restart_payload()

        # update the registration tab
        self._update_registration_state()
