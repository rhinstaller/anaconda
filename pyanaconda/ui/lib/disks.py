# User interface library functions for filesystem/disk space checking
#
# Copyright (C) 2013  Red Hat, Inc.
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
# Red Hat Author(s): David Lehman <dlehman@redhat.com>
#                    Chris Lumens <clumens@redhat.com>
#

from blivet.devices import MultipathDevice, iScsiDiskDevice, FcoeDiskDevice

from pyanaconda.flags import flags

__all__ = ["FakeDiskLabel", "FakeDisk", "getDisks", "isLocalDisk"]

class FakeDiskLabel(object):
    def __init__(self, free=0):
        self.free = free

class FakeDisk(object):
    def __init__(self, name, size=0, free=0, partitioned=True, vendor=None,
                 model=None, serial=None, removable=False):
        self.name = name
        self.size = size
        self.format = FakeDiskLabel(free=free)
        self.partitioned = partitioned
        self.vendor = vendor
        self.model = model
        self.serial = serial
        self.removable = removable

    @property
    def description(self):
        return "%s %s" % (self.vendor, self.model)

def getDisks(devicetree, fake=False):
    if not fake:
        devices = devicetree.devices
        if flags.imageInstall:
            hidden_images = [d for d in devicetree._hidden \
                             if d.name in devicetree.diskImages]
            devices += hidden_images
        else:
            devices += devicetree._hidden

        disks = []
        for d in devices:
            if d.isDisk and not d.format.hidden and not d.protected:
                # unformatted DASDs are detected with a size of 0, but they should
                # still show up as valid disks if this function is called, since we
                # can still use them; anaconda will know how to handle them, so they
                # don't need to be ignored anymore
                if d.type == "dasd":
                    disks.append(d)
                elif d.size > 0 and d.mediaPresent:
                    disks.append(d)
    else:
        disks = []
        disks.append(FakeDisk("sda", size=300000, free=10000, serial="00001",
                              vendor="Seagate", model="Monster"))
        disks.append(FakeDisk("sdb", size=300000, free=300000, serial="00002",
                              vendor="Seagate", model="Monster"))
        disks.append(FakeDisk("sdc", size=8000, free=2100, removable=True,
                              vendor="SanDisk", model="Cruzer", serial="00003"))

    # Remove duplicate names from the list.
    return sorted(set(disks), key=lambda d: d.name)

def isLocalDisk(disk):
    return (not isinstance(disk, MultipathDevice)
            and not isinstance(disk, iScsiDiskDevice)
            and not isinstance(disk, FcoeDiskDevice))

def applyDiskSelection(storage, data, use_names):
    onlyuse = use_names[:]
    for disk in (d for d in storage.disks if d.name in onlyuse):
        onlyuse.extend(d.name for d in disk.ancestors
                       if d.name not in onlyuse)

    data.ignoredisk.onlyuse = onlyuse
    data.clearpart.drives = use_names[:]
