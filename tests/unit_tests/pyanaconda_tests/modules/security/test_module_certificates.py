#
# Copyright (C) 2025  Red Hat, Inc.
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
# Red Hat Author(s): Radek Vykydal <rvykydal@redhat.com>
#
import os
import tempfile
import unittest

from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.modules.common.constants.objects import CERTIFICATES
from pyanaconda.modules.common.structures.security import CertificateData
from pyanaconda.modules.common.errors.installation import SecurityInstallationError
from pyanaconda.modules.security.certificates.certificates import CertificatesModule
from pyanaconda.modules.security.certificates.certificates_interface import CertificatesInterface
from pyanaconda.modules.security.certificates.installation import ImportCertificatesTask
from tests.unit_tests.pyanaconda_tests import check_dbus_property, check_task_creation, \
    patch_dbus_publish_object


CERT_RVTEST = """-----BEGIN CERTIFICATE-----
MIIBjTCCATOgAwIBAgIUWR5HO3v/0I80Ne0jQWVZFODuWLEwCgYIKoZIzj0EAwIw
FDESMBAGA1UEAwwJUlZURVNUIENBMB4XDTI0MTEyMDEzNTk1N1oXDTM0MTExODEz
NTk1N1owFDESMBAGA1UEAwwJUlZURVNUIENBMFkwEwYHKoZIzj0CAQYIKoZIzj0D
AQcDQgAELghFKGEgS8+5/2nx50W0xOqTrKc2Jz/rD/jfL0m4z4fkeAslCOkIKv74
0wfBXMngxi+OF/b3Vh8FmokuNBQO5qNjMGEwHQYDVR0OBBYEFOJarl9Xkd13sLzI
mHqv6aESlvuCMB8GA1UdIwQYMBaAFOJarl9Xkd13sLzImHqv6aESlvuCMA8GA1Ud
EwEB/wQFMAMBAf8wDgYDVR0PAQH/BAQDAgEGMAoGCCqGSM49BAMCA0gAMEUCIAet
7nyre42ReoRKoyHWLDsQmQDzoyU3FQdC0cViqOtrAiEAxYIL+XTTp7Xy9RNE4Xg7
yNWXfdraC/AfMM8fqsxlVJM=
-----END CERTIFICATE-----"""

CERT_RVTEST2 = """-----BEGIN CERTIFICATE-----
MIIBkTCCATegAwIBAgIUN6r4TjFJqP/TS6U25iOGL2Wt/6kwCgYIKoZIzj0EAwIw
FjEUMBIGA1UEAwwLUlZURVNUIDIgQ0EwHhcNMjQxMTIwMTQwMzIxWhcNMzQxMTE4
MTQwMzIxWjAWMRQwEgYDVQQDDAtSVlRFU1QgMiBDQTBZMBMGByqGSM49AgEGCCqG
SM49AwEHA0IABOtXBMEhtcH43dIDHkelODXrSWQQ8PW7oo8lQUEYTNAL1rpWJJDD
1u+bpLe62Z0kzYK0CpeKuXFfwGrzx7eA6vajYzBhMB0GA1UdDgQWBBStV+z7SZSi
YXlamkx+xjm/W1sMSTAfBgNVHSMEGDAWgBStV+z7SZSiYXlamkx+xjm/W1sMSTAP
BgNVHRMBAf8EBTADAQH/MA4GA1UdDwEB/wQEAwIBBjAKBggqhkjOPQQDAgNIADBF
AiEAkQjETC3Yx2xOkA+R0/YR+R+QqpR8p1fd/cGKWFUYxSoCIEuDJcfvPJfFYdzn
CFOCLuymezWz+1rdIXLU1+XStLuB
-----END CERTIFICATE-----"""


class CertificatesInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the Certificates module."""

    def setUp(self):
        """Set up the module."""
        self.certificates_module = CertificatesModule()
        self.certificates_interface = CertificatesInterface(self.certificates_module)

    def _check_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            CERTIFICATES,
            self.certificates_interface,
            *args, **kwargs
        )

    @staticmethod
    def _get_dbus_certs(certs):
        return [
            {
                'cert': get_variant(Str, cert),
                'filename': get_variant(Str, filename),
                'dir': get_variant(Str, cdir)
            }
            for cert, filename, cdir in certs
        ]

    @staticmethod
    def _get_certs(certs_values):
        certs = []
        for values in certs_values:
            c = CertificateData()
            c.cert, c.filename, c.dir = values
            certs.append(c)
        return certs

    def _iface_certificates_setter(self):
        """Provide setter for testing read-only Certificates property."""
        return lambda value: self.certificates_module.set_certificates(
            CertificateData.from_structure_list(value)
        )

    def test_certificates_property(self):
        """Test the certificates property."""
        assert self.certificates_interface.Certificates == []

        certs_value = self._get_dbus_certs([
                (CERT_RVTEST, 'rvtest.pem', '/etc/pki/ca-trust/extracted/pem'),
                (CERT_RVTEST2, 'rvtest2.pem', ''),
        ])

        self._check_dbus_property(
            "Certificates",
            certs_value,
            # read-only property, so provide setter
            setter=self._iface_certificates_setter()
        )

    def _set_certificates(self, certs_values):
        certs_value = self._get_dbus_certs(certs_values)
        set_certificates = self._iface_certificates_setter()
        set_certificates(certs_value)

    @patch_dbus_publish_object
    def test_import_with_task_default(self, publisher):
        """Test the ImportWithTask method"""
        task_path = self.certificates_interface.ImportWithTask()
        obj = check_task_creation(task_path, publisher, ImportCertificatesTask)
        assert obj.implementation._sysroot == "/"

    @patch_dbus_publish_object
    def test_import_with_task_configured(self, publisher):
        """Test the ImportWithTask method"""
        c1 = (CERT_RVTEST, 'rvtest.pem', '/etc/pki/ca-trust/extracted/pem')
        c2 = (CERT_RVTEST2, 'rvtest2.pem', '')
        self._set_certificates([c1, c2])

        task_path = self.certificates_interface.ImportWithTask()
        obj = check_task_creation(task_path, publisher, ImportCertificatesTask)
        assert obj.implementation._sysroot == "/"
        assert len(obj.implementation._certificates) == 2
        obj_c1, obj_c2 = obj.implementation._certificates
        assert c1 == (obj_c1.cert, obj_c1.filename, obj_c1.dir)
        assert c2 == (obj_c2.cert, obj_c2.filename, obj_c2.dir)

    @patch_dbus_publish_object
    def test_install_with_task_default(self, publisher):
        """Test the InstallWithTask method"""
        task_path = self.certificates_interface.InstallWithTask()
        obj = check_task_creation(task_path, publisher, ImportCertificatesTask)
        assert obj.implementation._sysroot == "/mnt/sysroot"
        assert obj.implementation._certificates == []

    @patch_dbus_publish_object
    def test_install_with_task_configured(self, publisher):
        """Test the InstallWithTask method"""
        c1 = (CERT_RVTEST, 'rvtest.pem', '/etc/pki/ca-trust/extracted/pem')
        c2 = (CERT_RVTEST2, 'rvtest2.pem', '')
        self._set_certificates([c1, c2])

        task_path = self.certificates_interface.InstallWithTask()
        obj = check_task_creation(task_path, publisher, ImportCertificatesTask)
        assert obj.implementation._sysroot == "/mnt/sysroot"
        assert len(obj.implementation._certificates) == 2
        obj_c1, obj_c2 = obj.implementation._certificates
        assert c1 == (obj_c1.cert, obj_c1.filename, obj_c1.dir)
        assert c2 == (obj_c2.cert, obj_c2.filename, obj_c2.dir)

    def _check_cert_file(self, cert, sysroot, is_missing=False):
        cert_file = sysroot + cert.dir + "/" + cert.filename
        if is_missing:
            assert os.path.exists(cert_file) is False
        else:
            with open(cert_file) as f:
                # Anaconda adds `\n` to the value when dumping it
                assert f.read() == cert.cert+'\n'

    @patch_dbus_publish_object
    def test_pre_install_with_task_default(self, publisher):
        """Test the PreInstallWithTask method"""
        task_path = self.certificates_interface.PreInstallWithTask()
        obj = check_task_creation(task_path, publisher, ImportCertificatesTask)
        assert obj.implementation._sysroot == "/mnt/sysroot"
        assert obj.implementation._certificates == []

    @patch_dbus_publish_object
    def test_pre_install_with_task_configured(self, publisher):
        """Test the PreInstallWithTask method"""
        c1 = (CERT_RVTEST, 'rvtest.pem', '/etc/pki/ca-trust/extracted/pem')
        c2 = (CERT_RVTEST2, 'rvtest2.pem', '')
        self._set_certificates([c1, c2])

        task_path = self.certificates_interface.PreInstallWithTask()
        obj = check_task_creation(task_path, publisher, ImportCertificatesTask)
        assert obj.implementation._sysroot == "/mnt/sysroot"
        assert len(obj.implementation._certificates) == 2
        obj_c1, obj_c2 = obj.implementation._certificates
        assert c1 == (obj_c1.cert, obj_c1.filename, obj_c1.dir)
        assert c2 == (obj_c2.cert, obj_c2.filename, obj_c2.dir)

    def test_import_certificates_task_files(self):
        """Test the ImportCertificatesTask task dumping the certificate"""
        certs = self._get_certs([
            (CERT_RVTEST, 'rvtest.pem', '/etc/pki/dir1'),
            (CERT_RVTEST2, 'rvtest2.pem', '/etc/pki/dir2'),
        ])

        with tempfile.TemporaryDirectory() as sysroot:
            # c1 has existing dir
            os.makedirs(sysroot+certs[0].dir)
            # c2 has non-existing dir

            ImportCertificatesTask(
                sysroot=sysroot,
                certificates=certs,
            ).run()

            for c in certs:
                self._check_cert_file(c, sysroot)

    def test_import_certificates_task_existing_file(self):
        """Test the ImportCertificatesTask task with existing file to be imported"""
        certs = self._get_certs([
            (CERT_RVTEST, 'rvtest.pem', '/etc/pki/dir1'),
        ])

        c1 = certs[0]
        with tempfile.TemporaryDirectory() as sysroot:
            # certificate file to be dumped already exists
            os.makedirs(sysroot+c1.dir)
            c1_file = sysroot + c1.dir + "/" + c1.filename
            open(c1_file, 'w')

            ImportCertificatesTask(
                sysroot=sysroot,
                certificates=[c1],
            ).run()

            self._check_cert_file(c1, sysroot)

    def test_import_certificates_missing_destination(self):
        """Test the ImportCertificatesTask task with missing destination"""
        certs = self._get_certs([
            (CERT_RVTEST, 'rvtest.pem', ''),
        ])

        with tempfile.TemporaryDirectory() as sysroot:
            with self.assertRaises(SecurityInstallationError):
                ImportCertificatesTask(
                    sysroot=sysroot,
                    certificates=certs,
                ).run()
