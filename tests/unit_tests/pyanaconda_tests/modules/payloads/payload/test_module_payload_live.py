#
# Copyright (C) 2019  Red Hat, Inc.
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
import os
import tempfile
import unittest
import pytest
import requests

from contextlib import contextmanager
from requests_file import FileAdapter
from unittest.mock import patch, Mock, call

from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.util import join_paths, touch
from pyanaconda.modules.common.errors.installation import PayloadInstallationError
from pyanaconda.modules.common.structures.live_image import LiveImageConfigurationData
from pyanaconda.modules.payloads.payload.live_image.download_progress import DownloadProgress
from pyanaconda.modules.payloads.payload.live_image.installation import VerifyImageChecksum, \
    InstallFromImageTask, InstallFromTarTask, DownloadImageTask, MountImageTask, RemoveImageTask
from pyanaconda.modules.payloads.payload.live_os.utils import get_kernel_version_list


class LiveUtilsTestCase(unittest.TestCase):

    def setUp(self):
        self._kernel_test_files_list = []
        self._kernel_test_valid_list = []

    def _create_kernel_files(self, kernel_file, is_valid):
        kernel_dir = os.path.dirname(kernel_file)
        name = os.path.basename(kernel_file)

        os.makedirs(kernel_dir, exist_ok=True)
        open(kernel_file, 'wb').close()

        self._kernel_test_files_list.append(name[8:])
        if is_valid:
            self._kernel_test_valid_list.append(name[8:])

    def test_kernel_list_empty(self):
        """Test empty get kernel list function."""
        with tempfile.TemporaryDirectory() as temp:
            result = get_kernel_version_list(temp)

        assert result == []

    def test_kernel_list(self):
        """Test get kernel list function."""
        with tempfile.TemporaryDirectory() as temp:

            boot_base = os.path.join(temp, "boot/vmlinuz-{}")
            efi_base = os.path.join(temp, "boot/efi/EFI/", conf.bootloader.efi_dir, "vmlinuz-{}")

            self._create_kernel_files(boot_base.format("boot-test1"), is_valid=True)
            self._create_kernel_files(boot_base.format("boot-test2.x86_64"), is_valid=True)
            self._create_kernel_files(boot_base.format("rescue-kernel.ppc64"), is_valid=False)
            self._create_kernel_files(efi_base.format("efi-test1"), is_valid=True)
            self._create_kernel_files(efi_base.format("efi-test2"), is_valid=True)
            self._create_kernel_files(efi_base.format("efi-test3.fc2000.i386"), is_valid=True)
            self._create_kernel_files(efi_base.format("efi-test-rescue-kernel"), is_valid=False)

            kernel_list = get_kernel_version_list(temp)

            assert kernel_list == self._kernel_test_valid_list


class InstallFromImageTaskTestCase(unittest.TestCase):
    """Test the InstallFromImageTask class."""

    @patch("pyanaconda.modules.payloads.payload.live_image.installation.os.sync")
    @patch("pyanaconda.modules.payloads.payload.live_image.installation.execWithRedirect")
    def test_install_image_task(self, exec_with_redirect, os_sync):
        """Test installation from an image task."""
        exec_with_redirect.return_value = 0

        with tempfile.TemporaryDirectory() as mount_point:
            task = InstallFromImageTask(
                sysroot="/mnt/root",
                mount_point=mount_point
            )
            task.run()

        exec_with_redirect.assert_called_once_with("rsync", [
            "-pogAXtlHrDx",
            "--stats",
            "--exclude", "/dev/",
            "--exclude", "/proc/",
            "--exclude", "/tmp/*",
            "--exclude", "/sys/",
            "--exclude", "/run/",
            "--exclude", "/boot/*rescue*",
            "--exclude", "/boot/loader/",
            "--exclude", "/boot/efi/loader/",
            "--exclude", "/etc/machine-id",
            mount_point + "/",
            "/mnt/root"
        ])

    @patch("pyanaconda.modules.payloads.payload.live_image.installation.os.sync")
    @patch("pyanaconda.modules.payloads.payload.live_image.installation.execWithRedirect")
    def test_install_image_task_failed_exception(self, exec_with_redirect, os_sync):
        """Test installation from an image task with exception."""
        exec_with_redirect.side_effect = OSError("Fake!")

        with tempfile.TemporaryDirectory() as mount_point:
            task = InstallFromImageTask(
                sysroot="/mnt/root",
                mount_point=mount_point
            )

            with pytest.raises(PayloadInstallationError) as cm:
                task.run()

        msg = "Failed to install image: Fake!"
        assert str(cm.value) == msg

    @patch("pyanaconda.modules.payloads.payload.live_image.installation.os.sync")
    @patch("pyanaconda.modules.payloads.payload.live_image.installation.execWithRedirect")
    def test_install_image_task_failed_return_code(self, exec_with_redirect, os_sync):
        """Test installation from an image task with bad return code."""
        exec_with_redirect.return_value = 11

        with tempfile.TemporaryDirectory() as mount_point:
            task = InstallFromImageTask(
                sysroot="/mnt/root",
                mount_point=mount_point
            )

            with pytest.raises(PayloadInstallationError) as cm:
                task.run()

        msg = "Failed to install image: rsync exited with code 11"
        assert str(cm.value) == msg


