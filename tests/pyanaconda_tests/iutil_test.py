# -*- coding: utf-8 -*-
#
# Copyright (C) 2013  Red Hat, Inc.
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
# Red Hat Author(s): Vratislav Podzimek <vpodzime@redhat.com>
#                    Martin Kolman <mkolman@redhat.com>

from pyanaconda import iutil
import unittest
import os
import tempfile
import signal
import shutil
from test_constants import ANACONDA_TEST_DIR

from timer import timer

class UpcaseFirstLetterTests(unittest.TestCase):

    def setUp(self):
        # create the directory used for file/folder tests
        if not os.path.exists(ANACONDA_TEST_DIR):
            os.makedirs(ANACONDA_TEST_DIR)

    def tearDown(self):
        # remove the testing directory
        shutil.rmtree(ANACONDA_TEST_DIR)

    def upcase_first_letter_test(self):
        """Upcasing first letter should work as expected."""

        # no change
        self.assertEqual(iutil.upcase_first_letter("Czech RePuBliC"),
                         "Czech RePuBliC")

        # simple case
        self.assertEqual(iutil.upcase_first_letter("czech"), "Czech")

        # first letter only
        self.assertEqual(iutil.upcase_first_letter("czech republic"),
                         "Czech republic")

        # no lowercase
        self.assertEqual(iutil.upcase_first_letter("czech Republic"),
                         "Czech Republic")

