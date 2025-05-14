#
# Subscription related helper functions.
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
from enum import Enum

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.constants import (
    PAYLOAD_TYPE_DNF,
    SECRET_TYPE_HIDDEN,
    SECRET_TYPE_TEXT,
    SOURCE_TYPE_CDN,
    SOURCE_TYPES_OVERRIDEN_BY_CDN,
    THREAD_WAIT_FOR_CONNECTING_NM,
)
from pyanaconda.core.threads import thread_manager
from pyanaconda.errors import ERROR_RAISE, errorHandler
from pyanaconda.modules.common import task
from pyanaconda.modules.common.constants.services import SUBSCRIPTION
from pyanaconda.modules.common.errors.subscription import (
    MultipleOrganizationsError,
    RegistrationError,
    SatelliteProvisioningError,
    UnregistrationError,
)
from pyanaconda.modules.common.structures.subscription import SubscriptionRequest
from pyanaconda.modules.common.util import is_module_available
from pyanaconda.payload.manager import payloadMgr
from pyanaconda.ui.lib.payload import create_source, set_source, tear_down_sources

log = get_module_logger(__name__)

# The following secret types mean a secret has been set
# (and it is either in plaintext or hidden in the module).
SECRET_SET_TYPES = (SECRET_TYPE_TEXT, SECRET_TYPE_HIDDEN)


# Asynchronous subscription state tracking
class SubscriptionPhase(Enum):
    UNREGISTER = 1
    REGISTER = 2
    ATTACH_SUBSCRIPTION = 3
    DONE = 4

# temporary methods for Subscription/CDN related source switching


def switch_source(payload, source_type):
    """Switch to an installation source.

    :param payload: Anaconda payload instance
    :param source_type: installation source type
    """
    tear_down_sources(payload.proxy)
    new_source_proxy = create_source(source_type)
    set_source(payload.proxy, new_source_proxy)


def _do_payload_restart(payload):
    """Restart the Anaconda payload.

    This should be done after changing the installation sorce,
    such as when switching to and from the CDN.

    :param payload: Anaconda payload instance
    """
    payloadMgr.start(payload)


def check_cdn_is_installation_source(payload):
    """Check if Red Hat CDN is the current installation source.

    :param payload: Anaconda payload instance
    """
    if payload.type == PAYLOAD_TYPE_DNF:
        source_proxy = payload.get_source_proxy()
        return source_proxy.Type == SOURCE_TYPE_CDN
    else:
        # the CDN source pretty much only supports
        # DNF payload at the moment
        return False


def is_cdn_registration_required(payload):
    """Check if Red Hat CDN registration is required.

    :param payload: the payload object
    """
    if not check_cdn_is_installation_source(payload):
        return False

    if not is_module_available(SUBSCRIPTION):
        return False

    subscription_proxy = SUBSCRIPTION.get_proxy()
    return not subscription_proxy.IsSubscriptionAttached


# Kickstart error handling

class KickstartRegistrationError(Exception):
    """Registration attempt from kickstart failed."""
    pass


def kickstart_error_handler(message):
    """Helper function which raises exception if kickstart triggered registration fails."""
    exn = KickstartRegistrationError(message)
    if errorHandler.cb(exn) == ERROR_RAISE:
        raise exn

# Asynchronous registration + subscription & unregistration handling
#
# The Red Hat subscription related tasks communicate over network and might
# take some time to finish (up to tens of seconds). We definitely don't want
# to block either automated installation or the UI before they finish.
#
# These tasks (register + attach subscription and unregister) need to run in
# threads and these threads need to be started from at least two places:
# - from early startup code for automated installations
# - from Subscription spoke based on user interaction
#
# Also in some cases, multiple individual DBus tasks will need to be run
# in sequence with any errors handled accordingly.
#
# Anaconda modularity is not yet advanced enough to handle this in a generic
# manner, so we need simple scheduler living in the context of the main Anaconda
# thread. The simple scheduler hosts the code that starts the respective subscription
# handling thread, which assures appropriate tasks are run.
#
# As the scheduler code than can be run either during early startup or in reaction to user
# interaction in the Subscription spoke we avoid code duplication.


def noop(*args, **kwargs):
    """Function that doesn't do anything."""
    pass


# auth-data-sufficient checks
#
# NOTE: As those are used also in the GUI we can't just put them to a private methods
#       in one of the tasks.


