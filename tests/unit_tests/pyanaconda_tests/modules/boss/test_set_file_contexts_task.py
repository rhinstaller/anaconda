#
# Copyright (C) 2021  Red Hat, Inc.
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
import unittest
from unittest.mock import patch

from pyanaconda.modules.boss.installation import SetContextsTask


class SetContextsTaskTest(unittest.TestCase):
    @patch("pyanaconda.modules.boss.installation.restorecon")
    def test_run(self, restore_mock):
        """Test SetContextsTask success."""
        task = SetContextsTask("/somewhere")
        with self.assertLogs() as cm:
            task.run()

        restore_mock.assert_called_once_with(
            [
                "/boot",
                "/dev",
                "/etc",
                "/lib64",
                "/root",
                "/usr/lib",
                "/usr/lib64",
                "/var/cache/yum",
                "/var/home",
                "/var/lib",
                "/var/lock",
                "/var/log",
                "/var/media",
                "/var/mnt",
                "/var/opt",
                "/var/roothome",
                "/var/run",
                "/var/spool",
                "/var/srv"
            ],
            root="/somewhere",
            skip_nonexistent=True
        )

        logs = "\n".join(cm.output)
        assert "restorecon was not installed" not in logs

    @patch("pyanaconda.core.util.execWithRedirect")
    def test_restorecon_missing(self, exec_mock):
        """Test SetContextsTask with missing restorecon."""
        exec_mock.side_effect = FileNotFoundError("testing")
        task = SetContextsTask("/somewhere")

        with self.assertLogs() as cm:
            task.run()  # asserts also that exception is not raised

        logs = "\n".join(cm.output)
        assert "restorecon was not installed" in logs
