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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from abc import ABC
from threading import Lock

from pyanaconda.modules.common.errors.task import NoResultError

__all__ = ['ResultProvider']


class ResultProvider(ABC):
    """Abstract class that allows to provide a result of a task."""

    def __init__(self):
        super().__init__()
        self.__result_lock = Lock()
        self.__result = None

    def _set_result(self, result):
        """Set the result of the task.

        :param result: a result of the task
        """
        with self.__result_lock:
            self.__result = result

    def get_result(self):
        """Get the result of the task.

        It raises an exception if no result is provided.

        :return: a result of the task
        :raises: NoResultError if the result is None
        """
        with self.__result_lock:
            if self.__result is None:
                raise NoResultError("The result is not provided.")

            return self.__result