def org_keys_sufficient(subscription_request=None):
    """Report if sufficient credentials are set for org & keys registration attempt.

    :param subscription_request: an subscription request, if None a fresh subscription request
                                 will be fetched from the Subscription module over DBus
    :type subscription_request: SubscriptionRequest instance
    :return: True if sufficient, False otherwise
    :rtype: bool
    """
    if subscription_request is None:
        subscription_proxy = SUBSCRIPTION.get_proxy()
        subscription_request_struct = subscription_proxy.SubscriptionRequest
        subscription_request = SubscriptionRequest.from_structure(subscription_request_struct)
    organization_set = bool(subscription_request.organization)
    key_set = subscription_request.activation_keys.type in SECRET_SET_TYPES
    return organization_set and key_set


def username_password_sufficient(subscription_request=None):
    """Report if sufficient credentials are set for username & password registration attempt.

    :param subscription_request: an subscription request, if None a fresh subscription request
                                 will be fetched from the Subscription module over DBus
    :type subscription_request: SubscriptionRequest instance
    :return: True if sufficient, False otherwise
    :rtype: bool
    """
    if subscription_request is None:
        subscription_proxy = SUBSCRIPTION.get_proxy()
        subscription_request_struct = subscription_proxy.SubscriptionRequest
        subscription_request = SubscriptionRequest.from_structure(subscription_request_struct)
    username_set = bool(subscription_request.account_username)
    password_set = subscription_request.account_password.type in SECRET_SET_TYPES
    return username_set and password_set


def register_and_subscribe(payload, progress_callback=noop, error_callback=noop,
                           restart_payload=False):
    """Try to register and subscribe the installation environment.

    :param payload: Anaconda payload instance
    :param progress_callback: progress callback function, takes one argument, subscription phase
    :type progress_callback: callable(subscription_phase)
    :param error_callback: error callback function, takes one argument, the error instance
    :type error_callback: callable(error_message)
    :param bool restart_payload: should payload restart be attempted if it appears necessary ?

    NOTE: The restart_payload attribute controls if the subscription helper function should
          attempt to restart the payload thread if it deems it necessary (DVD -> CDN switch,
          registration with CDN source, etc.). If restart_payload is True, it might restart
          the payload. If it is False, it well never try to do that.

          The main usecase of this at the moment is when the subscription helper function
          is invoked during early Anaconda kickstart installation. At this stage the initial
          payload restart has not yet been run and starting it too early could lead to various
          issues. At this stage we don't want the helper function to restart payload, so we keep
          restart_payload at default value (False). Later on during manual user interaction we
          definitely want payload to be restarted as needed (the initial restart long done)
          and so we pass restart_payload=True.
    """
    # connect to the Subscription DBus module
    subscription_proxy = SUBSCRIPTION.get_proxy()

    # First make sure network connectivity is available
    # by waiting for the connectivity check thread
    # to finish, in case it is running, usually early
    # during Anaconda startup.
    thread_manager.wait(THREAD_WAIT_FOR_CONNECTING_NM)

    # Next we make sure to set RHSM config options
    # to be in sync with the current subscription request.
    task_path = subscription_proxy.SetRHSMConfigWithTask()
    task_proxy = SUBSCRIPTION.get_proxy(task_path)
    task.sync_run_task(task_proxy)

    # Then check if we are not already registered.
    #
    # In some fairly bizarre cases it is apparently
    # possible that registration & attach will succeed,
    # but the attached subscription will be incomplete
    # and/or invalid. These cases will be caught by
    # the subscription token check and marked as failed
    # by Anaconda.
    #
    # It is also possible that registration succeeds,
    # but attach fails.
    #
    # To make recovery and another registration attempt
    # possible, we need to first unregister the already
    # registered system, as a registration attempt on
    # an already registered system would fail.
    if subscription_proxy.IsRegistered:
        log.debug("registration attempt: system already registered, unregistering")
        progress_callback(SubscriptionPhase.UNREGISTER)
        task_path = subscription_proxy.UnregisterWithTask()
        task_proxy = SUBSCRIPTION.get_proxy(task_path)
        try:
            task.sync_run_task(task_proxy)
        except UnregistrationError as e:
            log.debug("registration attempt: unregistration failed: %s", e)
            # Failing to unregister the system is an unrecoverable error,
            # so we end there.
            error_callback(e)
            return
        log.debug("Subscription GUI: unregistration succeeded")

    # Try to register and subscribe
    #
    # If we got this far the system was either not registered
    # or was unregistered successfully.
    log.debug("registration attempt: attempting to register")
    progress_callback(SubscriptionPhase.REGISTER)

    # registration and subscription is handled by a combined tasks that also
    # handles Satellite support and attached subscription parsing
    task_path = subscription_proxy.RegisterAndSubscribeWithTask()

    task_proxy = SUBSCRIPTION.get_proxy(task_path)
    try:
        task.sync_run_task(task_proxy)
    except SatelliteProvisioningError as e:
        log.debug("registration attempt: Satellite provisioning failed: %s", e)
        error_callback(e)
        return
    except MultipleOrganizationsError as e:
        log.debug(
            "registration attempt: please specify org id for current account and try again: %s",
            e
        )
        error_callback(e)
        return
    except RegistrationError as e:
        log.debug("registration attempt: registration attempt failed: %s", e)
        error_callback(e)
        return

    # check if the current installation source should be overridden by
    # the CDN source we can now use
    # - at the moment this is true only for the CDROM source
    source_proxy = payload.get_source_proxy()
    if payload.type == PAYLOAD_TYPE_DNF:
        if source_proxy.Type in SOURCE_TYPES_OVERRIDEN_BY_CDN:
            log.debug("registration attempt: overriding current installation source by CDN")
            switch_source(payload, SOURCE_TYPE_CDN)
        # If requested, also restart the payload if CDN is the installation source
        # The CDN either already was the installation source or we just switched to it.
        #
        # Make sure to get fresh source proxy as the old one might be stale after
        # a source switch.
        source_proxy = payload.get_source_proxy()
        if restart_payload and source_proxy.Type == SOURCE_TYPE_CDN:
            log.debug("registration attempt: restarting payload after registration")
            _do_payload_restart(payload)

    # and done, report subscription attempt was successful
    progress_callback(SubscriptionPhase.DONE)


