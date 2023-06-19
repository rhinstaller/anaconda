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
from subprocess import CalledProcessError

# import Cockpit's machinery for test VMs and its browser test API
TEST_DIR = os.path.dirname(__file__)
sys.path.append(os.path.join(TEST_DIR, "common"))
sys.path.append(os.path.join(TEST_DIR, "helpers"))
sys.path.append(os.path.join(os.path.dirname(TEST_DIR), "bots/machine"))

from installer import Installer
from language import Language
from storage import Storage
from review import Review
from progress import Progress
from testlib import MachineCase  # pylint: disable=import-error
from machine_install import VirtInstallMachine
from step_logger import log_step


class End2EndTest(MachineCase):
    MachineCase.machine_class = VirtInstallMachine

    def setUp(self):
        super().setUp()
        self._installer = Installer(self.browser, self.machine)
        self._language = Language(self.browser, self.machine)
        self._storage = Storage(self.browser, self.machine)
        self._review = Review(self.browser)
        self._progress = Progress(self.browser)
        self.__installation_finished = False
        self.logs_dir = os.path.join('./test_logs', self.__class__.__name__)
        if not os.path.isdir(self.logs_dir):
            os.makedirs(self.logs_dir)

    def __add_public_key(self):
        with open(self.machine.identity_file + '.pub', 'r') as pub:
            public_key = pub.read()

        sysroot_ssh = '/mnt/sysroot/root/.ssh'
        authorized_keys = os.path.join(sysroot_ssh, 'authorized_keys')
        self.machine.execute(fr'''mkdir -p {sysroot_ssh}
            echo "{public_key}" >> {authorized_keys}
            chmod 700 {sysroot_ssh}''')

    def __download_logs(self):
        self.machine.download('/tmp/anaconda.log', 'anaconda.log', self.logs_dir)
        self.machine.download('/tmp/packaging.log', 'packaging.log', self.logs_dir)
        self.machine.download('/tmp/storage.log', 'storage.log', self.logs_dir)
        self.machine.download('/tmp/dbus.log', 'dbus.log', self.logs_dir)
        self.machine.download('/tmp/syslog', 'syslog', self.logs_dir)
        try:
            self.machine.download('/tmp/anaconda-tb-*', '.', self.logs_dir)
        except CalledProcessError:
            pass

    def configure_language(self):
        pass

    def configure_storage_disks(self):
        disks = list(self._storage.get_disks())
        self._storage.select_disk(disks[0])

    def configure_storage_partitioning(self):
        pass

    def configure_storage_encryption(self):
        pass

    def check_review_screen(self):
        pass

    def monitor_progress(self):
        self._progress.wait_done()

    def reboot_to_installed_system(self):
        self.__add_public_key()
        self.__download_logs()
        self.__installation_finished = True
        self._progress.reboot()
        self.machine.wait_reboot()

    def post_install_step(self):
        pass

    @log_step(docstring=True)
    def check_installed_system(self):
        """ Tries to set root password """
        self.machine.execute('echo "test" | passwd --stdin root') # Workaround for locked root account

    def run_integration_test(self):
        self._installer.open()
        self.configure_language()
        self._installer.next()
        self.configure_storage_disks()
        self._installer.next()
        self.configure_storage_partitioning()
        self._installer.next()
        self.configure_storage_encryption()
        self._installer.next()
        self.check_review_screen()
        self._installer.begin_installation()
        self.monitor_progress()
        self.post_install_step()
        self.reboot_to_installed_system()
        self.check_installed_system()

    def tearDown(self):
        if not self.__installation_finished:
            self.__download_logs()
        super().tearDown()
