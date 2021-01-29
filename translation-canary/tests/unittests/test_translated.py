# Copyright (C) 2015  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU Lesser General Public License v.2, or (at your option) any later
# version. This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY expressed or implied, including the implied
# warranties of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See
# the GNU Lesser General Public License for more details.  You should have
# received a copy of the GNU Lesser General Public License along with this
# program; if not, write to the Free Software Foundation, Inc., 51 Franklin
# Street, Fifth Floor, Boston, MA 02110-1301, USA.  Any Red Hat trademarks
# that are incorporated in the source code or documentation are not subject
# to the GNU Lesser General Public License and may only be used or
# replicated with the express permission of Red Hat, Inc.
#
# Red Hat Author(s): David Shea <dshea@redhat.com>

import unittest
import unittest.mock
import tempfile
import warnings
import polib
import os

from translation_canary.translated.test_markup import test_markup
from translation_canary.translated.test_percentage import test_percentage
from translation_canary.translated.test_usability import test_usability, test_msgfmt

from translation_canary.translated import testFile, testSourceTree

# convert a polib.POFile into a NamedTemporaryFile
def pofile(poobj):
    f = tempfile.NamedTemporaryFile(suffix='.po')
    poobj.save(f.name)
    return f

# convenience function for creating a single-entry mofile
def pofile_from_entry(*args, **kwargs):
    poobj = polib.POFile()
    poobj.metadata["Content-Type"] = "text/plain; charset=UTF-8"
    poobj.append(polib.POEntry(*args, **kwargs))
    return pofile(poobj)

class TestMarkup(unittest.TestCase):
    # I know, pylint, that's the point
    # pylint: disable=invalid-markup

    def test_ok(self):
        # no markup
        with pofile_from_entry(msgid="test string", msgstr="estay ingstray") as p:
            test_markup(p.name)

        # matching markup
        with pofile_from_entry(msgid="<b>bold</b> string", msgstr="<b>oldbay</b> ingstray") as p:
            test_markup(p.name)

        # matching plural
        with pofile_from_entry(msgid="%d <b>bold</b> string", msgid_plural="%d <b>bold</b> strings",
                msgstr_plural={0: "%d <b>oldbay</b> ingstray", 1: "%d <b>oldbay</b> instrays"}) as p:
            test_markup(p.name)

    def test_missing(self):
        with pofile_from_entry(msgid="<b>bold</b> string", msgstr="oldbay ingstray") as p:
            self.assertRaises(AssertionError, test_markup, p.name)

    def test_mismatch(self):
        with pofile_from_entry(msgid="<b>bold</b> string", msgstr="<i>oldbay</i> ingstray") as p:
            self.assertRaises(AssertionError, test_markup, p.name)

    def test_typo(self):
        with pofile_from_entry(msgid="<b>bold</b> string", msgstr="<boldbay</b> ingstray") as p:
            self.assertRaises(AssertionError, test_markup, p.name)

    def test_mismatch_plural(self):
        with pofile_from_entry(msgid="%d <b>bold</b> string", msgid_plural="%d <b>bold</b> strings",
                msgstr_plural={0: "%d <b>olbday</b> ingstray", 1: "%d oldbay ingstrays"}) as p:
            self.assertRaises(AssertionError, test_markup, p.name)

    def test_invalid(self):
        # Tags themselves are valid, but the XML is not
        with pofile_from_entry(msgid="<b>bold</b> string", msgstr="<b/>oldbay</b> ingstray") as p:
            self.assertRaises(AssertionError, test_markup, p.name)

class TestPercentage(unittest.TestCase):
    def setUp(self):
        # Convert warnings into exceptions to make them easier to test for
        warnings.simplefilter("error")
        # polib throws a DeprecationWarnings so ignore that
        warnings.simplefilter("default", DeprecationWarning)

    def tearDown(self):
        warnings.resetwarnings()

    def test_ok(self):
        # 100%
        with pofile_from_entry(msgid="test string", msgstr="estay ingstray") as p:
            test_percentage(p.name)

    def test_not_ok(self):
        # 0%
        with pofile_from_entry(msgid="test string", msgstr="") as p:
            self.assertRaises(Warning, test_percentage, p.name)