def unregister(payload, overridden_source_type, progress_callback=noop, error_callback=noop,
               restart_payload=False):
    """Try to unregister the installation environment.

    NOTE: Unregistering also removes any attached subscriptions and
          if an installation source has been overridden, switches
          back to it.

    :param payload: Anaconda payload instance
    :param overridden_source_type: type of the source that was overridden by the CDN source at
                             registration time (if any)
    :param progress_callback: progress callback function, takes one argument, subscription phase
    :type progress_callback: callable(subscription_phase)
    :param error_callback: error callback function, takes one argument, the error message
    :type error_callback: callable(error_message)
    :param bool restart_payload: should payload restart be attempted if it appears necessary ?

    NOTE: For more information about the restart_payload attribute, see the
          register_and_subscribe() function doc string.
    """
    # connect to the Subscription DBus module
    subscription_proxy = SUBSCRIPTION.get_proxy()

    if subscription_proxy.IsRegistered:
        log.debug("registration attempt: unregistering the system")
        # Make sure to set RHSM config options to be in sync
        # with the current subscription request in the unlikely
        # case of someone doing a valid change in the subscription
        # request since we registered.
        task_path = subscription_proxy.SetRHSMConfigWithTask()
        task_proxy = SUBSCRIPTION.get_proxy(task_path)
        task.sync_run_task(task_proxy)
        progress_callback(SubscriptionPhase.UNREGISTER)
        task_path = subscription_proxy.UnregisterWithTask()
        task_proxy = SUBSCRIPTION.get_proxy(task_path)
        try:
            task.sync_run_task(task_proxy)
        except UnregistrationError as e:
            log.debug("registration attempt: unregistration failed: %s", e)
            error_callback(e)
            return

        # If the CDN overrode an installation source we should revert that
        # on unregistration, provided CDN is the current source.
        source_proxy = payload.get_source_proxy()
        switched_source = False
        if payload.type == PAYLOAD_TYPE_DNF:
            if source_proxy.Type == SOURCE_TYPE_CDN and overridden_source_type:
                log.debug(
                    "registration attempt: rolling back CDN installation source override"
                )
                switch_source(payload, overridden_source_type)
                switched_source = True

            # If requested, also restart the payload if:
            # - installation source switch occured
            # - the current source is CDN, which can no longer be used
            #   after unregistration, so we need to refresh the Source
            #   and Software spokes
            if restart_payload and (source_proxy.Type == SOURCE_TYPE_CDN or switched_source):
                log.debug("registration attempt: restarting payload after unregistration")
                _do_payload_restart(payload)

        log.debug("registration attempt: unregistration succeeded")
        progress_callback(SubscriptionPhase.DONE)
    else:
        log.warning("registration attempt: not registered, so can't unregister")
        progress_callback(SubscriptionPhase.DONE)
        return
