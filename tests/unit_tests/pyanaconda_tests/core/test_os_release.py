#
# Copyright (C) 2013  Red Hat, Inc.
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

import os
import tempfile
import unittest
from unittest.mock import patch

from pyanaconda.core.os_release import get_os_release_value


class OSReleaseTestCase(unittest.TestCase):

    @patch("pyanaconda.core.os_release.platform.freedesktop_os_release",
           side_effect=AssertionError("Must not read runtime metadata for a sysroot"))
    def test_get_os_release_value(self, read_os_release):
        """Read target metadata independently of the running system."""
        with tempfile.TemporaryDirectory() as root:
            # prepare paths
            os.makedirs(root + "/usr/lib")
            os.makedirs(root + "/etc")

            # no file
            with self.assertLogs(level="DEBUG") as cm:
                version = get_os_release_value("VERSION_ID", root)

            msg = "VERSION_ID not found in os-release files"
            assert any(map(lambda x: msg in x, cm.output))
            assert version is None

            # backup file only
            with open(root + "/usr/lib/os-release", "w") as f:
                f.write("# blah\nVERSION_ID=foo256bar  \n VERSION_ID = wrong\n\n")
            version = get_os_release_value("VERSION_ID", root)
            assert version == "foo256bar"

            # main file and backup too
            with open(root + "/etc/os-release", "w") as f:
                f.write("# blah\nVERSION_ID=more-important\n")
            version = get_os_release_value("VERSION_ID", root)
            assert version == "more-important"

            # both, main file twice
            with open(root + "/etc/os-release", "w") as f:
                f.write("# blah\nVERSION_ID=more-important\nVERSION_ID=not-reached\n \n")
            version = get_os_release_value("VERSION_ID", root)
            assert version == "more-important"

            # quoted values
            with open(root + "/etc/os-release", "w") as f:
                f.write("PRETTY_NAME=\"Fedora 32\"\n")
            assert get_os_release_value("PRETTY_NAME", root) == "Fedora 32"

            # no files
            os.remove(root + "/usr/lib/os-release")
            os.remove(root + "/etc/os-release")
            version = get_os_release_value("VERSION_ID", root)
            assert version is None
