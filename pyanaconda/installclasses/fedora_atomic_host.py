#
# Fedora Atomic Host install class defaults
#
# Copyright (C) 2014  Red Hat, Inc.  All rights reserved.
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
from pyanaconda.installclasses.fedora import FedoraBaseInstallClass
from pyanaconda.product import productVariant
from pyanaconda.storage.partitioning import SERVER_PARTITIONING

import logging
log = logging.getLogger("anaconda")

__all__ = ['AtomicHostInstallClass']


class AtomicHostInstallClass(FedoraBaseInstallClass):
    name = "Atomic Host"
    sortPriority = FedoraBaseInstallClass.sortPriority + 1
    defaultFS = "xfs"
    default_partitioning = SERVER_PARTITIONING

    if productVariant != "AtomicHost":
        hidden = True
