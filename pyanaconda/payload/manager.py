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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.constants import (
    PAYLOAD_STATUS_PROBING_STORAGE,
    PAYLOAD_STATUS_SETTING_SOURCE,
    THREAD_EXECUTE_STORAGE,
    THREAD_PAYLOAD,
    THREAD_PAYLOAD_RESTART,
    THREAD_STORAGE,
    THREAD_STORAGE_WATCHER,
    THREAD_SUBSCRIPTION,
    THREAD_WAIT_FOR_CONNECTING_NM,
)
from pyanaconda.core.i18n import _
from pyanaconda.core.threads import thread_manager
from pyanaconda.errors import ERROR_RAISE
from pyanaconda.errors import errorHandler as error_handler
from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.common.structures.validation import ValidationReport
from pyanaconda.modules.common.task.progress import ProgressReporter
from pyanaconda.modules.common.task.runnable import Runnable

log = get_module_logger(__name__)

__all__ = ["NonCriticalSourceSetupError", "payloadMgr"]


class NonCriticalSourceSetupError(SourceSetupError):
    """Non-critical error raised during the source setup."""
    pass


class _PayloadManager(Runnable, ProgressReporter):
    """Framework for starting and watching the payload thread.

    The payload thread data should be accessed using the payloadMgr object,
    and the running thread can be accessed using thread_manager with the
    THREAD_PAYLOAD constant, if you need to wait for it or something. The
    thread should be started using payloadMgr.start.
    """

    def __init__(self):
        super().__init__()
        self._report = ValidationReport()

    @property
    def report(self):
        """The latest validation report."""
        return self._report

    @property
    def steps(self):
        """Total number of steps."""
        return 1

    @property
    def is_running(self):
        """Is the payload thread running right now?"""
        return thread_manager.exists(THREAD_PAYLOAD_RESTART) or thread_manager.exists(THREAD_PAYLOAD)

    def start(self, *args, **kwargs):
        """Start or restart the payload thread.

        This method starts a new thread to restart the payload thread, so
        this method's return is not blocked by waiting on the previous payload
        thread. If there is already a payload thread restart pending, this method
        has no effect.
        """
        log.debug("Restarting payload thread")

        # If a restart thread is already running, don't start a new one.
        if thread_manager.get(THREAD_PAYLOAD_RESTART):
            return

        # Launch a new thread so that this method can return immediately.
        thread_manager.add_thread(
            name=THREAD_PAYLOAD_RESTART,
            target=self._start,
            args=args,
            kwargs=kwargs,
        )

    def _start(self, *args, **kwargs):
        """Start the payload thread after it is finished."""
        # Wait for the previous payload thread to finish.
        thread_manager.wait(THREAD_PAYLOAD)

        # Start a new payload thread.
        thread_manager.add_thread(
            name=THREAD_PAYLOAD,
            target=self._task_run_callback,
            target_started=self._task_started_callback,
            target_stopped=self._task_stopped_callback,
            args=args,
            kwargs=kwargs,
        )

    def _task_run_callback(self, *args, **kwargs):
        """Run the task."""
        self._report = ValidationReport()

        try:
            # Try to set up the payload.
            self._run(*args, **kwargs)
        except NonCriticalSourceSetupError as e:
            # Report the non-fatal error.
            self._report.error_messages.append(str(e))

            # The payload has failed, but it can be reconfigured in the UI.
            # Emit the failed signal, but don't propagate the error.
            self._task_failed_callback()

        except Exception as e:  # pylint: disable=broad-except
            # The payload has failed and it cannot be reconfigured in the UI.
            # Emit the failed signal and ask the user what to do.
            self._task_failed_callback()

            # Handle the fatal error.
            if error_handler.cb(e) == ERROR_RAISE:
                raise
        else:
            # The payload is successfully set up.
            # Emit the succeeded signal.
            self._task_succeeded_callback()

    def _run(self, payload, **kwargs):
        """The task implementation.

        Report the progress of the task with the self.report_progress
        method. Raise the _InteractivePayloadFailed exception to indicate
        that we failed to set up the installation source, but it can be
        reconfigured in the UI.

        :param payload: the payload instance
        """
        # Wait for storage
        self.report_progress(PAYLOAD_STATUS_PROBING_STORAGE)
        thread_manager.wait(THREAD_STORAGE)
        thread_manager.wait(THREAD_STORAGE_WATCHER)
        thread_manager.wait(THREAD_EXECUTE_STORAGE)

        # Wait for network
        # FIXME: condition for cases where we don't want network
        # (set and use payload.needs_network ?)
        thread_manager.wait(THREAD_WAIT_FOR_CONNECTING_NM)

        # Wait for subscription
        thread_manager.wait(THREAD_SUBSCRIPTION)

        # Set up the payload.
        self.report_progress(_(PAYLOAD_STATUS_SETTING_SOURCE))

        try:
            # Try to set up the payload.
            payload.setup(self.report_progress, **kwargs)

        except Exception:  # pylint: disable=broad-except
            # Tear down the payload if we failed.
            payload.unsetup()
            raise

    def finish(self):
        """Finish the task run.

        The thread errors are fatal, so there is nothing to do here.
        """
        pass


# Initialize the PayloadManager instance.
payloadMgr = _PayloadManager()
