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
from pyanaconda.core.configuration.base import Section


class SecuritySection(Section):
    """The Security section."""

    @property
    def selinux(self):
        """Enable SELinux usage in the installed system.

        Valid values:

         -1  The value is not set.
          0  SELinux is disabled (permissive).
          1  SELinux is enabled (enforcing).
        """
        value = self._get_option("selinux", int)

        if value not in (-1, 0, 1):
            raise ValueError("Invalid value: {}".format(value))

        return value
