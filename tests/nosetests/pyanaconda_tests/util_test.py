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

import unittest
import os
import tempfile
import signal
import shutil
from threading import Lock

import sys
from unittest.mock import Mock, patch

from pyanaconda.errors import ExitError
from pyanaconda.core.process_watchers import WatchProcesses
from pyanaconda.core import util
from pyanaconda.core.util import synchronized, LazyObject
from pyanaconda.core.configuration.anaconda import conf

from timer import timer

ANACONDA_TEST_DIR = '/tmp/anaconda_tests_dir'


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
        self.assertEqual(util.upcase_first_letter("Czech RePuBliC"),
                         "Czech RePuBliC")

        # simple case
        self.assertEqual(util.upcase_first_letter("czech"), "Czech")

        # first letter only
        self.assertEqual(util.upcase_first_letter("czech republic"),
                         "Czech republic")

        # no lowercase
        self.assertEqual(util.upcase_first_letter("czech Republic"),
                         "Czech Republic")


class RunSystemctlTests(unittest.TestCase):

    def is_service_installed_test(self):
        """Test the is_service_installed function."""
        with patch('pyanaconda.core.util.execWithCapture') as execute:
            execute.return_value = "fake.service enabled enabled"
            self.assertEqual(util.is_service_installed("fake"), True)
            execute.assert_called_once_with("systemctl", [
                "list-unit-files", "fake.service", "--no-legend", "--root", "/mnt/sysroot"
            ])

        with patch('pyanaconda.core.util.execWithCapture') as execute:
            execute.return_value = "fake.service enabled enabled"
            self.assertEqual(util.is_service_installed("fake.service", root="/"), True)
            execute.assert_called_once_with("systemctl", [
                "list-unit-files", "fake.service", "--no-legend"
            ])

        with patch('pyanaconda.core.util.execWithCapture') as execute:
            execute.return_value = ""
            self.assertEqual(util.is_service_installed("fake", root="/"), False)
            execute.assert_called_once_with("systemctl", [
                "list-unit-files", "fake.service", "--no-legend"
            ])


