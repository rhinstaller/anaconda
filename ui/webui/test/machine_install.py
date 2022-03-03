#!/usr/bin/python3

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
import socket
import subprocess
import sys

ANACONDA_ROOT_DIR = os.path.normpath(os.path.dirname(__file__)+'/../../..')
WEBUI_DIR = f'{ANACONDA_ROOT_DIR}/ui/webui'
WEBUI_TEST_DIR = f'{WEBUI_DIR}/test'
BOTS_DIR = f'{WEBUI_DIR}/bots'

# pylint: disable=environment-modify
sys.path.append(BOTS_DIR)
sys.path.append(f'{BOTS_DIR}/machine')

# pylint: disable=import-error
from testvm import VirtMachine  # nopep8
from testvm import Machine  # nopep8

# This env variable must be always set for anaconda webui tests.
# In the anaconda environment /run/nologin always exists however cockpit test
# suite expects it to not exist
os.environ["TEST_ALLOW_NOLOGIN"] = "true"


class VirtInstallMachine(VirtMachine):
    http_server = None

    def _execute(self, cmd):
        return subprocess.check_call(cmd, stderr=subprocess.STDOUT, shell=True)

    def _get_free_port(self, start_port):
        port = start_port
        while True:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if not (sock.connect_ex(('127.0.0.1', port)) == 0):
                return port
            port = port + 1

    def start(self):
        update_img_file = os.path.join(ANACONDA_ROOT_DIR, "updates.img")
        if not os.path.exists(update_img_file):
            raise Exception("Missing updates.img file")

        # Make sure the server is created at anaconda root directory
        os.chdir(ANACONDA_ROOT_DIR)
        # Create a dummy live image tar file for the test to consume
        self._execute("tar cvf live.tar --files-from /dev/null")
        http_port = self._get_free_port(8000)
        self.http_server = subprocess.Popen(["python3", "-m", "http.server", str(http_port)])
        os.chdir(WEBUI_DIR)

        try:
            self._execute(
                "virt-install "
                "--connect qemu:///session "
                "--quiet "
                f"--name {self.label} "
                f"--os-variant {self.image.rstrip('-boot')} "
                "--memory 2048 "
                "--noautoconsole "
                f"--graphics vnc,listen={self.ssh_address} "
                "--extra-args "
                f"'inst.sshd inst.nokill inst.webui inst.updates=http://10.0.2.2:{http_port}/updates.img' "
                "--network none "
                f"--qemu-commandline="
                "'-netdev user,id=hostnet0,"
                f"hostfwd=tcp:{self.ssh_address}:{self.ssh_port}-:22,"
                f"hostfwd=tcp:{self.web_address}:{self.web_port}-:9090 "
                "-device virtio-net-pci,netdev=hostnet0,id=net0' "
                f"--initrd-inject {os.getcwd()}/test/ks.cfg "
                "--extra-args 'inst.ks=file:/ks.cfg' "
                "--disk size=10,format=qcow2 "
                f"--location {os.getcwd()}/bots/images/{self.image}"
            )
            Machine.wait_boot(self)

            # For the non-remote installations cockpit-desktop is used to host the WebUI
            # Spawn a cockpit-ws process to allow us unsafe remote access to the anaconda-webui to enable testing
            if Machine.wait_execute(self, timeout_sec=15):
                Machine.execute(self, command="/usr/libexec/cockpit-ws --no-tls --port 9090 --local-session=cockpit-bridge &>/dev/null &")
            else:
                raise Exception("Unable to reach machine {0} via ssh: {1}:{2}".format(
                                self.label, self.ssh_address, self.ssh_port))
        except Exception as e:
            self.kill()
            raise e

    def kill(self):
        self._execute(f"virsh -q -c qemu:///session destroy {self.label} || true")
        self._execute(
            f"virsh -q -c qemu:///session undefine "
            f"--remove-all-storage {self.label} || true"
        )
        if self.http_server:
            self.http_server.kill()
