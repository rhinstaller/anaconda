#
# Copyright (C) 2022  Red Hat, Inc.
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

from pyanaconda.ui.gui.spokes.lib.installation_source_helpers import get_unique_repo_name, \
    validate_repo_name
from pyanaconda.ui.helpers import InputCheck


class InstallationSourceUtilsTestCase(unittest.TestCase):
    """Test functions used by the Installation Source spoke."""

    def test_get_unique_repo_name(self):
        """Test the get_unique_repo_name function."""
        assert "New_Repository" == get_unique_repo_name()
        assert "New_Repository" == get_unique_repo_name([
            "New_Repository_1",
        ])
        assert "New_Repository" == get_unique_repo_name([
            "New_Repository_1",
            "New_Repository_2",
        ])
        assert "New_Repository_1" == get_unique_repo_name([
            "New_Repository"
        ])
        assert "New_Repository_2" == get_unique_repo_name([
            "New_Repository",
            "New_Repository_1",
        ])
        assert "New_Repository_3" == get_unique_repo_name([
            "New_Repository",
            "New_Repository_1",
            "New_Repository_2",
        ])
        assert "New_Repository_4" == get_unique_repo_name([
            "New_Repository",
            "New_Repository_3",
        ])

    def test_validate_repo_name(self):
        """Test the validate_repo_name function."""
        assert validate_repo_name("New_Repository_1") == InputCheck.CHECK_OK
        assert validate_repo_name("AppStream") == InputCheck.CHECK_OK
        assert validate_repo_name("my_repo") == InputCheck.CHECK_OK
        assert validate_repo_name("my_repo", conflicting_names=["another"]) == InputCheck.CHECK_OK

        msg = "Empty repository name"
        assert validate_repo_name("") == msg

        msg = "Invalid repository name"
        assert validate_repo_name("invalid repo") == msg
        assert validate_repo_name("repo(invalid)") == msg

        msg = "Repository name conflicts with internal repository name."
        assert validate_repo_name("anaconda") == msg
        assert validate_repo_name("rawhide") == msg
        assert validate_repo_name("my_repo", conflicting_names=["my_repo"]) == msg
