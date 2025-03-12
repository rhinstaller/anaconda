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
import os

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.constants import INSTALLATION_PHASE_PREINSTALL, PAYLOAD_TYPE_DNF
from pyanaconda.core.path import join_paths, make_directories
from pyanaconda.modules.common.errors.installation import SecurityInstallationError
from pyanaconda.modules.common.task import Task

log = get_module_logger(__name__)


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

    def _dump_certificate(self, cert, root):
        """Dump the certificate into specified file and directory."""
        if not cert.dir:
            raise SecurityInstallationError(
                "Certificate destination is missing for {}".format(cert.filename)
            )

        dst_dir = join_paths(root, cert.dir)
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

    def run(self):
        """Import CA certificates.

        Dump the certificates into specified files and directories.
        """
        if self._phase == INSTALLATION_PHASE_PREINSTALL:
            if self._payload_type != PAYLOAD_TYPE_DNF:
                log.debug("Not importing certificates in pre install phase for %s payload.",
                          self._payload_type)
                return

        for cert in self._certificates:
            log.debug("Importing certificate with filename: %s dir: %s", cert.filename, cert.dir)
            self._dump_certificate(cert, self._sysroot)
