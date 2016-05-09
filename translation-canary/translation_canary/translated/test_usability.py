# Check a .po file for basic usability
#
# This will test that the file is well-formed and that the Plural-Forms value
# is parseable
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

import gettext
import tempfile
import polib
import subprocess

def test_usability(pofile):
    # Use polib to write a mofile
    with tempfile.NamedTemporaryFile(mode="w+b") as mofile:
        pofile = polib.pofile(pofile)
        pofile.save_as_mofile(mofile.name)

        # Try to open it
        _t = gettext.GNUTranslations(fp=mofile)

def test_msgfmt(pofile):
    # Check that the .po file can actually be compiled
    with tempfile.NamedTemporaryFile(mode="w+b", suffix=".mo") as mofile:
        try:
            # Ignore the output on success
            subprocess.check_output(["msgfmt", "-c", "--verbose", "-o", mofile.name, pofile],
                                    stderr=subprocess.STDOUT, universal_newlines=True)
        except subprocess.CalledProcessError as e:
            raise AssertionError("Unable to compile %s: %s" % (pofile, e.output))
