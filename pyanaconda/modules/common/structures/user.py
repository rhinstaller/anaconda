#
# DBus structures for describing the user.
#
# Copyright (C) 2019  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
from dasbus.structure import DBusData, generate_string_from_data
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.core.constants import ID_MODE_USE_DEFAULT, ID_MODE_USE_VALUE

__all__ = ["UserData"]


class UserData(DBusData):
    """User data."""

    def __init__(self):
        self._name = ""
        self._uid = 0
        self._uid_mode = ID_MODE_USE_DEFAULT
        self._groups = []
        self._gid = 0
        self._gid_mode = ID_MODE_USE_DEFAULT
        self._homedir = ""
        self._password = ""
        self._is_crypted = True
        self._lock = False
        self._shell = ""
        self._gecos = ""

    @property
    def name(self) -> Str:
        """Username."

        For example: 'user'

        Should comply with the usual limitations for Linux usernames.

        :return: a username
        :rtype: str
        """
        return self._name

    @name.setter
    def name(self, name: Str):
        self._name = name

    @property
    def uid_mode(self) -> Str:
        """Mode of UID.

        Contains a string describing the mode of the user's UID: Use the value or default.

        Possible values are:
        - "ID_MODE_USE_VALUE"
        - "ID_MODE_USE_DEFAULT"

        :return: the mode
        :rtype str:
        """
        return self._uid_mode

    @uid_mode.setter
    def uid_mode(self, status: Str):
        self._uid_mode = status

    @property
    def uid(self) -> UInt32:
        """The users UID.

        If ignored due to uid_mode, this defaults to the next available non-system UID.

        For example: 1234

        :return: user's UID
        :rtype: int
        """
        return self._uid

    @uid.setter
    def uid(self, uid: UInt32):
        self._uid = uid

    def get_uid(self):
        """Return a UID value which can be a number or None.

        Prefer using this method instead of directly reading uid and uid_mode.

        :return: UID or None if not set
        :rtype: int or None
        """
        if self._uid_mode == ID_MODE_USE_DEFAULT:
            return None
        else:
            return self._uid

    def set_uid(self, new_uid):
        """Set UID value and mode from a value which can be None.

        Prefer using this method instead of directly setting uid and uid_mode.

        :param new_uid: new UID
        :type new_uid: int or None
        """
        if new_uid is not None:
            self._uid = new_uid
            self._uid_mode = ID_MODE_USE_VALUE
        else:
            self._uid = 0
            self._uid_mode = ID_MODE_USE_DEFAULT

    @property
    def groups(self) -> List[Str]:
        """List of additional groups (in additional to the default group named after
        the user) the user should be a member of. Any groups that do not already
        exist will be created.

        For example: ['mock', 'dialout']

        :return: a list of groups the user should be a member of
        :rtype: a list of str
        """
        return self._groups

    @groups.setter
    def groups(self, groups: List[Str]):
        self._groups = groups

    @property
    def gid_mode(self) -> Str:
        """Mode of GID.

        Contains a string describing the mode of the user's GID: Use the value or default.

        Possible values are:
        - "ID_MODE_USE_VALUE"
        - "ID_MODE_USE_DEFAULT"

        :return: the mode
        :rtype str:
        """
        return self._gid_mode

    @gid_mode.setter
    def gid_mode(self, status: Str):
        self._gid_mode = status

    @property
    def gid(self) -> UInt32:
        """The GID of the user's primary group.

        If ignored due to gid_mode, defaults to the next available non-system GID.

        For example: 1234

        :return: primary group GID
        :rtype: int
        """
        return self._gid

    @gid.setter
    def gid(self, gid: UInt32):
        self._gid = gid

    def get_gid(self):
        """Return a GID value which can be a number or None.

        Prefer using this method instead of directly reading gid and gid_mode.

        :return: GID or None if not set
        :rtype: int or None
        """
        if self._gid_mode == ID_MODE_USE_DEFAULT:
            return None
        else:
            return self._gid

    def set_gid(self, new_gid):
        """Set GID value and mode from a value which can be None.

        Prefer using this method instead of directly writing gid and gid_mode.

        :param new_gid: new GID
        :type new_gid: int or None
        """
        if new_gid is not None:
            self._gid = new_gid
            self._gid_mode = ID_MODE_USE_VALUE
        else:
            self._gid = 0
            self._gid_mode = ID_MODE_USE_DEFAULT

    @property
    def homedir(self) -> Str:
        """The home directory of the user.

        If not provided, this defaults to /home/.

        For example: 'user_home'

        :return: home directory of the user
        :rtype: str
        """
        return self._homedir

    @homedir.setter
    def homedir(self, homedir: Str):
        self._homedir = homedir

    @property
    def password(self) -> Str:
        """The user password.

        If not provided, the account will be locked by default. If this is set,
        the password argument is assumed to already be encrypted.

        If the plaintext property has been set, it has the opposite effect,
        the user password is assumed to not be encrypted.

        To create an encrypted password you can use python:

        python3 -c 'import crypt_r; print(crypt_r.crypt("My Password", "$y$j9T$My Sault"))'

        This will compute a hash of your password using the yescrypt hasing method and
        your provided salt.

        If the yescrypt method is not supported by your system, you can use the
        sha512crypt hashing method:

        python3 -c 'import crypt_r; print(crypt_r.crypt("My Password", "$6$My Sault"))'

        This will compute a hash of your password using the sha512crypt hasing method
        and your provided salt.

        For example: "CorrectHorseBatteryStaple"

        :return: user password
        :rtype: str
        """
        return self._password

    @password.setter
    def password(self, password: Str):
        self._password = password

    @property
    def is_crypted(self) -> Bool:
        """Reports if the password is already crypted.

        A password is considered to be crypted by default.

        For example: True

        :return: if password is already crypted
        :rtype: bool
        """
        return self._is_crypted

    @is_crypted.setter
    def is_crypted(self, is_crypted: Bool):
        self._is_crypted = is_crypted

    @property
    def lock(self) -> Bool:
        """If lock is True, this user account will be locked be locked.

        That is, the user will not be able to login from the console.

        For example: False

        :rtype: if the user account should be locked
        :rtype: bool
        """
        return self._lock

    @lock.setter
    def lock(self, lock: Bool):
        self._lock = lock

    @property
    def shell(self) -> Str:
        """The users login shell.

        If not provided this defaults to the system default.

        For example: "/bin/bash"

        :return: user login shell
        :rtype: str
        """
        return self._shell

    @shell.setter
    def shell(self, shell: Str):
        self._shell = shell

    @property
    def gecos(self) -> Str:
        """Provides the GECOS information for the user.

        This is a string of various system-specific fields separated by a comma.
        It is frequently used to specify the user's full name, office number, and the like.
        See man 5 passwd for more details.

        For examples: "foo"

        :return: GECOS information for the user
        :rtype: str
        """
        return self._gecos

    @gecos.setter
    def gecos(self, gecos: Str):
        self._gecos = gecos

    def __eq__(self, other_instance):
        """Compare if this UserData instance is the same as other UserData instance.

        As we don't really do much validation for the user specifications, including
        duplication checks and will just warn about errors during user creation then
        simply checking the user name seems like a good enough way to tell two users apart.

        Different settings other than username are just two variants of the same user.
        Two users with different username are two different users.

        :param other_instance: another UserData instance
        :return: if the other instance seems to be functionally the same as this one
        """
        return self.name == other_instance.name

    def __repr__(self):
        """Describe the user for easy debugging.

        As there are many fields many of which might not be set,
        we only try to list the values that are set.

        :return: a string describing the UserData instance
        :rtype: str
        """
        return generate_string_from_data(
            self, skip=["password"], add={"password_set": bool(self.password)}
        )

    def has_admin_priviledges(self):
        """Report if the user described by this structure is an admin.

        Admin users are members of the "wheel" group.

        :return: True if user is admin, False otherwise
        :rtype: bool
        """
        return "wheel" in self._groups

    def set_admin_priviledges(self, admin):
        """Set if the user should be an admin.

        This effectively means adding/removing the "wheel" group from users group list.
        """
        if admin and "wheel" not in self._groups:
            self._groups.append("wheel")
        elif not admin and "wheel" in self._groups:
            self._groups.remove("wheel")
