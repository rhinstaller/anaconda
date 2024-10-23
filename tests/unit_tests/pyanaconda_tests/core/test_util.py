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
import sys
import pytest

from threading import Lock
from unittest.mock import Mock, patch
from timer import timer
from io import StringIO
from textwrap import dedent

from pyanaconda.core.path import make_directories
from pyanaconda.errors import ExitError
from pyanaconda.core.process_watchers import WatchProcesses
from pyanaconda.core import util
from pyanaconda.core.util import synchronized, LazyObject, is_stage2_on_nfs
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.live_user import User


class RunProgramTests(unittest.TestCase):
    def test_run_program(self):
        """Test the _run_program method."""

        # correct calling should return rc==0
        assert util._run_program(['ls'])[0] == 0

        # incorrect calling should return rc!=0
        assert util._run_program(['ls', '--asdasd'])[0] != 0

        # check if an int is returned for bot success and error
        assert isinstance(util._run_program(['ls'])[0], int)
        assert isinstance(util._run_program(['ls', '--asdasd'])[0], int)

        # error should raise OSError
        with pytest.raises(OSError):
            util._run_program(['asdasdadasd'])

    def test_run_program_binary(self):
        """Test _run_program with binary output."""

        # Echo something that cannot be decoded as utf-8
        retcode, output = util._run_program(['echo', '-en', r'\xa0\xa1\xa2'], binary_output=True)

        assert retcode == 0
        assert output == b'\xa0\xa1\xa2'

    def test_exec_with_redirect(self):
        """Test execWithRedirect."""
        # correct calling should return rc==0
        assert util.execWithRedirect('ls', []) == 0

        # incorrect calling should return rc!=0
        assert util.execWithRedirect('ls', ['--asdasd']) != 0

    def test_exec_with_capture(self):
        """Test execWithCapture."""

        # check some output is returned
        assert len(util.execWithCapture('ls', ['--help'])) > 0

        # check no output is returned
        assert len(util.execWithCapture('true', [])) == 0

    def test_exec_with_capture_no_stderr(self):
        """Test execWithCapture with no stderr"""

        with tempfile.NamedTemporaryFile(mode="w+t") as testscript:
            testscript.write("""#!/bin/sh
echo "output"
echo "error" >&2
""")
            testscript.flush()

            # check that only the output is captured
            assert util.execWithCapture("/bin/sh", [testscript.name], filter_stderr=True) == \
                    "output\n"

            # check that both output and error are captured
            assert util.execWithCapture("/bin/sh", [testscript.name]) == "output\nerror\n"

    def test_exec_with_capture_empty(self):
        """Test execWithCapture with no output"""

        # check that the output is an empty string
        assert util.execWithCapture("/bin/sh", ["-c", "exit 0"]) == ""

    @patch("pyanaconda.core.util.startProgram")
    @patch("pyanaconda.core.util.get_live_user")
    def test_exec_with_capture_as_live_user(self, mock_get_live_user, mock_start_program):
        """Test execWithCaptureAsLiveUser."""
        mock_get_live_user.return_value = User(name="testlive",
                                               uid=1000,
                                               env_add={"TEST": "test"},
                                               env_prune=("TEST_PRUNE",)
                                               )
        mock_start_program.return_value.communicate.return_value = (b"", b"")

        util.execWithCaptureAsLiveUser('ls', [])

        mock_start_program.assert_called_once()
        assert mock_start_program.call_args.kwargs["user"] == 1000
        assert mock_start_program.call_args.kwargs["env_add"] == {"TEST": "test"}
        assert mock_start_program.call_args.kwargs["env_prune"] == ("TEST_PRUNE",)

    def test_exec_readlines(self):
        """Test execReadlines."""

        # test no lines are returned
        assert list(util.execReadlines("true", [])) == []

        # test some lines are returned
        assert len(list(util.execReadlines("ls", ["--help"]))) > 0

        # check that it always returns an iterator for both
        # if there is some output and if there isn't any
        assert hasattr(util.execReadlines("ls", ["--help"]), "__iter__")
        assert hasattr(util.execReadlines("true", []), "__iter__")

    def test_exec_readlines_normal_output(self):
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
                assert next(rl_iterator) == "one"
                assert next(rl_iterator) == "two"
                assert next(rl_iterator) == "three"
                with pytest.raises(StopIteration):
                    rl_iterator.__next__()

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
                assert next(rl_iterator) == "one"
                assert next(rl_iterator) == "two"
                assert next(rl_iterator) == "three"
                with pytest.raises(StopIteration):
                    rl_iterator.__next__()

    def test_exec_readlines_exits(self):
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
                assert next(rl_iterator) == "one"
                assert next(rl_iterator) == "two"
                assert next(rl_iterator) == "three"
                with pytest.raises(OSError):
                    rl_iterator.__next__()

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
                assert next(rl_iterator) == "one"
                assert next(rl_iterator) == "two"
                assert next(rl_iterator) == "three"
                with pytest.raises(OSError):
                    rl_iterator.__next__()

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
                assert next(rl_iterator) == "one"
                assert next(rl_iterator) == "two"
                assert next(rl_iterator) == "three"
                with pytest.raises(OSError):
                    rl_iterator.__next__()

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
                assert next(rl_iterator) == "one"
                assert next(rl_iterator) == "two"
                assert next(rl_iterator) == "three"
                with pytest.raises(OSError):
                    rl_iterator.__next__()

    def test_exec_readlines_exits_noraise(self):
        """Test execReadlines in different child exit situations without raising errors."""

        # No tests should raise anything.

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
                rl_iterator = util.execReadlines(
                    "/bin/sh",
                    [testscript.name],
                    raise_on_nozero=False
                )
                assert next(rl_iterator) == "one"
                assert next(rl_iterator) == "two"
                assert next(rl_iterator) == "three"
                with pytest.raises(StopIteration):
                    rl_iterator.__next__()

                assert rl_iterator.rc == 1

        # Test with signal
        with tempfile.NamedTemporaryFile(mode="wt") as testscript:
            testscript.write("""#!/bin/sh
echo "one"
echo "two"
echo "three"
kill -TERM $$
""")
            testscript.flush()

            with timer(5):
                rl_iterator = util.execReadlines(
                    "/bin/sh",
                    [testscript.name],
                    raise_on_nozero=False
                )
                assert next(rl_iterator) == "one"
                assert next(rl_iterator) == "two"
                assert next(rl_iterator) == "three"
                with pytest.raises(StopIteration):
                    rl_iterator.__next__()

                assert rl_iterator.rc == -15

        # Same as above but exit before a final newline
        with tempfile.NamedTemporaryFile(mode="wt") as testscript:
            testscript.write("""#!/bin/sh
echo "one"
echo "two"
echo -n "three"
exit 1
""")
            testscript.flush()

            with timer(5):
                rl_iterator = util.execReadlines(
                    "/bin/sh",
                    [testscript.name],
                    raise_on_nozero=False
                )
                assert next(rl_iterator) == "one"
                assert next(rl_iterator) == "two"
                assert next(rl_iterator) == "three"
                with pytest.raises(StopIteration):
                    rl_iterator.__next__()

                assert rl_iterator.rc == 1

        with tempfile.NamedTemporaryFile(mode="wt") as testscript:
            testscript.write("""#!/bin/sh
echo "one"
echo "two"
echo -n "three"
kill -TERM $$
""")
            testscript.flush()

            with timer(5):
                rl_iterator = util.execReadlines(
                    "/bin/sh",
                    [testscript.name],
                    raise_on_nozero=False
                )
                assert next(rl_iterator) == "one"
                assert next(rl_iterator) == "two"
                assert next(rl_iterator) == "three"
                with pytest.raises(StopIteration):
                    rl_iterator.__next__()

                assert rl_iterator.rc == -15

    def test_exec_readlines_signals(self):
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
                    assert next(rl_iterator) == "one"
                    assert next(rl_iterator) == "two"
                    assert next(rl_iterator) == "three"
                    with pytest.raises(StopIteration):
                        rl_iterator.__next__()
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
                    assert next(rl_iterator) == "one"
                    assert next(rl_iterator) == "two"
                    assert next(rl_iterator) == "three"
                    with pytest.raises(StopIteration):
                        rl_iterator.__next__()
        finally:
            signal.signal(signal.SIGHUP, old_HUP_handler)

    def test_exec_readlines_filter_stderr(self):
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
                assert next(rl_iterator) == "one"
                assert next(rl_iterator) == "two"
                assert next(rl_iterator) == "three"
                with pytest.raises(StopIteration):
                    rl_iterator.__next__()

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
                assert next(rl_iterator) == "one"
                assert next(rl_iterator) == "three"
                with pytest.raises(StopIteration):
                    rl_iterator.__next__()

    def test_start_program_preexec_fn(self):
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
            assert testfile.read() == marker_text

    def test_start_program_stdout(self):
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
            assert testfile.read().strip() == marker_text

    def test_start_program_reset_handlers(self):
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
                assert proc.returncode == -(signal.SIGPIPE)

            # Start another copy without reset_handlers
            proc = util.startProgram(["/bin/sh", testscript.name], reset_handlers=False)

            with timer(5):
                # Kill with SIGPIPE, then SIGTERM, and make sure SIGTERM was the one
                # that worked.
                proc.send_signal(signal.SIGPIPE)
                proc.terminate()
                proc.communicate()
                assert proc.returncode == -(signal.SIGTERM)

    def test_exec_readlines_auto_kill(self):
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
                assert next(rl_iterator) == "hey"
                assert next(rl_iterator) == "hey"

                # Delete the iterator and wait for the process to be killed
                del rl_iterator
                proc.communicate()

            # Check that the process is gone
            assert proc.poll() is not None

    def test_watch_process(self):
        """Test watchProcess"""

        def test_still_running():
            with timer(5):
                # Run something forever so we can kill it
                proc = util.startProgram(["/bin/sh", "-c", "while true; do sleep 1; done"])
                WatchProcesses.watch_process(proc, "test1")
                proc.kill()
                # Wait for the SIGCHLD
                signal.pause()
        with pytest.raises(ExitError):
            test_still_running()

        # Make sure watchProcess checks that the process has not already exited
        with timer(5):
            proc = util.startProgram(["true"])
            proc.communicate()
        with pytest.raises(ExitError):
            WatchProcesses.watch_process(proc, "test2")

    @patch("pyanaconda.core.util.startProgram")
    def test_do_preexec(self, mock_start_program):
        """Test the do_preexec option of exec*** functions."""
        mock_start_program.return_value.communicate.return_value = (b"", b"")

        util.execWithRedirect("ls", [])
        mock_start_program.assert_called_once()
        assert mock_start_program.call_args.kwargs["do_preexec"] is True
        mock_start_program.reset_mock()

        util.execWithRedirect("ls", [], do_preexec=False)
        mock_start_program.assert_called_once()
        assert mock_start_program.call_args.kwargs["do_preexec"] is False
        mock_start_program.reset_mock()

        util.execWithCapture("ls", [], do_preexec=True)
        mock_start_program.assert_called_once()
        assert mock_start_program.call_args.kwargs["do_preexec"] is True
        mock_start_program.reset_mock()

        util.execWithCapture("ls", [], do_preexec=False)
        mock_start_program.assert_called_once()
        assert mock_start_program.call_args.kwargs["do_preexec"] is False
        mock_start_program.reset_mock()


