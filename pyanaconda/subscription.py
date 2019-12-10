#
# Temporary subscription scheduling module
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
# Why is this needed ?
#
# The Red Hat subscription related tasks communicate over network and might
# take some time to finish (up to tens of seconds). We definitely don't want
# to block either automated installation or the UI for these to finish.
#
# Some of these tasks (register + attach) need to run in threads
# and these threads need to be started from at least two places:
# - from early startup code for automated installations
# - from UI based on user interaction
#
# Also in some cases, multiple individual DBus tasks will need to be run.
# Anaconda modularity on RHEL8 is not advanced enough to handle this by itself,
# so we need simple sheduler living in the context of the main Anaconda
# thread, that hosts the code that starts the respective subscription thread,
# that makes sure appropriate tasks are run.
#
# This code than can be run either during early startup or in reaction to user
# interaction in the UI, avoiding code duplication.

from enum import Enum

from pyanaconda.threading import threadMgr

from pyanaconda.core.i18n import _

from pyanaconda.core.constants import THREAD_WAIT_FOR_CONNECTING_NM
from pyanaconda.core.constants import RHSM_AUTH_USERNAME_PASSWORD, RHSM_AUTH_ORG_KEY

from pyanaconda.modules.common.constants.services import SUBSCRIPTION
from pyanaconda.modules.common.task import sync_run_task


from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class SubscriptionPhase(Enum):
    UNREGISTER = 1
    REGISTER = 2
    ATTACH = 3
    DONE = 4

def dummy_progress_callback(phase):
    """Dummy progress reporting function used if no custom function is set."""
    pass

def dummy_error_callback(error_message):
    """Dummy error reporting function used if no custom function is set."""
    pass

def subscribe(progress_callback=None, error_callback=None):
    """Try to register a system."""

    # assign dummy callback functions if none were provided
    if progress_callback is None:
        progress_callback = dummy_progress_callback
    if error_callback is None:
        error_callback = dummy_error_callback

    error_message = ""
    # connect to the Subscription DBus module
    subscription_proxy = SUBSCRIPTION.get_proxy()

    # first sure network connectivity is available
    threadMgr.wait(THREAD_WAIT_FOR_CONNECTING_NM)

    # Then check if we are not already registered.
    #
    # In some fairly bizzare cases it is apparently
    # possible that registration & attach will succeed,
    # but the attached subcription will be uncomplete
    # and/or invalid. These cases will be caught by
    # the subscription token check and marked
    # as failed by Anaconda.
    #
    # It is also possible that reigstration succeeds,
    # but attach fails.
    #
    # To make recovery and another regsitration attempt
    # possible, we need to first unregister the already
    # registered system, as a registration attempt on
    # an already registered system would fail.
    if subscription_proxy.IsRegistered:
        log.debug("RHSM: subscription thread: system already registered, unregistering")
        progress_callback(SubscriptionPhase.UNREGISTER)
        task_path = subscription_proxy.UnregisterWithTask()
        task_proxy = SUBSCRIPTION.get_proxy(task_path)
        sync_run_task(task_proxy)
        error = task_proxy.Error
        if error:
            log.debug("Subscription GUI: unregistration failed: %s", error)
            error_message = error
        else:
            log.debug("Subscription GUI: unregistration succeeded")
            # success, clear any previous errors
            error_message = ""

    if error_message:
        # Failing to un-register the system is an unrecoverable error,
        # so we end there
        error_callback(error_message)
        return

    # Try to register.
    # If we got this far the system was either not registered or unregistered
    # successfully.
    log.debug("RHSM: subscription thread: attempting to register")
    progress_callback(SubscriptionPhase.REGISTER)
    # check authentication method has been set and credentials seem to be
    # sufficient (though not necessarily valid)
    credentials_sufficient = False
    auth_method = subscription_proxy.AuthenticationMethod
    if auth_method == RHSM_AUTH_USERNAME_PASSWORD:
        username_set = bool(subscription_proxy.AccountUsername)
        password_set = subscription_proxy.AccountUsername
        credentials_sufficient = username_set and password_set
    elif auth_method == RHSM_AUTH_ORG_KEY:
        organization_set = bool(subscription_proxy.Organization)
        key_set = subscription_proxy.IsActivationKeySet
        credentials_sufficient = organization_set and key_set

    if credentials_sufficient:
        task_path = subscription_proxy.RegisterWithTask()
        task_proxy = SUBSCRIPTION.get_proxy(task_path)
        sync_run_task(task_proxy)
        error = task_proxy.Error
        if error:
            log.debug("RHSM: subscription thread: registration attempt failed: %s", error)
            error_message = error
        else:
            log.debug("RHSM: subscription thread: registration succeeded")
            error_message = ""
    else:
        error_message = _("Registration faile due to insufficient credentials.")
        log.debug("RHSM: subscription thread: credentials insufficient, skipping registration attempt")

    # try to attach subscription
    if error_message:
        log.debug("RHSM: subscription thread: skipping auto attach due to registration error")
        error_callback(error_message)
        return
    else:
        log.debug("RHSM: subscription thread: attempting to auto attach an entitlement")
        progress_callback(SubscriptionPhase.ATTACH)
        task_path = subscription_proxy.AttachWithTask()
        task_proxy = SUBSCRIPTION.get_proxy(task_path)
        sync_run_task(task_proxy)
        error = task_proxy.Error
        if error:
            log.debug("RHSM: subscription thread: failed to attach subscription")
            error_message = error
            error_callback(error_message)
            return
        else:
            log.debug("RHSM: subscription thread: auto attach succeeded")
            # success, clear any previous errors
            error_message = ""
            progress_callback(SubscriptionPhase.DONE)
