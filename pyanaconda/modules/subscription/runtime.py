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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from dasbus.typing import get_variant, Str

from pyanaconda.modules.common.task import Task

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class SetRHSMConfigurationTask(Task):
    """Task for setting configuration to the RHSM service.

    Set configuration options of the RHSM service via it's
    DBus interface, based on the provided SubscriptionRequest
    structure.

    Also in case one of the configuration options was unset,
    restore the key to its original value. This way for example
    a user decides at runtime to use the default server hostname
    or RHSM baseurl, they can just delete the value in the UI,
    triggering the original value to be restored when we encounter
    the empty value for a key that originally was set to
    a non empty value.
    """

    # Keys in the RHSM config key/value store we care about and
    # should be able to restore to original value.
    #
    # NOTE: These keys map 1:1 to rhsm.conf. To see what they do the
    #       best bet is to check the /etc/rhsm/rhsm.conf file on a system
    #       with the subscription-manager package installed. The file
    #       is heavily documented with comment's explaining what
    #       the different keys do.
    CONFIG_KEY_SERVER_HOSTNAME = "server.hostname"
    CONFIG_KEY_SERVER_PROXY_HOSTNAME = "server.proxy_hostname"
    CONFIG_KEY_SERVER_PROXY_PORT = "server.proxy_port"
    CONFIG_KEY_SERVER_PROXY_USER = "server.proxy_user"
    CONFIG_KEY_SERVER_PROXY_PASSWORD = "server.proxy_password"
    CONFIG_KEY_RHSM_BASEURL = "rhsm.baseurl"

    def __init__(self, rhsm_config_proxy, rhsm_config_defaults, subscription_request):
        """Create a new task for setting RHSM configuration.

        :param rhsm_config_proxy: DBus proxy for the RHSM Config object
        :param dict rhsm_config_defaults: a dictionary of original RHSM configuration values
        :param subscription_request: subscription request DBus Structure
        :type subscription_request: SubscriptionRequest instance
        """
        super().__init__()
        self._rhsm_config_proxy = rhsm_config_proxy
        self._request = subscription_request
        self._rhsm_config_defaults = rhsm_config_defaults

    @property
    def name(self):
        return "Set RHSM configuration."

    def run(self):
        log.debug("subscription: setting RHSM config values")
        # We will use the SetAll() dbus method and we need to
        # assemble a dictionary that we will feed to it.
        # Start by preparing a SubscriptionData property mapping
        # to the RHSM config keys.
        #
        # A note about constructing the dict:
        # - DBus API needs all values to be strings, so we need to convert the
        #   port number to string
        # - all values need to be string variants
        # - proxy password is stored in SecretData instance and we need to retrieve
        #   its value
        property_key_map = {
            self.CONFIG_KEY_SERVER_HOSTNAME: self._request.server_hostname,
            self.CONFIG_KEY_SERVER_PROXY_HOSTNAME: self._request.server_proxy_hostname,
            self.CONFIG_KEY_SERVER_PROXY_PORT: str(self._request.server_proxy_port),
            self.CONFIG_KEY_SERVER_PROXY_USER: self._request.server_proxy_user,
            self.CONFIG_KEY_SERVER_PROXY_PASSWORD: self._request.server_proxy_password.value,
            self.CONFIG_KEY_RHSM_BASEURL: self._request.rhsm_baseurl
        }

        # Then process the mapping into the final dict we will set to RHSM. This includes
        # checking if some values have been cleared by the user and should be restored to
        # the original values that have been in the RHSM config before we started
        # manipulating it.
        #
        # Also the RHSM DBus API requires a dict of variants, so we need to provide
        # that as well.
        config_dict = {}
        for key, value in property_key_map.items():
            if value:
                # if value is present in request, use it
                config_dict[key] = get_variant(Str, value)
            else:
                # if no value is present in request, use
                # value from the original RHSM config state
                # (if any)
                log.debug("subscription: restoring original value for RHSM config key %s", key)
                config_dict[key] = get_variant(Str, self._rhsm_config_defaults.get(key, ""))

        # and finally set the dict to RHSM via the DBus API
        self._rhsm_config_proxy.SetAll(config_dict, "")
