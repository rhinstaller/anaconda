#
# DBus structures for subscription related data.
#
# Copyright (C) 2020  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
from dasbus.structure import DBusData
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.core.constants import DEFAULT_SUBSCRIPTION_REQUEST_TYPE
from pyanaconda.modules.common.structures.secret import SecretData, SecretDataList

__all__ = ["SubscriptionRequest", "SystemPurposeData"]

class SystemPurposeData(DBusData):
    """System purpose data."""

    def __init__(self):
        self._role = ""
        self._sla = ""
        self._usage = ""
        self._addons = []

    @property
    def role(self) -> Str:
        """Return the System Purpose role (if any).

        :return: system purpose role
        """
        return self._role

    @role.setter
    def role(self, role: Str):
        self._role = role

    @property
    def sla(self) -> Str:
        """Return the System Purpose SLA (if any).

        :return: system purpose SLA
        """
        return self._sla

    @sla.setter
    def sla(self, sla: Str):
        self._sla = sla

    @property
    def usage(self) -> Str:
        """Return the System Purpose usage (if any).

        :return: system purpose usage
        """
        return self._usage

    @usage.setter
    def usage(self, usage: Str):
        self._usage = usage

    @property
    def addons(self) -> List[Str]:
        """Return list of additional layered products or features (if any).

        :return: system purpose addons
        """
        return self._addons

    @addons.setter
    def addons(self, addons: List[Str]):
        self._addons = addons

    def check_data_available(self):
        """A helper function used to determining if some system purpose data is available.

        Otherwise we would have to query all the fields each time we want to check if we
        have any system purpose data available.

        :return: is any system purpose data is available
        :rtype: bool
        """
        return any((self.role, self.sla, self.usage, self.addons))

    def __eq__(self, other_instance):
        """Used to determining if other SystemPurposeData instance has the same data.

        Otherwise we would have to compare all the fields each time we want to check if the
        two SystemPurposeData instances have the same data.

        :param other_instance: another SystemPurposeData to compare with this one
        :type other_instance: SystemPurposeData instance
        :return: True if the other structure has the same system purpose data as this one,
                 False otherwise
        :rtype: bool
        """
        # if the other instance is not instance of SubscriptionRequest,
        # then it is always considered to be different
        if not isinstance(other_instance, SystemPurposeData):
            return False
        # addon ordering is not important
        if set(self.addons) != set(other_instance.addons):
            return False
        elif self.role != other_instance.role:
            return False
        elif self.sla != other_instance.sla:
            return False
        elif self.usage != other_instance.usage:
            return False
        else:
            return True


