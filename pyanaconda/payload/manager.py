# Class for management payload threading.
#
# Copyright (C) 2019  Red Hat, Inc.
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

import threading
from enum import IntEnum

from dasbus.error import DBusError

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.constants import (
    PAYLOAD_TYPE_DNF,
    THREAD_EXECUTE_STORAGE,
    THREAD_PAYLOAD,
    THREAD_PAYLOAD_RESTART,
    THREAD_STORAGE,
    THREAD_STORAGE_WATCHER,
    THREAD_SUBSCRIPTION,
    THREAD_WAIT_FOR_CONNECTING_NM,
)
from pyanaconda.core.i18n import N_, _
from pyanaconda.errors import ERROR_RAISE, errorHandler
from pyanaconda.payload.errors import PayloadError
from pyanaconda.threading import AnacondaThread, threadMgr

log = get_module_logger(__name__)


__all__ = ["payloadMgr", "PayloadState"]


class PayloadState(IntEnum):
    """Enum for payload state after payload was restarted."""
    STARTED = 0
    WAITING_STORAGE = 1
    WAITING_NETWORK = 2
    VERIFYING_AVAILABILITY = 3
    DOWNLOADING_PKG_METADATA = 4
    DOWNLOADING_GROUP_METADATA = 5
    FINISHED = 6
    PAYLOAD_THREAD_TERMINATED = 7

    # Error
    ERROR = -1


