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

import unittest
import tempfile
import os
import hashlib
import shutil

import pyanaconda.core.payload as util

from blivet.size import Size

from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.payload.dnf import utils
from pyanaconda.payload.dnf.repomd import RepoMDMetaHash


class PickLocation(unittest.TestCase):
    def pick_download_location_test(self):
        """Take the biggest mountpoint which can be used for download"""
        df_map = {os.path.join(conf.target.system_root, "not_used"): Size("20 G"),
                  os.path.join(conf.target.system_root, "home"): Size("2 G"),
                  os.path.join(conf.target.system_root): Size("5 G")}
        download_size = Size("1.5 G")
        install_size = Size("1.8 G")

        mpoint = utils.pick_mount_point(df_map, download_size, install_size, True)

        self.assertEqual(mpoint, os.path.join(conf.target.system_root, "home"))

    def pick_download_root_test(self):
        """Take the root for download because there are no other available mountpoints
           even when the root isn't big enough.

           This is required when user skipped the space check.
        """
        df_map = {os.path.join(conf.target.system_root, "not_used"): Size("20 G"),
                  os.path.join(conf.target.system_root, "home"): Size("2 G"),
                  os.path.join(conf.target.system_root): Size("5 G")}
        download_size = Size("2.5 G")
        install_size = Size("3.0 G")

        mpoint = utils.pick_mount_point(df_map, download_size, install_size, True)

        self.assertEqual(mpoint, os.path.join(conf.target.system_root))

    def pick_install_location_test(self):
        """Take the root for download and install."""
        df_map = {os.path.join(conf.target.system_root, "not_used"): Size("20 G"),
                  os.path.join(conf.target.system_root, "home"): Size("2 G"),
                  os.path.join(conf.target.system_root): Size("6 G")}
        download_size = Size("1.5 G")
        install_size = Size("3.0 G")

        mpoint = utils.pick_mount_point(df_map, download_size, install_size, False)

        self.assertEqual(mpoint, conf.target.system_root)

    def pick_install_location_error_test(self):
        """No suitable location is found."""
        df_map = {os.path.join(conf.target.system_root, "not_used"): Size("20 G"),
                  os.path.join(conf.target.system_root, "home"): Size("1 G"),
                  os.path.join(conf.target.system_root): Size("4 G")}
        download_size = Size("1.5 G")
        install_size = Size("3.0 G")

        mpoint = utils.pick_mount_point(df_map, download_size, install_size, False)

        self.assertEqual(mpoint, None)


class DummyRepo(object):
    def __init__(self):
        self.id = "anaconda"
        self.baseurl = []
        self.sslverify = True


class DNFPayloadMDCheckTests(unittest.TestCase):
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
        self._dummyRepo.baseurl = ["file://" + self._temp_dir]

    def tearDown(self):
        # remove the testing directory
        shutil.rmtree(self._temp_dir)

    def download_file_repomd_test(self):
        """Test if we can download repomd.xml with file:// successfully."""
        m = hashlib.sha256()
        m.update(self._content_repomd.encode('ascii', 'backslashreplace'))
        reference_digest = m.digest()

        r = RepoMDMetaHash(self._dummyRepo, None)
        r.store_repoMD_hash()

        self.assertEqual(r.repoMD_hash, reference_digest)

    def verify_repo_test(self):
        """Test verification method."""
        r = RepoMDMetaHash(self._dummyRepo, None)
        r.store_repoMD_hash()

        # test if repomd comparision works properly
        self.assertTrue(r.verify_repoMD())

        # test if repomd change will be detected
        with open(self._md_file, 'a') as f:
            f.write("This should not be here!")
        self.assertFalse(r.verify_repoMD())

        # test correct behavior when the repo file won't be available
        os.remove(self._md_file)
        self.assertFalse(r.verify_repoMD())


class PayloadUtilsTests(unittest.TestCase):

    def parse_nfs_url_test(self):
        """Test parseNfsUrl."""

        # empty NFS url should return 3 blanks
        self.assertEqual(util.parse_nfs_url(""), ("", "", ""))

        # the string is delimited by :, there is one prefix and 3 parts,
        # the prefix is discarded and all parts after the 3th part
        # are also discarded
        self.assertEqual(util.parse_nfs_url("discard:options:host:path"),
                         ("options", "host", "path"))
        self.assertEqual(util.parse_nfs_url("discard:options:host:path:foo:bar"),
                         ("options", "host", "path"))
        self.assertEqual(util.parse_nfs_url(":options:host:path::"),
                         ("options", "host", "path"))
        self.assertEqual(util.parse_nfs_url(":::::"),
                         ("", "", ""))

        # if there is only prefix & 2 parts,
        # the two parts are host and path
        self.assertEqual(util.parse_nfs_url("prefix:host:path"),
                         ("", "host", "path"))
        self.assertEqual(util.parse_nfs_url(":host:path"),
                         ("", "host", "path"))
        self.assertEqual(util.parse_nfs_url("::"),
                         ("", "", ""))

        # if there is only a prefix and single part,
        # the part is the host

        self.assertEqual(util.parse_nfs_url("prefix:host"),
                         ("", "host", ""))
        self.assertEqual(util.parse_nfs_url(":host"),
                         ("", "host", ""))
        self.assertEqual(util.parse_nfs_url(":"),
                         ("", "", ""))

    def create_nfs_url_test(self):
        """Test create_nfs_url."""

        self.assertEqual(util.create_nfs_url("", ""), "")
        self.assertEqual(util.create_nfs_url("", "", None), "")
        self.assertEqual(util.create_nfs_url("", "", ""), "")

        self.assertEqual(util.create_nfs_url("host", ""), "nfs:host:")
        self.assertEqual(util.create_nfs_url("host", "", "options"), "nfs:options:host:")

        self.assertEqual(util.create_nfs_url("host", "path"), "nfs:host:path")
        self.assertEqual(util.create_nfs_url("host", "/path", "options"), "nfs:options:host:/path")

        self.assertEqual(util.create_nfs_url("host", "/path/to/something"),
                         "nfs:host:/path/to/something")
        self.assertEqual(util.create_nfs_url("host", "/path/to/something", "options"),
                         "nfs:options:host:/path/to/something")

    def nfs_combine_test(self):
        """Test combination of parse and create nfs functions."""

        host = "host"
        path = "/path/to/somewhere"
        options = "options"

        url = util.create_nfs_url(host, path, options)
        self.assertEqual(util.parse_nfs_url(url), (options, host, path))

        url = "nfs:options:host:/my/path"
        (options, host, path) = util.parse_nfs_url(url)
        self.assertEqual(util.create_nfs_url(host, path, options), url)

    def split_protocol_test(self):
        """Test split protocol test."""

        self.assertEqual(util.split_protocol("http://abc/cde"),
                         ("http://", "abc/cde"))
        self.assertEqual(util.split_protocol("https://yay/yay"),
                         ("https://", "yay/yay"))
        self.assertEqual(util.split_protocol("ftp://ups/spu"),
                         ("ftp://", "ups/spu"))
        self.assertEqual(util.split_protocol("file:///test/file"),
                         ("file://", "/test/file"))
        self.assertEqual(util.split_protocol("nfs:ups/spu:/abc:opts"),
                         ("", "nfs:ups/spu:/abc:opts"))
        self.assertEqual(util.split_protocol("http:/typo/test"),
                         ("", "http:/typo/test"))
        self.assertEqual(util.split_protocol(""), ("", ""))

        with self.assertRaises(ValueError):
            util.split_protocol("http://ftp://ups/this/is/not/correct")
