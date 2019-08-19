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

from tempfile import TemporaryDirectory
from mock import patch, Mock, call

from blivet.size import Size

from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.modules.common.structures.requirement import Requirement
from pyanaconda.payload import dnfpayload
from pyanaconda.payload.flatpak import FlatpakPayload
from pyanaconda.payload.dnfpayload import RepoMDMetaHash
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

        mpoint = dnfpayload._pick_mpoint(df_map, download_size, install_size, True)

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

        mpoint = dnfpayload._pick_mpoint(df_map, download_size, install_size, True)

        self.assertEqual(mpoint, os.path.join(conf.target.system_root))

    def pick_install_location_test(self):
        """Take the root for download and install."""
        df_map = {os.path.join(conf.target.system_root, "not_used"): Size("20 G"),
                  os.path.join(conf.target.system_root, "home"): Size("2 G"),
                  os.path.join(conf.target.system_root): Size("6 G")}
        download_size = Size("1.5 G")
        install_size = Size("3.0 G")

        mpoint = dnfpayload._pick_mpoint(df_map, download_size, install_size, False)

        self.assertEqual(mpoint, conf.target.system_root)

    def pick_install_location_error_test(self):
        """No suitable location is found."""
        df_map = {os.path.join(conf.target.system_root, "not_used"): Size("20 G"),
                  os.path.join(conf.target.system_root, "home"): Size("1 G"),
                  os.path.join(conf.target.system_root): Size("4 G")}
        download_size = Size("1.5 G")
        install_size = Size("3.0 G")

        mpoint = dnfpayload._pick_mpoint(df_map, download_size, install_size, False)

        self.assertEqual(mpoint, None)


class DummyRepo(object):
    def __init__(self):
        self.id = "anaconda"
        self.baseurl = []
        self.sslverify = True


class DummyPayload(object):
    def __init__(self):
        class DummyMethod(object):
            def __init__(self):
                self.method = None

        class DummyData(object):
            def __init__(self):
                self.method = DummyMethod()

        self.data = DummyData()


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

        r = RepoMDMetaHash(DummyPayload(), self._dummyRepo)
        r.store_repoMD_hash()

        self.assertEqual(r.repoMD_hash, reference_digest)

    def verify_repo_test(self):
        """Test verification method."""
        r = RepoMDMetaHash(DummyPayload(), self._dummyRepo)
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
        flatpak = FlatpakPayload("/mock/system/root/path")

        self.assertFalse(flatpak.is_available())

        with TemporaryDirectory() as temp:
            flatpak._remote_path = temp

            self.assertTrue(flatpak.is_available())

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
                                 call.set_url("file://{}".format(flatpak.remote_path))]
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

        self._installation.list_remote_refs_sync.return_value = [
            RefMock(name="org.space.coolapp", kind=RefKind.APP, arch="x86_64", branch="stable"),
            RefMock(name="com.prop.notcoolapp", kind=RefKind.APP, arch="i386", branch="f36"),
            RefMock(name="org.space.coolruntime", kind=RefKind.RUNTIME, arch="x86_64",
                    branch="stable"),
            RefMock(name="com.prop.notcoolruntime", kind=RefKind.RUNTIME, arch="i386",
                    branch="f36")
        ]

        flatpak.install_all()

        expected_calls = [call.connect("new_operation", flatpak._operation_started_callback),
                          call.connect("operation_done", flatpak._operation_stopped_callback),
                          call.connect("operation_error", flatpak._operation_error_callback),
                          call.add_install(FlatpakPayload.REMOTE_NAME,
                                           "app/org.space.coolapp/x86_64/stable",
                                           None),
                          call.add_install(FlatpakPayload.REMOTE_NAME,
                                           "app/com.prop.notcoolapp/i386/f36",
                                           None),
                          call.add_install(FlatpakPayload.REMOTE_NAME,
                                           "runtime/org.space.coolruntime/x86_64/stable",
                                           None),
                          call.add_install(FlatpakPayload.REMOTE_NAME,
                                           "runtime/com.prop.notcoolruntime/i386/f36",
                                           None),
                          call.run()]

        self.assertEqual(self._transaction.mock_calls, expected_calls)


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
