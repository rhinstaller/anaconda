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
# source code or documentation are not subject to the GNU General Public # License and may only be used or replicated with the express permission of # Red Hat, Inc.
#
# Red Hat Author(s): David Shea <dshea@redhat.com>

import unittest
import tempfile
import warnings
import shutil
import os
import polib

from translation_canary.translated.test_markup import test_markup
from translation_canary.translated.test_percentage import test_percentage
from translation_canary.translated.test_usability import test_usability

# convert a polib.MOFile into a NamedTemporaryFile
def mofile(moobj):
    f = tempfile.NamedTemporaryFile(suffix='.mo')
    moobj.save(f.name)
    return f

# convenience function for creating a single-entry mofile
def mofile_from_entry(*args, **kwargs):
    moobj = polib.MOFile()
    moobj.append(polib.MOEntry(*args, **kwargs))
    return mofile(moobj)

class TestMarkup(unittest.TestCase):
    # I know, pylint, that's the point
    # pylint: disable=invalid-markup

    def test_ok(self):
        # no markup
        with mofile_from_entry(msgid="test string", msgstr="estay ingstray") as m:
            test_markup(m.name)

        # matching markup
        with mofile_from_entry(msgid="<b>bold</b> string", msgstr="<b>oldbay</b> ingstray") as m:
            test_markup(m.name)

        # matching plural
        with mofile_from_entry(msgid="%d <b>bold</b> string", msgid_plural="%d <b>bold</b> strings",
                msgstr_plural={0: "%d <b>oldbay</b> ingstray", 1: "%d <b>oldbay</b> instrays"}) as m:
            test_markup(m.name)

    def test_missing(self):
        with mofile_from_entry(msgid="<b>bold</b> string", msgstr="oldbay ingstray") as m:
            self.assertRaises(AssertionError, test_markup, m.name)

    def test_mismatch(self):
        with mofile_from_entry(msgid="<b>bold</b> string", msgstr="<i>oldbay</i> ingstray") as m:
            self.assertRaises(AssertionError, test_markup, m.name)

    def test_typo(self):
        with mofile_from_entry(msgid="<b>bold</b> string", msgstr="<boldbay</b> ingstray") as m:
            self.assertRaises(AssertionError, test_markup, m.name)

    def test_mismatch_plural(self):
        with mofile_from_entry(msgid="%d <b>bold</b> string", msgid_plural="%d <b>bold</b> strings",
                msgstr_plural={0: "%d <b>olbday</b> ingstray", 1: "%d oldbay ingstrays"}) as m:
            self.assertRaises(AssertionError, test_markup, m.name)

    def test_invalid(self):
        # Tags themselves are valid, but the XML is not
        with mofile_from_entry(msgid="<b>bold</b> string", msgstr="<b/>oldbay</b> ingstray") as m:
            self.assertRaises(AssertionError, test_markup, m.name)

class TestPercentage(unittest.TestCase):
    # test_percentage actually looks at .po files, so the tests need to create
    # both a .po and a .mo in self.tmpdir

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.popath = os.path.join(self.tmpdir, "test.po")
        self.mopath = os.path.join(self.tmpdir, "test.mo")

        # Convert warnings into exceptions to make them easier to test for
        warnings.simplefilter("error")
        # polib throws a DeprecationWarnings so ignore that
        warnings.simplefilter("default", DeprecationWarning)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)
        warnings.resetwarnings()

    def test_ok(self):
        # 100%
        pofile = polib.POFile()
        pofile.append(polib.POEntry(msgid="test string", msgstr="estay ingstray"))
        pofile.save(self.popath)
        pofile.save_as_mofile(self.mopath)
        test_percentage(self.mopath)

    def test_not_ok(self):
        # 0%
        pofile = polib.POFile()
        pofile.append(polib.POEntry(msgid="test string", msgstr=""))
        pofile.save(self.popath)
        pofile.save_as_mofile(self.mopath)

        self.assertRaises(Warning, test_percentage, self.mopath)

class TestUsability(unittest.TestCase):
    def test_ok(self):
        # what lt's Plural-Forms is supposed to look like
        moobj = polib.MOFile()
        moobj.metadata["Plural-Forms"] = "nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && (n%100<10 || n%100>=20) ? 1 : 2)\n"

        with mofile(moobj) as m:
            test_usability(m.name)

    def test_busted_plural_forms(self):
        # https://bugzilla.redhat.com/show_bug.cgi?id=1283599
        moobj = polib.MOFile()
        moobj.metadata["Plural-Forms"] = "nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && (n%100<10 or n%100>=20) ? 1 : 2)\n"

        with mofile(moobj) as m:
            self.assertRaises(Exception, test_usability, m.name)
