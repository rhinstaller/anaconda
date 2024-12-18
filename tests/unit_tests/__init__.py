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
import locale
import os

import gi.overrides
import pytest

# Apply overrides for the anaconda widgets.
if "ANACONDA_WIDGETS_OVERRIDES" in os.environ:
    for p in os.environ["ANACONDA_WIDGETS_OVERRIDES"].split(":"):
        gi.overrides.__path__.insert(0, os.path.abspath(p))


# Set the default locale.
locale.setlocale(locale.LC_ALL, "en_US.UTF-8")

# Register modules with helper functions.
pytest.register_assert_rewrite(
    "tests.unit_tests.pyanaconda_tests",
    "tests.unit_tests.pyanaconda_tests.modules.payloads.payload.module_payload_shared",
)
