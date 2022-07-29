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
from dasbus.error import DBusError
from pyanaconda.core.constants import THREAD_STORAGE, THREAD_PAYLOAD, THREAD_PAYLOAD_RESTART, \
    THREAD_WAIT_FOR_CONNECTING_NM, THREAD_SUBSCRIPTION, PAYLOAD_TYPE_DNF, \
    THREAD_STORAGE_WATCHER, THREAD_EXECUTE_STORAGE, PAYLOAD_STATUS_PROBING_STORAGE, \
    PAYLOAD_STATUS_SETTING_SOURCE
from pyanaconda.core.i18n import _
from pyanaconda.modules.common.task.progress import ProgressReporter
from pyanaconda.modules.common.task.runnable import Runnable
from pyanaconda.threading import threadMgr, AnacondaThread
from pyanaconda.errors import errorHandler as error_handler, ERROR_RAISE
from pyanaconda.anaconda_loggers import get_module_logger

log = get_module_logger(__name__)

__all__ = ["payloadMgr"]


class _PayloadFailed(Exception):
    """Failed to set up the installation source."""


class _InteractivePayloadFailed(_PayloadFailed):
    """The installation source requires reconfiguration in the UI."""


class _PayloadManager(Runnable, ProgressReporter):
    """Framework for starting and watching the payload thread.

    The payload thread data should be accessed using the payloadMgr object,
    and the running thread can be accessed using threadMgr with the
    THREAD_PAYLOAD constant, if you need to wait for it or something. The
    thread should be started using payloadMgr.start.
    """

    @property
    def steps(self):
        """Total number of steps."""
        return 1

    @property
    def is_running(self):
        """Is the payload thread running right now?"""
        return threadMgr.exists(THREAD_PAYLOAD_RESTART) or threadMgr.exists(THREAD_PAYLOAD)

    def start(self, *args, **kwargs):
        """Start or restart the payload thread.

        This method starts a new thread to restart the payload thread, so
        this method's return is not blocked by waiting on the previous payload
        thread. If there is already a payload thread restart pending, this method
        has no effect.
        """
        log.debug("Restarting payload thread")

        # If a restart thread is already running, don't start a new one.
        if threadMgr.get(THREAD_PAYLOAD_RESTART):
            return

        # Launch a new thread so that this method can return immediately.
        threadMgr.add(AnacondaThread(
            name=THREAD_PAYLOAD_RESTART,
            target=self._start,
            args=args,
            kwargs=kwargs,
        ))

    def _start(self, *args, **kwargs):
        """Start the payload thread after it is finished."""
        # Wait for the previous payload thread to finish.
        threadMgr.wait(THREAD_PAYLOAD)

        # Start a new payload thread.
        threadMgr.add(
            AnacondaThread(
                name=THREAD_PAYLOAD,
                target=self._task_run_callback,
                target_started=self._task_started_callback,
                target_stopped=self._task_stopped_callback,
                args=args,
                kwargs=kwargs,
            )
        )

    def _task_run_callback(self, *args, **kwargs):
        """Run the task."""
        try:
            # Try to set up the payload.
            self._run(*args, **kwargs)
        except _InteractivePayloadFailed:
            # The payload has failed, but it can be reconfigured in the UI.
            # Emit the failed signal, but don't propagate the error.
            self._task_failed_callback()
        except Exception as e:  # pylint: disable=broad-except
            # The payload has failed and it cannot be reconfigured in the UI.
            # Emit the failed signal and ask the user what to do.
            self._task_failed_callback()

            if error_handler.cb(e) == ERROR_RAISE:
                raise
        else:
            # The payload is successfully set up.
            # Emit the succeeded signal.
            self._task_succeeded_callback()

    def _run(self, payload, fallback=False, try_media=True, only_on_change=False):
        """The task implementation.

        Report the progress of the task with the self.report_progress
        method. Raise the _InteractivePayloadFailed exception to indicate
        that we failed to set up the installation source, but it can be
        reconfigured in the UI.

        :param payload: the payload instance
        :param bool fallback: whether to fall back to the default repo in case of error
        :param bool try_media: whether to check for valid mounted media
        :param bool only_on_change: restart thread only if existing repositories changed
        """
        # Wait for storage
        self.report_progress(PAYLOAD_STATUS_PROBING_STORAGE)
        threadMgr.wait(THREAD_STORAGE)
        threadMgr.wait(THREAD_STORAGE_WATCHER)
        threadMgr.wait(THREAD_EXECUTE_STORAGE)

        # Wait for network
        # FIXME: condition for cases where we don't want network
        # (set and use payload.needs_network ?)
        threadMgr.wait(THREAD_WAIT_FOR_CONNECTING_NM)

        # Wait for subscription
        threadMgr.wait(THREAD_SUBSCRIPTION)

        # Set up the payload.
        self.report_progress(_(PAYLOAD_STATUS_SETTING_SOURCE))

        # Non-package payloads do everything in the setup method.
        # There is no UI support that could handle the error state,
        # so we need to handle or raise the error directly.
        payload.setup()

        # If this is a non-package Payload, we're done
        if payload.type != PAYLOAD_TYPE_DNF:
            return

        # Test if any repository changed from the last update
        if only_on_change:
            log.debug("Testing repositories availability")
            if payload.dnf_manager.verify_repomd_hashes():
                log.debug("Payload isn't restarted, repositories are still available.")
                return

        # Keep setting up package-based repositories
        # Download package metadata
        self.report_progress(_("Downloading package metadata..."))

        # FIXME: This import is a temporary workaround. Use a DBus error instead.
        from pyanaconda.modules.payloads.payload.dnf.dnf_manager import DNFManagerError

        try:
            payload.update_base_repo(fallback=fallback, try_media=try_media)
        except (OSError, DBusError, DNFManagerError) as e:
            log.error("Payload error: %s", e)
            payload.unsetup()
            raise _InteractivePayloadFailed(str(e)) from e

        # Gather the group data
        self.report_progress(_("Downloading group metadata..."))
        payload.dnf_manager.load_packages_metadata()

        # Check if that failed
        if not payload.is_ready():
            log.error("No base repo configured")
            payload.unsetup()
            raise _InteractivePayloadFailed()

        # run payload specific post configuration tasks
        payload.dnf_manager.load_repomd_hashes()

    def finish(self):
        """Finish the task run.

        The thread errors are fatal, so there is nothing to do here.
        """
        pass


# Initialize the PayloadManager instance.
payloadMgr = _PayloadManager()
