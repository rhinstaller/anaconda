#
# Copyright (C) 2021 Red Hat, Inc.
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

__all__ = ["context"]


class UserInterfaceContext:
    """The context of the user interface.

    The context provides access to persistent objects
    of the user interface. The goal is to replace all
    these objects with this one.

    WARNING: This class is also used by the Initial Setup tool.
    Please keep that in mind when doing any API breaking changes.

    We might replace this object with a DBus module in
    the future.
    """

    def __init__(self):
        self._payload_type = None

    @property
    def payload_type(self):
        """The type of the payload.

        :return: a string or None
        """
        return self._payload_type

    @payload_type.setter
    def payload_type(self, value):
        self._payload_type = value


context = UserInterfaceContext()