class SubscriptionRequest(DBusData):
    """Data for a subscription request.

    NOTE: Names of some of the fields are based on
          how the given keys are called in rhsm.conf.
    """

    def __init__(self):
        # subscription request type
        # (based on authentication method used)
        self._type = DEFAULT_SUBSCRIPTION_REQUEST_TYPE
        # user identification
        # - in case an account is member
        #   of multiple organizations, both
        #   organization and account username
        #   need to be set
        self._organization = ""
        self._redhat_account_username = ""
        self._redhat_account_organization = ""
        # Candlepin instance
        self._server_hostname = ""
        # CDN base url
        self._rhsm_baseurl = ""
        # RHSM HTTP proxy
        self._server_proxy_hostname = ""
        self._server_proxy_port = -1
        self._server_proxy_user = ""
        # private data
        # - we are using SecretData & SecretDataList
        #   nested DBus structures to protect this
        #   sensitive data
        # - this way they can be set-only & easily
        #   removed from SubscriptionRequest on
        #   output from the Subscription module
        # - they also support a robust way of clearing
        #   previously set sensitive data if required
        self._redhat_account_password = SecretData()
        self._activation_keys = SecretDataList()
        self._server_proxy_password = SecretData()

    @property
    def type(self) -> Str:
        """Subscription request type.

        Subscription request type is based on the authentication method used.

        At the moment the following two are supported:
        - username + password
        - organization id + one or more activation keys

        By default username + password is used.

        Valid values are:
        "username_password"
        "org_activation_key"

        :return: subscription request type
        :rtype: str
        """
        return self._type

    @type.setter
    def type(self, request_type: Str):
        self._type = request_type

    @property
    def organization(self) -> Str:
        """Organization id for subscription purposes.

        In most cases one of the following will be used:
        - org id + one or more activation keys
        - username + password

        There is also a less often expected use case,
        which applies if the same user account exists
        in multiple organizations on the same Candlepin
        instance. In such a case both username and
        organization id needs to be set.

        :return: organization id
        :rtype: str
        """
        return self._organization

    @organization.setter
    def organization(self, organization: Str):
        self._organization = organization

    @property
    def account_username(self) -> Str:
        """Red Hat account username for subscription purposes.

        In case the account for the given username is member
        of multiple organizations, organization id needs to
        be specified as well or else the registration attempt
        will not be successful.

        :return: Red Hat account username
        :rtype: str
        """
        return self._redhat_account_username

    @account_username.setter
    def account_username(self, account_username: Str):
        self._redhat_account_username = account_username

    @property
    def account_organization(self) -> Str:
        """Red Hat account organization for subscription purposes.

        In case the account for the given username is member
        of multiple organizations, organization id needs to
        be specified as well or else the registration attempt
        will not be successful. This account dependent organization
        id is deliberately separate from the org + key org id
        to avoid collisions and issues in the GUI when switching
        between authentication types.

        :return: Red Hat account organization id
        :rtype: str
        """
        return self._redhat_account_organization

    @account_organization.setter
    def account_organization(self, account_organization: Str):
        self._redhat_account_organization = account_organization

    @property
    def server_hostname(self) -> Str:
        """Subscription server hostname.

        This is basically a URL pointing to a Candlepin
        instance to be used. It could be the one handling
        general subscriptions hosted by Red Hat or one
        embedded in a Satellite deployment.

        If no custom server hostname is set, the default
        value used by subscription manager will be used,
        which is usually the URL pointing to the general
        purpose Red Hat hosted Candlepin instance.

        :return: Candlepin instance URL
        :rtype: str
        """
        return self._server_hostname

    @server_hostname.setter
    def server_hostname(self, server_hostname: Str):
        self._server_hostname = server_hostname

    @property
    def rhsm_baseurl(self) -> Str:
        """CDN repository base URL.

        Sets the base URL for the RHSM generated
        repo file.

        Setting this to a non default value only
        makes sense if registering against Satellite
        (as you would want to use the repos hosted
        on the given Satellite instance) or possibly
        during testing.

        If no custom rhsm baseurl is set, the default
        value used by subscription managed will be used,
        which is generally baseurl for the Red Hat CDN.

        :return: RHSM base url
        :rtype: str
        """
        return self._rhsm_baseurl

    @rhsm_baseurl.setter
    def rhsm_baseurl(self, rhsm_baseurl: Str):
        self._rhsm_baseurl = rhsm_baseurl

    @property
    def server_proxy_hostname(self) -> Str:
        """RHSM HTTP proxy - hostname.

        This is the hostname of the RHSM HTTP
        proxy, which will be used for subscription
        purposes only, eq. this will not configure
        a system wide HTTP proxy.

        :return: RHSM HTTP proxy hostname
        :rtype: str
        """
        return self._server_proxy_hostname

    @server_proxy_hostname.setter
    def server_proxy_hostname(self, hostname: Str):
        self._server_proxy_hostname = hostname

    @property
    def server_proxy_port(self) -> Int:
        """RHSM HTTP proxy - port number.

        -1 means port has not been set.

        :returns: RHSM HTTP proxy port number
        :rtype: int
        """
        return self._server_proxy_port

    @server_proxy_port.setter
    def server_proxy_port(self, port_number: Int):
        self._server_proxy_port = port_number

    @property
    def server_proxy_user(self) -> Str:
        """RHSM HTTP proxy - access username.

        :return: RHSM HTTP proxy access username
        :rtype: str
        """
        return self._server_proxy_user

    @server_proxy_user.setter
    def server_proxy_user(self, username: Str):
        self._server_proxy_user = username

    # private data
    # - generally sensitive data such as passwords
    #   or activation keys
    # - these values should be "write only",
    #   meaning data goes to the Subscription
    #   module but can't be read out later one
    #   via the public API
    # - only the Subscription module should have
    #   have access to these data internally &
    #   use them appropriately (eq. register
    #   the system, authenticate to HTTP proxy, etc.)
    # - it should be also possible to explicitly
    #   clear a previously set secret
    # - to protect these values we are using
    #   SecretData & SecretDataList, see their
    #   implementation for more information

    @property
    def account_password(self) -> SecretData:
        """Red Hat account password.

        NOTE: This property is stored in SecretData
              nested DBus structure to protect its contents.

        :return: Red hat account password stored in a SecretData instance
        :rtype: SecretData instance
        """
        return self._redhat_account_password

    @account_password.setter
    def account_password(self, password: SecretData):
        self._redhat_account_password = password

    @property
    def activation_keys(self) -> SecretDataList:
        """List of activation keys.

        For a successful activation key based registration
        at least one activation key needs to be set.

        NOTE: This property is stored in SecretDataList
              nested DBus structure to protect its contents.

        :return: list of activation keys stored in SecretDataList instance
        :rtype: SecretDataList instance
        """
        return self._activation_keys

    @activation_keys.setter
    def activation_keys(self, activation_keys: SecretDataList):
        self._activation_keys = activation_keys

    @property
    def server_proxy_password(self) -> SecretData:
        """RHSM HTTP proxy - access password.

        NOTE: This property is stored in SecretData
              nested DBus structure to protect its contents.

        :return: RHSM HTTP proxy password stored in SecretData instance
        :rtype: SecretData instance
        """
        return self._server_proxy_password

    @server_proxy_password.setter
    def server_proxy_password(self, password: SecretData):
        self._server_proxy_password = password


class OrganizationData(DBusData):
    """Data about a single organization in the Red Hat account system.

    A Red Hat account is expected to be member of an organization,
    with some accounts being members of more than one organization.
    """

    def __init__(self):
        self._id = ""
        self._name = ""

    @property
    def id(self) -> Str:
        """Id of the organization.

        Example: "abc123efg456"

        :return: organization id
        :rtype: str
        """
        return self._id

    @id.setter
    def id(self, organization_id: Str):
        self._id = organization_id

    @property
    def name(self) -> Str:
        """Name of the organization.

        Example: "Foo Organization"

        :return: organization name
        :rtype: str
        """
        return self._name

    @name.setter
    def name(self, organization_name: Str):
        self._name = organization_name
