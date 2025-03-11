#
# The partitioning factory.
#
# Copyright (C) 2019 Red Hat, Inc.
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
from pyanaconda.modules.storage.partitioning.constants import PartitioningMethod

__all__ = ["PartitioningFactory"]


class PartitioningFactory:
    """The partitioning factory."""

    @staticmethod
    def create_partitioning(method: PartitioningMethod):
        """Create a partitioning module.

        :param method: a partitioning method
        :return: a partitioning module
        """
        if method is PartitioningMethod.AUTOMATIC:
            from pyanaconda.modules.storage.partitioning.automatic.automatic_module import (
                AutoPartitioningModule,
            )
            return AutoPartitioningModule()

        if method is PartitioningMethod.MANUAL:
            from pyanaconda.modules.storage.partitioning.manual.manual_module import (
                ManualPartitioningModule,
            )
            return ManualPartitioningModule()

        if method is PartitioningMethod.CUSTOM:
            from pyanaconda.modules.storage.partitioning.custom.custom_module import (
                CustomPartitioningModule,
            )
            return CustomPartitioningModule()

        if method is PartitioningMethod.INTERACTIVE:
            from pyanaconda.modules.storage.partitioning.interactive.interactive_module import (
                InteractivePartitioningModule,
            )
            return InteractivePartitioningModule()

        if method is PartitioningMethod.BLIVET:
            from pyanaconda.modules.storage.partitioning.blivet.blivet_module import (
                BlivetPartitioningModule,
            )
            return BlivetPartitioningModule()

        raise ValueError("Unknown partitioning method: {}".format(method))

    @staticmethod
    def get_method_for_kickstart(data):
        """Get a partitioning method for the given kickstart data.

        :param data: a kickstart data
        :return: a partitioning method
        """
        if data.autopart.seen:
            return PartitioningMethod.AUTOMATIC

        if data.mount.seen:
            return PartitioningMethod.MANUAL

        if data.reqpart.seen:
            return PartitioningMethod.CUSTOM

        if data.partition.seen:
            return PartitioningMethod.CUSTOM

        if data.logvol.seen:
            return PartitioningMethod.CUSTOM

        if data.volgroup.seen:
            return PartitioningMethod.CUSTOM

        if data.raid.seen:
            return PartitioningMethod.CUSTOM

        if data.btrfs.seen:
            return PartitioningMethod.CUSTOM

        return None
