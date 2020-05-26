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
import gi

import pyanaconda.core.payload as util

from tempfile import TemporaryDirectory
from unittest.mock import patch, Mock, call

from blivet.size import Size

from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.modules.common.structures.requirement import Requirement
from pyanaconda.payload.dnf import utils
from pyanaconda.payload.flatpak import FlatpakPayload
from pyanaconda.payload.dnf.repomd import RepoMDMetaHash
from pyanaconda.payload.requirement import PayloadRequirements
from pyanaconda.payload.errors import PayloadRequirementsMissingApply

gi.require_version("Flatpak", "1.0")
from gi.repository.Flatpak import RefKind


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


class PayloadRequirementsTestCase(unittest.TestCase):

    def requirements_test(self):
        """Check that requirements work correctly."""

        ### requirements are ordered by adding
        reqs = PayloadRequirements()
        reqs.add_packages(["p1"], "reason1")
        reqs.add_packages(["p3"], "reason2")
        reqs.add_packages(["p2"], "reason3")
        reqs.add_packages(["p2", "p3", "p4"], "reason4")

        package_reqs = [(req.id, req.reasons, req.strong) for
                         req in reqs.packages]

        self.assertEqual(package_reqs,
                [("p1", ["reason1"], True),
                 ("p3", ["reason2", "reason4"], True),
                 ("p2", ["reason3", "reason4"], True),
                 ("p4", ["reason4"], True)])


        ### reasons are not merged, just appended
        reqs = PayloadRequirements()
        reqs.add_packages(["p1"], "reason1")
        reqs.add_packages(["p1"], "reason1")

        package_reqs = [(req.id, req.reasons, req.strong) for
                         req in reqs.packages]
        self.assertEqual(package_reqs,
                [("p1", ["reason1", "reason1"], True)])


        ### strength of a package requirement is merged (ORed)
        reqs = PayloadRequirements()
        # default is strong
        reqs.add_packages(["p1"], "reason1")
        package_reqs = [(req.id, req.reasons, req.strong) for
                         req in reqs.packages]
        self.assertEqual(package_reqs,
                [("p1", ["reason1"], True)])
        # a strong req will be always strong
        reqs.add_packages(["p1"], "reason2", strong=False)
        package_reqs = [(req.id, req.reasons, req.strong) for
                         req in reqs.packages]
        self.assertEqual(package_reqs,
                [("p1", ["reason1", "reason2"], True)])

        # weak can become strong
        reqs = PayloadRequirements()
        reqs.add_packages(["p1"], "reason1", strong=False)
        reqs.add_packages(["p1"], "reason2")
        package_reqs = [(req.id, req.reasons, req.strong) for
                         req in reqs.packages]
        self.assertEqual(package_reqs,
                [("p1", ["reason1", "reason2"], True)])

        ### no group requirements yet
        self.assertEqual(reqs.groups, [])
        # let's add some group requirement
        reqs.add_groups(["g1"], "reason")
        group_reqs = [(req.id, req.reasons, req.strong) for
                         req in reqs.groups]
        self.assertEqual(group_reqs,
                [("g1", ["reason"], True)])

        ### applying requirements
        reqs = PayloadRequirements()
        self.assertTrue(reqs.empty)
        # no requirements, so all requirements were applied
        self.assertTrue(reqs.applied)
        # no callback was assigned yet
        # calling apply without callback set raises exception
        with self.assertRaises(PayloadRequirementsMissingApply):
            reqs.apply()
        # apply callback gets one argument: requirements instance
        def cb(requirements):
            return requirements is reqs
        # set the apply callback
        reqs.set_apply_callback(cb)
        # BTW, applied is still true
        self.assertTrue(reqs.applied)
        reqs.add_packages(["p1"], "reason1", strong=False)
        self.assertEqual(reqs.empty, False)
        # a package has been added, applied is False
        self.assertFalse(reqs.applied)
        # after calling apply, applied becomes True
        self.assertTrue(reqs.apply())
        self.assertTrue(reqs.applied)
        # applied becomes False after adding a requirement even when it adds the
        # same object (package "p1"). The reason is that the updated requirement
        # may became strong so the application may be different.
        reqs.add_packages(["p1"], "reason2")
        self.assertFalse(reqs.applied)
        self.assertTrue(reqs.apply())
        self.assertTrue(reqs.applied)

    def add_requirements_test(self):
        """Check that multiple requirements can be added at once."""

        reqs = PayloadRequirements()
        self.assertTrue(reqs.empty)

        # add a package, group & unknown requirement type
        req_list = []
        req_list.append(Requirement.for_package("foo-package", reason="foo package needed"))
        req_list.append(Requirement.for_group("bar-group", reason="bar group needed"))
        unknown_req = Requirement()
        unknown_req.name = "baz-unknown"
        unknown_req.reson = "unknown reason for installation"
        unknown_req.type = "baz-unknown-type"
        req_list.append(unknown_req)

        # add the requrements list and check it is processed correctly
        reqs.add_requirements(req_list)

        self.assertFalse(reqs.empty)

        # package
        self.assertEqual(len(reqs.packages), 1)
        self.assertEqual(reqs.packages[0].id, "foo-package")
        self.assertEqual(len(reqs.packages[0].reasons), 1)
        self.assertEqual(reqs.packages[0].reasons[0], "foo package needed")
        self.assertTrue(reqs.packages[0].strong)

        # group
        self.assertEqual(len(reqs.groups), 1)
        self.assertEqual(reqs.groups[0].id, "bar-group")
        self.assertEqual(len(reqs.groups[0].reasons), 1)
        self.assertEqual(reqs.groups[0].reasons[0], "bar group needed")
        self.assertTrue(reqs.groups[0].strong)


