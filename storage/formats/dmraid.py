# dmraid.py
# dmraid device formats
#
# Copyright (C) 2009  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Dave Lehman <dlehman@redhat.com>
#

from iutil import log_method_call
from flags import flags
from ..errors import *
from . import DeviceFormat, register_device_format

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("storage")


class DMRaidMember(DeviceFormat):
    """ A dmraid member disk. """
    _type = "dmraidmember"
    _name = "dm-raid member device"
    # XXX This looks like trouble.
    #
    #     Maybe a better approach is a RaidMember format with subclass
    #     for MDRaidMember, letting all *_raid_member types fall through
    #     to the generic RaidMember format, which is basically read-only.
    #
    #     One problem that presents is the possibility of someone passing
    #     a dmraid member to the MDRaidArrayDevice constructor.
    _udevTypes = ["adaptec_raid_member", "ddf_raid_member",
                 "highpoint_raid_member", "isw_raid_member",
                 "jmicron_raid_member", "lsi_mega_raid_member",
                 "nvidia_raid_member", "promise_fasttrack_raid_member",
                 "silicon_medley_raid_member", "via_raid_member"]
    _formattable = False                # can be formatted
    _supported = True                   # is supported
    _linuxNative = False                # for clearpart
    _packages = ["dmraid"]              # required packages
    _resizable = False                  # can be resized
    _bootable = False                   # can be used as boot 
    _maxSize = 0                        # maximum size in MB
    _minSize = 0                        # minimum size in MB

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
        self._raidmem = None

    @property
    def raidmem(self):
        return self._raidmem

    @raidmem.setter
    def raidmem(self, raidmem):
        self._raidmem = raidmem

    def create(self, *args, **kwargs):
        log_method_call(self, device=self.device,
                        type=self.type, status=self.status)
        raise DMRaidMemberError("creation of dmraid members is non-sense")

    def destroy(self, *args, **kwargs):
        log_method_call(self, device=self.device,
                        type=self.type, status=self.status)
        raise DMRaidMemberError("destruction of dmraid members is non-sense")


if flags.cmdline.has_key("iswmd"):
    DMRaidMember._udevTypes.remove("isw_raid_member")

register_device_format(DMRaidMember)

