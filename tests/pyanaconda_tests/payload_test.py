# -*- coding: utf-8 -*-
#
# Copyright (C) 2017  Red Hat, Inc.
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
# Red Hat Author(s): Jiri Konecny <jkonecny@redhat.com>
#

import unittest
import tempfile
import os
import hashlib
import shutil

from pyanaconda.packaging.yumpayload import RepoMDMetaHash
from pyanaconda.packaging import SSLOptions

class DummyRepo(object):

    def __init__(self):
        self.id = "anaconda"
        self.urls = []
        self.sslverify = None
        self.sslclientcert = None
        self.sslclientkey = None
        self.sslcacert = None

class DummyPayload(object):
    def __init__(self):
        class DummyMethod(object):
            def __init__(self):
                self.method = None

        class DummyData(object):
            def __init__(self):
                self.method = DummyMethod()

        self.data = DummyData()

class YumPayloadMDCheckTests(unittest.TestCase):

    def setUp(self):
        self._content_repomd = """
Content of the repomd.xml file

or it should be. Nah it's just a test!
"""
        self._temp_dir = tempfile.mkdtemp(suffix="pyanaconda_tests")
        os.makedirs(os.path.join(self._temp_dir, "repodata"))
        self._md_file = os.path.join(self._temp_dir, "repodata", "repomd.xml")
        with open(self._md_file, 'w') as f:
            f.write(self._content_repomd)
        self._dummyRepo = DummyRepo()
        self._dummyRepo.urls = ["file://" + self._temp_dir]

    def tearDown(self):
        # remove the testing directory
        shutil.rmtree(self._temp_dir)

    def download_file_repomd_test(self):
        """Test if we can download repomd.xml with file:// successfully."""
        m = hashlib.sha256()
        m.update(self._content_repomd)
        reference_digest = m.digest()

        r = RepoMDMetaHash(DummyPayload(), self._dummyRepo)
        r.storeRepoMDHash()

        self.assertEqual(r.repoMDHash, reference_digest)

    def verify_repo_test(self):
        """Test verification method."""
        r = RepoMDMetaHash(DummyPayload(), self._dummyRepo)
        r.storeRepoMDHash()

        # test if repomd comparision works properly
        self.assertTrue(r.verifyRepoMD())

        # test if repomd change will be detected
        with open(self._md_file, 'a') as f:
            f.write("This should not be here!")
        self.assertFalse(r.verifyRepoMD())

        # test correct behavior when the repo file won't be available
        os.remove(self._md_file)
        self.assertFalse(r.verifyRepoMD())

class SSLOptionsTests(unittest.TestCase):

    def empty_grabber_verify_true_test(self):
        options = SSLOptions(True)
        expected = {"ssl_verify_peer": True,
                    "ssl_verify_host": True}
        self.assertEqual(options.getUrlGrabberSslOpts(), expected)

    def empty_grabber_verify_false_test(self):
        options = SSLOptions(False)
        expected = {"ssl_verify_peer": False,
                    "ssl_verify_host": False}
        self.assertEqual(options.getUrlGrabberSslOpts(), expected)

    def empty_yum_dict_verify_true_test(self):
        options = SSLOptions(True)
        expected = {"sslverify": True}
        self.assertEqual(options.getYumSslDict(), expected)

    def empty_yum_dict_verify_false_test(self):
        options = SSLOptions(False)
        expected = {"sslverify": False}
        self.assertEqual(options.getYumSslDict(), expected)

    def grabber_verify_true_test(self):
        options = SSLOptions(True, cacert="cacert", clientcert="clientcert", clientkey="clientkey")
        expected = {"ssl_verify_peer": True,
                    "ssl_verify_host": True,
                    "ssl_ca_cert": "cacert",
                    "ssl_cert": "clientcert",
                    "ssl_key": "clientkey"}
        self.assertEqual(options.getUrlGrabberSslOpts(), expected)

    def grabber_verify_false_test(self):
        options = SSLOptions(False, cacert="cacert",
                             clientcert="clientcert", clientkey="clientkey")
        expected = {"ssl_verify_peer": True,
                    "ssl_verify_host": True,
                    "ssl_ca_cert": "cacert",
                    "ssl_cert": "clientcert",
                    "ssl_key": "clientkey"}
        self.assertEqual(options.getUrlGrabberSslOpts(), expected)

    def yum_dict_verify_true_test(self):
        options = SSLOptions(True, cacert="cacert", clientcert="clientcert", clientkey="clientkey")
        expected = {"sslverify": True,
                    "sslcacert": "cacert",
                    "sslclientcert": "clientcert",
                    "sslclientkey": "clientkey"}
        self.assertEqual(options.getYumSslDict(), expected)

    def yum_dict_verify_false_test(self):
        options = SSLOptions(False, cacert="cacert",
                             clientcert="clientcert", clientkey="clientkey")
        expected = {"sslverify": True,
                    "sslcacert": "cacert",
                    "sslclientcert": "clientcert",
                    "sslclientkey": "clientkey"}
        self.assertEqual(options.getYumSslDict(), expected)