class FlatpakTest(unittest.TestCase):

    def setUp(self):
        self._remote = Mock()
        self._installation = Mock()
        self._transaction = Mock()

    def _setup_flatpak_objects(self, remote_cls, installation_cls, transaction_cls):
        remote_cls.new.return_value = self._remote
        installation_cls.new_for_path.return_value = self._installation
        transaction_cls.new_for_installation.return_value = self._transaction

        self._transaction.get_installation.return_value = self._installation

    def is_available_test(self):
        """Test check for flatpak availability of the system sources."""
        self.assertFalse(FlatpakPayload.is_available())

        with TemporaryDirectory() as temp:
            FlatpakPayload.LOCAL_REMOTE_PATH = "file://" + temp

            self.assertTrue(FlatpakPayload.is_available())

    @patch("pyanaconda.payload.flatpak.Transaction")
    @patch("pyanaconda.payload.flatpak.Installation")
    @patch("pyanaconda.payload.flatpak.Remote")
    def initialize_with_path_test(self, remote_cls, installation_cls, transaction_cls):
        """Test flatpak initialize with path."""
        self._setup_flatpak_objects(remote_cls, installation_cls, transaction_cls)

        flatpak = FlatpakPayload("/mock/system/root/path")
        flatpak.initialize_with_path("/test/path/installation")

        remote_cls.new.assert_called_once()
        installation_cls.new_for_path.assert_called_once()
        transaction_cls.new_for_installation.assert_called_once_with(self._installation)

        expected_remote_calls = [call.set_gpg_verify(False),
                                 call.set_url(flatpak.LOCAL_REMOTE_PATH)]
        self.assertEqual(self._remote.method_calls, expected_remote_calls)

        expected_remote_calls = [call.add_remote(self._remote, False, None)]
        self.assertEqual(self._installation.method_calls, expected_remote_calls)

    def cleanup_call_without_initialize_test(self):
        """Test the cleanup call without initialize."""
        flatpak = FlatpakPayload("/tmp/flatpak-test")

        flatpak.cleanup()

    @patch("pyanaconda.payload.flatpak.shutil.rmtree")
    @patch("pyanaconda.payload.flatpak.Transaction")
    @patch("pyanaconda.payload.flatpak.Installation")
    @patch("pyanaconda.payload.flatpak.Remote")
    def cleanup_call_no_repo_test(self, remote_cls, installation_cls, transaction_cls, rmtree):
        """Test the cleanup call with no repository created."""
        flatpak = FlatpakPayload("any path")

        self._setup_flatpak_objects(remote_cls, installation_cls, transaction_cls)

        file_mock_path = Mock()
        file_mock_path.get_path.return_value = "/install/test/path"
        self._installation.get_path.return_value = file_mock_path

        flatpak.initialize_with_path("/install/test/path")
        flatpak.cleanup()

        rmtree.assert_not_called()

    @patch("pyanaconda.payload.flatpak.shutil.rmtree")
    @patch("pyanaconda.payload.flatpak.Transaction")
    @patch("pyanaconda.payload.flatpak.Installation")
    @patch("pyanaconda.payload.flatpak.Remote")
    def cleanup_call_mock_repo_test(self, remote_cls, installation_cls, transaction_cls, rmtree):
        """Test the cleanup call with mocked repository."""
        flatpak = FlatpakPayload("any path")

        self._setup_flatpak_objects(remote_cls, installation_cls, transaction_cls)

        with TemporaryDirectory() as temp:
            install_path = os.path.join(temp, "install/test/path")
            file_mock_path = Mock()
            file_mock_path.get_path.return_value = install_path
            self._installation.get_path.return_value = file_mock_path

            os.makedirs(install_path)

            flatpak.initialize_with_path(install_path)
            flatpak.cleanup()

            rmtree.assert_called_once_with(install_path)

    @patch("pyanaconda.payload.flatpak.Transaction")
    @patch("pyanaconda.payload.flatpak.Installation")
    @patch("pyanaconda.payload.flatpak.Remote")
    def get_required_space_test(self, remote_cls, installation_cls, transaction_cls):
        """Test flatpak required space method."""
        flatpak = FlatpakPayload("any path")

        self._setup_flatpak_objects(remote_cls, installation_cls, transaction_cls)

        flatpak.initialize_with_system_path()

        self._installation.list_remote_refs_sync.return_value = [
            RefMock(installed_size=2000),
            RefMock(installed_size=3000),
            RefMock(installed_size=100)
        ]

        installation_size = flatpak.get_required_size()

        self.assertEqual(installation_size, 5100)

    @patch("pyanaconda.payload.flatpak.Transaction")
    @patch("pyanaconda.payload.flatpak.Installation")
    @patch("pyanaconda.payload.flatpak.Remote")
    def get_empty_refs_required_space_test(self, remote_cls, installation_cls, transaction_cls):
        """Test flatpak required space method with no refs."""
        flatpak = FlatpakPayload("any path")

        self._setup_flatpak_objects(remote_cls, installation_cls, transaction_cls)

        flatpak.initialize_with_system_path()

        self._installation.list_remote_refs_sync.return_value = []

        installation_size = flatpak.get_required_size()

        self.assertEqual(installation_size, 0)

    @patch("pyanaconda.payload.flatpak.Transaction")
    @patch("pyanaconda.payload.flatpak.Installation")
    @patch("pyanaconda.payload.flatpak.Remote")
    def install_test(self, remote_cls, installation_cls, transaction_cls):
        """Test flatpak installation is working."""
        flatpak = FlatpakPayload("remote/path")

        self._setup_flatpak_objects(remote_cls, installation_cls, transaction_cls)

        flatpak.initialize_with_system_path()

        mock_ref_list = [
            RefMock(name="org.space.coolapp", kind=RefKind.APP, arch="x86_64", branch="stable"),
            RefMock(name="com.prop.notcoolapp", kind=RefKind.APP, arch="i386", branch="f36"),
            RefMock(name="org.space.coolruntime", kind=RefKind.RUNTIME, arch="x86_64",
                    branch="stable"),
            RefMock(name="com.prop.notcoolruntime", kind=RefKind.RUNTIME, arch="i386",
                    branch="f36")
        ]

        self._installation.list_remote_refs_sync.return_value = mock_ref_list

        flatpak.install_all()

        expected_calls = [call.connect("new_operation", flatpak._operation_started_callback),
                          call.connect("operation_done", flatpak._operation_stopped_callback),
                          call.connect("operation_error", flatpak._operation_error_callback),
                          call.add_install(FlatpakPayload.LOCAL_REMOTE_NAME,
                                           mock_ref_list[0].format_ref(),
                                           None),
                          call.add_install(FlatpakPayload.LOCAL_REMOTE_NAME,
                                           mock_ref_list[1].format_ref(),
                                           None),
                          call.add_install(FlatpakPayload.LOCAL_REMOTE_NAME,
                                           mock_ref_list[2].format_ref(),
                                           None),
                          call.add_install(FlatpakPayload.LOCAL_REMOTE_NAME,
                                           mock_ref_list[3].format_ref(),
                                           None),
                          call.run()]

        self.assertEqual(self._transaction.mock_calls, expected_calls)

    @patch("pyanaconda.payload.flatpak.Transaction")
    @patch("pyanaconda.payload.flatpak.Installation")
    @patch("pyanaconda.payload.flatpak.Remote")
    def add_remote_test(self, remote_cls, installation_cls, transaction_cls):
        """Test flatpak add new remote."""
        flatpak = FlatpakPayload("remote/path")

        self._setup_flatpak_objects(remote_cls, installation_cls, transaction_cls)

        flatpak.initialize_with_system_path()
        flatpak.add_remote("hive", "url://zerglings/home")

        remote_cls.new.assert_called_with("hive")
        self._remote.set_gpg_verify.assert_called_with(True)
        self._remote.set_url("url://zerglings/home")
        self.assertEqual(remote_cls.new.call_count, 2)
        self.assertEqual(self._installation.add_remote.call_count, 2)

    @patch("pyanaconda.payload.flatpak.Transaction")
    @patch("pyanaconda.payload.flatpak.Installation")
    @patch("pyanaconda.payload.flatpak.Remote")
    def remove_remote_test(self, remote_cls, installation_cls, transaction_cls):
        """Test flatpak remove a remote."""
        flatpak = FlatpakPayload("remote/path")

        self._setup_flatpak_objects(remote_cls, installation_cls, transaction_cls)

        mock_remote1 = Mock()
        mock_remote2 = Mock()
        mock_remote1.get_name.return_value = "nest"
        mock_remote2.get_name.return_value = "hive"

        self._installation.list_remotes.return_value = [mock_remote1, mock_remote2]

        flatpak.initialize_with_system_path()
        flatpak.remove_remote("hive")

        self._installation.remove_remote.assert_called_once_with("hive", None)

    @patch("pyanaconda.payload.flatpak.Variant")
    @patch("pyanaconda.payload.flatpak.VariantType")
    @patch("pyanaconda.payload.flatpak.open")
    @patch("pyanaconda.payload.flatpak.Transaction")
    @patch("pyanaconda.payload.flatpak.Installation")
    @patch("pyanaconda.payload.flatpak.Remote")
    def replace_remote_test(self, remote_cls, installation_cls, transaction_cls,
                            open_mock, variant_type, variant):
        """Test flatpak replace remote for installed refs call."""
        flatpak = FlatpakPayload("/system/test-root")

        self._setup_flatpak_objects(remote_cls, installation_cls, transaction_cls)

        install_path = "/installation/path"

        install_path_mock = Mock()
        install_path_mock.get_path.return_value = install_path
        self._installation.get_path.return_value = install_path_mock

        ref_mock_list = [
            RefMock(name="org.space.coolapp", kind=RefKind.APP, arch="x86_64", branch="stable"),
            RefMock(name="org.space.coolruntime", kind=RefKind.RUNTIME, arch="x86_64",
                    branch="stable")
        ]

        self._installation.list_installed_refs.return_value = ref_mock_list

        flatpak.initialize_with_system_path()
        flatpak.replace_installed_refs_remote("cylon_officer")

        expected_refs = list(map(lambda x: x.format_ref(), ref_mock_list))

        open_calls = []

        for ref in expected_refs:
            ref_file_path = os.path.join(install_path, ref, "active/deploy")
            open_calls.append(call(ref_file_path, "rb"))
            open_calls.append(call(ref_file_path, "wb"))

        # test that every file is read and written
        self.assertEqual(open_mock.call_count, 2 * len(expected_refs))

        open_mock.has_calls(open_calls)


class RefMock(object):

    def __init__(self, name="org.app", kind=RefKind.APP, arch="x86_64", branch="stable",
                 installed_size=0):
        self._name = name
        self._kind = kind
        self._arch = arch
        self._branch = branch
        self._installed_size = installed_size

    def get_name(self):
        return self._name

    def get_kind(self):
        return self._kind

    def get_arch(self):
        return self._arch

    def get_branch(self):
        return self._branch

    def get_installed_size(self):
        return self._installed_size

    def format_ref(self):
        return "{}/{}/{}/{}".format("app" if self._kind is RefKind.APP else "runtime",
                                    self._name,
                                    self._arch,
                                    self._branch)


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