class RunProgramTests(unittest.TestCase):
    def run_program_test(self):
        """Test the _run_program method."""

        # correct calling should return rc==0
        self.assertEqual(util._run_program(['ls'])[0], 0)

        # incorrect calling should return rc!=0
        self.assertNotEqual(util._run_program(['ls', '--asdasd'])[0], 0)

        # check if an int is returned for bot success and error
        self.assertIsInstance(util._run_program(['ls'])[0], int)
        self.assertIsInstance(util._run_program(['ls', '--asdasd'])[0], int)

        # error should raise OSError
        with self.assertRaises(OSError):
            util._run_program(['asdasdadasd'])

    def run_program_binary_test(self):
        """Test _run_program with binary output."""

        # Echo something that cannot be decoded as utf-8
        retcode, output = util._run_program(['echo', '-en', r'\xa0\xa1\xa2'], binary_output=True)

        self.assertEqual(retcode, 0)
        self.assertEqual(output, b'\xa0\xa1\xa2')

    def exec_with_redirect_test(self):
        """Test execWithRedirect."""
        # correct calling should return rc==0
        self.assertEqual(util.execWithRedirect('ls', []), 0)

        # incorrect calling should return rc!=0
        self.assertNotEqual(util.execWithRedirect('ls', ['--asdasd']), 0)

    def exec_with_capture_test(self):
        """Test execWithCapture."""

        # check some output is returned
        self.assertGreater(len(util.execWithCapture('ls', ['--help'])), 0)

        # check no output is returned
        self.assertEqual(len(util.execWithCapture('true', [])), 0)

    def exec_with_capture_no_stderr_test(self):
        """Test execWithCapture with no stderr"""

        with tempfile.NamedTemporaryFile(mode="w+t") as testscript:
            testscript.write("""#!/bin/sh
echo "output"
echo "error" >&2
""")
            testscript.flush()

            # check that only the output is captured
            self.assertEqual(
                    util.execWithCapture("/bin/sh", [testscript.name], filter_stderr=True),
                    "output\n")

            # check that both output and error are captured
            self.assertEqual(util.execWithCapture("/bin/sh", [testscript.name]), "output\nerror\n")

    def exec_with_capture_empty_test(self):
        """Test execWithCapture with no output"""

        # check that the output is an empty string
        self.assertEqual(util.execWithCapture("/bin/sh", ["-c", "exit 0"]), "")

    def exec_readlines_test(self):
        """Test execReadlines."""

        # test no lines are returned
        self.assertEqual(list(util.execReadlines("true", [])), [])

        # test some lines are returned
        self.assertGreater(len(list(util.execReadlines("ls", ["--help"]))), 0)

        # check that it always returns an iterator for both
        # if there is some output and if there isn't any
        self.assertTrue(hasattr(util.execReadlines("ls", ["--help"]), "__iter__"))
        self.assertTrue(hasattr(util.execReadlines("true", []), "__iter__"))

    def exec_readlines_test_normal_output(self):
        """Test the output of execReadlines."""

        # Test regular-looking output
        with tempfile.NamedTemporaryFile(mode="w+t") as testscript:
            testscript.write("""#!/bin/sh
echo "one"
echo "two"
echo "three"
exit 0
""")
            testscript.flush()

            with timer(5):
                rl_iterator = util.execReadlines("/bin/sh", [testscript.name])
                self.assertEqual(next(rl_iterator), "one")
                self.assertEqual(next(rl_iterator), "two")
                self.assertEqual(next(rl_iterator), "three")
                self.assertRaises(StopIteration, rl_iterator.__next__)

        # Test output with no end of line
        with tempfile.NamedTemporaryFile(mode="w+t") as testscript:
            testscript.write("""#!/bin/sh
echo "one"
echo "two"
echo -n "three"
exit 0
""")
            testscript.flush()

            with timer(5):
                rl_iterator = util.execReadlines("/bin/sh", [testscript.name])
                self.assertEqual(next(rl_iterator), "one")
                self.assertEqual(next(rl_iterator), "two")
                self.assertEqual(next(rl_iterator), "three")
                self.assertRaises(StopIteration, rl_iterator.__next__)

    def exec_readlines_test_exits(self):
        """Test execReadlines in different child exit situations."""

        # Tests that exit on signal will raise OSError once output
        # has been consumed, otherwise the test will exit normally.

        # Test a normal, non-0 exit
        with tempfile.NamedTemporaryFile(mode="wt") as testscript:
            testscript.write("""#!/bin/sh
echo "one"
echo "two"
echo "three"
exit 1
""")
            testscript.flush()

            with timer(5):
                rl_iterator = util.execReadlines("/bin/sh", [testscript.name])
                self.assertEqual(next(rl_iterator), "one")
                self.assertEqual(next(rl_iterator), "two")
                self.assertEqual(next(rl_iterator), "three")
                self.assertRaises(OSError, rl_iterator.__next__)

        # Test exit on signal
        with tempfile.NamedTemporaryFile(mode="wt") as testscript:
            testscript.write("""#!/bin/sh
echo "one"
echo "two"
echo "three"
kill -TERM $$
""")
            testscript.flush()

            with timer(5):
                rl_iterator = util.execReadlines("/bin/sh", [testscript.name])
                self.assertEqual(next(rl_iterator), "one")
                self.assertEqual(next(rl_iterator), "two")
                self.assertEqual(next(rl_iterator), "three")
                self.assertRaises(OSError, rl_iterator.__next__)

        # Repeat the above two tests, but exit before a final newline
        with tempfile.NamedTemporaryFile(mode="wt") as testscript:
            testscript.write("""#!/bin/sh
echo "one"
echo "two"
echo -n "three"
exit 1
""")
            testscript.flush()

            with timer(5):
                rl_iterator = util.execReadlines("/bin/sh", [testscript.name])
                self.assertEqual(next(rl_iterator), "one")
                self.assertEqual(next(rl_iterator), "two")
                self.assertEqual(next(rl_iterator), "three")
                self.assertRaises(OSError, rl_iterator.__next__)

        with tempfile.NamedTemporaryFile(mode="wt") as testscript:
            testscript.write("""#!/bin/sh
echo "one"
echo "two"
echo -n "three"
kill -TERM $$
""")
            testscript.flush()

            with timer(5):
                rl_iterator = util.execReadlines("/bin/sh", [testscript.name])
                self.assertEqual(next(rl_iterator), "one")
                self.assertEqual(next(rl_iterator), "two")
                self.assertEqual(next(rl_iterator), "three")
                self.assertRaises(OSError, rl_iterator.__next__)

    def exec_readlines_test_signals(self):
        """Test execReadlines and signal receipt."""

        # ignored signal
        old_HUP_handler = signal.signal(signal.SIGHUP, signal.SIG_IGN)
        try:
            with tempfile.NamedTemporaryFile(mode="wt") as testscript:
                testscript.write("""#!/bin/sh
echo "one"
kill -HUP $PPID
echo "two"
echo -n "three"
exit 0
""")
                testscript.flush()

                with timer(5):
                    rl_iterator = util.execReadlines("/bin/sh", [testscript.name])
                    self.assertEqual(next(rl_iterator), "one")
                    self.assertEqual(next(rl_iterator), "two")
                    self.assertEqual(next(rl_iterator), "three")
                    self.assertRaises(StopIteration, rl_iterator.__next__)
        finally:
            signal.signal(signal.SIGHUP, old_HUP_handler)

        # caught signal
        def _hup_handler(signum, frame):
            pass
        old_HUP_handler = signal.signal(signal.SIGHUP, _hup_handler)
        try:
            with tempfile.NamedTemporaryFile(mode="wt") as testscript:
                testscript.write("""#!/bin/sh
echo "one"
kill -HUP $PPID
echo "two"
echo -n "three"
exit 0
""")
                testscript.flush()

                with timer(5):
                    rl_iterator = util.execReadlines("/bin/sh", [testscript.name])
                    self.assertEqual(next(rl_iterator), "one")
                    self.assertEqual(next(rl_iterator), "two")
                    self.assertEqual(next(rl_iterator), "three")
                    self.assertRaises(StopIteration, rl_iterator.__next__)
        finally:
            signal.signal(signal.SIGHUP, old_HUP_handler)

    def exec_readlines_test_filter_stderr(self):
        """Test execReadlines and filter_stderr."""

        # Test that stderr is normally included
        with tempfile.NamedTemporaryFile(mode="w+t") as testscript:
            testscript.write("""#!/bin/sh
echo "one"
echo "two" >&2
echo "three"
exit 0
""")
            testscript.flush()

            with timer(5):
                rl_iterator = util.execReadlines("/bin/sh", [testscript.name])
                self.assertEqual(next(rl_iterator), "one")
                self.assertEqual(next(rl_iterator), "two")
                self.assertEqual(next(rl_iterator), "three")
                self.assertRaises(StopIteration, rl_iterator.__next__)

        # Test that filter stderr removes the middle line
        with tempfile.NamedTemporaryFile(mode="w+t") as testscript:
            testscript.write("""#!/bin/sh
echo "one"
echo "two" >&2
echo "three"
exit 0
""")
            testscript.flush()

            with timer(5):
                rl_iterator = util.execReadlines("/bin/sh", [testscript.name], filter_stderr=True)
                self.assertEqual(next(rl_iterator), "one")
                self.assertEqual(next(rl_iterator), "three")
                self.assertRaises(StopIteration, rl_iterator.__next__)

    def start_program_preexec_fn_test(self):
        """Test passing preexec_fn to startProgram."""

        marker_text = "yo wassup man"
        # Create a temporary file that will be written before exec
        with tempfile.NamedTemporaryFile(mode="w+t") as testfile:

            # Write something to testfile to show this method was run
            def preexec():
                # Open a copy of the file here since close_fds has already closed the descriptor
                testcopy = open(testfile.name, 'w')
                testcopy.write(marker_text)
                testcopy.close()

            with timer(5):
                # Start a program that does nothing, with a preexec_fn
                proc = util.startProgram(["/bin/true"], preexec_fn=preexec)
                proc.communicate()

            # Rewind testfile and look for the text
            testfile.seek(0, os.SEEK_SET)
            self.assertEqual(testfile.read(), marker_text)

    def start_program_stdout_test(self):
        """Test redirecting stdout with startProgram."""

        marker_text = "yo wassup man"
        # Create a temporary file that will be written by the program
        with tempfile.NamedTemporaryFile(mode="w+t") as testfile:
            # Open a new copy of the file so that the child doesn't close and
            # delete the NamedTemporaryFile
            stdout = open(testfile.name, 'w')
            with timer(5):
                proc = util.startProgram(["/bin/echo", marker_text], stdout=stdout)
                proc.communicate()

            # Rewind testfile and look for the text
            testfile.seek(0, os.SEEK_SET)
            self.assertEqual(testfile.read().strip(), marker_text)

    def start_program_reset_handlers_test(self):
        """Test the reset_handlers parameter of startProgram."""

        with tempfile.NamedTemporaryFile(mode="w+t") as testscript:
            testscript.write("""#!/bin/sh
# Just hang out and do nothing, forever
while true ; do sleep 1 ; done
""")
            testscript.flush()

            # Start a program with reset_handlers
            proc = util.startProgram(["/bin/sh", testscript.name])

            with timer(5):
                # Kill with SIGPIPE and check that the python's SIG_IGN was not inheritted
                # The process should die on the signal.
                proc.send_signal(signal.SIGPIPE)
                proc.communicate()
                self.assertEqual(proc.returncode, -(signal.SIGPIPE))

            # Start another copy without reset_handlers
            proc = util.startProgram(["/bin/sh", testscript.name], reset_handlers=False)

            with timer(5):
                # Kill with SIGPIPE, then SIGTERM, and make sure SIGTERM was the one
                # that worked.
                proc.send_signal(signal.SIGPIPE)
                proc.terminate()
                proc.communicate()
                self.assertEqual(proc.returncode, -(signal.SIGTERM))

    def exec_readlines_auto_kill_test(self):
        """Test execReadlines with reading only part of the output"""

        with tempfile.NamedTemporaryFile(mode="w+t") as testscript:
            testscript.write("""#!/bin/sh
# Output forever
while true; do
echo hey
done
""")
            testscript.flush()

            with timer(5):
                rl_iterator = util.execReadlines("/bin/sh", [testscript.name])

                # Save the process context
                proc = rl_iterator._proc

                # Read two lines worth
                self.assertEqual(next(rl_iterator), "hey")
                self.assertEqual(next(rl_iterator), "hey")

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
                proc = util.startProgram(["/bin/sh", "-c", "while true; do sleep 1; done"])
                WatchProcesses.watch_process(proc, "test1")
                proc.kill()
                # Wait for the SIGCHLD
                signal.pause()
        self.assertRaises(ExitError, test_still_running)

        # Make sure watchProcess checks that the process has not already exited
        with timer(5):
            proc = util.startProgram(["true"])
            proc.communicate()
        self.assertRaises(ExitError, WatchProcesses.watch_process, proc, "test2")


