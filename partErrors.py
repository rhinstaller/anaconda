#
# partErrors.py: partitioning error exceptions
#
# Copyright (C) 2002  Red Hat, Inc.  All rights reserved.
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
# Author(s): Matt Wilson <msw@redhat.com>
#            Jeremy Katz <katzj@redhat.com>
#            Mike Fulbright <msf@redhat.com>
#

"""Exceptions for use in partitioning."""


class PartitioningError(Exception):
    """A critical error which must be resolved to continue the installation."""
    def __init__(self, message=""):
        self.message = str(message)

    def __str__ (self):
        return self.message

class PartitioningWarning(Exception):
    """A warning which may be ignored and still complete the installation."""
    def __init__(self, message=""):
        self.message = str(message)

    def __str__ (self):
        return self.message

class LabelError(Exception):
    """The device could not be labeled."""
    def __init__(self, message=""):
        self.message = str(message)

    def __str__(self):
        return self.message
