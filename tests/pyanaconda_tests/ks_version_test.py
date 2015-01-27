#!/usr/bin/python2
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
#
# Author: Chris Lumens <clumens@redhat.com>
from mock import Mock
import unittest
import os

class BaseTestCase(unittest.TestCase):
    def setUp(self):
        import sys

        sys.modules["anaconda_log"] = Mock()
        sys.modules["block"] = Mock()

        from pyanaconda import kickstart
        import pykickstart.version

        self.handler = pykickstart.version.makeVersion(kickstart.superclass.version)
        self._commandMap = kickstart.commandMap
        self._dataMap = kickstart.dataMap

# Verify that each kickstart command in anaconda uses the correct version of
# that command as provided by pykickstart.  That is, if there's an FC3 and an
# F10 version of a command, make sure anaconda >= F10 uses the F10 version.
class CommandVersionTestCase(BaseTestCase):
    def commands_test(self):
        """Test that anaconda uses the right versions of kickstart commands"""
        for (commandName, commandObj) in self._commandMap.items():
            pykickstartClass = self.handler.commands[commandName].__class__
            self.assertIsInstance(commandObj(), pykickstartClass)

# Do the same thing as CommandVersionTestCase, but for data objects.
class DataVersionTestCase(BaseTestCase):
    def data_test(self):
        """Test that anaconda uses the right versions of kickstart data"""
        for (dataName, dataObj) in self._dataMap.items():
            # pykickstart does not expose data objects as a mapping the way
            # it does command objects.
            pykickstartClass = eval("self.handler.%s" % dataName)
            self.assertIsInstance(dataObj(), pykickstartClass)

# Copy the commands tests but with the command map from dracut/parse-kickstart
class DracutCommandVersionTestCase(CommandVersionTestCase):
    def setUp(self):
        CommandVersionTestCase.setUp(self)

        # top_srcdir should have been set by nosetests.sh. If it wasn't, the KeyError
        # will fail the test.
        parse_kickstart_path = os.path.join(os.environ['top_srcdir'], 'dracut', 'parse-kickstart')

        import tempfile
        with tempfile.NamedTemporaryFile() as parse_temp:
            # Compile the file manually to a tempfile so that the import doesn't automatically
            # crud up the source directory with parse-kickstartc
            import py_compile
            parse_temp = tempfile.NamedTemporaryFile()
            py_compile.compile(parse_kickstart_path, parse_temp.name)

            # Use imp to pretend that hyphens are ok for module names
            import imp
            parse_module = imp.load_module('parse_kickstart', parse_temp.file,
                    parse_temp.name, ('', 'r', imp.PY_COMPILED))

        self._commandMap = parse_module.dracutCmds