class MiscTests(unittest.TestCase):

    def mkdir_chain_test(self):
        """Test mkdirChain."""

        # don't fail if directory path already exists
        util.mkdirChain('/')
        util.mkdirChain('/tmp')

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
            util.mkdirChain(path)
            return path

        # create the folders and check that they exist
        for p in test_paths:
            self.assertTrue(os.path.exists(create_return(p)))

        # try to create them again - all the paths should already exist
        # and the mkdirChain function needs to handle that
        # without a traceback
        for p in test_paths:
            util.mkdirChain(p)

    def get_active_console_test(self):
        """Test get_active_console."""

        # at least check if a string is returned
        self.assertIsInstance(util.get_active_console(), str)

    def is_console_on_vt_test(self):
        """Test isConsoleOnVirtualTerminal."""

        # at least check if a bool is returned
        self.assertIsInstance(util.isConsoleOnVirtualTerminal(), bool)

    def vt_activate_test(self):
        """Test vtActivate."""

        # pylint: disable=no-member

        def raise_os_error(*args, **kwargs):
            raise OSError

        _execWithRedirect = util.vtActivate.__globals__['execWithRedirect']

        try:
            # chvt does not exist on all platforms
            # and the function needs to correctly survie that
            util.vtActivate.__globals__['execWithRedirect'] = raise_os_error

            self.assertEqual(util.vtActivate(2), False)
        finally:
            util.vtActivate.__globals__['execWithRedirect'] = _execWithRedirect

    def strip_accents_test(self):
        """Test strip_accents."""

        # empty string
        self.assertEqual(util.strip_accents(u""), u"")
        self.assertEqual(util.strip_accents(""), "")

        # some Czech accents
        self.assertEqual(util.strip_accents(u"ěščřžýáíéúů"), u"escrzyaieuu")
        self.assertEqual(util.strip_accents(u"v češtině"), u"v cestine")
        self.assertEqual(util.strip_accents(u"měšťánek rozšíří HÁČKY"), u"mestanek rozsiri HACKY")
        self.assertEqual(util.strip_accents(u"nejneobhospodařovávatelnějšímu"),
                         u"nejneobhospodarovavatelnejsimu")

        # some German umlauts
        self.assertEqual(util.strip_accents(u"Lärmüberhörer"), u"Larmuberhorer")
        self.assertEqual(util.strip_accents(u"Heizölrückstoßabdämpfung"),
                         u"Heizolrucksto\xdfabdampfung")

        # some Japanese
        self.assertEqual(util.strip_accents(u"日本語"), u"\u65e5\u672c\u8a9e")
        self.assertEqual(util.strip_accents(u"アナコンダ"),  # Anaconda
                         u"\u30a2\u30ca\u30b3\u30f3\u30bf")

        # combined
        input_string = u"ASCI měšťánek アナコンダ Heizölrückstoßabdämpfung"
        output_string = u"ASCI mestanek \u30a2\u30ca\u30b3\u30f3\u30bf Heizolrucksto\xdfabdampfung"
        self.assertEqual(util.strip_accents(input_string), output_string)

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
        self.assertTrue(util.cmp_obj_attrs(a, a, ["b", "c"]))
        self.assertTrue(util.cmp_obj_attrs(a1, a1, ["b", "c"]))
        self.assertTrue(util.cmp_obj_attrs(b, b, ["b", "c"]))

        # a and a1 should have the same attributes
        self.assertTrue(util.cmp_obj_attrs(a, a1, ["b", "c"]))
        self.assertTrue(util.cmp_obj_attrs(a1, a, ["b", "c"]))
        self.assertTrue(util.cmp_obj_attrs(a1, a, ["c", "b"]))

        # missing attributes are considered a mismatch
        self.assertFalse(util.cmp_obj_attrs(a, a1, ["b", "c", "d"]))

        # empty attribute list is not a mismatch
        self.assertTrue(util.cmp_obj_attrs(a, b, []))

        # attributes of a and b differ
        self.assertFalse(util.cmp_obj_attrs(a, b, ["b", "c"]))
        self.assertFalse(util.cmp_obj_attrs(b, a, ["b", "c"]))
        self.assertFalse(util.cmp_obj_attrs(b, a, ["c", "b"]))

    def to_ascii_test(self):
        """Test _toASCII."""

        # check some conversions
        self.assertEqual(util._toASCII(""), "")
        self.assertEqual(util._toASCII(" "), " ")
        self.assertEqual(util._toASCII("&@`'łŁ!@#$%^&*{}[]$'<>*"),
                         "&@`'!@#$%^&*{}[]$'<>*")
        self.assertEqual(util._toASCII("ABC"), "ABC")
        self.assertEqual(util._toASCII("aBC"), "aBC")
        _out = "Heizolruckstoabdampfung"
        self.assertEqual(util._toASCII("Heizölrückstoßabdämpfung"), _out)

    def upper_ascii_test(self):
        """Test upperASCII."""

        self.assertEqual(util.upperASCII(""), "")
        self.assertEqual(util.upperASCII("a"), "A")
        self.assertEqual(util.upperASCII("A"), "A")
        self.assertEqual(util.upperASCII("aBc"), "ABC")
        self.assertEqual(util.upperASCII("_&*'@#$%^aBcžčŘ"),
                         "_&*'@#$%^ABCZCR")
        _out = "HEIZOLRUCKSTOABDAMPFUNG"
        self.assertEqual(util.upperASCII("Heizölrückstoßabdämpfung"), _out)


    def lower_ascii_test(self):
        """Test lowerASCII."""
        self.assertEqual(util.lowerASCII(""), "")
        self.assertEqual(util.lowerASCII("A"), "a")
        self.assertEqual(util.lowerASCII("a"), "a")
        self.assertEqual(util.lowerASCII("aBc"), "abc")
        self.assertEqual(util.lowerASCII("_&*'@#$%^aBcžčŘ"),
                         "_&*'@#$%^abczcr")
        _out = "heizolruckstoabdampfung"
        self.assertEqual(util.lowerASCII("Heizölrückstoßabdämpfung"), _out)

    def have_word_match_test(self):
        """Test have_word_match."""

        self.assertTrue(util.have_word_match("word1 word2", "word1 word2 word3"))
        self.assertTrue(util.have_word_match("word1 word2", "word2 word1 word3"))
        self.assertTrue(util.have_word_match("word2 word1", "word3 word1 word2"))
        self.assertTrue(util.have_word_match("word1", "word1 word2"))
        self.assertTrue(util.have_word_match("word1 word2", "word2word1 word3"))
        self.assertTrue(util.have_word_match("word2 word1", "word3 word1word2"))
        self.assertTrue(util.have_word_match("word1", "word1word2"))
        self.assertTrue(util.have_word_match("", "word1"))

        self.assertFalse(util.have_word_match("word3 word1", "word1"))
        self.assertFalse(util.have_word_match("word1 word3", "word1 word2"))
        self.assertFalse(util.have_word_match("word3 word2", "word1 word2"))
        self.assertFalse(util.have_word_match("word1word2", "word1 word2 word3"))
        self.assertFalse(util.have_word_match("word1", ""))
        self.assertFalse(util.have_word_match("word1", None))
        self.assertFalse(util.have_word_match(None, "word1"))
        self.assertFalse(util.have_word_match("", None))
        self.assertFalse(util.have_word_match(None, ""))
        self.assertFalse(util.have_word_match(None, None))

        # Compare designated unicode and "standard" unicode string and make sure nothing crashes
        self.assertTrue(util.have_word_match("fête", u"fête champêtre"))
        self.assertTrue(util.have_word_match(u"fête", "fête champêtre"))

    def parent_dir_test(self):
        """Test the parent_dir function"""
        dirs = [("", ""), ("/", ""), ("/home/", ""), ("/home/bcl", "/home"), ("home/bcl", "home"),
                ("/home/bcl/", "/home"), ("/home/extra/bcl", "/home/extra"),
                ("/home/extra/bcl/", "/home/extra"), ("/home/extra/../bcl/", "/home")]

        for d, r in dirs:
            self.assertEqual(util.parent_dir(d), r)

    def open_with_perm_test(self):
        """Test the open_with_perm function"""
        # Create a directory for test files
        test_dir = tempfile.mkdtemp()
        try:
            # Reset the umask
            old_umask = os.umask(0)
            try:
                # Create a file with mode 0777
                util.open_with_perm(test_dir + '/test1', 'w', 0o777)
                self.assertEqual(os.stat(test_dir + '/test1').st_mode & 0o777, 0o777)

                # Create a file with mode 0600
                util.open_with_perm(test_dir + '/test2', 'w', 0o600)
                self.assertEqual(os.stat(test_dir + '/test2').st_mode & 0o777, 0o600)
            finally:
                os.umask(old_umask)
        finally:
            shutil.rmtree(test_dir)

    def touch_test(self):
        """Test if the touch function correctly creates empty files"""
        test_dir = tempfile.mkdtemp()
        try:
            file_path = os.path.join(test_dir, "EMPTY_FILE")
            # try to create an empty file with touch()
            util.touch(file_path)

            # check if it exists & is a file
            self.assertTrue(os.path.isfile(file_path))

            # check if the file is empty
            self.assertEqual(os.stat(file_path).st_size, 0)
        finally:
            shutil.rmtree(test_dir)

    def set_mode_test(self):
        """Test if the set_mode function"""
        test_dir = tempfile.mkdtemp()
        try:
            file_path = os.path.join(test_dir, "EMPTY_FILE")

            # test default mode - file will be created when it doesn't exists
            util.set_mode(file_path)

            # check if it exists & is a file
            assert os.path.isfile(file_path)
            # check if the file is empty
            assert os.stat(file_path).st_mode == 0o100600

            # test change of mode on already created file
            util.set_mode(file_path, 0o744)

            # check if the file is empty
            assert os.stat(file_path).st_mode == 0o100744
        finally:
            shutil.rmtree(test_dir)

    def item_counter_test(self):
        """Test the item_counter generator."""
        # normal usage
        counter = util.item_counter(3)
        self.assertEqual(next(counter), "1/3")
        self.assertEqual(next(counter), "2/3")
        self.assertEqual(next(counter), "3/3")
        with self.assertRaises(StopIteration):
            next(counter)
        # zero items
        counter = util.item_counter(0)
        with self.assertRaises(StopIteration):
            next(counter)
        # one item
        counter = util.item_counter(1)
        self.assertEqual(next(counter), "1/1")
        with self.assertRaises(StopIteration):
            next(counter)
        # negative item count
        counter = util.item_counter(-1)
        with self.assertRaises(ValueError):
            next(counter)

    def synchronized_decorator_test(self):
        """Check that the @synchronized decorator works correctly."""

        # The @synchronized decorator work on methods of classes
        # that provide self._lock with Lock or RLock instance.
        class LockableClass(object):
            def __init__(self):
                self._lock = Lock()

            def test_method(self):
                lock_state = self._lock.locked()  # pylint: disable=no-member
                return lock_state

            @synchronized
            def sync_test_method(self):
                lock_state = self._lock.locked()  # pylint: disable=no-member
                return lock_state

        lockable = LockableClass()
        self.assertFalse(lockable.test_method())
        self.assertTrue(lockable.sync_test_method())

        # The @synchronized decorator does not work on classes without self._lock.
        class NotLockableClass(object):
            @synchronized
            def sync_test_method(self):
                return "Hello world!"

        not_lockable = NotLockableClass()
        with self.assertRaises(AttributeError):
            not_lockable.sync_test_method()

        # It also does not work on functions.
        @synchronized
        def test_function():
            return "Hello world!"

        with self.assertRaises(TypeError):
            test_function()

    def sysroot_test(self):
        self.assertEqual(conf.target.physical_root, "/mnt/sysimage")
        self.assertEqual(conf.target.system_root, "/mnt/sysroot")

    def join_paths_test(self):
        self.assertEqual(util.join_paths("/first/path/"),
                         "/first/path/")
        self.assertEqual(util.join_paths(""),
                         "")
        self.assertEqual(util.join_paths("/first/path/", "/second/path"),
                         "/first/path/second/path")
        self.assertEqual(util.join_paths("/first/path/", "/second/path", "/third/path"),
                         "/first/path/second/path/third/path")
        self.assertEqual(util.join_paths("/first/path/", "/second/path", "third/path"),
                         "/first/path/second/path/third/path")
        self.assertEqual(util.join_paths("/first/path/", "second/path"),
                         "/first/path/second/path")
        self.assertEqual(util.join_paths("first/path", "/second/path"),
                         "first/path/second/path")
        self.assertEqual(util.join_paths("first/path", "second/path"),
                         "first/path/second/path")

    def decode_bytes_test(self):
        self.assertEqual("STRING", util.decode_bytes("STRING"))
        self.assertEqual("BYTES", util.decode_bytes(b"BYTES"))
        self.assertRaises(ValueError, util.decode_bytes, None)
        self.assertRaises(ValueError, util.decode_bytes, 0)
        self.assertRaises(ValueError, util.decode_bytes, [])

    @patch.dict('sys.modules')
    def get_anaconda_version_string_test(self):
        # Forget imported modules from pyanaconda. We have to forget every parent module of
        # pyanaconda.version but this is just more robust and easier. Without this the
        # version module is already imported and it's not loaded again.
        for name in list(sys.modules):
            if name.startswith('pyanaconda'):
                sys.modules.pop(name)

        # Disable the version module.
        sys.modules['pyanaconda.version'] = None

        from pyanaconda.core.util import get_anaconda_version_string
        self.assertEqual(get_anaconda_version_string(), "unknown")

        # Mock the version module.
        sys.modules['pyanaconda.version'] = Mock(
            __version__="1.0",
            __build_time_version__="1.0-1"
        )
        self.assertEqual(get_anaconda_version_string(), "1.0")
        self.assertEqual(get_anaconda_version_string(build_time_version=True), "1.0-1")

    @patch("pyanaconda.core.util.execWithRedirect")
    def test_restorecon(self, exec_mock):
        """Test restorecon helper normal function"""
        # default behavior
        self.assertTrue(util.restorecon(["foo"], root="/root"))
        exec_mock.assert_called_once_with("restorecon", ["-r", "foo"], root="/root")

        # also skip
        exec_mock.reset_mock()
        self.assertTrue(util.restorecon(["bar"], root="/root", skip_nonexistent=True))
        exec_mock.assert_called_once_with("restorecon", ["-ir", "bar"], root="/root")

        # explicitly don't skip
        exec_mock.reset_mock()
        self.assertTrue(util.restorecon(["bar"], root="/root", skip_nonexistent=False))
        exec_mock.assert_called_once_with("restorecon", ["-r", "bar"], root="/root")

        # missing restorecon
        exec_mock.reset_mock()
        exec_mock.side_effect = FileNotFoundError
        self.assertFalse(util.restorecon(["baz"], root="/root"))
        exec_mock.assert_called_once_with("restorecon", ["-r", "baz"], root="/root")


