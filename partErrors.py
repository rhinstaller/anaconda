#
# partErrors.py: partitioning error exceptions
#
# Matt Wilson <msw@redhat.com>
# Jeremy Katz <katzj@redhat.com>
# Mike Fulbright <msf@redhat.com>
#
# Copyright 2002 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
"""Exceptions for use in partitioning."""


class PartitioningError(Exception):
    """A critical error which must be resolved to continue the installation."""
    def __init__ (self, value):
        self.value = value

    def __str__ (self):
        return self.value

class PartitioningWarning(Exception):
    """A warning which may be ignored and still complete the installation."""
    def __init__ (self, value):
        self.value = value
        
    def __str__ (self):
        return self.value

class LabelError(Exception):
    """The device could not be labeled."""
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return self.value
