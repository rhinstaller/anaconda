# -*- coding: utf-8 -*-
#
# Copyright (C) 2017  Red Hat, Inc.
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
# Red Hat Author(s): Vendula Poncova <vponcova@redhat.com>
#
import unittest
import pyanaconda.modules.storage.checker.utils as checks

from blivet.size import Size
from pyanaconda.modules.storage.checker.utils import StorageChecker


class StorageCheckerTests(unittest.TestCase):

    def setUp(self):
        self.maxDiff = None

    def nocheck_test(self):
        """Test a check with no checks."""
        checker = StorageChecker()
        report = checker.check(None)

        self.assertEqual(report.success, True)
        self.assertEqual(report.failure, False)
        self.assertListEqual(report.errors, [])
        self.assertListEqual(report.warnings, [])

    def simple_error_test(self):
        """Test an simple error report."""
        checker = StorageChecker()

        def check(storage, constraints, report_error, report_warning):
            report_error("error")

        checker.add_check(check)
        report = checker.check(None)

        self.assertEqual(report.success, False)
        self.assertListEqual(report.errors, ["error"])
        self.assertListEqual(report.warnings, [])

    def simple_warning_test(self):
        """Test an simple warning report."""
        checker = StorageChecker()

        def check(storage, constraints, report_error, report_warning):
            report_warning("warning")

        checker.add_check(check)
        report = checker.check(None)
        self.assertEqual(report.success, False)
        self.assertListEqual(report.errors, [])
        self.assertListEqual(report.warnings, ["warning"])

    def simple_info_test(self):
        """Test simple info messages. """
        checker = StorageChecker()
        report = checker.check(None)
        self.assertListEqual(report.info, [
            "Storage check started with constraints {}.",
            "Storage check finished with success."
        ])

    def info_test(self):
        """Test info messages. """
        checker = StorageChecker()

        def error_check(storage, constraints, report_error, report_warning):
            report_error("error")

        def warning_check(storage, constraints, report_error, report_warning):
            report_warning("warning")

        def skipped_check(storage, constraints, report_error, report_warning):
            report_warning("skipped")

        checker.add_constraint("x", None)
        checker.add_check(error_check)
        checker.add_check(warning_check)
        checker.add_check(skipped_check)

        report = checker.check(None, skip=(skipped_check,))
        self.assertListEqual(report.info, [
            "Storage check started with constraints {'x': None}.",
            "Run sanity check error_check.",
            "Found sanity error: error",
            "Run sanity check warning_check.",
            "Found sanity warning: warning",
            "Skipped sanity check skipped_check.",
            "Storage check finished with failure(s)."
        ])

    def simple_constraints_test(self):
        """Test simple constraint adding."""
        checker = StorageChecker()

        # Try to add a new constraint with a wrong method.
        self.assertRaises(KeyError, checker.set_constraint, "x", None)

        # Try to add a new constraint two times.
        checker.add_constraint("x", None)
        self.assertRaises(KeyError, checker.add_constraint, "x", None)

    def check_constraints_test(self):
        """Test constraints checking."""
        checker = StorageChecker()

        def check(storage, constraints, report_error, report_warning):
            report_warning("%s" % constraints)

        checker.add_check(check)
        report = checker.check(None)
        self.assertListEqual(report.warnings, ["{}"])

        checker.add_constraint("x", 1)
        report = checker.check(None)
        self.assertListEqual(report.warnings, ["{'x': 1}"])

        checker.set_constraint("x", 0)
        report = checker.check(None)
        self.assertListEqual(report.warnings, ["{'x': 0}"])

    def dictionary_constraints_test(self):
        """Test the dictionary constraints."""
        checker = StorageChecker()

        checker.add_constraint("x", {"a": 1, "b": 2, "c": 3})
        self.assertIn("x", checker.constraints)
        self.assertEqual(checker.constraints["x"], {"a": 1, "b": 2, "c": 3})

        checker.set_constraint("x", {"e": 4, "f": 5})
        self.assertIn("x", checker.constraints)
        self.assertEqual(checker.constraints["x"], {"e": 4, "f": 5})

    def complicated_test(self):
        """Run a complicated check."""
        checker = StorageChecker()

        # Set the checks,
        def check_x(storage, constraints, report_error, report_warning):
            if constraints["x"] != 1:
                report_error("x is not equal to 1")

        def check_y(storage, constraints, report_error, report_warning):
            if constraints["y"] != 2:
                report_error("y is not equal to 2")

        def check_z(storage, constraints, report_error, report_warning):
            if constraints["z"] != 3:
                report_error("z is not equal to 3")

        checker.add_check(check_x)
        checker.add_check(check_y)
        checker.add_check(check_z)

        # Set the constraints.
        checker.add_constraint("x", 1)
        checker.add_constraint("y", 2)
        checker.add_constraint("z", 3)

        # Run the checker. OK
        report = checker.check(None)
        self.assertEqual(report.success, True)
        self.assertListEqual(report.errors, [])
        self.assertListEqual(report.warnings, [])

        # Set constraints to different values.
        checker.set_constraint("x", 0)
        checker.set_constraint("y", 1)
        checker.set_constraint("z", 2)

        # Run the checker. FAIL
        report = checker.check(None)
        self.assertEqual(report.success, False)
        self.assertListEqual(report.errors, [
            "x is not equal to 1",
            "y is not equal to 2",
            "z is not equal to 3"
        ])
        self.assertListEqual(report.warnings, [])

        # Run the checker. Test SKIP.
        report = checker.check(None, skip=(check_y,))
        self.assertEqual(report.success, False)
        self.assertListEqual(report.errors, [
            "x is not equal to 1",
            "z is not equal to 3"
        ])
        self.assertListEqual(report.warnings, [])

        # Run the checker. Test CONSTRAINTS.
        constraints = {"x": 1, "y": 2, "z": 3}
        report = checker.check(None, constraints=constraints)
        self.assertEqual(report.success, True)
        self.assertListEqual(report.errors, [])
        self.assertListEqual(report.warnings, [])

        # Remove checks.
        checker.remove_check(check_x)
        checker.remove_check(check_y)
        checker.remove_check(check_z)

        report = checker.check(None)
        self.assertEqual(report.success, True)
        self.assertListEqual(report.errors, [])
        self.assertListEqual(report.warnings, [])

    def default_settings_test(self):
        """Check the default storage checker."""
        checker = StorageChecker()
        checker.set_default_constraints()
        checker.set_default_checks()

        self.assertEqual(checker.constraints, {
            checks.STORAGE_MIN_RAM:  Size("320 MiB"),
            checks.STORAGE_ROOT_DEVICE_TYPES: set(),
            checks.STORAGE_MIN_PARTITION_SIZES: {
                '/': Size("250 MiB"),
                '/usr': Size("250 MiB"),
                '/tmp': Size("50 MiB"),
                '/var': Size("384 MiB"),
                '/home': Size("100 MiB"),
                '/boot': Size("512 MiB")
            },
            checks.STORAGE_REQ_PARTITION_SIZES: dict(),
            checks.STORAGE_MUST_BE_ON_LINUXFS: {
                '/', '/var', '/tmp', '/usr', '/home', '/usr/share', '/usr/lib'
            },
            checks.STORAGE_MUST_BE_ON_ROOT: {
                '/bin', '/dev', '/sbin', '/etc', '/lib', '/root', '/mnt', 'lost+found', '/proc'
            },
            checks.STORAGE_MUST_NOT_BE_ON_ROOT: set(),
            checks.STORAGE_REFORMAT_WHITELIST: {
                '/boot', '/var', '/tmp', '/usr'
            },
            checks.STORAGE_REFORMAT_BLACKLIST: {
                '/home', '/usr/local', '/opt', '/var/www'
            },
            checks.STORAGE_SWAP_IS_RECOMMENDED: True,
            checks.STORAGE_LUKS2_MIN_RAM: Size("128 MiB"),
        })

        self.assertEqual(checker.checks, [
            checks.verify_root,
            checks.verify_s390_constraints,
            checks.verify_partition_formatting,
            checks.verify_partition_sizes,
            checks.verify_partition_format_sizes,
            checks.verify_bootloader,
            checks.verify_gpt_biosboot,
            checks.verify_swap,
            checks.verify_swap_uuid,
            checks.verify_mountpoints_on_linuxfs,
            checks.verify_mountpoints_on_root,
            checks.verify_mountpoints_not_on_root,
            checks.verify_unlocked_devices_have_key,
            checks.verify_luks_devices_have_key,
            checks.verify_luks2_memory_requirements,
            checks.verify_mounted_partitions,
            checks.verify_lvm_destruction,
        ])