class InstallFromTarTaskTestCase(unittest.TestCase):
    """Test the InstallFromTarTask class."""

    @patch("pyanaconda.modules.payloads.payload.live_image.installation.os.sync")
    @patch("pyanaconda.modules.payloads.payload.live_image.installation.execWithRedirect")
    def test_install_tar_task(self, exec_with_redirect, os_sync):
        """Test installation from a tarball."""
        exec_with_redirect.return_value = 0

        with tempfile.NamedTemporaryFile("w") as f:
            task = InstallFromTarTask(
                sysroot="/mnt/root",
                tarfile=f.name
            )
            task.run()

        exec_with_redirect.assert_called_once_with("tar", [
            "--numeric-owner",
            "--selinux",
            "--acls",
            "--xattrs",
            "--xattrs-include", "*",
            "--exclude", "./dev/*",
            "--exclude", "./proc/*",
            "--exclude", "./tmp/*",
            "--exclude", "./sys/*",
            "--exclude", "./run/*",
            "--exclude", "./boot/*rescue*",
            "--exclude", "./boot/loader",
            "--exclude", "./boot/efi/loader",
            "--exclude", "./etc/machine-id",
            "-xaf", f.name,
            "-C", "/mnt/root"
        ])

    @patch("pyanaconda.modules.payloads.payload.live_image.installation.os.sync")
    @patch("pyanaconda.modules.payloads.payload.live_image.installation.execWithRedirect")
    def test_install_tar_task_failed_exception(self, exec_with_redirect, os_sync):
        """Test installation from a tarball with an exception."""
        exec_with_redirect.side_effect = OSError("Fake!")

        with tempfile.NamedTemporaryFile("w") as f:
            task = InstallFromTarTask(
                sysroot="/mnt/root",
                tarfile=f.name
            )

            with pytest.raises(PayloadInstallationError) as cm:
                task.run()

        msg = "Failed to install tar: Fake!"
        assert str(cm.value) == msg


class VerifyImageChecksumTestCase(unittest.TestCase):
    """Test the VerifyImageChecksum class."""

    def _create_image(self, f):
        """Create a fake image."""
        f.write("IMAGE CONTENT")
        f.flush()

    def test_verify_no_checksum(self):
        """Test the verification of a checksum."""
        with tempfile.TemporaryDirectory() as d:
            f_name = join_paths(d, "image")

            task = VerifyImageChecksum(
                image_path=f_name,
                checksum=""
            )

            with self.assertLogs(level="DEBUG") as cm:
                task.run()

        msg = "No checksum to verify."
        assert msg in "\n".join(cm.output)

    def test_verify_checksum(self):
        """Test the verification of a checksum."""
        checksum = \
            "7190E29480A9081FD917E33990F00098" \
            "DD9FBD348BC52B0775780348BDA3A617"

        with tempfile.NamedTemporaryFile("w") as f:
            self._create_image(f)

            task = VerifyImageChecksum(
                image_path=f.name,
                checksum=checksum
            )

            with self.assertLogs(level="DEBUG") as cm:
                task.run()

        msg = "Checksum of the image does match."
        assert msg in "\n".join(cm.output)

    def test_verify_wrong_checksum(self):
        """Test the verification of a wrong checksum."""
        with tempfile.NamedTemporaryFile("w") as f:
            self._create_image(f)

            task = VerifyImageChecksum(
                image_path=f.name,
                checksum="incorrect"
            )

            with pytest.raises(PayloadInstallationError) as cm:
                task.run()

        msg = "Checksum of the image does not match."
        assert str(cm.value) == msg


class DownloadProgressTestCase(unittest.TestCase):
    """Test the DownloadProgress class."""

    def test_stream_download(self):
        """Test the stream download progress report."""
        callback = Mock()
        progress = DownloadProgress(
            url="http://my/url",
            callback=callback,
            total_size=250,
        )

        progress.start()
        for i in (0, 1, 50, 100, 101, 200, 250):
            progress.update(i)
        progress.end()

        assert callback.mock_calls == [
            call("Downloading http://my/url (0%)"),
            call("Downloading http://my/url (20%)"),
            call("Downloading http://my/url (40%)"),
            call("Downloading http://my/url (80%)"),
            call("Downloading http://my/url (100%)"),
        ]


