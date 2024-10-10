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
# Red Hat Author(s): Vendula Poncova <vponcova@redhat.com>
#
import pyanaconda
import unittest

from importlib import import_module
from pkgutil import walk_packages


class SimpleImportTestCase(unittest.TestCase):
    """Simple test case for pyanaconda.

    Import all pyanaconda modules.
    """

    def _check_package(self, package, expected_imports, skipped_imports):
        """Check if all submodules of the package can be imported."""
        failed = set()
        missing = set(expected_imports)
        path = package.__path__
        prefix = package.__name__ + '.'

        for _, name, _ in walk_packages(path, prefix, failed.add):
            if name.endswith(".__main__"):
                continue

            if name in skipped_imports:
                continue

            print(name)
            import_module(name)
            missing.discard(name)

        if failed:
            self.fail("Failed to import: {}".format(", ".join(failed)))

        if missing:
            self.fail("Expected to import: {}".format(", ".join(missing)))

    def test_import_pyanaconda(self):
        """Import everything from pyanaconda.

        Import all submodules and randomly check some of them.
        """
        self._check_package(pyanaconda, [
            "pyanaconda.core",
            "pyanaconda.core.util",
            "pyanaconda.core.configuration.anaconda",
            "pyanaconda.modules.common.constants.interfaces",
            "pyanaconda.modules.storage.checker.utils",
            "pyanaconda.ui.categories",
            "pyanaconda.ui.gui.spokes.lib.cart",
            "pyanaconda.ui.tui.spokes.askrd",
            "pyanaconda.rescue"
        ], [
            "pyanaconda.modules.storage.partitioning.blivet.blivet_handler",
            "pyanaconda.ui.gui.spokes.blivet_gui"
        ])
