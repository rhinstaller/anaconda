#!/usr/bin/python3
#
# Copyright (C) 2023 Red Hat, Inc.
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
from step_logger import log_step  # pylint: disable=import-error


class StorageEncryption(End2EndTest):
    luks_pass = 'password'

    def configure_storage_encryption(self):
        self._storage.check_encryption_selected(False)
        self._storage.set_encryption_selected(True)
        self._storage.check_encryption_selected(True)
        
        self._installer.next(subpage=True)

        self._storage.set_password(self.luks_pass)
        self._storage.check_password(self.luks_pass)
        self._storage.set_password_confirm(self.luks_pass)
        self._storage.check_password_confirm(self.luks_pass)
        self._storage.check_pw_strength('weak')

    @log_step()
    def post_install_step(self):
        self._storage.unlock_storage_on_boot(self.luks_pass)

    @log_step(docstring=True)
    def check_installed_system(self):
        """ Check encryption is enabled """
        print(self.machine.execute('lsblk'))
        self.assertTrue('is active and is in use' in self.machine.execute('cryptsetup status /dev/mapper/luks*'))

    def test_storage_encryption(self):
        self.run_integration_test()

if __name__ == '__main__':
    test_main()
