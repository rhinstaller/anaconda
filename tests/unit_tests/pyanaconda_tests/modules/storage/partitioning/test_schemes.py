#
# Tests for automatic partitioning schemes.
#
# Copyright (C) 2026 Red Hat, Inc.
#
import unittest
from unittest.mock import patch

from pykickstart.constants import AUTOPART_TYPE_BTRFS

from pyanaconda.core.configuration.storage import PartitioningScheme
from pyanaconda.modules.storage.partitioning.schemes import (
    get_default_partitioning_scheme_name,
    get_supported_file_system_types,
    get_supported_partitioning_schemes,
)


class PartitioningSchemesTestCase(unittest.TestCase):
    """Tests for partitioning scheme metadata."""

    @patch("pyanaconda.modules.storage.partitioning.schemes._is_supported_autopart_type")
    def test_get_supported_partitioning_schemes(self, is_supported):
        is_supported.return_value = True

        schemes = get_supported_partitioning_schemes()

        self.assertGreaterEqual(len(schemes), 1)
        ids = {scheme.scheme_id for scheme in schemes}
        self.assertIn("BTRFS", ids)
        self.assertIn("LVM", ids)

        # A scheme reports whether it lets the request pick a file system type.
        by_id = {scheme.scheme_id: scheme for scheme in schemes}
        self.assertTrue(by_id["LVM"].has_file_system_type)
        self.assertFalse(by_id["BTRFS"].has_file_system_type)

    @patch("pyanaconda.modules.storage.partitioning.schemes._is_supported_autopart_type")
    def test_get_supported_partitioning_schemes_filters_unsupported(self, is_supported):
        """A scheme blivet cannot create on this system is not reported."""
        is_supported.side_effect = lambda autopart_type: autopart_type != AUTOPART_TYPE_BTRFS

        ids = {scheme.scheme_id for scheme in get_supported_partitioning_schemes()}

        self.assertNotIn("BTRFS", ids)
        self.assertIn("LVM", ids)

    @patch("pyanaconda.modules.storage.partitioning.schemes.conf")
    def test_get_default_partitioning_scheme_name(self, mocked_conf):
        mocked_conf.storage.default_scheme = PartitioningScheme.BTRFS.value
        self.assertEqual(get_default_partitioning_scheme_name(), "BTRFS")

    def test_get_supported_file_system_types(self):
        types = get_supported_file_system_types()

        self.assertIn("ext4", types)
        # Not mountable, not formattable or not Linux native.
        self.assertNotIn("swap", types)
        self.assertNotIn("vfat", types)
        self.assertNotIn("biosboot", types)