class TestUsability(unittest.TestCase):
    def test_ok(self):
        # what lt's Plural-Forms is supposed to look like
        poobj = polib.POFile()
        poobj.metadata["Plural-Forms"] = "nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && (n%100<10 || n%100>=20) ? 1 : 2)\n"

        with pofile(poobj) as p:
            test_usability(p.name)

    def test_busted_plural_forms(self):
        # https://bugzilla.redhat.com/show_bug.cgi?id=1283599
        poobj = polib.POFile()
        poobj.metadata["Plural-Forms"] = "nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && (n%100<10 or n%100>=20) ? 1 : 2)\n"

        with pofile(poobj) as p:
            self.assertRaises(Exception, test_usability, p.name)

class TestMsgFmt(unittest.TestCase):
    def test_ok(self):
        with pofile_from_entry(msgid="test string", msgstr="estay ingstray") as p:
            test_msgfmt(p.name)

    # Test a few cases that msgfmt will catch
    def test_busted_newlines(self):
        with pofile_from_entry(msgid="multi\nline\nstring", msgstr="ultimay\ninelay\ningstray\n") as p:
            self.assertRaises(AssertionError, test_msgfmt, p.name)

    def test_busted_format(self):
        with pofile_from_entry(msgid="test %(type)s", msgstr="estay", flags=["python-format"]) as p:
            self.assertRaises(AssertionError, test_msgfmt, p.name)

    def test_translated_format(self):
        with pofile_from_entry(msgid="test %(type)s", msgstr="estay %(ypetay)", flags=["python-format"]) as p:
            self.assertRaises(AssertionError, test_msgfmt, p.name)

# Test the top-level functions
# fake tests for testing with
def _true_test(_p):
    pass

def _false_test(_p):
    raise AssertionError("no good")

def _picky_test(p):
    if os.path.basename(p).startswith("p"):
        raise AssertionError("I don't like this one")

class TestTestFile(unittest.TestCase):
    @unittest.mock.patch("translation_canary.translated._tests", [_true_test])
    def test_success(self):
        with pofile_from_entry() as p:
            self.assertTrue(testFile(p.name))

    @unittest.mock.patch("translation_canary.translated._tests", [_false_test])
    def test_failure(self):
        with pofile_from_entry() as p:
            self.assertFalse(testFile(p.name))

    @unittest.mock.patch("translation_canary.translated._tests", [_true_test])
    def test_release_mode_success(self):
        with pofile_from_entry() as p:
            self.assertTrue(testFile(p.name, releaseMode=True))
            self.assertTrue(os.path.exists(p.name))

    @unittest.mock.patch("translation_canary.translated._tests", [_false_test])
    def test_release_mode_failure(self):
        p = tempfile.NamedTemporaryFile(suffix='.po', delete=False)
        try:
            # testFile should return True but delete the file
            self.assertTrue(testFile(p.name, releaseMode=True))
            self.assertFalse(os.path.exists(p.name))
        finally:
            try:
                p.close()
                os.unlink(p.name)
            except FileNotFoundError:
                pass

    @unittest.mock.patch("translation_canary.translated._tests", [_false_test])
    def test_release_mode_failure_with_lingua(self):
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, "test.po"), "w").close()
            with open(os.path.join(d, "LINGUAS"), "w") as linguas:
                linguas.write("test other\n")

            # Check that test.po is removed and test is removed from LINGUAS
            self.assertTrue(testFile(os.path.join(d, "test.po"), releaseMode=True))
            self.assertFalse(os.path.exists(os.path.join(d, "test.po")))

            with open(os.path.join(d, "LINGUAS"), "r")  as linguas:
                self.assertEqual(linguas.read().strip(), "other")

    @unittest.mock.patch("translation_canary.translated._tests", [_false_test])
    def test_release_mode_failure_with_lingua_no_modify(self):
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, "test.po"), "w").close()
            with open(os.path.join(d, "LINGUAS"), "w") as linguas:
                linguas.write("test other\n")

            # Check that test.po is removed and test is *not* removed from LINGUAS
            self.assertTrue(testFile(os.path.join(d, "test.po"), releaseMode=True, modifyLinguas=False))
            self.assertFalse(os.path.exists(os.path.join(d, "test.po")))

            with open(os.path.join(d, "LINGUAS"), "r") as linguas:
                self.assertEqual(linguas.read().strip(), "test other")

