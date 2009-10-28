# partspec.py
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
# Red Hat Author(s): Chris Lumens <clumens@redhat.com>
#

class PartSpec(object):
    def __init__(self, mountpoint=None, fstype=None, size=None, maxSize=None,
                 grow=False, asVol=False, weight=0, requiredSpace=0):
        """ Create a new storage specification.  These are used to specify
            the default partitioning layout as an object before we have the
            storage system up and running.  The attributes are obvious
            except for the following:

            asVol -- Should this be allocated as a logical volume?  If not,
                     it will be allocated as a partition.
            weight -- An integer that modifies the sort algorithm for partition
                      requests.  A larger value means the partition will end up
                      closer to the front of the disk.  This is mainly used to
                      make sure /boot ends up in front, and any special (PReP,
                      appleboot, etc.) partitions end up in front of /boot.
                      This value means nothing if asVol=False.
            requiredSpace -- This value is only taken into account if
                             asVol=True, and specifies the size in MB that the
                             containing VG must be for this PartSpec to even
                             get used.  The VG's size is calculated before any
                             other LVs are created inside it.  If not enough
                             space exists, this PartSpec will never get turned
                             into an LV.
        """

        self.mountpoint = mountpoint
        self.fstype = fstype
        self.size = size
        self.maxSize = maxSize
        self.grow = grow
        self.asVol = asVol
        self.weight = weight
        self.requiredSpace = requiredSpace

    def __str__(self):
        s = ("%(type)s instance (%(id)s) -- \n"
             "  mountpoint = %(mountpoint)s  asVol = %(asVol)s\n"
             "  weight = %(weight)s  fstype = %(fstype)s\n"
             "  size = %(size)s  maxSize = %(maxSize)s  grow = %(grow)s\n" %
             {"type": self.__class__.__name__, "id": "%#x" % id(self),
              "mountpoint": self.mountpoint, "asVol": self.asVol,
              "weight": self.weight, "fstype": self.fstype, "size": self.size,
              "maxSize": self.maxSize, "grow": self.grow})

        return s