class RunProgramTests(unittest.TestCase):
    def run_program_test(self):
        """Test the _run_program method."""

        # correct calling should return rc==0
        self.assertEqual(iutil._run_program(['ls'])[0], 0)

        # incorrect calling should return rc!=0
        self.assertNotEqual(iutil._run_program(['ls', '--asdasd'])[0], 0)

        # check if an int is returned for bot success and error
        self.assertIsInstance(iutil._run_program(['ls'])[0], int)
        self.assertIsInstance(iutil._run_program(['ls', '--asdasd'])[0], int)

        # error should raise OSError
        with self.assertRaises(OSError):
            iutil._run_program(['asdasdadasd'])

    def exec_with_redirect_test(self):
        """Test execWithRedirect."""
        # correct calling should return rc==0
        self.assertEqual(iutil.execWithRedirect('ls', []), 0)

        # incorrect calling should return rc!=0
        self.assertNotEqual(iutil.execWithRedirect('ls', ['--asdasd']), 0)

    def exec_with_capture_test(self):
        """Test execWithCapture."""

        # check some output is returned
        self.assertGreater(len(iutil.execWithCapture('ls', ['--help'])), 0)

        # check no output is returned
        self.assertEqual(len(iutil.execWithCapture('true', [])), 0)

    def exec_with_capture_no_stderr_test(self):
        """Test execWithCapture with no stderr"""

        with tempfile.NamedTemporaryFile() as testscript:
            testscript.write("""#!/bin/sh
echo "output"
echo "error" >&2
""")
            testscript.flush()

            # check that only the output is captured
            self.assertEqual(
                    iutil.execWithCapture("/bin/sh", [testscript.name], filter_stderr=True),
                    "output\n")

            # check that both output and error are captured
            self.assertEqual(iutil.execWithCapture("/bin/sh", [testscript.name]),
                    "output\nerror\n")

    def exec_readlines_test(self):
        """Test execReadlines."""

        # test no lines are returned
        self.assertEqual(list(iutil.execReadlines("true", [])), [])

        # test some lines are returned
        self.assertGreater(len(list(iutil.execReadlines("ls", ["--help"]))), 0)

        # check that it always returns an iterator for both
        # if there is some output and if there isn't any
        self.assertTrue(hasattr(iutil.execReadlines("ls", ["--help"]), "__iter__"))
        self.assertTrue(hasattr(iutil.execReadlines("true", []), "__iter__"))

    def exec_readlines_test_normal_output(self):
        """Test the output of execReadlines."""

        # Test regular-looking output
        with tempfile.NamedTemporaryFile() as testscript:
            testscript.write("""#!/bin/sh
echo "one"
echo "two"
echo "three"
exit 0
""")
            testscript.flush()

            with timer(5):
                rl_iterator = iutil.execReadlines("/bin/sh", [testscript.name])
                self.assertEqual(rl_iterator.next(), "one")
                self.assertEqual(rl_iterator.next(), "two")
                self.assertEqual(rl_iterator.next(), "three")
                self.assertRaises(StopIteration, rl_iterator.next)

        # Test output with no end of line
        with tempfile.NamedTemporaryFile() as testscript:
            testscript.write("""#!/bin/sh
echo "one"
echo "two"
echo -n "three"
exit 0
""")
            testscript.flush()

            with timer(5):
                rl_iterator = iutil.execReadlines("/bin/sh", [testscript.name])
                self.assertEqual(rl_iterator.next(), "one")
                self.assertEqual(rl_iterator.next(), "two")
                self.assertEqual(rl_iterator.next(), "three")
                self.assertRaises(StopIteration, rl_iterator.next)

    def exec_readlines_test_exits(self):
        """Test execReadlines in different child exit situations."""

        # Tests that exit on signal will raise OSError once output
        # has been consumed, otherwise the test will exit normally.

        # Test a normal, non-0 exit
        with tempfile.NamedTemporaryFile() as testscript:
            testscript.write("""#!/bin/sh
echo "one"
echo "two"
echo "three"
exit 1
""")
            testscript.flush()

            with timer(5):
                rl_iterator = iutil.execReadlines("/bin/sh", [testscript.name])
                self.assertEqual(rl_iterator.next(), "one")
                self.assertEqual(rl_iterator.next(), "two")
                self.assertEqual(rl_iterator.next(), "three")
                self.assertRaises(OSError, rl_iterator.next)

        # Test exit on signal
        with tempfile.NamedTemporaryFile() as testscript:
            testscript.write("""#!/bin/sh
echo "one"
echo "two"
echo "three"
kill -TERM $$
""")
            testscript.flush()

            with timer(5):
                rl_iterator = iutil.execReadlines("/bin/sh", [testscript.name])
                self.assertEqual(rl_iterator.next(), "one")
                self.assertEqual(rl_iterator.next(), "two")
                self.assertEqual(rl_iterator.next(), "three")
                self.assertRaises(OSError, rl_iterator.next)

        # Repeat the above two tests, but exit before a final newline
        with tempfile.NamedTemporaryFile() as testscript:
            testscript.write("""#!/bin/sh
echo "one"
echo "two"
echo -n "three"
exit 1
""")
            testscript.flush()

            with timer(5):
                rl_iterator = iutil.execReadlines("/bin/sh", [testscript.name])
                self.assertEqual(rl_iterator.next(), "one")
                self.assertEqual(rl_iterator.next(), "two")
                self.assertEqual(rl_iterator.next(), "three")
                self.assertRaises(OSError, rl_iterator.next)

        with tempfile.NamedTemporaryFile() as testscript:
            testscript.write("""#!/bin/sh
echo "one"
echo "two"
echo -n "three"
kill -TERM $$
""")
            testscript.flush()

            with timer(5):
                rl_iterator = iutil.execReadlines("/bin/sh", [testscript.name])
                self.assertEqual(rl_iterator.next(), "one")
                self.assertEqual(rl_iterator.next(), "two")
                self.assertEqual(rl_iterator.next(), "three")
                self.assertRaises(OSError, rl_iterator.next)

    def exec_readlines_test_signals(self):
        """Test execReadlines and signal receipt."""

        # ignored signal
        old_HUP_handler = signal.signal(signal.SIGHUP, signal.SIG_IGN)
        try:
            with tempfile.NamedTemporaryFile() as testscript:
                testscript.write("""#!/bin/sh
echo "one"
kill -HUP $PPID
echo "two"
echo -n "three"
exit 0
""")
                testscript.flush()

                with timer(5):
                    rl_iterator = iutil.execReadlines("/bin/sh", [testscript.name])
                    self.assertEqual(rl_iterator.next(), "one")
                    self.assertEqual(rl_iterator.next(), "two")
                    self.assertEqual(rl_iterator.next(), "three")
                    self.assertRaises(StopIteration, rl_iterator.next)
        finally:
            signal.signal(signal.SIGHUP, old_HUP_handler)

        # caught signal
        def _hup_handler(signum, frame):
            pass
        old_HUP_handler = signal.signal(signal.SIGHUP, _hup_handler)
        try:
            with tempfile.NamedTemporaryFile() as testscript:
                testscript.write("""#!/bin/sh
echo "one"
kill -HUP $PPID
echo "two"
echo -n "three"
exit 0
""")
                testscript.flush()

                with timer(5):
                    rl_iterator = iutil.execReadlines("/bin/sh", [testscript.name])
                    self.assertEqual(rl_iterator.next(), "one")
                    self.assertEqual(rl_iterator.next(), "two")
                    self.assertEqual(rl_iterator.next(), "three")
                    self.assertRaises(StopIteration, rl_iterator.next)
        finally:
            signal.signal(signal.SIGHUP, old_HUP_handler)

    def start_program_preexec_fn_test(self):
        """Test passing preexec_fn to startProgram."""

        marker_text = "yo wassup man"
        # Create a temporary file that will be written before exec
        with tempfile.NamedTemporaryFile() as testfile:

            # Write something to testfile to show this method was run
            def preexec():
                # Open a copy of the file here since close_fds has already closed the descriptor
                testcopy = open(testfile.name, 'w')
                testcopy.write(marker_text)
                testcopy.close()

            with timer(5):
                # Start a program that does nothing, with a preexec_fn
                proc = iutil.startProgram(["/bin/true"], preexec_fn=preexec)
                proc.communicate()

            # Rewind testfile and look for the text
            testfile.seek(0, os.SEEK_SET)
            self.assertEqual(testfile.read(), marker_text)

    def start_program_stdout_test(self):
        """Test redirecting stdout with startProgram."""

        marker_text = "yo wassup man"
        # Create a temporary file that will be written by the program
        with tempfile.NamedTemporaryFile() as testfile:
            # Open a new copy of the file so that the child doesn't close and
            # delete the NamedTemporaryFile
            stdout = open(testfile.name, 'w')
            with timer(5):
                proc = iutil.startProgram(["/bin/echo", marker_text], stdout=stdout)
                proc.communicate()

            # Rewind testfile and look for the text
            testfile.seek(0, os.SEEK_SET)
            self.assertEqual(testfile.read().strip(), marker_text)

    def start_program_reset_handlers_test(self):
        """Test the reset_handlers parameter of startProgram."""

        with tempfile.NamedTemporaryFile() as testscript:
            testscript.write("""#!/bin/sh
# Just hang out and do nothing, forever
while true ; do sleep 1 ; done
""")
            testscript.flush()

            # Start a program with reset_handlers
            proc = iutil.startProgram(["/bin/sh", testscript.name])

            with timer(5):
                # Kill with SIGPIPE and check that the python's SIG_IGN was not inheritted
                # The process should die on the signal.
                proc.send_signal(signal.SIGPIPE)
                proc.communicate()
                self.assertEqual(proc.returncode, -(signal.SIGPIPE))

            # Start another copy without reset_handlers
            proc = iutil.startProgram(["/bin/sh", testscript.name], reset_handlers=False)

            with timer(5):
                # Kill with SIGPIPE, then SIGTERM, and make sure SIGTERM was the one
                # that worked.
                proc.send_signal(signal.SIGPIPE)
                proc.terminate()
                proc.communicate()
                self.assertEqual(proc.returncode, -(signal.SIGTERM))

    def exec_readlines_auto_kill_test(self):
        """Test execReadlines with reading only part of the output"""

        with tempfile.NamedTemporaryFile() as testscript:
            testscript.write("""#!/bin/sh
# Output forever
while true; do
echo hey
done
""")
            testscript.flush()

            with timer(5):
                rl_iterator = iutil.execReadlines("/bin/sh", [testscript.name])

                # Save the process context
                proc = rl_iterator._proc

                # Read two lines worth
                self.assertEqual(rl_iterator.next(), "hey")
                self.assertEqual(rl_iterator.next(), "hey")

                # Delete the iterator and wait for the process to be killed
                del rl_iterator
                proc.communicate()

            # Check that the process is gone
            self.assertIsNotNone(proc.poll())

    def watch_process_test(self):
        """Test watchProcess"""

        def test_still_running():
            with timer(5):
                # Run something forever so we can kill it
                proc = iutil.startProgram(["/bin/sh", "-c", "while true; do sleep 1; done"])
                iutil.watchProcess(proc, "test1")
                proc.kill()
                # Wait for the SIGCHLD
                signal.pause()
        self.assertRaises(iutil.ExitError, test_still_running)

        # Make sure watchProcess checks that the process has not already exited
        with timer(5):
            proc = iutil.startProgram(["true"])
            proc.communicate()
        self.assertRaises(iutil.ExitError, iutil.watchProcess, proc, "test2")

