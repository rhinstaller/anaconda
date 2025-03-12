#
# DBus interface for the certificate module.
#
# Copyright (C) 2024 Red Hat, Inc.
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
from dasbus.server.interface import dbus_interface
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.modules.common.base import KickstartModuleInterfaceTemplate
from pyanaconda.modules.common.constants.objects import CERTIFICATES
from pyanaconda.modules.common.containers import TaskContainer
from pyanaconda.modules.common.structures.security import CertificateData


@dbus_interface(CERTIFICATES.interface_name)
class CertificatesInterface(KickstartModuleInterfaceTemplate):
    """DBus interface for the certificate installation module."""

    def connect_signals(self):
        super().connect_signals()
        self.watch_property("Certificates", self.implementation.certificates_changed)

    @property
    def Certificates(self) -> List[Structure]:
        """All certificates.

        :return: a list of certificate DBus Structures
        """
        return CertificateData.to_structure_list(self.implementation.certificates)

    def ImportWithTask(self) -> ObjPath:
        """Import certificates in the installer environment

        :return: a DBus path of the import task
        """
        return TaskContainer.to_object_path(
            self.implementation.import_with_task()
        )

    def InstallWithTask(self) -> ObjPath:
        """Import certificates into the installed system

        :return: a DBus path of the import task
        """
        return TaskContainer.to_object_path(
            self.implementation.install_with_task()
        )

    def PreInstallWithTask(self, payload_type: Str) -> ObjPath:
        """Import certificates into the system before the payload installation

        NOTE: the reason is potential use by rpm scriptlets

        :param payload_type: a string with the payload type
        :return: a DBus path of the import task
        """
        return TaskContainer.to_object_path(
            self.implementation.pre_install_with_task(payload_type)
        )
