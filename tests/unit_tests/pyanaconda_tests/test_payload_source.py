#
# Copyright (C) 2018  Red Hat, Inc.
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
# Authors: Jiri Konecny <jkonecny@redhat.com>
#


import enum
import unittest

import pytest

from pyanaconda.modules.common.constants.services import PAYLOADS
from pyanaconda.payload.source import PayloadSourceTypeUnrecognized, SourceFactory
from pyanaconda.payload.source.sources import *  # pylint: disable=wildcard-import
from tests.unit_tests.pyanaconda_tests import patch_dbus_get_proxy_with_cache


class TestValues(enum.Enum):
    http = "http://server.example.com/test"
    https = "https://server.example.com/test"
    ftp = "ftp://server.example.com/test"
    nfs_ks = "nfs://server.nfs.com:/path/on/server"
    nfs_main_repo = "nfs:soft,async:server.example.com:/path/to/install_tree"
    nfs_main_repo2 = "nfs:server.example.com:/path/to/install_tree"
    file = "file:///root/extremely_secret_file.txt"

    cdrom = "cdrom"
    cdrom_test = "cdrom:/dev/cdrom"
    harddrive = "hd:/dev/sda2:/path/to/iso.iso"
    harddrive_label = "hd:LABEL=TEST:/path/to/iso.iso"
    harddrive_uuid = "hd:UUID=8176c7bf-04ff-403a-a832-9557f94e61db:/path/to/iso.iso"
    hmc = "hmc"

    broken_http = "htttp://broken.server.com/test"
    broken_https = "htttps://broken.server.com/test"
    broken_ftp = "ftp2://broken.server.com/test"

    def map_to_classes(self):
        if self == self.http:
            return HTTPSource
        elif self == self.https:
            return HTTPSSource
        elif self == self.ftp:
            return FTPSource
        elif self in (self.nfs_ks, self.nfs_main_repo, self.nfs_main_repo2):
            return NFSSource
        elif self == self.file:
            return FileSource
        elif self in (self.cdrom, self.cdrom_test):
            return CDRomSource
        elif self in (self.harddrive, self.harddrive_label, self.harddrive_uuid):
            return HDDSource
        elif self == self.hmc:
            return HMCSource
        else:
            return None


class TestSourceFactoryTests(unittest.TestCase):

    def test_parse_repo_cmdline(self):
        for val in TestValues:
            klass = val.map_to_classes()

            if klass is None:
                with pytest.raises(PayloadSourceTypeUnrecognized):
                    SourceFactory.parse_repo_cmdline_string(val.value)
                continue

            source = SourceFactory.parse_repo_cmdline_string(val.value)
            assert isinstance(source, klass), \
                "Instance of source {} expected - get {}".format(klass, source)

    def _check_is_methods(self, check_method, valid_array, type_str):
        for val in TestValues:

            ret = check_method(val.value)
            if val in valid_array:
                assert ret, "Value {} is not marked as {}".format(val.value, type_str)
            else:
                assert not ret, "Value {} should non be marked as {}".format(val.value, type_str)

    def test_is_cdrom(self):
        self._check_is_methods(SourceFactory.is_cdrom,
                               [TestValues.cdrom, TestValues.cdrom_test],
                               "cdrom")

    def test_is_harddrive(self):
        self._check_is_methods(SourceFactory.is_harddrive,
                               [TestValues.harddrive, TestValues.harddrive_uuid,
                                TestValues.harddrive_label],
                               "harddrive")

    def test_is_nfs(self):
        self._check_is_methods(SourceFactory.is_nfs,
                               [TestValues.nfs_ks, TestValues.nfs_main_repo,
                                TestValues.nfs_main_repo2],
                               "nfs")

    def test_is_http(self):
        self._check_is_methods(SourceFactory.is_http,
                               [TestValues.http],
                               "http")

    def test_is_https(self):
        self._check_is_methods(SourceFactory.is_https,
                               [TestValues.https],
                               "https")

    def test_is_ftp(self):
        self._check_is_methods(SourceFactory.is_ftp,
                               [TestValues.ftp],
                               "ftp")

    def test_is_file(self):
        self._check_is_methods(SourceFactory.is_file,
                               [TestValues.file],
                               "file")

    def test_is_hmc(self):
        self._check_is_methods(SourceFactory.is_hmc,
                               [TestValues.hmc],
                               "hmc")

    def _check_create_proxy(self, source_type, test_value):
        payloads_proxy = PAYLOADS.get_proxy()
        payloads_proxy.CreateSource.return_value = "my/source/1"

        source = SourceFactory.parse_repo_cmdline_string(test_value)
        source_proxy = source.create_proxy()

        payloads_proxy.CreateSource.assert_called_once_with(source_type)
        assert source_proxy == PAYLOADS.get_proxy("my/source/1")

        return source_proxy

    @patch_dbus_get_proxy_with_cache
    def test_create_proxy_cdrom(self, proxy_getter):
        self._check_create_proxy(SOURCE_TYPE_CDROM, "cdrom")

    @patch_dbus_get_proxy_with_cache
    def test_create_proxy_harddrive(self, proxy_getter):
        proxy = self._check_create_proxy(SOURCE_TYPE_HDD, "hd:/dev/sda2:/path/to/iso.iso")
        proxy.SetPartition.assert_called_once_with("/dev/sda2")
        proxy.SetDirectory.assert_called_once_with("/path/to/iso.iso")

    @patch_dbus_get_proxy_with_cache
    def test_create_proxy_nfs(self, proxy_getter):
        proxy = self._check_create_proxy(SOURCE_TYPE_NFS, "nfs:server.com:/path/to/install_tree")
        proxy.SetURL.assert_called_once_with("nfs:server.com:/path/to/install_tree")

    @patch_dbus_get_proxy_with_cache
    def test_create_proxy_url(self, proxy_getter):
        proxy = self._check_create_proxy(SOURCE_TYPE_URL, "http://server.example.com/test")

        repo_configuration = RepoConfigurationData()
        repo_configuration.type = URL_TYPE_BASEURL
        repo_configuration.url = "http://server.example.com/test"

        proxy.SetRepoConfiguration.assert_called_once_with(
            RepoConfigurationData.to_structure(repo_configuration)
        )

    @patch_dbus_get_proxy_with_cache
    def test_create_proxy_file(self, proxy_getter):
        proxy = self._check_create_proxy(SOURCE_TYPE_URL, "file:///root/extremely_secret_file.txt")

        repo_configuration = RepoConfigurationData()
        repo_configuration.type = URL_TYPE_BASEURL
        repo_configuration.url = "file:///root/extremely_secret_file.txt"

        proxy.SetRepoConfiguration.assert_called_once_with(
            RepoConfigurationData.to_structure(repo_configuration)
        )

    @patch_dbus_get_proxy_with_cache
    def test_create_proxy_hmc(self, proxy_getter):
        self._check_create_proxy(SOURCE_TYPE_HMC, "hmc")