class DownloadImageTaskTestCase(unittest.TestCase):
    """Test the DownloadImageTask class."""

    def setUp(self):
        """Set up the test."""
        self.data = LiveImageConfigurationData()
        self.callback = Mock()
        self.directory = None

    @contextmanager
    def _create_directory(self):
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as d:
            self.directory = d
            yield
            self.directory = None

    @property
    def target_path(self):
        """Get a path to the target image."""
        return join_paths(self.directory, "target")

    def _run_task(self):
        """Run the task."""
        task = DownloadImageTask(
            configuration=self.data,
            image_path=self.target_path
        )
        task.progress_changed_signal.connect(self.callback)
        task.run()

    def _run_task_for_local_file(self):
        """Run the task with local files."""
        with self._create_directory():
            source_path = join_paths(self.directory, "source")
            self.data.url = "file://{}".format(source_path)

            # Create a 4MB source image.
            with open(source_path, "wb") as f:
                f.seek(1024 * 1024 * 4 - 1)
                f.write(b'1')

            self._run_task()

            # Check the target image.
            with open(source_path, "rb") as f1:
                with open(self.target_path, "rb") as f2:
                    assert f1.read() == f2.read()

    @patch("pyanaconda.modules.payloads.payload.live_image.installation.requests_session")
    def test_local_file_direct(self, session_getter):
        """Download a local file directly."""
        session = requests.Session()
        session.mount("file://", FileAdapter(set_content_length=False))
        session_getter.return_value = session

        self._run_task_for_local_file()
        self.callback.assert_called_once_with(
            0, 'Downloading {}'.format(self.data.url)
        )

    def test_local_file_stream(self):
        """Download a local file as a stream."""
        self._run_task_for_local_file()
        assert self.callback.mock_calls == [
            call(0, 'Downloading {} (0%)'.format(self.data.url)),
            call(0, 'Downloading {} (25%)'.format(self.data.url)),
            call(0, 'Downloading {} (50%)'.format(self.data.url)),
            call(0, 'Downloading {} (75%)'.format(self.data.url)),
            call(0, 'Downloading {} (100%)'.format(self.data.url)),
        ]

    @patch("pyanaconda.modules.payloads.payload.live_image.installation.requests_session")
    def test_remote_file_direct(self, session_getter):
        """Mock download of a remote file"""
        # Set up the response.
        session = session_getter.return_value.__enter__.return_value
        response = session.get.return_value
        response.headers = {}
        response.content = b"CONTENT"

        # Run the task.
        with self._create_directory():
            self.data.url = "http://source"
            self.data.proxy = "http://proxy"
            self.data.ssl_verification_enabled = False
            self._run_task()

            with open(self.target_path, "rb") as f:
                assert f.read() == b"CONTENT"

        # Check the calls.
        session.get.assert_called_once_with(
            url='http://source',
            proxies={
                'http': 'http://proxy:3128',
                'https': 'http://proxy:3128'
            },
            verify=False,
            stream=True,
            timeout=46,
        )

        self.callback.assert_called_once_with(
            0, 'Downloading http://source'
        )

    @patch("pyanaconda.modules.payloads.payload.live_image.installation.requests_session")
    def test_remote_file_failed(self, session_getter):
        """Fail to download a remote file."""
        # Set up the response.
        session = session_getter.return_value.__enter__.return_value
        response = session.get.return_value
        response.raise_for_status.side_effect = requests.HTTPError("Fake!")

        # Run the task.
        with self._create_directory():
            self.data.url = "http://source"

            with pytest.raises(PayloadInstallationError) as cm:
                self._run_task()

            assert str(cm.value) == "Error while downloading the image: Fake!"


