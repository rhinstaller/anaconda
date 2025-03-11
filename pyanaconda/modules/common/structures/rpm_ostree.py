#
# DBus structures for the RPM OSTree data.
#
# Copyright (C) 2020 Red Hat, Inc.
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
from dasbus.typing import Bool, Str

__all__ = ["RPMOSTreeConfigurationData", "RPMOSTreeContainerConfigurationData"]


class RPMOSTreeConfigurationData(DBusData):
    """Structure to hold RPM OSTree configuration."""

    def __init__(self):
        self._osname = ""
        self._remote = ""
        self._url = ""
        self._ref = ""
        self._gpg_verification_enabled = True

    @staticmethod
    def is_container():
        """Is this native container source?"""
        return False

    @property
    def osname(self) -> Str:
        """Management root for OS installation."""
        return self._osname

    @osname.setter
    def osname(self, value: Str):
        self._osname = value

    @property
    def remote(self) -> Str:
        """Remote management root for OS installation."""
        return self._remote

    @remote.setter
    def remote(self, value: Str):
        self._remote = value

    @property
    def url(self) -> Str:
        """URL of the repository to install from."""
        return self._url

    @url.setter
    def url(self, value: Str):
        self._url = value

    @property
    def ref(self) -> Str:
        """Name of branch in the repository."""
        return self._ref

    @ref.setter
    def ref(self, value: Str):
        self._ref = value

    @property
    def gpg_verification_enabled(self) -> Bool:
        """Is the GPG key verification enabled?"""
        return self._gpg_verification_enabled

    @gpg_verification_enabled.setter
    def gpg_verification_enabled(self, value: Bool):
        self._gpg_verification_enabled = value


class RPMOSTreeContainerConfigurationData(DBusData):
    """Structure to hold RPM OSTree from container configuration."""

    def __init__(self):
        self._stateroot = ""
        self._remote = ""
        self._transport = ""
        self._url = ""
        self._signature_verification_enabled = True

    @staticmethod
    def is_container():
        """Is this native container source?"""
        return True

    @property
    def stateroot(self) -> Str:
        """Name for the state directory, also known as "osname".

        This could be optional.
        """
        return self._stateroot

    @stateroot.setter
    def stateroot(self, value: Str):
        self._stateroot = value

    @property
    def transport(self) -> Str:
        """Ostree transport protocol used.

        This could be optional (default will be 'repository').
        """
        return self._transport

    @transport.setter
    def transport(self, value: Str):
        self._transport = value

    @property
    def remote(self) -> Str:
        """Name of the OSTree remote."""
        return self._remote

    @remote.setter
    def remote(self, value: Str):
        self._remote = value

    @property
    def url(self) -> Str:
        """URL of the repository to install from."""
        return self._url

    @url.setter
    def url(self, value: Str):
        self._url = value

    @property
    def signature_verification_enabled(self) -> Bool:
        """Is the GPG key verification enabled?"""
        return self._signature_verification_enabled

    @signature_verification_enabled.setter
    def signature_verification_enabled(self, value: Bool):
        self._signature_verification_enabled = value
