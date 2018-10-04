#
# default.py
#
# Copyright (C) 2017  Red Hat, Inc.  All rights reserved.
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
from pyanaconda.installclasses.rhel import RHELBaseInstallClass

__all__ = ["DefaultInstallClass"]


class DefaultInstallClass(RHELBaseInstallClass):
    """This install class will be used by default.

    In case, that anaconda cannot use any other install class,
    this one will be used, so the installation will not fail.
    """
    sortPriority = 0
    hidden = False
