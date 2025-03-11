#
# Copyright (C) 2018 Red Hat, Inc.
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
from abc import ABC
from threading import Lock

from pyanaconda.anaconda_loggers import get_module_logger

log = get_module_logger(__name__)

__all__ = ['Cancellable']


class Cancellable(ABC):
    """Abstract class that allows to cancel a task."""

    def __init__(self):
        super().__init__()
        self.__cancel_lock = Lock()
        self.__cancel = False

    def cancel(self):
        """Request the cancellation of the task."""
        with self.__cancel_lock:
            self.__cancel = True

    def check_cancel(self):
        """Should the task be canceled right now?

        Check if the task cancellation is requested.
        If yes, clear the cancel flag.

        This is a thread safe method.

        :returns: bool
        """
        with self.__cancel_lock:
            return self.__cancel