class MiscTests(unittest.TestCase):
    def get_dir_size_test(self):
        """Test the getDirSize."""

        # dev null should have a size == 0
        self.assertEqual(iutil.getDirSize('/dev/null'), 0)

        # incorrect path should also return 0
        self.assertEqual(iutil.getDirSize('/dev/null/foo'), 0)

        # check if an int is always returned
        self.assertIsInstance(iutil.getDirSize('/dev/null'), int)
        self.assertIsInstance(iutil.getDirSize('/dev/null/foo'), int)

        # TODO: mock some dirs and check if their size is
        # computed correctly

    def mkdir_chain_test(self):
        """Test mkdirChain."""

        # don't fail if directory path already exists
        iutil.mkdirChain('/dev/null')
        iutil.mkdirChain('/')
        iutil.mkdirChain('/tmp')

        # create a path and test it exists
        test_folder = "test_mkdir_chain"
        test_paths = [
            "foo",
            "foo/bar/baz",
            u"foo/bar/baz",
            "",
            "čřščščřščř",
            u"čřščščřščř",
            "asdasd asdasd",
            "! spam"
        ]

        # join with the toplevel test folder and the folder for this
        # test
        test_paths = [os.path.join(ANACONDA_TEST_DIR, test_folder, p)
                      for p in test_paths]

        def create_return(path):
            iutil.mkdirChain(path)
            return path

        # create the folders and check that they exist
        for p in test_paths:
            self.assertTrue(os.path.exists(create_return(p)))

        # try to create them again - all the paths should already exist
        # and the mkdirChain function needs to handle that
        # without a traceback
        for p in test_paths:
            iutil.mkdirChain(p)

    def get_active_console_test(self):
        """Test get_active_console."""

        # at least check if a string is returned
        self.assertIsInstance(iutil.get_active_console(), str)

    def is_console_on_vt_test(self):
        """Test isConsoleOnVirtualTerminal."""

        # at least check if a bool is returned
        self.assertIsInstance(iutil.isConsoleOnVirtualTerminal(), bool)

    def parse_nfs_url_test(self):
        """Test parseNfsUrl."""

        # empty NFS url should return 3 blanks
        self.assertEqual(iutil.parseNfsUrl(""), ("", "", ""))

        # the string is delimited by :, there is one prefix and 3 parts,
        # the prefix is discarded and all parts after the 3th part
        # are also discarded
        self.assertEqual(iutil.parseNfsUrl("discard:options:host:path"),
                         ("options", "host", "path"))
        self.assertEqual(iutil.parseNfsUrl("discard:options:host:path:foo:bar"),
                         ("options", "host", "path"))
        self.assertEqual(iutil.parseNfsUrl(":options:host:path::"),
                         ("options", "host", "path"))
        self.assertEqual(iutil.parseNfsUrl(":::::"),
                         ("", "", ""))

        # if there is only prefix & 2 parts,
        # the two parts are host and path
        self.assertEqual(iutil.parseNfsUrl("prefix:host:path"),
                         ("", "host", "path"))
        self.assertEqual(iutil.parseNfsUrl(":host:path"),
                         ("", "host", "path"))
        self.assertEqual(iutil.parseNfsUrl("::"),
                         ("", "", ""))

        # if there is only a prefix and single part,
        # the part is the host

        self.assertEqual(iutil.parseNfsUrl("prefix:host"),
                         ("", "host", ""))
        self.assertEqual(iutil.parseNfsUrl(":host"),
                         ("", "host", ""))
        self.assertEqual(iutil.parseNfsUrl(":"),
                         ("", "", ""))

    def vt_activate_test(self):
        """Test vtActivate."""

        # pylint: disable=no-member

        def raise_os_error(*args, **kwargs):
            raise OSError

        _execWithRedirect = iutil.vtActivate.func_globals['execWithRedirect']

        try:
            # chvt does not exist on all platforms
            # and the function needs to correctly survie that
            iutil.vtActivate.func_globals['execWithRedirect'] = raise_os_error

            self.assertEqual(iutil.vtActivate(2), False)
        finally:
            iutil.vtActivate.func_globals['execWithRedirect'] = _execWithRedirect

    def get_deep_attr_test(self):
        """Test getdeepattr."""

        # pylint: disable=attribute-defined-outside-init

        class O(object):
            pass

        a = O()
        a.b = O()
        a.b1 = 1
        a.b.c = 2
        a.b.c1 = "ř"

        self.assertEqual(iutil.getdeepattr(a, "b1"), 1)
        self.assertEqual(iutil.getdeepattr(a, "b.c"), 2)
        self.assertEqual(iutil.getdeepattr(a, "b.c1"), "ř")

        # be consistent with getattr and throw
        # AttributeError if non-existent attribute is requested
        with self.assertRaises(AttributeError):
            iutil.getdeepattr(a, "")
        with self.assertRaises(AttributeError):
            iutil.getdeepattr(a, "b.c.d")

    def set_deep_attr_test(self):
        """Test setdeepattr."""

        # pylint: disable=attribute-defined-outside-init
        # pylint: disable=no-member

        class O(object):
            pass

        a = O()
        a.b = O()
        a.b1 = 1
        a.b.c = O()
        a.b.c1 = "ř"

        # set to a new attribute
        iutil.setdeepattr(a, "b.c.d", True)
        self.assertEqual(a.b.c.d, True)

        # override existing attribute
        iutil.setdeepattr(a, "b.c", 1234)
        self.assertEqual(a.b.c, 1234)

        # "" is actually a valid attribute name
        # that can be only accessed by getattr
        iutil.setdeepattr(a, "", 1234)
        self.assertEqual(getattr(a, ""), 1234)

        iutil.setdeepattr(a, "b.", 123)
        self.assertEqual(iutil.getdeepattr(a, "b."), 123)

        # error should raise AttributeError
        with self.assertRaises(AttributeError):
            iutil.setdeepattr(a, "b.c.d.e.f.g.h", 1234)

    def strip_accents_test(self):
        """Test strip_accents."""

        # string needs to be Unicode,
        # otherwise TypeError is raised
        with self.assertRaises(TypeError):
            iutil.strip_accents("")
        with self.assertRaises(TypeError):
            iutil.strip_accents("abc")
        with self.assertRaises(TypeError):
            iutil.strip_accents("ěščřžýáíé")

        # empty Unicode string
        self.assertEquals(iutil.strip_accents(u""), u"")

        # some Czech accents
        self.assertEquals(iutil.strip_accents(u"ěščřžýáíéúů"), u"escrzyaieuu")
        self.assertEquals(iutil.strip_accents(u"v češtině"), u"v cestine")
        self.assertEquals(iutil.strip_accents(u"měšťánek rozšíří HÁČKY"),
                                              u"mestanek rozsiri HACKY")
        self.assertEquals(iutil.strip_accents(u"nejneobhospodařovávatelnějšímu"),
                                              u"nejneobhospodarovavatelnejsimu")

        # some German umlauts
        self.assertEquals(iutil.strip_accents(u"Lärmüberhörer"), u"Larmuberhorer")
        self.assertEquals(iutil.strip_accents(u"Heizölrückstoßabdämpfung"),
                                              u"Heizolrucksto\xdfabdampfung")

        # some Japanese
        self.assertEquals(iutil.strip_accents(u"日本語"), u"\u65e5\u672c\u8a9e")
        self.assertEquals(iutil.strip_accents(u"アナコンダ"),  # Anaconda
                          u"\u30a2\u30ca\u30b3\u30f3\u30bf")

        # combined
        input_string = u"ASCI měšťánek アナコンダ Heizölrückstoßabdämpfung"
        output_string =u"ASCI mestanek \u30a2\u30ca\u30b3\u30f3\u30bf Heizolrucksto\xdfabdampfung"
        self.assertEquals(iutil.strip_accents(input_string), output_string)

    def cmp_obj_attrs_test(self):
        """Test cmp_obj_attrs."""

        # pylint: disable=attribute-defined-outside-init

        class O(object):
            pass

        a = O()
        a.b = 1
        a.c = 2

        a1 = O()
        a1.b = 1
        a1.c = 2

        b = O()
        b.b = 1
        b.c = 3

        # a class should have it's own attributes
        self.assertTrue(iutil.cmp_obj_attrs(a, a, ["b", "c"]))
        self.assertTrue(iutil.cmp_obj_attrs(a1, a1, ["b", "c"]))
        self.assertTrue(iutil.cmp_obj_attrs(b, b, ["b", "c"]))

        # a and a1 should have the same attributes
        self.assertTrue(iutil.cmp_obj_attrs(a, a1, ["b", "c"]))
        self.assertTrue(iutil.cmp_obj_attrs(a1, a, ["b", "c"]))
        self.assertTrue(iutil.cmp_obj_attrs(a1, a, ["c", "b"]))

        # missing attributes are considered a mismatch
        self.assertFalse(iutil.cmp_obj_attrs(a, a1, ["b", "c", "d"]))

        # empty attribute list is not a mismatch
        self.assertTrue(iutil.cmp_obj_attrs(a, b, []))

        # attributes of a and b differ
        self.assertFalse(iutil.cmp_obj_attrs(a, b, ["b", "c"]))
        self.assertFalse(iutil.cmp_obj_attrs(b, a, ["b", "c"]))
        self.assertFalse(iutil.cmp_obj_attrs(b, a, ["c", "b"]))

    def to_ascii_test(self):
        """Test _toASCII."""

        # works with strings only, chokes on Unicode strings
        with self.assertRaises(ValueError):
            iutil._toASCII(u" ")
        with self.assertRaises(ValueError):
            iutil._toASCII(u"ABC")
        with self.assertRaises(ValueError):
            iutil._toASCII(u"Heizölrückstoßabdämpfung")

        # but empty Unicode string is fine :)
        iutil._toASCII(u"")

        # check some conversions
        self.assertEqual(iutil._toASCII(""), "")
        self.assertEqual(iutil._toASCII(" "), " ")
        self.assertEqual(iutil._toASCII("&@`'łŁ!@#$%^&*{}[]$'<>*"),
                                        "&@`'\xc5\x82\xc5\x81!@#$%^&*{}[]$'<>*")
        self.assertEqual(iutil._toASCII("ABC"), "ABC")
        self.assertEqual(iutil._toASCII("aBC"), "aBC")
        _out = "Heiz\xc3\xb6lr\xc3\xbccksto\xc3\x9fabd\xc3\xa4mpfung" 
        self.assertEqual(iutil._toASCII("Heizölrückstoßabdämpfung"), _out)

    def upper_ascii_test(self):
        """Test upperASCII."""

        self.assertEqual(iutil.upperASCII(""),"")
        self.assertEqual(iutil.upperASCII("a"),"A")
        self.assertEqual(iutil.upperASCII("A"),"A")
        self.assertEqual(iutil.upperASCII("aBc"),"ABC")
        self.assertEqual(iutil.upperASCII("_&*'@#$%^aBcžčŘ"),
                                          "_&*'@#$%^ABC\xc5\xbe\xc4\x8d\xc5\x98")
        _out = "HEIZ\xc3\xb6LR\xc3\xbcCKSTO\xc3\x9fABD\xc3\xa4MPFUNG"
        self.assertEqual(iutil.upperASCII("Heizölrückstoßabdämpfung"), _out)


    def lower_ascii_test(self):
        """Test lowerASCII."""
        self.assertEqual(iutil.lowerASCII(""),"")
        self.assertEqual(iutil.lowerASCII("A"),"a")
        self.assertEqual(iutil.lowerASCII("a"),"a")
        self.assertEqual(iutil.lowerASCII("aBc"),"abc")
        self.assertEqual(iutil.lowerASCII("_&*'@#$%^aBcžčŘ"),
                                          "_&*'@#$%^abc\xc5\xbe\xc4\x8d\xc5\x98")
        _out = "heiz\xc3\xb6lr\xc3\xbccksto\xc3\x9fabd\xc3\xa4mpfung"
        self.assertEqual(iutil.lowerASCII("Heizölrückstoßabdämpfung"), _out)

    def have_word_match_test(self):
        """Test have_word_match."""

        self.assertTrue(iutil.have_word_match("word1 word2", "word1 word2 word3"))
        self.assertTrue(iutil.have_word_match("word1 word2", "word2 word1 word3"))
        self.assertTrue(iutil.have_word_match("word2 word1", "word3 word1 word2"))
        self.assertTrue(iutil.have_word_match("word1", "word1 word2"))
        self.assertTrue(iutil.have_word_match("word1 word2", "word2word1 word3"))
        self.assertTrue(iutil.have_word_match("word2 word1", "word3 word1word2"))
        self.assertTrue(iutil.have_word_match("word1", "word1word2"))
        self.assertTrue(iutil.have_word_match("", "word1"))

        self.assertFalse(iutil.have_word_match("word3 word1", "word1"))
        self.assertFalse(iutil.have_word_match("word1 word3", "word1 word2"))
        self.assertFalse(iutil.have_word_match("word3 word2", "word1 word2"))
        self.assertFalse(iutil.have_word_match("word1word2", "word1 word2 word3"))
        self.assertFalse(iutil.have_word_match("word1", ""))
        self.assertFalse(iutil.have_word_match("word1", None))
        self.assertFalse(iutil.have_word_match(None, "word1"))
        self.assertFalse(iutil.have_word_match("", None))
        self.assertFalse(iutil.have_word_match(None, ""))
        self.assertFalse(iutil.have_word_match(None, None))

        # Compare unicode and str and make sure nothing crashes
        self.assertTrue(iutil.have_word_match("fête", u"fête champêtre"))
        self.assertTrue(iutil.have_word_match(u"fête", "fête champêtre"))

    def parent_dir_test(self):
        """Test the parent_dir function"""
        dirs = [("", ""), ("/", ""), ("/home/", ""), ("/home/bcl", "/home"), ("home/bcl", "home"),
                ("/home/bcl/", "/home"), ("/home/extra/bcl", "/home/extra"),
                ("/home/extra/bcl/", "/home/extra"), ("/home/extra/../bcl/", "/home")]

        for d, r in dirs:
            self.assertEquals(iutil.parent_dir(d), r)
