#
# Anaconda main DBus module & module manager.
#
# Copyright (C) 2017 Red Hat, Inc.
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
import os
from collections import namedtuple
from pathlib import Path

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.dbus import DBus
from pyanaconda.core.signal import Signal
from pyanaconda.modules.boss.boss_interface import BossInterface
from pyanaconda.modules.boss.install_manager import InstallManager
from pyanaconda.modules.boss.installation import (
    RunInstallationTask,
)
from pyanaconda.modules.boss.kickstart_manager import KickstartManager
from pyanaconda.modules.boss.module_manager import ModuleManager
from pyanaconda.modules.common.base import Service
from pyanaconda.modules.common.constants.installation import (
    InstallationErrorDialogType,
    InstallationStatus,
)
from pyanaconda.modules.common.constants.services import BOSS
from pyanaconda.modules.common.containers import TaskContainer

log = get_module_logger(__name__)

__all__ = ["Boss"]


InitialState = namedtuple("InitialState", ["status", "error_message", "error_type"])


class Boss(Service):
    """The Boss service."""

    def __init__(self):
        super().__init__()
        self._module_manager = ModuleManager()
        self._kickstart_manager = KickstartManager()
        self._install_manager = InstallManager()
        self._installation_task = None
        self.active_installation_task_changed = Signal()
        initial_state = self._load_initial_state()
        self._installation_status = initial_state.status
        self.installation_status_changed = Signal()
        self._pending_error_message = initial_state.error_message
        self._pending_error_type = initial_state.error_type
        self.pending_error_changed = Signal()

        self._module_manager.module_observers_changed.connect(
            self._kickstart_manager.on_module_observers_changed
        )

        self._module_manager.module_observers_changed.connect(
            self._install_manager.on_module_observers_changed
        )

    ERROR_FILE_NAME = "installation-error-msg"

    @property
    def _error_file(self) -> Path:
        rundir = Path(os.environ.get("ANACONDA_RUN_DIR", "/run/anaconda"))
        return rundir / self.ERROR_FILE_NAME

    def _load_initial_state(self):
        err = self._error_file.read_text() if self._error_file.exists() else ""
        return InitialState(
            status=InstallationStatus.FAILED if err else InstallationStatus.NOT_STARTED,
            error_message=err,
            error_type=InstallationErrorDialogType.FATAL_ERROR if err else "",
        )

    def publish(self):
        """Publish the boss."""
        TaskContainer.set_namespace(BOSS.namespace)
        DBus.publish_object(BOSS.object_path, BossInterface(self))
        DBus.register_service(BOSS.service_name)

    def get_modules(self):
        """Get service names of running modules.

        Get a list of all running DBus modules (including addons)
        that were discovered and started by the boss.

        :return: a list of service names
        """
        return self._module_manager.get_service_names()

    def start_modules_with_task(self):
        """Start the modules with the task."""
        return self._module_manager.start_modules_with_task()

    def stop(self):
        """Stop all modules and then stop the boss."""
        self._module_manager.stop_modules()
        super().stop()

    def read_kickstart_file(self, path):
        """Read the specified kickstart file.

        :param path: a path to a file
        :returns: a kickstart report
        """
        log.info("Reading a kickstart file at %s.", path)
        return self._kickstart_manager.read_kickstart_file(path)

    def generate_kickstart(self):
        """Return a kickstart representation of modules.

        :return: a kickstart string
        """
        log.info("Generating kickstart data...")
        return self._kickstart_manager.generate_kickstart()

    def collect_requirements(self):
        """Collect requirements of the modules.

        :return: a list of requirements
        """
        return self._install_manager.collect_requirements()

    @property
    def installation_status(self):
        """The current installation status.

        :return: an InstallationStatus value
        """
        return self._installation_status

    @property
    def pending_error_message(self):
        """The error message awaiting a UI response or describing a fatal error.

        Non-empty when a non-critical error dialog is waiting for the user,
        or when a fatal error has occurred. A reconnecting client should
        read this to discover unhandled errors.

        :return: an error message string or empty string
        """
        return self._pending_error_message

    @property
    def pending_error_type(self):
        """The type of the pending error (e.g. YES_NO or FATAL_ERROR).

        :return: an InstallationErrorDialogType value or empty string
        """
        return self._pending_error_type

    def get_installation_task(self):
        """Get the active installation task, if any.

        :return: the active installation task or None
        """
        if self._installation_task is not None \
                and self._installation_task.is_running:
            return self._installation_task

        return None

    def install_with_tasks(self):
        """Return installation tasks of this module.

        If an installation task is already running, return
        the existing task to allow reconnection. If it is
        completed, return an empty list. Otherwise, create
        a new one.

        :return: a list of installation tasks
        """
        if self._installation_task is not None:
            return [self._installation_task]

        if self._installation_status in [InstallationStatus.SUCCEEDED, InstallationStatus.FAILED]:
            log.debug("install_with_tasks was called, but the installation is already finished.")
            return []

        self._installation_task = RunInstallationTask(
            install_manager=self._install_manager,
        )

        self._installation_task.started_signal.connect(
            self._on_installation_started
        )
        self._installation_task.succeeded_signal.connect(
            self._on_installation_succeeded
        )
        self._installation_task.failed_signal.connect(
            self._on_installation_failed
        )
        self._installation_task.stopped_signal.connect(
            self._on_installation_stopped
        )
        self._installation_task.error_raised_signal.connect(
            self._on_error_raised
        )
        self._installation_task.error_response_signal.connect(
            self._on_error_response
        )

        return [self._installation_task]

    def _set_installation_status(self, status):
        """Set the installation status if the transition is valid.

        Terminal states (SUCCEEDED, FAILED) cannot be overwritten.
        The signal is only emitted when the status actually changes.

        :param status: the new InstallationStatus value
        """
        if self._installation_status in (InstallationStatus.SUCCEEDED, InstallationStatus.FAILED):
            log.debug("Ignoring status change to %s — already in terminal state %s.",
                       status, self._installation_status)
            return

        if self._installation_status == status:
            return

        self._installation_status = status
        self.installation_status_changed.emit()

    def _set_pending_error(self, error_message, error_type):
        """Store an error and notify listeners.

        For fatal errors, also persist the message to disk (so it
        survives a Boss restart) and transition to FAILED.
        Non-critical errors are stored but do not change the status.
        """
        self._pending_error_message = error_message
        self._pending_error_type = error_type
        if error_type == InstallationErrorDialogType.FATAL_ERROR:
            self._persist_error_message(error_message)
            self._set_installation_status(InstallationStatus.FAILED)
        self.pending_error_changed.emit()

    def _persist_error_message(self, error_message):
        self._error_file.write_text(error_message)

    def _on_error_response(self, should_continue):
        """Handle the user's response to a non-critical error.

        On continue: clear the pending error so the UI returns to normal.
        On abort: do nothing here — the task thread will fail and
        _thread_failed_callback will emit the actual fatal error
        with the proper exception message (not the non-critical dialog text).
        """
        if should_continue:
            log.info("User chose to continue past the error.")
            self._set_pending_error(error_message="", error_type="")
        else:
            log.info("User chose to abort.")

    def _on_installation_started(self):
        """Handle the installation task start."""
        log.info("The installation has started.")
        self._set_installation_status(InstallationStatus.RUNNING)
        self.active_installation_task_changed.emit()

    def _on_installation_succeeded(self):
        """Handle the installation task success."""
        log.info("The installation has succeeded.")
        self._set_installation_status(InstallationStatus.SUCCEEDED)

    def _on_installation_failed(self):
        """Handle the installation task failure."""
        log.error("The installation has failed.")
        self._set_installation_status(InstallationStatus.FAILED)

    def _on_error_raised(self, message, error_type):
        """Handle errors raised during installation.

        :param message: the error message
        :param error_type: the error type string
        """
        log.info("Error raised: type=%s, message=%s", error_type, message[:80])
        self._set_pending_error(error_message=message, error_type=error_type)

    def _on_installation_stopped(self):
        """Handle the installation task stop."""
        log.info("The installation has stopped.")
        self._installation_task = None
        self.active_installation_task_changed.emit()

    def collect_configure_runtime_tasks(self):
        """Collect tasks for configuration of the runtime environment.

        FIXME: This is a temporary workaround for add-ons.

        :return: a list of task proxies
        """
        return self._install_manager.collect_configure_runtime_tasks()

    def collect_configure_bootloader_tasks(self, kernel_versions):
        """Collect tasks for configuration of the bootloader.

        FIXME: This is a temporary workaround for add-ons.

        :param kernel_versions: a list of kernel versions
        :return: a list of task proxies
        """
        return self._install_manager.collect_configure_bootloader_tasks(kernel_versions)

    def collect_install_system_tasks(self):
        """Collect tasks for installation of the system.

        FIXME: This is a temporary workaround for add-ons.

        :return: a list of task proxies
        """
        return self._install_manager.collect_install_system_tasks()

    def set_locale(self, locale):
        """Set locale of boss and all modules.

        :param str locale: locale to set
        """
        log.info("Setting locale of all modules to %s.", locale)
        super().set_locale(locale)
        self._module_manager.set_modules_locale(locale)
