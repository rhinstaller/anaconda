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
#  Author(s):  Vendula Poncova <vponcova@redhat.com>
#
from enum import Enum

from pyanaconda.core.configuration.base import Section


class SystemType(Enum):
    """The type of the installation system."""
    BOOT_ISO = "BOOT_ISO"
    LIVE_OS = "LIVE_OS"
    BOOTED_OS = "BOOTED_OS"
    UNKNOWN = "UNKNOWN"


class SystemSection(Section):
    """The Installation System section."""

    @property
    def _type(self):
        """Type of the installation system.

        FIXME: This is a temporary solution.
        """
        return self._get_option("type", SystemType)

    @property
    def _is_boot_iso(self):
        """Are we running in the boot.iso?"""
        return self._type is SystemType.BOOT_ISO

    @property
    def _is_live_os(self):
        """Are we running in the live OS?"""
        return self._type is SystemType.LIVE_OS

    @property
    def _is_booted_os(self):
        """Are we running in the booted OS?

        FIXME: This is a temporary workaround for the initial-setup.
        """
        return self._type is SystemType.BOOTED_OS

    @property
    def _is_unknown(self):
        """Are we running in the unknown OS?"""
        return self._type is SystemType.UNKNOWN

    @property
    def can_reboot(self):
        """Can we reboot the system?"""
        return self._is_boot_iso or self._is_booted_os

    @property
    def can_start_compositor(self):
        """Can we start our own Wayland session?"""
        return self._is_boot_iso

    @property
    def can_switch_tty(self):
        """Can we change the foreground virtual terminal?"""
        return self._is_boot_iso

    @property
    def can_audit(self):
        """Can we control auditing?"""
        return self._is_boot_iso

    @property
    def can_set_hardware_clock(self):
        """Can we set the Hardware Clock?"""
        return self._is_boot_iso or self._is_booted_os

    @property
    def can_initialize_system_clock(self):
        """Can we initialize the System Clock?

        FIXME: This is a temporary workaround.
        """
        return self._is_boot_iso or self._is_live_os or self._is_booted_os

    @property
    def can_set_system_clock(self):
        """Can we set the System Clock?"""
        return self._is_boot_iso or self._is_booted_os

    @property
    def can_set_time_synchronization(self):
        """Can we run the NTP daemon?"""
        return self._is_boot_iso or self._is_booted_os

    @property
    def can_activate_keyboard(self):
        """Can we activate the keyboard?

        FIXME: This is a temporary workaround.
        """
        return self._is_boot_iso or self._is_booted_os

    @property
    def can_activate_layouts(self):
        """Can we activate the layouts?

        FIXME: This is a temporary workaround.
        """
        return self._is_boot_iso or self._is_booted_os

    @property
    def can_configure_keyboard(self):
        """Can we configure the keyboard?"""
        return self._is_boot_iso or self._is_live_os or self._is_booted_os

    @property
    def can_modify_syslog(self):
        """Can we modify syslog?"""
        return self._is_boot_iso or self._is_booted_os

    @property
    def can_change_hostname(self):
        """Can we change the hostname?"""
        return self._is_boot_iso or self._is_booted_os

    @property
    def can_configure_network(self):
        """Can we configure the network?"""
        return self._is_boot_iso or self._is_booted_os

    @property
    def can_detect_enabled_smt(self):
        """Can we try to detect enabled SMT?"""
        return self._get_option("can_detect_enabled_smt", bool)

    @property
    def provides_network_config(self):
        """Can we copy network configuration to the target system?

        We can do it only if the current system configuration is created by
        anaconda (or installation process in general, as on Live OS) and
        therefore can be copied to the target system.
        """
        return self._is_boot_iso or self._is_live_os

    @property
    def provides_system_bus(self):
        """Can we access the system DBus?"""
        return self._is_boot_iso or self._is_live_os or self._is_booted_os

    @property
    def provides_resolver_config(self):
        """Can we copy /etc/resolv.conf to the target system?"""
        return self._is_boot_iso

    @property
    def provides_liveuser(self):
        """Is the user `liveuser` available?"""
        return self._is_live_os

    @property
    def can_use_driver_disks(self):
        """Can the system use driver disks?"""
        return self._is_boot_iso

    @property
    def supports_web_ui(self):
        """Can we run Web UI on this system?"""
        return self._is_boot_iso or self._is_live_os
