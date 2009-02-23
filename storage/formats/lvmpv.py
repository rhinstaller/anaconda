# lvmpv.py
# Device format classes for anaconda's storage configuration module.
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

from errors import *
from iutil import log_method_call
from deviceformat import *
import lvm
#from parted import PARTITION_LVM

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("storage")


class LVMPhysicalVolume(DeviceFormat):
    """ An LVM physical volume. """
    _type = "lvmpv"
    _name = "physical volume (LVM)"
    _udevTypes = ["LVM2_member"]
    #partedFlags = PARTITION_LVM
    _formattable = True                 # can be formatted
    _supported = True                   # is supported
    _linuxNative = True                 # for clearpart
    _packages = ["lvm2"]                # required packages

    def __init__(self, *args, **kwargs):
        """ Create an LVMPhysicalVolume instance.

            Keyword Arguments:

                device -- path to the underlying device
                uuid -- this PV's uuid (not the VG uuid)
                vgName -- the name of the VG this PV belongs to
                vgUuid -- the UUID of the VG this PV belongs to
                peStart -- offset of first physical extent
                exists -- indicates whether this is an existing format

        """
        log_method_call(self, *args, **kwargs)
        DeviceFormat.__init__(self, *args, **kwargs)
        self.vgName = kwargs.get("vgName")
        self.vgUuid = kwargs.get("vgUuid")
        # liblvm may be able to tell us this at some point, even
        # for not-yet-created devices
        self.peStart = kwargs.get("peStart", 0.1875)    # in MB

    def probe(self):
        """ Probe for any missing information about this device. """
        log_method_call(self, device=os.path.basename(self.device),
                        type=self.type, status=self.status)
        if not self.exists:
            raise PhysicalVolumeError("format has not been created")

        pass
        #info = lvm.pvinfo(self.device)
        #self.vgName = info['vg_name']
        #self.vgUuid = info['vg_uuid']

    def create(self, *args, **kwargs):
        """ Create the format. """
        log_method_call(self, device=os.path.basename(self.device),
                        type=self.type, status=self.status)
        if self.exists:
            raise PhysicalVolumeError("format already exists")

        """ Consider use of -Z|--zero
            -f|--force or -y|--yes may be required
        """
        lvm.pvcreate(self.device)
        self.notifyKernel()

    def destroy(self, *args, **kwargs):
        """ Destroy the format. """
        log_method_call(self, device=os.path.basename(self.device),
                        type=self.type, status=self.status)
        if not self.exists:
            raise PhysicalVolumeError("format has not been created")

        if self.status:
            raise PhysicalVolumeError("device is active")

        # FIXME: verify path exists?
        lvm.pvremove(self.device)
        self.notifyKernel()

    @property
    def status(self):
        # XXX hack
        for d in os.listdir("/dev/mapper"):
            if d.startswith("%s-" % self.vgName):
                return True
        return False


register_device_format(LVMPhysicalVolume)

