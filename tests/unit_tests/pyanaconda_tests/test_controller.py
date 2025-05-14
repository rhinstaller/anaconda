#
# Martin Kolman <mkolman@redhat.com>
#
# Copyright 2016 Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use, modify,
# copy, or redistribute it subject to the terms and conditions of the GNU
# General Public License v.2.  This program is distributed in the hope that it
# will be useful, but WITHOUT ANY WARRANTY expressed or implied, including the
# implied warranties of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.  Any Red Hat
# trademarks that are incorporated in the source code or documentation are not
# subject to the GNU General Public License and may only be used or replicated
# with the express permission of Red Hat, Inc.
#

import unittest

from pyanaconda.lifecycle import Controller


class TestModule(object):
    def __init__(self):
        self._test = 1


class InstallTasksTestCase(unittest.TestCase):
    def setUp(self):
        self._test_variable1 = 0

    def _increment_var1(self):
        self._test_variable1 += 1

    def test_controller(self):
        """Check that the module initialization controller works correctly."""
        module1 = TestModule()
        module2 = TestModule()
        module3 = TestModule()

        ctrl = Controller()

        ctrl.init_done.connect(self._increment_var1)

        # mark the modules as being initialized
        ctrl.module_init_start(module1)
        ctrl.module_init_start(module2)
        ctrl.module_init_start(module3)

        # tell the controller that all expected modules have been added
        ctrl.all_modules_added()

        # report modules initialization as being finished
        # - order should not matter
        ctrl.module_init_done(module2)
        ctrl.module_init_done(module3)
        ctrl.module_init_done(module1)

        # When the last of the expected modules reports
        # initialization as done the init_done signal of the
        # controller should be triggered. So check that
        # it really happened.
        assert self._test_variable1 == 1

    def test_controller_robustness(self):
        """Check of controller handles various edge cases."""
        module1 = TestModule()
        module2 = TestModule()
        module3 = TestModule()
        module4 = TestModule()
        module5 = TestModule()
        module6 = TestModule()
        module7 = TestModule()
        module8 = TestModule()
        module9 = TestModule()

        ctrl = Controller()

        ctrl.init_done.connect(self._increment_var1)

        # add some modules and set them as initialized right away
        # - this should basically cancel itself out as
        # - the init_done signal will not be triggered as all_modules_added()
        #   has not yet been called
        ctrl.module_init_start(module4)
        ctrl.module_init_start(module5)
        ctrl.module_init_done(module5)
        ctrl.module_init_done(module4)
        # check that the init_done has not yet been triggered
        assert self._test_variable1 == 0

        # mark the modules as being initialized
        ctrl.module_init_start(module1)
        ctrl.module_init_start(module2)
        ctrl.module_init_start(module3)

        # tell the controller that all expected modules have been added
        ctrl.all_modules_added()

        # attempts to add & set modules as initialized after all_modules_added() is called
        # should be also ignored
        ctrl.module_init_start(module6)
        ctrl.module_init_start(module7)
        ctrl.module_init_done(module6)

        # check that the init_done has not yet been triggered
        assert self._test_variable1 == 0

        # report modules initialization as being finished
        # - order should not matter
        ctrl.module_init_done(module2)
        ctrl.module_init_done(module3)
        ctrl.module_init_done(module1)

        # attempts to add & set modules as initialized after the init_done signal
        # has been triggered should be ignored as well
        ctrl.module_init_start(module8)
        ctrl.module_init_start(module9)
        ctrl.module_init_done(module7)  # from attempt
        ctrl.module_init_done(module9)
        ctrl.module_init_done(module8)

        # check that the init_done signal has been triggered only once
        assert self._test_variable1 == 1
