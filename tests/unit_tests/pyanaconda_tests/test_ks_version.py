#!/usr/bin/python3
#
# Copyright (C) 2013  Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
import importlib
import os
import shutil
import sys
import tempfile
import unittest
import warnings

import pytest
from pykickstart.version import isRHEL as is_rhel

from pyanaconda import kickstart
from pyanaconda.core.kickstart.version import VERSION


# Verify that each kickstart command in anaconda uses the correct version of
# that command as provided by pykickstart.  That is, if there's an FC3 and an
# F10 version of a command, make sure anaconda >= F10 uses the F10 version.
class CommandVersionTestCase(unittest.TestCase):

    # Names of the kickstart commands and data that should be temporarily ignored.
    IGNORED_NAMES = {
    }

    def assert_compare_versions(self, children, parents):
        """Check if children inherit from parents."""
        if is_rhel(VERSION):
            pytest.skip("This test is disabled on RHEL.")

        for name in children:
            if name in self.IGNORED_NAMES:
                warnings.warn("Skipping the kickstart name {}.".format(name))
                continue

            # Print info about the command for better debugging.
            print(name, children[name], parents[name])

            # Skip commands that were moved on DBus.
            if isinstance(children[name](), kickstart.UselessCommand):
                continue

            assert isinstance(children[name](), parents[name])

    def test_commands(self):
        """Test that anaconda uses the right versions of kickstart commands"""
        anaconda_cmds = kickstart.commandMap
        pykickstart_cmds = kickstart.superclass.commandMap
        self.assert_compare_versions(anaconda_cmds, pykickstart_cmds)

    def test_data(self):
        """Test that anaconda uses the right versions of kickstart data"""
        anaconda_data = kickstart.dataMap
        pykickstart_data = kickstart.superclass.dataMap
        self.assert_compare_versions(anaconda_data, pykickstart_data)

    def test_dracut_commands(self):
        """Test that dracut uses the right versions of kickstart commands"""
        # top_srcdir should have been set by unit_tests.sh. If it wasn't, the KeyError
        # will fail the test.
        parse_kickstart_path = os.path.join(os.environ['top_srcdir'], 'dracut', 'parse-kickstart')
        temp_module_name = "parse_kickstart_for_dracut_test"

        # Make sure we can import the script: Copy it to a temporary directory, to a file with no
        # slashes in name, and extension .py.
        with tempfile.TemporaryDirectory() as tempdir:
            temp_file_path = tempdir + "/" + temp_module_name + ".py"
            shutil.copyfile(parse_kickstart_path, temp_file_path)
            sys.path.append(tempdir)
            parse_module = importlib.import_module(temp_module_name)
            sys.path.remove(tempdir)

        dracut_commands = parse_module.dracutCmds
        pykickstart_commands = kickstart.superclass.commandMap
        self.assert_compare_versions(dracut_commands, pykickstart_commands)
