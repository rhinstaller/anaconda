#!/usr/bin/python
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
        for (commandName, commandObj) in self._commandMap.iteritems():
            pykickstartClass = self.handler.commands[commandName].__class__
            self.assertIsInstance(commandObj(), pykickstartClass)

# Do the same thing as CommandVersionTestCase, but for data objects.
class DataVersionTestCase(BaseTestCase):
    def data_test(self):
        for (dataName, dataObj) in self._dataMap.iteritems():
            # pykickstart does not expose data objects as a mapping the way
            # it does command objects.
            pykickstartClass = eval("self.handler.%s" % dataName)
            self.assertIsInstance(dataObj(), pykickstartClass)
