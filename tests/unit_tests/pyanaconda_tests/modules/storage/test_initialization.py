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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import unittest
from unittest.mock import patch

from blivet.formats import get_device_format_class

from pyanaconda.modules.storage.initialization import _set_default_label_type


class DefaultDiskLabelTypeTestCase(unittest.TestCase):
    """Test the initialization of the default disk label type."""

    def setUp(self):
        """Set up the test."""
        self.disklabel.set_default_label_type(None)

    def tearDown(self):
        """Tear down the test."""
        self.disklabel.set_default_label_type(None)

    @property
    def disklabel(self):
        """The disk label class."""
        return get_device_format_class("disklabel")

    def test_set_default_label_type(self):
        """Don't crash by default."""
        _set_default_label_type()

    @patch("pyanaconda.modules.storage.initialization.conf")
    @patch("blivet.formats.disklabel.DiskLabel.get_platform_label_types")
    def test_set_default_label_type_unsupported(self, supported_types_getter, mocked_conf):
        """Test the unsupported disk label type initialization."""
        mocked_conf.storage.disk_label_type = "gpt"
        supported_types_getter.return_value = ["mac"]

        with self.assertLogs(level="WARNING") as cm:
            _set_default_label_type()

        msg = "The requested disk label type 'gpt' is not supported on " \
              "this platform. Using the default disk label 'mac' instead."

        assert msg in "\n".join(cm.output)
        assert self.disklabel._default_label_type is None

    @patch("pyanaconda.modules.storage.initialization.conf")
    @patch("blivet.formats.disklabel.DiskLabel.get_platform_label_types")
    def test_set_default_label_type_none(self, label_types_getter, mocked_conf):
        """Test the unset disk label type initialization."""
        mocked_conf.storage.disk_label_type = ""
        label_types_getter.return_value = ["msdos", "gpt"]
        _set_default_label_type()
        assert self.disklabel._default_label_type is None

    @patch("pyanaconda.modules.storage.initialization.conf")
    @patch("blivet.formats.disklabel.DiskLabel.get_platform_label_types")
    def test_set_default_label_type_gpt(self, label_types_getter, mocked_conf):
        """Test the unsupported disk label type initialization."""
        mocked_conf.storage.disk_label_type = "gpt"
        label_types_getter.return_value = ["msdos", "gpt"]
        _set_default_label_type()
        assert self.disklabel._default_label_type == "gpt"

    @patch("pyanaconda.modules.storage.initialization.conf")
    @patch("blivet.formats.disklabel.DiskLabel.get_platform_label_types")
    def test_set_default_label_type_mbr(self, label_types_getter, mocked_conf):
        """Test the mbr disk label type initialization."""
        mocked_conf.storage.disk_label_type = "mbr"
        label_types_getter.return_value = ["gpt", "msdos"]
        _set_default_label_type()
        assert self.disklabel._default_label_type == "msdos"
