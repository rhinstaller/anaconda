# vim:set fileencoding=utf-8
#
# Copyright (C) 2015  Red Hat, Inc.
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
import shutil
import tempfile
import unittest
from unittest.mock import patch

import pytest

try:
    import crypt_r
except ImportError:
    import crypt as crypt_r  # pylint: disable=deprecated-module

from pyanaconda.core import users
from pyanaconda.core.path import make_directories, touch


@unittest.skipIf(os.geteuid() != 0, "user creation must be run as root")
class UserCreateTest(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory with empty passwd and group files
        self.tmpdir = tempfile.mkdtemp()
        os.mkdir(self.tmpdir + "/etc")

        open(self.tmpdir + "/etc/passwd", "w").close()
        open(self.tmpdir + "/etc/group", "w").close()
        open(self.tmpdir + "/etc/shadow", "w").close()
        open(self.tmpdir + "/etc/gshadow", "w").close()

        # Copy over enough of libnss for UID and GID lookups to work
        with open(self.tmpdir + "/etc/nsswitch.conf", "w") as f:
            f.write("passwd: files\n")
            f.write("shadow: files\n")
            f.write("group: files\n")
            f.write("initgroups: files\n")

        # provide also valid login.defs so that the created data is correct
        shutil.copyfile("/etc/login.defs", self.tmpdir + "/etc/login.defs")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _readFields(self, filename, key):
        """Look for a line in a password or group file where the first field
           matches key, and return the record as a list of fields.
        """
        with open(self.tmpdir + filename) as f:
            for line in f:
                fields = line.strip().split(':')
                if fields[0] == key:
                    return fields
        return None

    def test_create_group(self):
        """Create a group."""
        users.create_group("test_group", root=self.tmpdir)

        fields = self._readFields("/etc/group", "test_group")
        assert fields is not None
        assert fields[0] == "test_group"

        fields = self._readFields("/etc/gshadow", "test_group")
        assert fields is not None
        assert fields[0] == "test_group"

    def test_create_group_gid(self):
        """Create a group with a specific GID."""
        users.create_group("test_group", gid=47, root=self.tmpdir)

        fields = self._readFields("/etc/group", "test_group")

        assert fields is not None
        assert fields[0] == "test_group"
        assert fields[2] == "47"

    def test_create_group_exists(self):
        """Create a group that already exists."""
        with open(self.tmpdir + "/etc/group", "w") as f:
            f.write("test_group:x:47:\n")

        with pytest.raises(ValueError):
            users.create_group("test_group", root=self.tmpdir)

    def test_create_group_gid_exists(self):
        """Create a group with a GID that already exists."""
        with open(self.tmpdir + "/etc/group", "w") as f:
            f.write("gid_used:x:47:\n")

        with pytest.raises(ValueError):
            users.create_group("test_group", gid=47, root=self.tmpdir)

    def test_create_user(self):
        """Create a user."""
        users.create_user("test_user", root=self.tmpdir)

        pwd_fields = self._readFields("/etc/passwd", "test_user")
        assert pwd_fields is not None
        assert pwd_fields[0] == "test_user"

        # Check that the fields got the right default values
        # UID + GID set to some sort of int
        assert isinstance(int(pwd_fields[2]), int)
        assert isinstance(int(pwd_fields[3]), int)

        # home is /home/username
        assert pwd_fields[5] == "/home/test_user"

        # shell set to something
        assert pwd_fields[6]

        shadow_fields = self._readFields("/etc/shadow", "test_user")
        assert shadow_fields is not None
        assert shadow_fields[0] == "test_user"

        # Ensure the password is locked
        assert shadow_fields[1].startswith("!")

        # Ensure the date of last password change is empty
        assert shadow_fields[2] == ""

        # Check that the user group was created
        grp_fields = self._readFields("/etc/group", "test_user")
        assert grp_fields is not None
        assert grp_fields[0] == "test_user"

        # Check that user group's GID matches the user's GID
        assert grp_fields[2] == pwd_fields[3]

        gshadow_fields = self._readFields("/etc/gshadow", "test_user")
        assert gshadow_fields is not None
        assert gshadow_fields[0] == "test_user"

    def test_create_user_text_options(self):
        """Create a user with the text fields set."""
        users.create_user("test_user", gecos="Test User", homedir="/home/users/testuser", shell="/bin/test", root=self.tmpdir)

        pwd_fields = self._readFields("/etc/passwd", "test_user")
        assert pwd_fields is not None
        assert pwd_fields[0] == "test_user"
        assert pwd_fields[4] == "Test User"
        assert pwd_fields[5] == "/home/users/testuser"
        assert pwd_fields[6] == "/bin/test"

        # Check that the home directory was created
        assert os.path.isdir(self.tmpdir + "/home/users/testuser")

    def test_create_user_groups(self):
        """Create a user with a list of groups."""
        # Create one of the groups
        users.create_group("test3", root=self.tmpdir)

        # Create a user and add it three groups, two of which do not exist,
        # and one which specifies a GID.
        users.create_user("test_user", groups=["test1", "test2(5001)", "test3"], root=self.tmpdir)

        grp_fields1 = self._readFields("/etc/group", "test1")
        assert grp_fields1[3] == "test_user"

        grp_fields2 = self._readFields("/etc/group", "test2")
        assert grp_fields2[3] == "test_user"
        assert grp_fields2[2] == "5001"

        grp_fields3 = self._readFields("/etc/group", "test3")
        assert grp_fields3[3] == "test_user"

    def test_create_user_groups_gid_conflict(self):
        """Create a user with a bad list of groups."""
        # Create one of the groups
        users.create_group("test3", gid=5000, root=self.tmpdir)

        # Add test3 to the group list with a different GID.
        with pytest.raises(ValueError):
            users.create_user("test_user", groups=["test3(5002)"], root=self.tmpdir)

    def test_create_user_password(self):
        """Create a user with a password."""

        users.create_user("test_user1", password="password", root=self.tmpdir)
        shadow_fields = self._readFields("/etc/shadow", "test_user1")
        assert shadow_fields is not None
        # Make sure the password works
        assert crypt_r.crypt("password", shadow_fields[1]) == shadow_fields[1]

        # Set the encrypted password for another user with is_crypted
        cryptpw = shadow_fields[1]
        users.create_user("test_user2", password=cryptpw, is_crypted=True, root=self.tmpdir)
        shadow_fields = self._readFields("/etc/shadow", "test_user2")
        assert shadow_fields is not None
        assert cryptpw == shadow_fields[1]

        # Set an empty password
        users.create_user("test_user3", password="", root=self.tmpdir)
        shadow_fields = self._readFields("/etc/shadow", "test_user3")
        assert shadow_fields is not None
        assert shadow_fields[1] == ""

    def test_create_user_lock(self):
        """Create a locked user account."""

        # Create an empty, locked password
        users.create_user("test_user1", lock=True, password="", root=self.tmpdir)
        shadow_fields = self._readFields("/etc/shadow", "test_user1")
        assert shadow_fields is not None
        assert shadow_fields[1] == "!"

        # Create a locked password and ensure it can be unlocked (by removing the ! at the front)
        users.create_user("test_user2", lock=True, password="password", root=self.tmpdir)
        shadow_fields = self._readFields("/etc/shadow", "test_user2")
        assert shadow_fields is not None
        assert shadow_fields[1].startswith("!")
        assert crypt_r.crypt("password", shadow_fields[1][1:]) == shadow_fields[1][1:]

    def test_create_user_uid(self):
        """Create a user with a specific UID."""

        users.create_user("test_user", uid=1047, root=self.tmpdir)
        pwd_fields = self._readFields("/etc/passwd", "test_user")
        assert pwd_fields is not None
        assert pwd_fields[2] == "1047"

    def test_create_user_gid(self):
        """Create a user with a specific GID."""

        users.create_user("test_user", gid=1047, root=self.tmpdir)

        pwd_fields = self._readFields("/etc/passwd", "test_user")
        assert pwd_fields is not None
        assert pwd_fields[3] == "1047"

        grp_fields = self._readFields("/etc/group", "test_user")
        assert grp_fields is not None
        assert grp_fields[2] == "1047"

    def test_create_user_exists(self):
        """Create a user that already exists."""
        with open(self.tmpdir + "/etc/passwd", "w") as f:
            f.write("test_user:x:1000:1000::/:/bin/sh\n")

        with pytest.raises(ValueError):
            users.create_user("test_user", root=self.tmpdir)

    def test_create_user_uid_exists(self):
        """Create a user with a UID that already exists."""
        with open(self.tmpdir + "/etc/passwd", "w") as f:
            f.write("conflict:x:1000:1000::/:/bin/sh\n")

        with pytest.raises(ValueError):
            users.create_user("test_user", uid=1000, root=self.tmpdir)

    def test_create_user_gid_exists(self):
        """Create a user with a GID of an existing group."""
        users.create_group("test_group", gid=5000, root=self.tmpdir)
        users.create_user("test_user", gid=5000, root=self.tmpdir)

        passwd_fields = self._readFields("/etc/passwd", "test_user")
        assert passwd_fields is not None
        assert passwd_fields[3] == "5000"

    def test_set_user_ssh_key(self):
        keydata = "THIS IS TOTALLY A SSH KEY"

        users.create_user("test_user", homedir="/home/test_user", root=self.tmpdir)
        with patch("pyanaconda.core.users.util.restorecon") as restorecon_mock:
            users.set_user_ssh_key("test_user", keydata, root=self.tmpdir)

        restorecon_mock.assert_called_once_with(
            ["/home/test_user/.ssh"],
            root=self.tmpdir
        )

        keyfile = self.tmpdir + "/home/test_user/.ssh/authorized_keys"
        assert os.path.isfile(keyfile)
        with open(keyfile) as f:
            output_keydata = f.read()

        assert keydata == output_keydata.strip()

    def test_set_root_password(self):
        password = "password1"

        # Initialize a root user with an empty password, like the setup package would have
        with open(self.tmpdir + "/etc/passwd", "w") as f:
            f.write("root:x:0:0:root:/root:/bin/bash\n")

        with open(self.tmpdir + "/etc/shadow", "w") as f:
            f.write("root:*:16489:0:99999:7:::\n")

        users.set_root_password(password, root=self.tmpdir)
        shadow_fields = self._readFields("/etc/shadow", "root")
        assert crypt_r.crypt(password, shadow_fields[1]) == shadow_fields[1]

        # Try a different password with lock=True
        password = "password2"
        users.set_root_password(password, lock=True, root=self.tmpdir)
        shadow_fields = self._readFields("/etc/shadow", "root")
        assert shadow_fields[1].startswith("!")
        assert crypt_r.crypt(password, shadow_fields[1][1:]) == shadow_fields[1][1:]

        # Try an encrypted password
        password = crypt_r.crypt("testpass", crypt_r.METHOD_MD5)
        users.set_root_password(password, is_crypted=True, root=self.tmpdir)
        shadow_fields = self._readFields("/etc/shadow", "root")
        assert password == shadow_fields[1]

    def test_create_user_reuse_home(self):
        # Create a user, reusing an old home directory

        os.makedirs(self.tmpdir + "/home/test_user")
        os.chown(self.tmpdir + "/home/test_user", 500, 500)

        with patch("pyanaconda.core.util.restorecon") as restorecon_mock:
            users.create_user(
                "test_user",
                homedir="/home/test_user",
                uid=1000,
                gid=1000,
                root=self.tmpdir
            )

        restorecon_mock.assert_called_once_with(["/home/test_user"], root=self.tmpdir)

        passwd_fields = self._readFields("/etc/passwd", "test_user")
        assert passwd_fields is not None
        assert passwd_fields[2] == "1000"
        assert passwd_fields[3] == "1000"

        stat_fields = os.stat(self.tmpdir + "/home/test_user")
        assert stat_fields.st_uid == 1000
        assert stat_fields.st_gid == 1000

    def test_create_user_gid_in_group_list(self):
        """Create a user with a GID equal to that of one of the requested groups"""

        users.create_user("test_user", gid=1047, groups=["test_group(1047)"], root=self.tmpdir)

        # Ensure that the user's GID is equal to the GID requested
        pwd_fields = self._readFields("/etc/passwd", "test_user")
        assert pwd_fields is not None
        assert pwd_fields[3] == "1047"

        # and that the requested group has the right GID
        grp_fields = self._readFields("/etc/group", "test_group")
        assert grp_fields is not None
        assert grp_fields[2] == "1047"


class ReownHomedirTest(unittest.TestCase):
    """Tests for _reown_homedir"""
    def _make_dir(self, root, name, uid, gid):
        make_directories(root + name)
        os.chown(root + name, uid, gid)

    def _make_file(self, root, name, uid, gid):
        touch(root + name)
        os.chown(root + name, uid, gid)

    def _check_path(self, root, name, expected_uid, expected_gid):
        stats = os.stat(root + name)
        assert stats.st_uid == expected_uid
        assert stats.st_gid == expected_gid

    @patch("pyanaconda.core.users._getpwnam", return_value=["sam", "x", "2022", "2022"])
    @patch("pyanaconda.core.util.restorecon")
    @patch("pyanaconda.core.util.execWithRedirect")
    def test_reown_homedir(self, exec_mock, restorecon_mock, getpwnam_mock):
        """Test re-owning a home directory.

        We have "sam" who was uid/gid 1492 and now will be 2022.
        """
        with tempfile.TemporaryDirectory() as sysroot:
            # set up various stuff in the home dir to work on
            self._make_dir(sysroot, "/home/sam", 1492, 1492)  # main dir, uid/gid taken from here
            self._make_dir(sysroot, "/home/sam/Downloads", 1492, 1492)  # empty dir
            self._make_dir(sysroot, "/home/sam/Documents", 1492, 1492)  # full dir
            self._make_file(sysroot, "/home/sam/Documents/mine", 1492, 1492)   # own file
            self._make_file(sysroot, "/home/sam/Documents/theirs", 1881, 1881)  # other file
            self._make_file(sysroot, "/home/sam/Documents/oops", 1492, 2000)  # mixed file
            self._make_dir(sysroot, "/home/sam/root_owns_you", 10000, 10000)  # other dir
            self._make_file(sysroot, "/home/sam/root_owns_you/thoroughly", 10000, 10000)

            users._reown_homedir(sysroot, "/home/sam", "sam")

            exec_mock.assert_called_once_with(
                "chown",
                ["--recursive", "--no-dereference", "--from=1492:1492", "2022:2022",
                 sysroot + "/home/sam"]
            )
            restorecon_mock.assert_called_once_with(["/home/sam"], root=sysroot)

            # now also run the same thing as was mocked, to make sure the expectations are met
            os.system("chown --recursive --no-dereference --from=1492:1492 2022:2022"
                      " {}/home/sam".format(sysroot))

            self._check_path(sysroot, "/home/sam", 2022, 2022)
            self._check_path(sysroot, "/home/sam/Downloads", 2022, 2022)
            self._check_path(sysroot, "/home/sam/Documents", 2022, 2022)
            self._check_path(sysroot, "/home/sam/Documents/mine", 2022, 2022)
            self._check_path(sysroot, "/home/sam/Documents/theirs", 1881, 1881)
            self._check_path(sysroot, "/home/sam/Documents/oops", 1492, 2000)
            self._check_path(sysroot, "/home/sam/root_owns_you", 10000, 10000)
            self._check_path(sysroot, "/home/sam/root_owns_you/thoroughly", 10000, 10000)