@unittest.mock.patch("translation_canary.translated._tests", [_picky_test])
class TestTestSourceTree(unittest.TestCase):
    def setUp(self):
        self.tmpobj = tempfile.TemporaryDirectory()
        self.tmpdir = self.tmpobj.name

    def tearDown(self):
        self.tmpobj.cleanup()

    def test_success(self):
        open(os.path.join(self.tmpdir, "aa.po"), "w").close()
        open(os.path.join(self.tmpdir, "ab.po"), "w").close()
        self.assertTrue(testSourceTree(self.tmpdir))

    def test_some_failure(self):
        open(os.path.join(self.tmpdir, "aa.po"), "w").close()
        open(os.path.join(self.tmpdir, "pa.po"), "w").close()
        self.assertFalse(testSourceTree(self.tmpdir))

    def test_all_failure(self):
        open(os.path.join(self.tmpdir, "pa.po"), "w").close()
        open(os.path.join(self.tmpdir, "pb.po"), "w").close()
        self.assertFalse(testSourceTree(self.tmpdir))

    def test_release_mode_success(self):
        open(os.path.join(self.tmpdir, "aa.po"), "w").close()
        open(os.path.join(self.tmpdir, "ab.po"), "w").close()
        self.assertTrue(testSourceTree(self.tmpdir, releaseMode=True))

    def test_release_mode_failure(self):
        open(os.path.join(self.tmpdir, "aa.po"), "w").close()
        open(os.path.join(self.tmpdir, "pa.po"), "w").close()
        self.assertTrue(testSourceTree(self.tmpdir, releaseMode=True))
        self.assertTrue(os.path.exists(os.path.join(self.tmpdir, "aa.po")))
        self.assertFalse(os.path.exists(os.path.join(self.tmpdir, "pa.po")))

    def test_release_mode_failure_with_lingua(self):
        open(os.path.join(self.tmpdir, "aa.po"), "w").close()
        open(os.path.join(self.tmpdir, "pa.po"), "w").close()
        with open(os.path.join(self.tmpdir, "LINGUAS"), "w") as l:
            l.write("aa pa\n")

        self.assertTrue(testSourceTree(self.tmpdir, releaseMode=True))
        self.assertTrue(os.path.exists(os.path.join(self.tmpdir, "aa.po")))
        self.assertFalse(os.path.exists(os.path.join(self.tmpdir, "pa.po")))

        with open(os.path.join(self.tmpdir, "LINGUAS")) as l:
            self.assertEqual(l.read().strip(), "aa")

    def test_release_mode_failure_with_lingua_no_modify(self):
        open(os.path.join(self.tmpdir, "aa.po"), "w").close()
        open(os.path.join(self.tmpdir, "pa.po"), "w").close()

        with open(os.path.join(self.tmpdir, "LINGUAS"), "w") as l:
            l.write("aa pa\n")

        self.assertTrue(testSourceTree(self.tmpdir, releaseMode=True, modifyLinguas=False))
        self.assertTrue(os.path.exists(os.path.join(self.tmpdir, "aa.po")))
        self.assertFalse(os.path.exists(os.path.join(self.tmpdir, "pa.po")))

        with open(os.path.join(self.tmpdir, "LINGUAS")) as l:
            self.assertEqual(l.read().strip(), "aa pa")
