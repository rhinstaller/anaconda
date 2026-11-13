#
# DBus structure for module completeness.
#
# Copyright (C) 2026 Red Hat, Inc.
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
from dasbus.structure import DBusData
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.modules.common.constants.completeness import IncompletenessKind

__all__ = ["IncompletenessReason", "ModuleCompleteness"]


class IncompletenessReason(DBusData):
    """A reason why a module is not ready to install."""

    def __init__(self):
        self._kind = ""
        self._id = ""
        self._message = ""
        self._context = ""
        self._module_name = ""

    @property
    def kind(self) -> Str:
        """A kind of the reason.

        One of the IncompletenessKind values. Tells a caller whether
        waiting can resolve the reason.

        :return: a reason kind
        """
        return self._kind

    @kind.setter
    def kind(self, value: Str):
        self._kind = value

    @property
    def id(self) -> Str:
        """A stable machine-readable code of the reason.

        Lets clients special-case or route a reason without matching
        against translated text.

        For example:
            storage.no-root-device
            users.no-root-password

        :return: a reason id
        """
        return self._id

    @id.setter
    def id(self, value: Str):
        self._id = value

    @property
    def message(self) -> Str:
        """A translated, human-readable explanation.

        :return: a message
        """
        return self._message

    @message.setter
    def message(self, value: Str):
        self._message = value

    @property
    def context(self) -> Str:
        """An optional hint about where to send the user.

        :return: a context or an empty string
        """
        return self._context

    @context.setter
    def context(self, value: Str):
        self._context = value

    @property
    def module_name(self) -> Str:
        """A service name of the module that reported the reason.

        Modules leave this empty. It is annotated by the Boss when it
        aggregates reasons, so a caller can tell them apart.

        :return: a service name or an empty string
        """
        return self._module_name

    @module_name.setter
    def module_name(self, value: Str):
        self._module_name = value

    @classmethod
    def for_busy(cls, reason_id, message, context=""):
        """Create a reason for a module that is still working.

        :param reason_id: a stable machine-readable code
        :param message: a translated explanation
        :param context: an optional hint for clients
        :return: a new reason
        """
        return cls._create(IncompletenessKind.BUSY, reason_id, message, context)

    @classmethod
    def for_unconfigured(cls, reason_id, message, context=""):
        """Create a reason for required input that nobody supplied.

        :param reason_id: a stable machine-readable code
        :param message: a translated explanation
        :param context: an optional hint for clients
        :return: a new reason
        """
        return cls._create(
            IncompletenessKind.UNCONFIGURED, reason_id, message, context
        )

    @classmethod
    def for_invalid(cls, reason_id, message, context=""):
        """Create a reason for input that was supplied and is wrong.

        :param reason_id: a stable machine-readable code
        :param message: a translated explanation
        :param context: an optional hint for clients
        :return: a new reason
        """
        return cls._create(IncompletenessKind.INVALID, reason_id, message, context)

    @classmethod
    def _create(cls, kind, reason_id, message, context):
        reason = cls()
        reason.kind = kind
        reason.id = reason_id
        reason.message = message
        reason.context = context
        return reason


class ModuleCompleteness(DBusData):
    """Completeness of a single module, as collected by the Boss."""

    def __init__(self):
        self._service_name = ""
        self._complete = True
        self._mandatory = True
        self._reasons = []

    @property
    def service_name(self) -> Str:
        """A service name of the module.

        :return: a service name
        """
        return self._service_name

    @service_name.setter
    def service_name(self, value: Str):
        self._service_name = value

    @property
    def complete(self) -> Bool:
        """Would this module block an installation started right now?

        :return: True if the module is ready to install, otherwise False
        """
        return self._complete

    @complete.setter
    def complete(self, value: Bool):
        self._complete = value

    @property
    def mandatory(self) -> Bool:
        """Should this module being incomplete block the installation?

        :return: True if incompleteness blocks the installation
        """
        return self._mandatory

    @mandatory.setter
    def mandatory(self, value: Bool):
        self._mandatory = value

    @property
    def reasons(self) -> List[IncompletenessReason]:
        """Reasons why this module is not ready to install.

        :return: a list of reasons
        """
        return self._reasons

    @reasons.setter
    def reasons(self, value: List[IncompletenessReason]):
        self._reasons = value
