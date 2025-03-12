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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Chris Lumens <clumens@redhat.com>
#

from pykickstart.constants import (
    AUTOPART_TYPE_BTRFS,
    AUTOPART_TYPE_LVM,
    AUTOPART_TYPE_LVM_THINP,
    AUTOPART_TYPE_PLAIN,
)


class PartSpec:

    def __init__(self, mountpoint=None, fstype=None, size=None, max_size=None,
                 grow=False, btr=False, lv=False, thin=False, weight=0,
                 required_space=0, encrypted=False, schemes=None):
        """ Create a new storage specification.  These are used to specify
            the default partitioning layout as an object before we have the
            storage system up and running.  The attributes are obvious
            except for the following:

            btr -- Should this be allocated as a btrfs subvolume?  If not,
                   it will be allocated as a partition.
            lv -- Should this be allocated as a logical volume?  If not,
                  it will be allocated as a partition.
            thin -- Should this be allocated as a thin logical volume if it is
                    being allocated as a logical volume?
            weight -- An integer that modifies the sort algorithm for partition
                      requests.  A larger value means the partition will end up
                      closer to the front of the disk.  This is mainly used to
                      make sure /boot ends up in front, and any special (PReP,
                      appleboot, etc.) partitions end up in front of /boot.
                      This value means nothing unless lv and btr are both False.
            required_space -- This value is only taken into account if
                             lv=True, and specifies the size in MiB that the
                             containing VG must be for this PartSpec to even
                             get used.  The VG's size is calculated before any
                             other LVs are created inside it.  If not enough
                             space exists, this PartSpec will never get turned
                             into an LV.
            encrypted -- Should this request be encrypted? For logical volume
                         requests, this is satisfied if the PVs are encrypted
                         as in the case of encrypted LVM autopart.
            schemes -- Create the mount point only for specific schemes if any.
        """

        self.mountpoint = mountpoint
        self.fstype = fstype
        self.size = size
        self.max_size = max_size
        self.grow = grow
        self.lv = lv
        self.btr = btr
        self.thin = thin
        self.weight = weight
        self.required_space = required_space
        self.encrypted = encrypted
        self.schemes = schemes or set()

    # Force str and unicode types in case any of the properties are unicode
    def _to_string(self):
        s = ("%(type)s instance (%(id)s) -- \n"
             "  mountpoint = %(mountpoint)s  lv = %(lv)s"
             "  thin = %(thin)s  btrfs = %(btrfs)s\n"
             "  weight = %(weight)s  fstype = %(fstype)s  encrypted = %(enc)s\n"
             "  size = %(size)s  max_size = %(max_size)s  grow = %(grow)s\n"
             "  required_space = %(required_space)s\n"
             "  schemes = %(schemes)s" %
             {"type": self.__class__.__name__, "id": "%#x" % id(self),
              "mountpoint": self.mountpoint, "lv": self.lv, "btrfs": self.btr,
              "weight": self.weight, "fstype": self.fstype, "size": self.size,
              "enc": self.encrypted, "max_size": self.max_size, "grow": self.grow,
              "thin": self.thin, "required_space": self.required_space,
              "schemes": self.schemes})

        return s

    def is_partition(self, scheme):
        """Is the specified device a partition in the given scheme?

        :param scheme: a partitioning scheme
        :return: True or False
        """
        return not self.is_volume(scheme)

    def is_volume(self, scheme):
        """Is the specified device a volume in the given scheme?

        :param scheme: a partitioning scheme
        :return: True or False
        """
        if scheme == AUTOPART_TYPE_PLAIN:
            return False

        return self.is_lvm_volume(scheme) or self.is_btrfs_subvolume(scheme)

    def is_lvm_volume(self, scheme):
        """Is the specified device an LVM volume in the given scheme?

        :param scheme: a partitioning scheme
        :return: True or False
        """
        return scheme in (AUTOPART_TYPE_LVM, AUTOPART_TYPE_LVM_THINP) and self.lv

    def is_lvm_thin_volume(self, scheme):
        """Is the specified device an LVM thin volume in the given scheme?

        :param scheme: a partitioning scheme
        :return: True or False
        """
        if not self.is_lvm_volume(scheme):
            return False

        return scheme == AUTOPART_TYPE_LVM_THINP and self.thin

    def is_btrfs_subvolume(self, scheme):
        """Is the specified device a Btrfs subvolume in the given scheme?

        :param scheme: a partitioning scheme
        :return: True or False
        """
        return scheme == AUTOPART_TYPE_BTRFS and self.btr

    def __str__(self):
        return self._to_string()

    def __eq__(self, other):
        return isinstance(other, PartSpec) and vars(self) == vars(other)

    def __repr__(self):
        return str(self)
