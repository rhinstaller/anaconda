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
import os

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.constants import INSTALLATION_PHASE_PREINSTALL, PAYLOAD_TYPE_DNF
from pyanaconda.core.path import join_paths, make_directories
from pyanaconda.core.util import execWithRedirect
from pyanaconda.modules.common.errors.installation import SecurityInstallationError
from pyanaconda.modules.common.task import Task

log = get_module_logger(__name__)

# Mapping of certificate types to their default directories.
CERT_TYPE_DIRS = {
    "anchor": "/etc/pki/ca-trust/source/anchors/",
}

# Certificate types that require running update-ca-trust extract.
CERT_TYPES_REQUIRING_UPDATE = {"anchor"}


class ImportCertificatesTask(Task):
    """Task for importing certificates into a system."""

    def __init__(self, sysroot, certificates, payload_type=None, phase=None):
        """Create a new certificates import task.

        :param str sysroot: a path to the root of the target system
        :param certificates: list of certificate data holders
        :param payload_type: a type of the payload
        :param phase: installation phase - INSTALLATION_PHASE_PREINSTALL or None for any other
        """
        super().__init__()
        self._sysroot = sysroot
        self._certificates = certificates
        self._payload_type = payload_type
        self._phase = phase

    @property
    def name(self):
        return "Import CA certificates"

    @staticmethod
    def _get_cert_dir(cert):
        """Get the directory for a certificate based on its type."""
        if cert.type and cert.type in CERT_TYPE_DIRS:
            return CERT_TYPE_DIRS[cert.type]
        return cert.dir

    def _dump_certificate(self, cert, root):
        """Dump the certificate into specified file and directory."""
        cert_dir = self._get_cert_dir(cert)

        if not cert_dir:
            raise SecurityInstallationError(
                "Certificate destination is missing for {}".format(cert.filename)
            )

        dst_dir = join_paths(root, cert_dir)
        if not os.path.exists(dst_dir):
            log.debug("Path %s for certificate %s does not exist, creating.",
                      dst_dir, cert.filename)
            make_directories(dst_dir)

        dst = join_paths(dst_dir, cert.filename)

        if os.path.exists(dst):
            log.info("Certificate file %s already exists, replacing.", dst)

        with open(dst, 'w') as f:
            f.write(cert.cert)
            f.write('\n')

    def _update_ca_trust(self):
        """Run update-ca-trust extract to update the system trust store."""
        log.debug("Running update-ca-trust extract in %s.", self._sysroot)
        rc = execWithRedirect(
            "update-ca-trust", ["extract"],
            root=self._sysroot
        )
        if rc != 0:
            raise SecurityInstallationError(
                "Certificate update failed: update-ca-trust extract failed with return code {}".format(rc)
            )

    def run(self):
        """Import CA certificates.

        Dump the certificates into specified files and directories.
        """
        if self._phase == INSTALLATION_PHASE_PREINSTALL:
            if self._payload_type != PAYLOAD_TYPE_DNF:
                log.debug("Not importing certificates in pre install phase for %s payload.",
                          self._payload_type)
                return

        needs_update = False

        for cert in self._certificates:
            if cert.type and cert.type not in CERT_TYPE_DIRS:
                raise SecurityInstallationError(
                    "Unknown certificate type {} for {}".format(cert.type, cert.filename)
                )

            # In the pre-install phase the target chroot is empty, so skip
            # certificates that only make sense with a fully populated system
            # (e.g. anchor type that needs update-ca-trust).
            if self._phase == INSTALLATION_PHASE_PREINSTALL \
                    and cert.type in CERT_TYPES_REQUIRING_UPDATE:
                log.debug("Skipping type=%s certificate %s in pre-install phase.",
                          cert.type, cert.filename)
                continue

            log.debug("Importing certificate with filename: %s dir: %s type: %s",
                      cert.filename, cert.dir, cert.type)
            self._dump_certificate(cert, self._sysroot)
            if cert.type in CERT_TYPES_REQUIRING_UPDATE:
                needs_update = True

        if needs_update:
            self._update_ca_trust()
