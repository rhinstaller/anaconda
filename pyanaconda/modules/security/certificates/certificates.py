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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pykickstart.parser import Certificate

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import INSTALLATION_PHASE_PREINSTALL
from pyanaconda.core.dbus import DBus
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.base import KickstartBaseModule
from pyanaconda.modules.common.constants.objects import CERTIFICATES
from pyanaconda.modules.common.structures.security import CertificateData
from pyanaconda.modules.security.certificates.certificates_interface import (
    CertificatesInterface,
)
from pyanaconda.modules.security.certificates.installation import ImportCertificatesTask

log = get_module_logger(__name__)


class CertificatesModule(KickstartBaseModule):
    """The certificates installation module."""

    def __init__(self):
        super().__init__()

        self.certificates_changed = Signal()
        self._certificates = []

    def publish(self):
        """Publish the module."""
        DBus.publish_object(CERTIFICATES.object_path, CertificatesInterface(self))

    def process_kickstart(self, data):
        """Process the kickstart data."""
        certificates = []
        for cert in data.certificates:
            cert_data = CertificateData()
            cert_data.filename = cert.filename
            cert_data.cert = cert.cert
            if cert.dir:
                cert_data.dir = cert.dir
            certificates.append(cert_data)
        self.set_certificates(certificates)

    def setup_kickstart(self, data):
        """Setup the kickstart data."""
        for cert in self._certificates:
            cert_ksdata = Certificate(cert=cert.cert, filename=cert.filename, dir=cert.dir)
            data.certificates.append(cert_ksdata)

    @property
    def certificates(self):
        """Return the certificates."""
        return self._certificates

    def set_certificates(self, certificates):
        """Set the certificates."""
        self._certificates = certificates
        self.certificates_changed.emit()
        # as there is no public setter in the DBus API, we need to emit
        # the properties changed signal here manually
        self.module_properties_changed.emit()
        log.debug("Certificates is set to %s.", certificates)

    def import_with_task(self):
        """Import certificates into the installer environment

        :return: an installation task
        """
        return ImportCertificatesTask(
            sysroot="/",
            certificates=self.certificates,
        )

    def install_with_task(self):
        """Import certificates into the installed system

        :return: a DBus path of the import task
        """
        return ImportCertificatesTask(
            sysroot=conf.target.system_root,
            certificates=self.certificates,
        )

    def pre_install_with_task(self, payload_type):
        """Import certificates into the system before the payload installation

        NOTE: the reason is potential use by rpm scriptlets

        :param payload_type: a string with the payload type
        :return: a DBus path of the import task
        """
        return ImportCertificatesTask(
            sysroot=conf.target.system_root,
            certificates=self.certificates,
            payload_type=payload_type,
            phase=INSTALLATION_PHASE_PREINSTALL,
        )
