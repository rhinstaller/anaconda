# prepboot.py
# Format class for PPC PReP Boot.
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

from ..errors import *
from . import DeviceFormat, register_device_format
from parted import PARTITION_PREP
import os
import logging
log = logging.getLogger("storage")

class PPCPRePBoot(DeviceFormat):
    """ Generic device format. """
    _type = "prepboot"
    _name = "PPC PReP Boot"
    _udevTypes = []
    partedFlag = PARTITION_PREP
    _formattable = True                 # can be formatted
    _linuxNative = True                 # for clearpart
    _maxSize = 10                       # maximum size in MB
    _minSize = 4                        # minimum size in MB

    def __init__(self, *args, **kwargs):
        """ Create a PRePBoot instance.

            Keyword Arguments:

                device -- path to the underlying device
                exists -- indicates whether this is an existing format

        """
        DeviceFormat.__init__(self, *args, **kwargs)

    def create(self, *args, **kwargs):
        if self.exists:
            raise FSError("PReP Boot format already exists")

        DeviceFormat.create(self, *args, **kwargs)

        try:
            fd = os.open(self.device, os.O_RDWR)
            length = os.lseek(fd, 0, os.SEEK_END)
            os.lseek(fd, 0, os.SEEK_SET)
            buf = '\0' * 1024 * 1024
            while length > 0:
                if length >= len(buf):
                     os.write(fd, buf)
                     length -= len(buf)
                else:
                     buf = '0' * length
                     os.write(fd, buf)
                     length = 0
            os.close(fd)
        except OSError as e:
            log.error("error zeroing out %s: %s" % (self.device, e))
            if fd:
                os.close(fd)

    @property
    def status(self):
        return False

    @property
    def supported(self):
        from pyanaconda import platform
        return isinstance(platform.getPlatform(), platform.IPSeriesPPC)

register_device_format(PPCPRePBoot)

