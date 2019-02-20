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

from pyanaconda.core.constants import THREAD_STORAGE, THREAD_PAYLOAD, THREAD_PAYLOAD_RESTART, \
    THREAD_WAIT_FOR_CONNECTING_NM
from pyanaconda.core.i18n import _, N_
from pyanaconda.threading import threadMgr, AnacondaThread
from pyanaconda.payload import PackagePayload
from pyanaconda.payload.errors import PayloadError

from pyanaconda.anaconda_loggers import get_module_logger

log = get_module_logger(__name__)


__all__ = ["payloadMgr"]


class PayloadManager(object):
    """Framework for starting and watching the payload thread.

    This class defines several states, and events can be triggered upon
    reaching a state. Depending on whether a state has already been reached
    when a listener is added, the event code may be run in either the
    calling thread or the payload thread. The event code will block the
    payload thread regardless, so try not to run anything that takes a long
    time.

    All states except STATE_ERROR are expected to happen linearly, and adding
    a listener for a state that has already been reached or passed will
    immediately trigger that listener. For example, if the payload thread is
    currently in STATE_GROUP_MD, adding a listener for STATE_NETWORK will
    immediately run the code being added for STATE_NETWORK.

    The payload thread data should be accessed using the payloadMgr object,
    and the running thread can be accessed using threadMgr with the
    THREAD_PAYLOAD constant, if you need to wait for it or something. The
    thread should be started using payloadMgr.restartThread.
    """

    STATE_START = 0
    # Waiting on storage
    STATE_STORAGE = 1
    # Waiting on network
    STATE_NETWORK = 2
    # Verify repository availability
    STATE_TEST_AVAILABILITY = 3
    # Downloading package metadata
    STATE_PACKAGE_MD = 4
    # Downloading group metadata
    STATE_GROUP_MD = 5
    # All done
    STATE_FINISHED = 6

    # Error
    STATE_ERROR = -1

    # Error strings
    ERROR_SETUP = N_("Failed to set up installation source")
    ERROR_MD = N_("Error downloading package metadata")

    def __init__(self):
        self._event_lock = threading.Lock()
        self._event_listeners = {}
        self._thread_state = self.STATE_START
        self._error = None

        # Initialize a list for each event state
        for event_id in range(self.STATE_ERROR, self.STATE_FINISHED + 1):
            self._event_listeners[event_id] = []

    @property
    def error(self):
        return _(self._error)

    def addListener(self, event_id, func):
        """Add a listener for an event.

        :param int event_id: The event to listen for, one of the EVENT_* constants
        :param function func: An object to call when the event is reached
        """

        # Check that the event_id is valid
        assert isinstance(event_id, int)
        assert event_id <= self.STATE_FINISHED
        assert event_id >= self.STATE_ERROR

        # Add the listener inside the lock in case we need to run immediately,
        # to make sure the listener isn't triggered twice
        with self._event_lock:
            self._event_listeners[event_id].append(func)

            # If an error event was requested, run it if currently in an error state
            if event_id == self.STATE_ERROR:
                if event_id == self._thread_state:
                    func()
            # Otherwise, run if the requested event has already occurred
            elif event_id <= self._thread_state:
                func()

    def restartThread(self, storage, ksdata, payload,
                      fallback=False, checkmount=True, onlyOnChange=False):
        """Start or restart the payload thread.

        This method starts a new thread to restart the payload thread, so
        this method's return is not blocked by waiting on the previous payload
        thread. If there is already a payload thread restart pending, this method
        has no effect.

        :param pyanaconda.storage.InstallerStorage storage: The blivet storage instance
        :param kickstart.AnacondaKSHandler ksdata: The kickstart data instance
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

        thread_args = (storage, ksdata, payload, fallback, checkmount, onlyOnChange)
        # Launch a new thread so that this method can return immediately
        threadMgr.add(AnacondaThread(name=THREAD_PAYLOAD_RESTART, target=self._restartThread,
                                     args=thread_args))

    @property
    def running(self):
        """Is the payload thread running right now?"""
        return threadMgr.exists(THREAD_PAYLOAD_RESTART) or threadMgr.exists(THREAD_PAYLOAD)

    def _restartThread(self, storage, ksdata, payload, fallback, checkmount, onlyOnChange):
        # Wait for the old thread to finish
        threadMgr.wait(THREAD_PAYLOAD)

        thread_args = (storage, ksdata, payload, fallback, checkmount, onlyOnChange)
        # Start a new payload thread
        threadMgr.add(AnacondaThread(name=THREAD_PAYLOAD, target=self._runThread,
                                     args=thread_args))

    def _setState(self, event_id):
        # Update the current state
        log.debug("Updating payload thread state: %d", event_id)
        with self._event_lock:
            # Update the state within the lock to avoid a race with listeners
            # currently being added
            self._thread_state = event_id

            # Run any listeners for the new state
            for func in self._event_listeners[event_id]:
                func()

    def _runThread(self, storage, ksdata, payload, fallback, checkmount, onlyOnChange):
        # This is the thread entry
        # Set the initial state
        self._error = None
        self._setState(self.STATE_START)

        # Wait for storage
        self._setState(self.STATE_STORAGE)
        threadMgr.wait(THREAD_STORAGE)

        # Wait for network
        self._setState(self.STATE_NETWORK)
        # FIXME: condition for cases where we don't want network
        # (set and use payload.needsNetwork ?)
        threadMgr.wait(THREAD_WAIT_FOR_CONNECTING_NM)

        payload.setup(storage)

        # If this is a non-package Payload, we're done
        if not isinstance(payload, PackagePayload):
            self._setState(self.STATE_FINISHED)
            return

        # Test if any repository changed from the last update
        if onlyOnChange:
            log.debug("Testing repositories availability")
            self._setState(self.STATE_TEST_AVAILABILITY)
            if payload.verifyAvailableRepositories():
                log.debug("Payload isn't restarted, repositories are still available.")
                self._setState(self.STATE_FINISHED)
                return

        # Keep setting up package-based repositories
        # Download package metadata
        self._setState(self.STATE_PACKAGE_MD)
        try:
            payload.updateBaseRepo(fallback=fallback, checkmount=checkmount)
            payload.addDriverRepos()
        except (OSError, PayloadError) as e:
            log.error("PayloadError: %s", e)
            self._error = self.ERROR_SETUP
            self._setState(self.STATE_ERROR)
            payload.unsetup()
            return

        # Gather the group data
        self._setState(self.STATE_GROUP_MD)
        payload.gatherRepoMetadata()
        payload.release()

        # Check if that failed
        if not payload.baseRepo:
            log.error("No base repo configured")
            self._error = self.ERROR_MD
            self._setState(self.STATE_ERROR)
            payload.unsetup()
            return

        # run payload specific post configuration tasks
        payload.postSetup()

        self._setState(self.STATE_FINISHED)


# Initialize the PayloadManager instance
payloadMgr = PayloadManager()
