#
# Certificate  module
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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pykickstart.parser import Certificate

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.dbus import DBus
from pyanaconda.modules.common.base import KickstartBaseModule
from pyanaconda.modules.common.constants.objects import CERTIFICATES
from pyanaconda.modules.common.structures.security import CertificateData
from pyanaconda.modules.security.certificates.certificates_interface import (
    CertificatesInterface,
)

log = get_module_logger(__name__)

class CertificatesModule(KickstartBaseModule):
    """The certificates installation module."""

    def __init__(self):
        super().__init__()

        self._certificates = []

    def publish(self):
        """Publish the module."""
        DBus.publish_object(CERTIFICATES.object_path, CertificatesInterface(self))

    def process_kickstart(self, data):
        """Process the kickstart data."""
        for cert in data.certificates:
            cert_data = CertificateData()
            cert_data.filename = cert.filename
            cert_data.cert = cert.cert
            if cert.dir:
                cert_data.dir = cert.dir
            self._certificates.append(cert_data)

    def setup_kickstart(self, data):
        """Setup the kickstart data."""
        for cert in self._certificates:
            cert_ksdata = Certificate(cert=cert.cert, filename=cert.filename, dir=cert.dir)
            data.certificates.append(cert_ksdata)