class MountImageTaskTestCase(unittest.TestCase):
    """Test the MountImageTask class."""

    def setUp(self):
        """Set up the test."""
        self.image_path = None
        self.image_mount = None
        self.iso_mount = None

    @contextmanager
    def _create_directory(self):
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as d:
            self.image_path = join_paths(d, "image.img")
            self.image_mount = join_paths(d, "image")
            self.iso_mount = join_paths(d, "iso")
            yield d

    def _run_task(self):
        """Run the task."""
        task = MountImageTask(
            image_path=self.image_path,
            image_mount_point=self.image_mount,
            iso_mount_point=self.iso_mount
        )
        return task.run()

    @patch("pyanaconda.modules.payloads.payload.live_image.installation.blivet.util.mount")
    @patch("pyanaconda.modules.payloads.payload.live_image.installation.execWithRedirect")
    def test_mount_image_no_dir(self, exec_mock, mount_mock):
        """Mount an image without the LiveOS directory."""
        exec_mock.return_value = 0
        mount_mock.return_value = 0

        with self._create_directory():
            assert self._run_task() == self.image_mount

            exec_mock.assert_called_once_with(
                "mount", ["--make-rprivate", "/"]
            )

            mount_mock.assert_called_once_with(
                self.image_path,
                self.image_mount,
                fstype="auto",
                options="ro"
            )

    @patch("pyanaconda.modules.payloads.payload.live_image.installation.blivet.util.mount")
    @patch("pyanaconda.modules.payloads.payload.live_image.installation.execWithRedirect")
    def test_mount_image_no_iso(self, exec_mock, mount_mock):
        """Mount an image without ISO files in the LiveOS directory."""
        exec_mock.return_value = 0
        mount_mock.return_value = 0

        with self._create_directory():
            iso_dir = join_paths(self.image_mount, "LiveOS")
            os.makedirs(iso_dir)

            assert self._run_task() == self.image_mount

    @patch("pyanaconda.modules.payloads.payload.live_image.installation.blivet.util.mount")
    @patch("pyanaconda.modules.payloads.payload.live_image.installation.execWithRedirect")
    def test_mount_iso(self, exec_mock, mount_mock):
        """Mount an ISO file in the LiveOS directory."""
        exec_mock.return_value = 0
        mount_mock.return_value = 0

        with self._create_directory():
            iso_dir = join_paths(self.image_mount, "LiveOS")
            os.makedirs(iso_dir)

            iso_path = join_paths(iso_dir, "iso.img")
            touch(iso_path)

            assert self._run_task() == self.iso_mount

            exec_mock.assert_called_once_with(
                "mount", ["--make-rprivate", "/"]
            )

            assert mount_mock.mock_calls == [
                call(
                    self.image_path,
                    self.image_mount,
                    fstype="auto",
                    options="ro"
                ),
                call(
                    iso_path,
                    self.iso_mount,
                    fstype="auto",
                    options="ro"
                )
            ]

    @patch("pyanaconda.modules.payloads.payload.live_image.installation.execWithRedirect")
    def test_rprivate_fail(self, exec_mock):
        """Test a failure of the rprivate mount call."""
        exec_mock.return_value = 1

        with self._create_directory():
            with pytest.raises(PayloadInstallationError) as cm:
                self._run_task()

            assert str(cm.value) == "Failed to make the '/' mount rprivate: 1"

    @patch("pyanaconda.modules.payloads.payload.live_image.installation.blivet.util.mount")
    @patch("pyanaconda.modules.payloads.payload.live_image.installation.execWithRedirect")
    def test_mount_fail(self, exec_mock, mount_mock):
        """Test a failure of the mount tool."""
        exec_mock.return_value = 0
        mount_mock.return_value = 1

        with self._create_directory():
            with pytest.raises(PayloadInstallationError) as cm:
                self._run_task()

            msg = "Failed to mount '{}' at '{}': {}".format(self.image_path, self.image_mount, 1)
            assert str(cm.value) == msg

    @patch("pyanaconda.modules.payloads.payload.live_image.installation.blivet.util.mount")
    @patch("pyanaconda.modules.payloads.payload.live_image.installation.execWithRedirect")
    def test_mount_exec_fail(self, exec_mock, mount_mock):
        """Test a failure of the mount call."""
        exec_mock.return_value = 0
        mount_mock.side_effect = OSError("Fake!")

        with self._create_directory():
            with pytest.raises(PayloadInstallationError) as cm:
                self._run_task()

            assert str(cm.value) == "Fake!"


class RemoveImageTaskTestCase(unittest.TestCase):
    """Test the RemoveImageTask class."""

    def test_delete_existing_file(self):
        """Delete a file that exists."""
        with tempfile.TemporaryDirectory() as d:
            image_path = join_paths(d, "image.img")
            touch(image_path)

            assert os.path.exists(image_path)

            # Delete the file.
            task = RemoveImageTask(image_path)
            task.run()

            assert not os.path.exists(image_path)

    def test_delete_missing_file(self):
        """Delete a file that doesn't exist."""
        with tempfile.TemporaryDirectory() as d:
            image_path = join_paths(d, "image.img")

            assert not os.path.exists(image_path)

            # Don't fail.
            task = RemoveImageTask(image_path)
            task.run()

            assert not os.path.exists(image_path)