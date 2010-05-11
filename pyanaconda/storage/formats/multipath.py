# multipath.py
# multipath device formats
#
# Copyright (C) 2009  Red Hat, Inc.
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
# Any Red Hat trademarks that are incorporated in the source code or
# documentation are not subject to the GNU General Public License and
# may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Peter Jones <pjones@redhat.com>
#

from ..storage_log import log_method_call
from ..errors import *
from . import DeviceFormat, register_device_format

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("storage")

class MultipathMember(DeviceFormat):
    """ A multipath member disk. """
    _type = "multipath_member"
    _name = "multipath member device"
    _udev_types = ["multipath_member"]
    _formattable = False                # can be formatted
    _supported = True                   # is supported
    _linuxNative = False                # for clearpart
    _packages = ["device-mapper-multipath"] # required packages
    _resizable = False                  # can be resized
    _bootable = False                   # can be used as boot
    _maxSize = 0                        # maximum size in MB
    _minSize = 0                        # minimum size in MB
    _hidden = True                      # hide devices with this formatting?

    def __init__(self, *args, **kwargs):
        """ Create a DeviceFormat instance.

            Keyword Arguments:

                device -- path to the underlying device
                uuid -- this format's UUID
                exists -- indicates whether this is an existing format

            On initialization this format is like DeviceFormat

        """
        log_method_call(self, *args, **kwargs)
        DeviceFormat.__init__(self, *args, **kwargs)

        # Initialize the attribute that will hold the block object.
        self._member = None

    def __str__(self):
        s = DeviceFormat.__str__(self)
        s += ("  member = %(member)r" % {"member": self.member})
        return s

    def _getMember(self):
        return self._member

    def _setMember(self, member):
        self._member = member

    member = property(lambda s: s._getMember(),
                      lambda s,m: s._setMember(m))

    def create(self, *args, **kwargs):
        log_method_call(self, device=self.device,
                        type=self.type, status=self.status)
        raise MultipathMemberError("creation of multipath members is non-sense")

    def destroy(self, *args, **kwargs):
        log_method_call(self, device=self.device,
                        type=self.type, status=self.status)
        raise MultipathMemberError("destruction of multipath members is non-sense")

register_device_format(MultipathMember)

