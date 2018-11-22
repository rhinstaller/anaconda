#
# Copyright (C) Stephen Gallagher
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

__all__ = ["FedoraServerInstallClass"]


class FedoraServerInstallClass(FedoraBaseInstallClass):
    name = "Fedora Server"
    defaultFS = "xfs"
    default_partitioning = SERVER_PARTITIONING
    sortPriority = FedoraBaseInstallClass.sortPriority + 1

    if productVariant != "Server":
        hidden = True

