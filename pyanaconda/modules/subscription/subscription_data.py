#
# Subscription data handling.
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

import json
import datetime

from pyanaconda.core.i18n import _

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

class SubscriptionData(object):
    """A class for parsing and holding state of a subscribed system."""

    SYSPURPOSE_DEFAULT_VALUE = ""

    def __init__(self, subscription_json=None, final_syspurpose_json=None):
        self._method = self.SYSPURPOSE_DEFAULT_VALUE
        self._sla = self.SYSPURPOSE_DEFAULT_VALUE
        self._usage = self.SYSPURPOSE_DEFAULT_VALUE
        self._role = self.SYSPURPOSE_DEFAULT_VALUE
        self._attached_subscriptions = []
        self._connected_to_insights = False

        # None & "" are both not valid JSON

        if subscription_json is not None and subscription_json != "":
            # parse the subscription JSON and let it set the
            # class instance state
            self._parse_subscription_json(subscription_json)

        if final_syspurpose_json is not None and final_syspurpose_json != "":
            # pass the final syspurpose JSON and let it set
            # the class instance state
            self._parse_final_syspurpose_json(final_syspurpose_json)

    @property
    def method(self):
        return self._method

    @property
    def role(self):
        return self._role

    @property
    def sla(self):
        return self._sla

    @property
    def usage(self):
        return self._usage

    @property
    def attached_subscriptions(self):
        return self._attached_subscriptions

    @property
    def connect_to_insights(self):
        return self._connected_to_insights

    def _parse_subscription_json(self, subscription_json):
        """Parse JSON data corresponding to subscriptions attached to the system.

        :param str subscription_json: JSON describing what subscriptions have been attached

        The expected JSON is at top level a list of rather complex dictionaries,
        with each dictionary describing a single subscription that has been attached
        to the system.

        In this function we actually only parse the JSON, split it per subscription
        and then re-encode each subscription back to a JSON string for the
        AttachedSubscription class to parse.

        This is not ideal, but makes the AttachedSubscription implementation and
        testing simpler, as it also takes just JSON string, not some weird
        slice of already parsed JSON list.
        """
        subscriptions = json.loads(subscription_json)
        # find the list of subscriptions
        consumed_subscriptions = subscriptions.get("consumed", [])
        log.debug("RHSM: parsing %d attached subscriptions", len(consumed_subscriptions))
        # split the list of subscriptions
        for attached_subscription in consumed_subscriptions:
            # into separate subscription dictionaries
            attached_subscription_json = json.dumps(attached_subscription)
            # re-encode back to JSON and pass to AttachedSubscription
            self._attached_subscriptions.append(AttachedSubscription(attached_subscription_json))

    def _parse_final_syspurpose_json(self, final_syspurpose_json):
        """Parse final System Purpose description in JSON format.

        :param str final_syspurpose_json: JSON describing final syspurpose state

        The expected JSON is a simple three key dictionary listing the final
        System Purpose state after subscription/subscriptions have been attached.
        """
        syspurpose_json = json.loads(final_syspurpose_json)
        self._role = syspurpose_json.get("role", self.SYSPURPOSE_DEFAULT_VALUE)
        self._sla = syspurpose_json.get("service_level_agreement", self.SYSPURPOSE_DEFAULT_VALUE)
        self._usage = syspurpose_json.get("usage", self.SYSPURPOSE_DEFAULT_VALUE)

class AttachedSubscription(object):
    """A class for parsing and holding data for a single attached subscription."""

    def __init__(self, attached_subscription_json):
        self._name = ""
        self._service_level = ""
        self._sku = ""
        self._contract = ""
        self._start_date = ""
        self._end_date = ""
        self._consumed_entitlement_count = ""

        self._parse_attached_subscription_json(attached_subscription_json)
        log.debug("RHSM: attached subscription parsed: %s", self.as_dict())

    @property
    def name(self):
        return self._name

    @property
    def service_level(self):
        return self._service_level

    @property
    def sku(self):
        return self._sku

    @property
    def contract(self):
        return self._contract

    @property
    def start_date(self):
        return self._start_date

    @property
    def end_date(self):
        return self._end_date

    @property
    def consumed_entitlement_count(self):
        return self._consumed_entitlement_count

    def as_dict(self):
        """Return the attached subscription instance as a dict.

        This dict has string keys and string values, suitable
        for transferring via DBus without advanced DBus structure
        support.
        """
        return {
            "name" : self.name,
            "service_level" : self.service_level,
            "sku" : self.sku,
            "contract" : self.contract,
            "start_date" : self.start_date,
            "end_date" : self.end_date,
            "consumed_entitlement_count" : self.consumed_entitlement_count
        }

    def _pretty_date(self, date_from_json):
        """Return pretty human readable date based on date from the input JSON."""
        # fallback in case of the parsing fails
        date_string = date_from_json
        try:
            # The start/end date in GetPools() output seems to be formatted as
            # "Locale’s appropriate date representation.".
            date = datetime.datetime.strptime(date_from_json, "%m/%d/%y")
            # get a nice human readable date
            date_string = date.strftime("%b %d, %Y")
        except ValueError:
            log.warning("subscription date parsing failed: %s", date_from_json)

        return date_string

    def _parse_attached_subscription_json(self, attached_subscription_json):
        subscription_info = json.loads(attached_subscription_json)
        # user visible product name
        self._name = subscription_info.get("subscription_name", _("product name unknown"))

        # subscription support level
        # - this does *not* seem to directly correlate to system purpose SLA attribute
        self._service_level = subscription_info.get("service_level", _("unknown"))

        # SKU
        # - looks like productId == SKU in this JSON output
        self._sku = subscription_info.get("sku", _("unknown"))

        # contract number
        self._contract = subscription_info.get("contract", _("Not Available"))

        # subscription start date
        # - convert the raw date data from JSON to something more readable
        start_date = subscription_info.get("starts", _("unknown"))
        self._start_date = self._pretty_date(start_date)

        # subscription end date
        end_date = subscription_info.get("ends", _("unknown"))
        self._end_date = self._pretty_date(end_date)

        # consumed entitlements
        # - this seems to correspond to the toplevel "quantity" key,
        #   not to the pool-level "consumed" key for some reason
        #   *or* the pool-level "quantity" key
        # - we need to make sure this is string, or else DBus serialization
        #   will complain later on
        quantity_string = str(subscription_info.get("quantity_used", _("unknown")))
        self._consumed_entitlement_count = quantity_string
