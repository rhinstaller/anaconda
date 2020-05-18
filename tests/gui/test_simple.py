#!/usr/bin/python3
#
# Copyright (C) 2014  Red Hat, Inc.
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

from tests.gui import base, welcome, summary, date_time, keyboard, storage, network
from tests.gui import progress, rootpassword

from blivet.size import Size

class SimpleTestSuite(base.DogtailTestCase):
    drives = [("one", Size("10 GiB"))]
    name = "simple"
    tests = [welcome.BasicWelcomeTestCase,
             summary.SummaryTestCase,
             date_time.DateTimeTestCase,
             keyboard.BasicKeyboardTestCase,
             network.NetworkTestCase,
             storage.BasicStorageTestCase,
             progress.ProgressTestCase,
             rootpassword.BasicRootPasswordTestCase,
             progress.FinishTestCase]