class LazyObjectTestCase(unittest.TestCase):

    class Object(object):

        def __init__(self):
            self._x = 0

        @property
        def x(self):
            return self._x

        @x.setter
        def x(self, value):
            self._x = value

        def f(self, value):
            self._x += value

    def setUp(self):
        self._obj = None

    @property
    def obj(self):
        if not self._obj:
            self._obj = self.Object()

        return self._obj

    @property
    def lazy_obj(self):
        return LazyObject(lambda: self.obj)

    def get_set_test(self):
        self.assertIsNotNone(self.lazy_obj)
        self.assertIsNone(self._obj)

        self.assertEqual(self.lazy_obj.x, 0)
        self.assertIsNotNone(self._obj)

        self.obj.x = -10
        self.assertEqual(self.obj.x, -10)
        self.assertEqual(self.lazy_obj.x, -10)

        self.lazy_obj.x = 10
        self.assertEqual(self.obj.x, 10)
        self.assertEqual(self.lazy_obj.x, 10)

        self.lazy_obj.f(90)
        self.assertEqual(self.obj.x, 100)
        self.assertEqual(self.lazy_obj.x, 100)

    def eq_test(self):
        a = object()
        lazy_a1 = LazyObject(lambda: a)
        lazy_a2 = LazyObject(lambda: a)

        self.assertEqual(a, lazy_a1)
        self.assertEqual(lazy_a1, a)

        self.assertEqual(a, lazy_a2)
        self.assertEqual(lazy_a2, a)

        self.assertEqual(lazy_a1, lazy_a2)
        self.assertEqual(lazy_a2, lazy_a1)

        self.assertEqual(lazy_a1, lazy_a1)
        self.assertEqual(lazy_a2, lazy_a2)

    def neq_test(self):
        a = object()
        lazy_a = LazyObject(lambda: a)

        b = object()
        lazy_b = LazyObject(lambda: b)

        self.assertNotEqual(b, lazy_a)
        self.assertNotEqual(lazy_a, b)

        self.assertNotEqual(lazy_a, lazy_b)
        self.assertNotEqual(lazy_b, lazy_a)

    def hash_test(self):
        a = object()
        lazy_a1 = LazyObject(lambda: a)
        lazy_a2 = LazyObject(lambda: a)

        b = object()
        lazy_b1 = LazyObject(lambda: b)
        lazy_b2 = LazyObject(lambda: b)

        self.assertEqual({a, lazy_a1, lazy_a2}, {a})
        self.assertEqual({b, lazy_b1, lazy_b2}, {b})
        self.assertEqual({lazy_a1, lazy_b2}, {a, b})
