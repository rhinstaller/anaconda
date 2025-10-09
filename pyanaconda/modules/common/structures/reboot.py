#
# DBus structure for module runtime reboot data.
#
# Copyright (C) 2025 Red Hat, Inc.
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
from dasbus.typing import Bool, Int

__all__ = ["RebootData"]


class RebootData(DBusData):
    """Module reboot/poweroff/halt/shutdown configuration data."""

    def __init__(self):
        self._action = -1    # KS_* constant: WAIT(0), REBOOT(1), SHUTDOWN(2)
        self._eject = False  # Whether to eject media before action
        self._kexec = False  # Whether to use kexec for reboot

    @property
    def action(self) -> Int:
        """Requested post-installation action.

        Possible values:
            - KS_WAIT (0)
            - KS_REBOOT (1)
            - KS_SHUTDOWN (2)
            - unset (-1)

        KS_WAIT (0) means no action requested.
        """
        return self._action

    @action.setter
    def action(self, value: Int | None):
        if value is None:
            # dbus cannot handle None
            value = -1
        self._action = value

    @property
    def eject(self) -> Bool:
        """Whether to eject optical media before reboot or poweroff.

        :return: True if media should be ejected, False otherwise.
        """
        return self._eject

    @eject.setter
    def eject(self, value: Bool):
        self._eject = value

    @property
    def kexec(self) -> Bool:
        """Whether to use kexec for reboot.

        If True and action is 'reboot', the system should reboot using kexec,
        bypassing BIOS/Firmware and bootloader.

        :return: True if kexec should be used, False otherwise.
        """
        return self._kexec

    @kexec.setter
    def kexec(self, value: Bool):
        self._kexec = value
