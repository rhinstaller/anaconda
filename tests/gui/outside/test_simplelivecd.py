#!/usr/bin/python2
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
#
# Author: Chris Lumens <clumens@redhat.com>

__all__ = ["SimpleLiveCDCreator", "SimpleLiveCD_OutsideTest"]

from . import Creator, OutsideMixin
import unittest

from blivet.size import Size

class SimpleLiveCDCreator(Creator):
    drives = [("one", Size("8 GiB"))]
    name = "simplelivecd"
    tests = [("welcome", "BasicWelcomeTestCase"),
             ("summary", "LiveCDSummaryTestCase"),
             ("date_time", "LiveCDDateTimeTestCase"),
             ("keyboard", "BasicKeyboardTestCase"),
             ("storage", "BasicStorageTestCase"),
             ("network", "LiveCDNetworkTestCase"),
             ("progress", "LiveCDProgressTestCase"),
             ("rootpassword", "BasicRootPasswordTestCase"),
             ("progress", "LiveCDFinishTestCase")]

class SimpleLiveCD_OutsideTest(OutsideMixin, unittest.TestCase):
    creatorClass = SimpleLiveCDCreator
