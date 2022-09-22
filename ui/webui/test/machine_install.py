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
import time

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
                f"'inst.sshd inst.webui.remote inst.webui inst.updates=http://10.0.2.2:{http_port}/updates.img' "
                "--network none "
                f"--qemu-commandline="
                "'-netdev user,id=hostnet0,"
                f"hostfwd=tcp:{self.ssh_address}:{self.ssh_port}-:22,"
                f"hostfwd=tcp:{self.web_address}:{self.web_port}-:9090 "
                "-device virtio-net-pci,netdev=hostnet0,id=net0,addr=0x4' "
                f"--initrd-inject {os.getcwd()}/test/ks.cfg "
                "--extra-args 'inst.ks=file:/ks.cfg' "
                "--disk size=15,format=qcow2 "
                f"--location {os.getcwd()}/bots/images/{self.image}"
            )
            Machine.wait_boot(self)

            for _ in range(30):
                try:
                    Machine.execute(self, "journalctl -t anaconda | grep 'anaconda: ui.webui: cockpit web view has been started'")
                    break
                except subprocess.CalledProcessError:
                    time.sleep(10)
            else:
                raise Exception("Webui initialization did not finish")

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

    # pylint: disable=arguments-differ  # this fails locally if you have bots checked out
    def add_disk(self, size=2):
        image = f"/var/tmp/disk-{self.label}.qcow2"

        self._execute(f"qemu-img create -f qcow2 {image} {size}G")
        self._execute(f"virt-xml -c qemu:///session {self.label} --update --add-device --disk {image},format=qcow2,size={size}")

    # pylint: disable=arguments-differ  # this fails locally if you have bots checked out
    def wait_poweroff(self):
        for _ in range(10):
            try:
                self._execute(f"virsh -q -c qemu:///session domstate {self.label} | grep 'shut off'")
                Machine.disconnect(self)
                break
            except subprocess.CalledProcessError:
                time.sleep(2)
        else:
            raise Exception("Test VM did not shut off")
