#
# DBus interface for the certificate module.
#
# Copyright (C) 2025 Red Hat, Inc.
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
from dasbus.server.interface import dbus_interface
from dasbus.typing import *  # pylint: disable=wildcard-import
from pyanaconda.modules.common.base import KickstartModuleInterfaceTemplate
from pyanaconda.modules.common.constants.objects import CERTIFICATES
from pyanaconda.modules.common.structures.security import CertificateData


@dbus_interface(CERTIFICATES.interface_name)
class CertificatesInterface(KickstartModuleInterfaceTemplate):
    """DBus interface for the certificate installation module."""

    def GetCertificates(self) -> List[Str]:
        """Get all certificates to be installed the system.

        :return: a list of certificates names with their content
        """
        return [CertificateData.to_structure(cert) for cert in self.implementation.get_certificates()]
