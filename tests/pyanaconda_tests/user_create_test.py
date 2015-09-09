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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): David Shea <dshea@redhat.com>
#

# Ignore any interruptible calls
# pylint: disable=interruptible-system-call

from pyanaconda import users
import unittest
import tempfile
import shutil
import os
import crypt
import platform
import glob

@unittest.skipIf(os.geteuid() != 0, "user creation must be run as root")
class UserCreateTest(unittest.TestCase):
    def setUp(self):
        self.users = users.Users()

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
        if platform.architecture()[0].startswith("64"):
            libdir = "/lib64"
        else:
            libdir = "/lib"

        os.mkdir(self.tmpdir + libdir)
        for lib in glob.glob(libdir + "/libnss_files*"):
            shutil.copy(lib, self.tmpdir + lib)

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

    def create_group_test(self):
        """Create a group."""
        self.users.createGroup("test_group", root=self.tmpdir)

        fields = self._readFields("/etc/group", "test_group")
        self.assertIsNotNone(fields)
        self.assertEqual(fields[0], "test_group")

        fields = self._readFields("/etc/gshadow", "test_group")
        self.assertIsNotNone(fields)
        self.assertEqual(fields[0], "test_group")

    def create_group_gid_test(self):
        """Create a group with a specific GID."""
        self.users.createGroup("test_group", gid=47, root=self.tmpdir)

        fields = self._readFields("/etc/group", "test_group")

        self.assertIsNotNone(fields)
        self.assertEqual(fields[0], "test_group")
        self.assertEqual(fields[2], "47")

    def create_group_exists_test(self):
        """Create a group that already exists."""
        with open(self.tmpdir + "/etc/group", "w") as f:
            f.write("test_group:x:47:\n")

        self.assertRaises(ValueError, self.users.createGroup, "test_group", root=self.tmpdir)

    def create_group_gid_exists_test(self):
        """Create a group with a GID that already exists."""
        with open(self.tmpdir + "/etc/group", "w") as f:
            f.write("gid_used:x:47:\n")

        self.assertRaises(ValueError, self.users.createGroup, "test_group", gid=47, root=self.tmpdir)

    def create_user_test(self):
        """Create a user."""
        self.users.createUser("test_user", root=self.tmpdir)

        pwd_fields = self._readFields("/etc/passwd", "test_user")
        self.assertIsNotNone(pwd_fields)
        self.assertEqual(pwd_fields[0], "test_user")

        # Check that the fields got the right default values
        # UID + GID set to some sort of int
        self.assertTrue(isinstance(int(pwd_fields[2]), int))
        self.assertTrue(isinstance(int(pwd_fields[3]), int))

        # home is /home/username
        self.assertEqual(pwd_fields[5], "/home/test_user")

        # shell set to something
        self.assertTrue(pwd_fields[6])

        shadow_fields = self._readFields("/etc/shadow", "test_user")
        self.assertIsNotNone(shadow_fields)
        self.assertEqual(shadow_fields[0], "test_user")

        # Ensure the password is locked
        self.assertTrue(shadow_fields[1].startswith("!"))

        # Ensure the date of last password change is empty
        self.assertEqual(shadow_fields[2], "")

        # Check that the user group was created
        grp_fields = self._readFields("/etc/group", "test_user")
        self.assertIsNotNone(grp_fields)
        self.assertEqual(grp_fields[0], "test_user")

        # Check that user group's GID matches the user's GID
        self.assertEqual(grp_fields[2], pwd_fields[3])

        gshadow_fields = self._readFields("/etc/gshadow", "test_user")
        self.assertIsNotNone(gshadow_fields)
        self.assertEqual(gshadow_fields[0], "test_user")

    def create_user_text_options_test(self):
        """Create a user with the text fields set."""
        self.users.createUser("test_user", gecos="Test User", homedir="/home/users/testuser", shell="/bin/test", root=self.tmpdir)

        pwd_fields = self._readFields("/etc/passwd", "test_user")
        self.assertIsNotNone(pwd_fields)
        self.assertEqual(pwd_fields[0], "test_user")
        self.assertEqual(pwd_fields[4], "Test User")
        self.assertEqual(pwd_fields[5], "/home/users/testuser")
        self.assertEqual(pwd_fields[6], "/bin/test")

        # Check that the home directory was created
        self.assertTrue(os.path.isdir(self.tmpdir + "/home/users/testuser"))

    def create_user_groups_test(self):
        """Create a user with a list of groups."""
        # First create some groups
        self.users.createGroup("test1", root=self.tmpdir)
        self.users.createGroup("test2", root=self.tmpdir)
        self.users.createGroup("test3", root=self.tmpdir)

        self.users.createUser("test_user", groups=["test1", "test2", "test3"], root=self.tmpdir)

        grp_fields1 = self._readFields("/etc/group", "test1")
        self.assertEqual(grp_fields1[3], "test_user")

        grp_fields2 = self._readFields("/etc/group", "test2")
        self.assertEqual(grp_fields2[3], "test_user")

        grp_fields3 = self._readFields("/etc/group", "test3")
        self.assertEqual(grp_fields3[3], "test_user")

    def create_user_password_test(self):
        """Create a user with a password."""

        self.users.createUser("test_user1", password="password", root=self.tmpdir)
        shadow_fields = self._readFields("/etc/shadow", "test_user1")
        self.assertIsNotNone(shadow_fields)
        # Make sure the password works
        self.assertEqual(crypt.crypt("password", shadow_fields[1]), shadow_fields[1])

        # Set the encrypted password for another user with isCrypted
        cryptpw = shadow_fields[1]
        self.users.createUser("test_user2", password=cryptpw, isCrypted=True, root=self.tmpdir)
        shadow_fields = self._readFields("/etc/shadow", "test_user2")
        self.assertIsNotNone(shadow_fields)
        self.assertEqual(cryptpw, shadow_fields[1])

        # Set an empty password
        self.users.createUser("test_user3", password="", root=self.tmpdir)
        shadow_fields = self._readFields("/etc/shadow", "test_user3")
        self.assertIsNotNone(shadow_fields)
        self.assertEqual("", shadow_fields[1])

    def create_user_lock_test(self):
        """Create a locked user account."""

        # Create an empty, locked password
        self.users.createUser("test_user1", lock=True, password="", root=self.tmpdir)
        shadow_fields = self._readFields("/etc/shadow", "test_user1")
        self.assertIsNotNone(shadow_fields)
        self.assertEqual("!", shadow_fields[1])

        # Create a locked password and ensure it can be unlocked (by removing the ! at the front)
        self.users.createUser("test_user2", lock=True, password="password", root=self.tmpdir)
        shadow_fields = self._readFields("/etc/shadow", "test_user2")
        self.assertIsNotNone(shadow_fields)
        self.assertTrue(shadow_fields[1].startswith("!"))
        self.assertEqual(crypt.crypt("password", shadow_fields[1][1:]), shadow_fields[1][1:])

    def create_user_uid_test(self):
        """Create a user with a specific UID."""

        self.users.createUser("test_user", uid=1047, root=self.tmpdir)
        pwd_fields = self._readFields("/etc/passwd", "test_user")
        self.assertIsNotNone(pwd_fields)
        self.assertEqual(pwd_fields[2], "1047")

    def create_user_gid_test(self):
        """Create a user with a specific GID."""

        self.users.createUser("test_user", gid=1047, root=self.tmpdir)

        pwd_fields = self._readFields("/etc/passwd", "test_user")
        self.assertIsNotNone(pwd_fields)
        self.assertEqual(pwd_fields[3], "1047")

        grp_fields = self._readFields("/etc/group", "test_user")
        self.assertIsNotNone(grp_fields)
        self.assertEqual(grp_fields[2], "1047")

    def create_user_algo_test(self):
        """Create a user with a specific password algorithm."""

        self.users.createUser("test_user1", password="password", algo="md5", root=self.tmpdir)
        shadow_fields = self._readFields("/etc/shadow", "test_user1")
        self.assertIsNotNone(shadow_fields)
        self.assertTrue(shadow_fields[1].startswith("$1$"))

        self.users.createUser("test_user2", password="password", algo="sha512", root=self.tmpdir)
        shadow_fields = self._readFields("/etc/shadow", "test_user2")
        self.assertIsNotNone(shadow_fields)
        self.assertTrue(shadow_fields[1].startswith("$6$"))

    def create_user_exists_test(self):
        """Create a user that already exists."""
        with open(self.tmpdir + "/etc/passwd", "w") as f:
            f.write("test_user:x:1000:1000::/:/bin/sh\n")

        self.assertRaises(ValueError, self.users.createUser, "test_user", root=self.tmpdir)

    def create_user_uid_exists_test(self):
        """Create a user with a UID that already exists."""
        with open(self.tmpdir + "/etc/passwd", "w") as f:
            f.write("conflict:x:1000:1000::/:/bin/sh\n")

        self.assertRaises(ValueError, self.users.createUser, "test_user", uid=1000, root=self.tmpdir)

    def set_user_ssh_key_test(self):
        keydata = "THIS IS TOTALLY A SSH KEY"

        self.users.createUser("test_user", homedir="/home/test_user", root=self.tmpdir)
        self.users.setUserSshKey("test_user", keydata, root=self.tmpdir)

        keyfile = self.tmpdir + "/home/test_user/.ssh/authorized_keys"
        self.assertTrue(os.path.isfile(keyfile))
        with open(keyfile) as f:
            output_keydata = f.read()

        self.assertEqual(keydata, output_keydata.strip())

    def create_user_reuse_home_test(self):
        # Create a user, reusing an old home directory

        os.makedirs(self.tmpdir + "/home/test_user")
        os.chown(self.tmpdir + "/home/test_user", 500, 500)

        self.users.createUser("test_user", homedir="/home/test_user", uid=1000, gid=1000, root=self.tmpdir)
        passwd_fields = self._readFields("/etc/passwd", "test_user")
        self.assertIsNotNone(passwd_fields)
        self.assertEqual(passwd_fields[2], "1000")
        self.assertEqual(passwd_fields[3], "1000")

        stat_fields = os.stat(self.tmpdir + "/home/test_user")
        self.assertEqual(stat_fields.st_uid, 1000)
        self.assertEqual(stat_fields.st_gid, 1000)
