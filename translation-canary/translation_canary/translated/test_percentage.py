# Check what percentage of strings a .po translates
#
# This will reject translations that fall below a certain threshold of
# translated strings.
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

import warnings

try:
    import polib
except ImportError:
    print("You need to install the python-polib package to read translations")
    raise

threshold = 10

def test_percentage(pofile):
    pofile = polib.pofile(pofile)
    if pofile.percent_translated() < threshold:
        # Issue a warning instead of an exception, since these should probably
        # be handled on a case-by-case basis
        warnings.warn("amount translated of %d%% below threshold of %d%%" % (pofile.percent_translated(), threshold))