class PayloadManager(object):
    """Framework for starting and watching the payload thread.

    This class defines several states (PayloadState enum), and events can
    be triggered upon reaching a state. Depending on whether a state has
    already been reached when a listener is added, the event code may be
    run in either the calling thread or the payload thread. The event code
    will block the payload thread regardless, so try not to run anything
    that takes a long time.

    All states except ERROR are expected to happen linearly, and adding
    a listener for a state that has already been reached or passed will
    immediately trigger that listener. For example, if the payload thread is
    currently in DOWNLOADING_GROUP_METADATA, adding a listener for
    WAITING_NETWORK will immediately run the code being added
    for WAITING_NETWORK.

    The payload thread data should be accessed using the payloadMgr object,
    and the running thread can be accessed using threadMgr with the
    THREAD_PAYLOAD constant, if you need to wait for it or something. The
    thread should be started using payloadMgr.restart_thread.
    """
    # Error strings
    ERROR_SETUP = N_("Failed to set up installation source")
    ERROR_MD = N_("Error downloading package metadata")

    def __init__(self):
        self._event_lock = threading.Lock()
        self._event_listeners = {}
        self._thread_state = PayloadState.STARTED
        self._error = None

        # Initialize a list for each event state
        for _name, value in PayloadState.__members__.items():  # pylint: disable=no-member
            self._event_listeners[PayloadState(value)] = []

    @property
    def error(self):
        return _(self._error)

    def add_listener(self, event_id, func):
        """Add a listener for an event.

        :param int event_id: The event to listen for, one of the EVENT_* constants
        :param function func: An object to call when the event is reached
        """

        # Check that the event_id is valid
        assert isinstance(event_id, PayloadState)

        # Add the listener inside the lock in case we need to run immediately,
        # to make sure the listener isn't triggered twice
        with self._event_lock:
            self._event_listeners[event_id].append(func)

            # If an error event was requested, run it if currently in an error state
            if event_id == PayloadState.ERROR:
                if event_id == self._thread_state:
                    func()
            # Otherwise, run if the requested event has already occurred
            elif event_id <= self._thread_state:
                func()

    def restart_thread(self, payload, fallback=False, checkmount=True, onlyOnChange=False):
        """Start or restart the payload thread.

        This method starts a new thread to restart the payload thread, so
        this method's return is not blocked by waiting on the previous payload
        thread. If there is already a payload thread restart pending, this method
        has no effect.

        :param payload.Payload payload: The payload instance
        :param bool fallback: Whether to fall back to the default repo in case of error
        :param bool checkmount: Whether to check for valid mounted media
        :param bool onlyOnChange: Restart thread only if existing repositories changed.
                                  This won't restart thread even when a new repository was added!!
        """
        log.debug("Restarting payload thread")

        # If a restart thread is already running, don't start a new one
        if threadMgr.get(THREAD_PAYLOAD_RESTART):
            return

        # Launch a new thread so that this method can return immediately
        threadMgr.add(AnacondaThread(
            name=THREAD_PAYLOAD_RESTART,
            target=self._restart_thread,
            args=(payload, fallback, checkmount, onlyOnChange)
        ))

    @property
    def running(self):
        """Is the payload thread running right now?"""
        return threadMgr.exists(THREAD_PAYLOAD_RESTART) or threadMgr.exists(THREAD_PAYLOAD)

    def _restart_thread(self, payload, fallback, checkmount, onlyOnChange):
        # Wait for the old thread to finish
        threadMgr.wait(THREAD_PAYLOAD)

        # Start a new payload thread
        threadMgr.add(AnacondaThread(
            name=THREAD_PAYLOAD,
            target=self._run_thread,
            args=(payload, fallback, checkmount, onlyOnChange)
        ))

        # Wait for the new thread to finish
        threadMgr.wait(THREAD_PAYLOAD)

        # Notify any listeners that payload thread has terminated
        #
        # This might be necessary to notify spokes waiting for
        # the payload thread to terminate, by the notification
        # not comming from the thread they are waiting for to terminate.
        self._set_state(PayloadState.PAYLOAD_THREAD_TERMINATED)

    def _set_state(self, event_id):
        # Update the current state
        log.debug("Updating payload thread state: %s", event_id.name)
        with self._event_lock:
            # Update the state within the lock to avoid a race with listeners
            # currently being added
            self._thread_state = event_id

            # Run any listeners for the new state
            for func in self._event_listeners[event_id]:
                func()

    def _run_thread(self, payload, fallback, checkmount, onlyOnChange):
        # This is the thread entry
        # Set the initial state
        self._error = None
        self._set_state(PayloadState.STARTED)

        # Wait for storage
        self._set_state(PayloadState.WAITING_STORAGE)
        threadMgr.wait(THREAD_STORAGE)
        threadMgr.wait(THREAD_STORAGE_WATCHER)
        threadMgr.wait(THREAD_EXECUTE_STORAGE)

        # Wait for network
        self._set_state(PayloadState.WAITING_NETWORK)
        # FIXME: condition for cases where we don't want network
        # (set and use payload.needs_network ?)
        threadMgr.wait(THREAD_WAIT_FOR_CONNECTING_NM)

        # Wait for subscription
        threadMgr.wait(THREAD_SUBSCRIPTION)

        # Non-package payloads do everything in the setup method.
        # There is no UI support that could handle the error state,
        # so we need to handle or raise the error directly.
        try:
            payload.setup()
        except (DBusError, PayloadError) as e:
            # Handle an error.
            if errorHandler.cb(e) == ERROR_RAISE:
                raise

        # If this is a non-package Payload, we're done
        if payload.type != PAYLOAD_TYPE_DNF:
            self._set_state(PayloadState.FINISHED)
            return

        # Test if any repository changed from the last update
        if onlyOnChange:
            log.debug("Testing repositories availability")
            self._set_state(PayloadState.VERIFYING_AVAILABILITY)
            if payload.verify_available_repositories():
                log.debug("Payload isn't restarted, repositories are still available.")
                self._set_state(PayloadState.FINISHED)
                return

        # Keep setting up package-based repositories
        # Download package metadata
        self._set_state(PayloadState.DOWNLOADING_PKG_METADATA)
        try:
            payload.update_base_repo(fallback=fallback, checkmount=checkmount)
            payload.add_driver_repos()
        except (OSError, DBusError, PayloadError) as e:
            log.error("PayloadError: %s", e)
            self._error = "%s: %s" % (self.ERROR_SETUP, e)
            self._set_state(PayloadState.ERROR)
            payload.unsetup()
            return

        # Gather the group data
        self._set_state(PayloadState.DOWNLOADING_GROUP_METADATA)
        payload.gather_repo_metadata()

        # Check if that failed
        if not payload.base_repo:
            log.error("No base repo configured")
            self._error = "%s: %s" % (self.ERROR_MD, e)
            self._set_state(PayloadState.ERROR)
            payload.unsetup()
            return

        # run payload specific post configuration tasks
        payload.post_setup()

        self._set_state(PayloadState.FINISHED)


# Initialize the PayloadManager instance
payloadMgr = PayloadManager()