class MiscTests(unittest.TestCase):

    def test_get_active_console(self):
        """Test get_active_console."""

        # at least check if a string is returned
        assert isinstance(util.get_active_console(), str)

    def test_is_console_on_vt(self):
        """Test isConsoleOnVirtualTerminal."""

        # at least check if a bool is returned
        assert isinstance(util.isConsoleOnVirtualTerminal(), bool)

    @patch("pyanaconda.core.util.execWithRedirect")
    def test_vt_activate(self, exec_mock):
        """Test vtActivate."""
        exec_mock.return_value = 0
        assert util.vtActivate(2) is True

        # chvt does not exist on all platforms
        exec_mock.side_effect = OSError
        assert util.vtActivate(2) is False

    def test_item_counter(self):
        """Test the item_counter generator."""
        # normal usage
        counter = util.item_counter(3)
        assert next(counter) == "1/3"
        assert next(counter) == "2/3"
        assert next(counter) == "3/3"
        with pytest.raises(StopIteration):
            next(counter)
        # zero items
        counter = util.item_counter(0)
        with pytest.raises(StopIteration):
            next(counter)
        # one item
        counter = util.item_counter(1)
        assert next(counter) == "1/1"
        with pytest.raises(StopIteration):
            next(counter)
        # negative item count
        counter = util.item_counter(-1)
        with pytest.raises(ValueError):
            next(counter)

    def test_synchronized_decorator(self):
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
        assert not lockable.test_method()
        assert lockable.sync_test_method()

        # The @synchronized decorator does not work on classes without self._lock.
        class NotLockableClass(object):
            @synchronized
            def sync_test_method(self):
                return "Hello world!"

        not_lockable = NotLockableClass()
        with pytest.raises(AttributeError):
            not_lockable.sync_test_method()

        # It also does not work on functions.
        @synchronized
        def test_function():
            return "Hello world!"

        with pytest.raises(TypeError):
            test_function()

    def test_sysroot(self):
        assert conf.target.physical_root == "/mnt/sysimage"
        assert conf.target.system_root == "/mnt/sysroot"

    @patch.dict('sys.modules')
    def test_get_anaconda_version_string(self):
        # Forget imported modules from pyanaconda. We have to forget every parent module of
        # pyanaconda.version but this is just more robust and easier. Without this the
        # version module is already imported and it's not loaded again.
        for name in list(sys.modules):
            if name.startswith('pyanaconda'):
                sys.modules.pop(name)

        # Disable the version module.
        sys.modules['pyanaconda.version'] = None

        from pyanaconda.core.util import get_anaconda_version_string
        assert get_anaconda_version_string() == "unknown"

        # Mock the version module.
        sys.modules['pyanaconda.version'] = Mock(
            __version__="1.0",
            __build_time_version__="1.0-1"
        )
        assert get_anaconda_version_string() == "1.0"
        assert get_anaconda_version_string(build_time_version=True) == "1.0-1"

    def test_get_os_relase_value(self):
        """Test the get_release_value function."""
        with tempfile.TemporaryDirectory() as root:
            # prepare paths
            make_directories(root + "/usr/lib")
            make_directories(root + "/etc")

            # no file
            with self.assertLogs(level="DEBUG") as cm:
                version = util.get_os_release_value("VERSION_ID", root)

            msg = "VERSION_ID not found in os-release files"
            assert any(map(lambda x: msg in x, cm.output))
            assert version is None

            # backup file only
            with open(root + "/usr/lib/os-release", "w") as f:
                f.write("# blah\nVERSION_ID=foo256bar  \n VERSION_ID = wrong\n\n")
            version = util.get_os_release_value("VERSION_ID", root)
            assert version == "foo256bar"
            assert util.get_os_release_value("PLATFORM_ID", root) is None

            # main file and backup too
            with open(root + "/etc/os-release", "w") as f:
                f.write("# blah\nVERSION_ID=more-important\n")
            version = util.get_os_release_value("VERSION_ID", root)
            assert version == "more-important"

            # both, main file twice
            with open(root + "/etc/os-release", "w") as f:
                f.write("# blah\nVERSION_ID=more-important\nVERSION_ID=not-reached\n \n")
            version = util.get_os_release_value("VERSION_ID", root)
            assert version == "more-important"

            # quoted values
            with open(root + "/etc/os-release", "w") as f:
                f.write("PRETTY_NAME=\"Fedora 32\"\nPLATFORM_ID='platform:f32'\n")
            assert util.get_os_release_value("PRETTY_NAME", root) == "Fedora 32"
            assert util.get_os_release_value("PLATFORM_ID", root) == "platform:f32"

            # no files
            os.remove(root + "/usr/lib/os-release")
            os.remove(root + "/etc/os-release")
            version = util.get_os_release_value("VERSION_ID", root)
            assert version is None

    @patch("pyanaconda.core.util.execWithRedirect")
    def test_restorecon(self, exec_mock):
        """Test restorecon helper normal function"""
        # default behavior
        assert util.restorecon(["foo"], root="/root")
        exec_mock.assert_called_once_with("restorecon", ["-r", "foo"], root="/root")

        # also skip
        exec_mock.reset_mock()
        assert util.restorecon(["bar"], root="/root", skip_nonexistent=True)
        exec_mock.assert_called_once_with("restorecon", ["-ir", "bar"], root="/root")

        # explicitly don't skip
        exec_mock.reset_mock()
        assert util.restorecon(["bar"], root="/root", skip_nonexistent=False)
        exec_mock.assert_called_once_with("restorecon", ["-r", "bar"], root="/root")

        # missing restorecon
        exec_mock.reset_mock()
        exec_mock.side_effect = FileNotFoundError
        assert not util.restorecon(["baz"], root="/root")
        exec_mock.assert_called_once_with("restorecon", ["-r", "baz"], root="/root")

    @patch("pyanaconda.core.util.execWithCapture")
    @patch("pyanaconda.core.util.os.path.exists")
    def test_ipmi_report(self, exists_mock, exec_mock):
        """Test IPMI reporting"""
        # IPMI present
        exists_mock.side_effect = [True, True]
        util.ipmi_report(util.IPMI_ABORTED)  # the actual value does not matter
        assert util._supports_ipmi is True
        assert exists_mock.call_count == 2
        assert exec_mock.call_count == 1
        assert exec_mock.mock_calls[0].args[0] == "ipmitool"

        # IPMI not present
        util._supports_ipmi = None  # reset the global state
        exists_mock.side_effect = [True, False]
        exec_mock.reset_mock()
        util.ipmi_report(util.IPMI_ABORTED)
        assert util._supports_ipmi is False
        exec_mock.assert_not_called()

    @patch("pyanaconda.core.util.ipmi_report")
    def test_ipmi_abort(self, ipmi_mock):
        """Test termination with IPMI messaging and running onerror scripts."""
        from pykickstart.constants import KS_SCRIPT_ONERROR, KS_SCRIPT_POST

        script1 = Mock(type=KS_SCRIPT_ONERROR)
        script2 = Mock(type=KS_SCRIPT_POST)

        util.ipmi_abort([script1, script2])

        ipmi_mock.assert_called_with(util.IPMI_ABORTED)
        script1.run.assert_called_once_with("/")
        script2.run.assert_not_called()

    def test_dracut_eject(self):
        """Test writing the device eject dracut shutdown hook."""
        devname = "/some/device"
        with tempfile.TemporaryDirectory() as tmpdir:
            hook_file_path = tmpdir + "/longer_path/hook.file"
            with patch("pyanaconda.core.util.DRACUT_SHUTDOWN_EJECT", new=hook_file_path):
                util.dracut_eject(devname)
                with open(hook_file_path, "r") as f:
                    file_contents = "\n".join(f.readlines())
                    assert "eject " + devname in file_contents

    @patch("pyanaconda.core.util.open")
    def test_is_stage2_on_nfs(self, mock_open):
        """Test check for installation running on nfs."""
        nfs_source_mounts = """
        LiveOS_rootfs / overlay rw,seclabel,relatime,lowerdir=/run/rootfsbase,upperdir=/run/overlayfs,workdir=/run/ovlwork,uuid=on 0 0
        proc /proc proc rw,nosuid,nodev,noexec,relatime 0 0
        tmpfs /run tmpfs rw,seclabel,nosuid,nodev,size=401324k,nr_inodes=819200,mode=755,inode64 0 0
        10.43.136.2:/mnt/data/trees/rawhide /run/install/repo nfs ro,relatime,vers=3,rsize=1048576,wsize=1048576,namlen=255,hard,nolock,proto=tcp,timeo=600,retrans=2,sec=sys,mountaddr=10.43.136.2,mountvers=3,mountport=20
        048,mountproto=udp,local_lock=all,addr=10.43.136.2 0 0
        mqueue /dev/mqueue mqueue rw,seclabel,nosuid,nodev,noexec,relatime 0 0
        tmpfs /run/credentials/systemd-vconsole-setup.service tmpfs ro,seclabel,nosuid,nodev,noexec,relatime,nosymfollow,size=1024k,nr_inodes=1024,mode=700,inode64,noswap 0 0
        10.43.136.2:/mnt/data/trees/rawhide /run/install/sources/mount-0000-nfs-device nfs rw,relatime,vers=3,rsize=1048576,wsize=1048576,namlen=255,hard,nolock,proto=tcp,timeo=600,retrans=2,sec=sys,mountaddr=10.43.136.2
        ,mountvers=3,mountport=20048,mountproto=udp,local_lock=all,addr=10.43.136.2 0 0
        """
        nfs_stage2_mounts = """
        LiveOS_rootfs / overlay rw,seclabel,relatime,lowerdir=/run/rootfsbase,upperdir=/run/overlayfs,workdir=/run/ovlwork,uuid=on 0 0
        proc /proc proc rw,nosuid,nodev,noexec,relatime 0 0
        tmpfs /run tmpfs rw,seclabel,nosuid,nodev,size=401324k,nr_inodes=819200,mode=755,inode64 0 0
        10.43.136.2:/mnt/data/users/rv/s2/rvm /run/install/repo nfs ro,relatime,vers=3,rsize=1048576,wsize=1048576,namlen=255,hard,nolock,proto=tcp,timeo=600,retrans=2,sec=sys,mountaddr=10.43.136.2,mountvers=3,mountport=
        mqueue /dev/mqueue mqueue rw,seclabel,nosuid,nodev,noexec,relatime 0 0
        tmpfs /run/credentials/systemd-vconsole-setup.service tmpfs ro,seclabel,nosuid,nodev,noexec,relatime,nosymfollow,size=1024k,nr_inodes=1024,mode=700,inode64,noswap 0 0
        """
        no_nfs_mounts = """
        LiveOS_rootfs / overlay rw,seclabel,relatime,lowerdir=/run/rootfsbase,upperdir=/run/overlayfs,workdir=/run/ovlwork,uuid=on 0 0
        rpc_pipefs /var/lib/nfs/rpc_pipefs rpc_pipefs rw,relatime 0 0
        mqueue /dev/mqueue mqueue rw,seclabel,nosuid,nodev,noexec,relatime 0 0
        tmpfs /run/credentials/systemd-vconsole-setup.service tmpfs ro,seclabel,nosuid,nodev,noexec,relatime,nosymfollow,size=1024k,nr_inodes=1024,mode=700,inode64,noswap 0 0
        """
        nfs4_mounts = """
        10.43.136.2:/mnt/data/users/rv/s2/rvm /run/install/repo nfs4 ro,relatime,vers=3,rsize=1048576,wsize=1048576,namlen=255,hard,nolock,proto=tcp,timeo=600,retrans=2,sec=sys,mountaddr=10.43.136.2,mountvers=3,mountport=
        """
        mock_open.return_value = StringIO(dedent(nfs_stage2_mounts))
        assert is_stage2_on_nfs() is True

        mock_open.return_value = StringIO(dedent(nfs_source_mounts))
        assert is_stage2_on_nfs() is True

        mock_open.return_value = StringIO(dedent(nfs4_mounts))
        assert is_stage2_on_nfs() is True

        mock_open.return_value = StringIO(dedent(no_nfs_mounts))
        assert is_stage2_on_nfs() is False


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

    def test_get_set(self):
        assert self.lazy_obj is not None
        assert self._obj is None

        assert self.lazy_obj.x == 0
        assert self._obj is not None

        self.obj.x = -10
        assert self.obj.x == -10
        assert self.lazy_obj.x == -10

        self.lazy_obj.x = 10
        assert self.obj.x == 10
        assert self.lazy_obj.x == 10

        self.lazy_obj.f(90)
        assert self.obj.x == 100
        assert self.lazy_obj.x == 100

    def test_eq(self):
        a = object()
        lazy_a1 = LazyObject(lambda: a)
        lazy_a2 = LazyObject(lambda: a)

        assert a == lazy_a1
        assert lazy_a1 == a

        assert a == lazy_a2
        assert lazy_a2 == a

        assert lazy_a1 == lazy_a2
        assert lazy_a2 == lazy_a1

        # ruff: noqa: PLR0124
        assert lazy_a1 == lazy_a1
        assert lazy_a2 == lazy_a2

    def test_neq(self):
        a = object()
        lazy_a = LazyObject(lambda: a)

        b = object()
        lazy_b = LazyObject(lambda: b)

        assert b != lazy_a
        assert lazy_a != b

        assert lazy_a != lazy_b
        assert lazy_b != lazy_a

    def test_hash(self):
        a = object()
        lazy_a1 = LazyObject(lambda: a)
        lazy_a2 = LazyObject(lambda: a)

        b = object()
        lazy_b1 = LazyObject(lambda: b)
        lazy_b2 = LazyObject(lambda: b)

        assert {a, lazy_a1, lazy_a2} == {a}
        assert {b, lazy_b1, lazy_b2} == {b}
        assert {lazy_a1, lazy_b2} == {a, b}
