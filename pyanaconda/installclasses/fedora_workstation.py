#
# Copyright (C) 2017  Red Hat, Inc.  All rights reserved.
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

__all__ = ["FedoraWorkstationInstallClass"]


class FedoraWorkstationInstallClass(FedoraBaseInstallClass):
    name = "Fedora Workstation"
    stylesheet = "/usr/share/anaconda/pixmaps/workstation/fedora-workstation.css"
    sortPriority = FedoraBaseInstallClass.sortPriority + 1
    defaultPackageEnvironment = "workstation-product-environment"
    bootloader_menu_autohide = True

    if productVariant != "Workstation":
        hidden = True
