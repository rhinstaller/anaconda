#!/usr/bin/python3 -u
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

import signal
import argparse
import os
import sys

BASE_DIR = os.path.normpath(os.path.dirname(__file__)+'/../..')
TEST_DIR = f'{BASE_DIR}/test'
BOTS_DIR = f'{BASE_DIR}/bots'

# pylint: disable=environment-modify
sys.path.append(BOTS_DIR)
sys.path.append(TEST_DIR)
sys.path.append(f'{BOTS_DIR}/machine')

from machine_install import VirtInstallMachine as VirtMachine
from machine_core.timeout import Timeout
from machine_core.machine import Machine
from machine_core.exceptions import Failure, RepeatableFailure
from machine_core.machine_virtual import VirtNetwork
from lib.constants import BOTS_DIR, TEST_DIR, IMAGES_DIR, SCRIPTS_DIR, DEFAULT_IMAGE, TEST_OS_DEFAULT
from lib.directories import get_images_data_dir
from machine_core.cli import cmd_cli
from lib.testmap import get_build_image, get_test_image


__all__ = (
    "Timeout", "Machine", "Failure", "RepeatableFailure", "VirtMachine",
    "VirtNetwork", "get_build_image", "get_test_image", "get_images_data_dir",
    "BOTS_DIR", "TEST_DIR", "IMAGES_DIR", "SCRIPTS_DIR",
    "DEFAULT_IMAGE", "TEST_OS_DEFAULT"
)

def cmd_cli():
    parser = argparse.ArgumentParser(description="Run a VM image until SIGTERM or SIGINT")
    parser.add_argument("image", help="Image name")
    args = parser.parse_args()

    machine = VirtMachine(image=args.image)
    machine.start()

    print("You can connect to the VM in the following ways:")
    # print ssh command
    print("ssh -o ControlPath=%s -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -p %s %s@%s" %
          (machine.ssh_master, machine.ssh_port, machine.ssh_user, machine.ssh_address))
    # print Cockpit web address
    print(
        "http://%s:%s/cockpit/@localhost/anaconda-webui/index.html" %
        (machine.web_address, machine.web_port)
    )
    # print marker that the VM is ready; tests can poll for this to wait for the VM
    print("RUNNING")

    signal.signal(signal.SIGTERM, lambda sig, frame: machine.stop())
    try:
        signal.pause()
    except KeyboardInterrupt:
        machine.stop()


# This can be used as helper program for tests not written in Python: Run given
# image name until SIGTERM or SIGINT; the iso must exist in test/images/;
# $ webui_testvm.py fedora-rawhide-boot
if __name__ == "__main__":
    cmd_cli()
