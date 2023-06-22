#!/usr/bin/python3
#
# Copyright (C) 2022 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; If not, see <http://www.gnu.org/licenses/>.

import os
import sys

# import Cockpit's machinery for test VMs and its browser test API
TEST_DIR = os.environ['WEBUI_TEST_DIR']
sys.path.append(TEST_DIR)
sys.path.append(os.path.join(TEST_DIR, "common"))
sys.path.append(os.path.join(TEST_DIR, "helpers"))
sys.path.append(os.path.join(os.path.dirname(TEST_DIR), "bots/machine"))

from end2end import End2EndTest  # pylint: disable=import-error
from testlib import test_main  # pylint: disable=import-error

class DefaultInstallation(End2EndTest):
    def test_default_installation(self):
        self.run_integration_test()

if __name__ == '__main__':
    test_main()
