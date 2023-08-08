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
import tempfile

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
from machine_core import timeout

# This env variable must be always set for anaconda webui tests.
# In the anaconda environment /run/nologin always exists however cockpit test
# suite expects it to not exist
os.environ["TEST_ALLOW_NOLOGIN"] = "true"


class VirtInstallMachine(VirtMachine):
    http_server = None

    def _execute(self, cmd):
        return subprocess.check_call(cmd, stderr=subprocess.STDOUT, shell=True)

    def _get_free_port(self, start_port=8000):
        port = start_port
        while True:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                if not (sock.connect_ex(('127.0.0.1', port)) == 0):
                    return port
            port = port + 1

    def _create_disk_image(self, size, image_path=None, quiet=False):
        if not image_path:
            _, image_path = tempfile.mkstemp(suffix='.qcow2', prefix=f"disk-anaconda-{self.label}", dir=self.run_dir)
        quiet = "-q" if quiet else ""
        self._execute(f"qemu-img create -f qcow2 {quiet} {image_path} {size}G")
        return image_path

    def _wait_http_server_running(self, port):
        WAIT_HTTP_RUNNING = """
        until curl --insecure --silent --max-time 3 http://localhost:%s >/dev/null; do
            sleep 0.5;
        done;
        """ % (port)
        with timeout.Timeout(seconds=50, error_message="Timeout while waiting for http server to start"):
            self._execute(WAIT_HTTP_RUNNING)

    def _serve_updates_img(self):
        http_port = self._get_free_port()
        self.http_server = subprocess.Popen(["python3", "-m", "http.server", "-d", ANACONDA_ROOT_DIR, str(http_port)])
        self._wait_http_server_running(http_port)

        return http_port

    def _serve_payload(self):
        payload_cached_path = os.path.realpath(os.path.join(BOTS_DIR, "./images/fedora-rawhide-anaconda-payload"))
        payload_cached_dir = os.path.dirname(payload_cached_path)
        payload_cached_name = os.path.basename(payload_cached_path)

        http_payload_port = self._get_free_port()
        self.http_payload_server = subprocess.Popen(["python3", "-m", "http.server", "-d", payload_cached_dir, str(http_payload_port)])
        self._wait_http_server_running(http_payload_port)

        return payload_cached_name, http_payload_port

    def _get_payload_ks_path(self, payload_cached_name, http_payload_port):
        payload_ks_fd, payload_ks_path = tempfile.mkstemp(
            suffix='.cfg',
            prefix=f"ks-{self.label}",
            dir=os.path.join(ANACONDA_ROOT_DIR, "./ui/webui/test")
        )
        with os.fdopen(payload_ks_fd, 'w') as f:
            f.write(f'liveimg --url="http://10.0.2.2:{http_payload_port}/{payload_cached_name}"')

        return payload_ks_path

    def start(self):
        update_img_file = os.path.join(ANACONDA_ROOT_DIR, "updates.img")
        if not os.path.exists(update_img_file):
            raise FileNotFoundError("Missing updates.img file")

        self.http_port = self._serve_updates_img()

        payload_cached_name, http_payload_port = self._serve_payload()
        self.payload_ks_path = self._get_payload_ks_path(payload_cached_name, http_payload_port)

        disk_image = self._create_disk_image(15, quiet=True)

        try:
            self._execute(
                "virt-install "
                "--wait "
                "--connect qemu:///session "
                "--quiet "
                f"--name {self.label} "
                f"--os-variant=detect=on "
                "--memory 2048 "
                "--noautoconsole "
                f"--graphics vnc,listen={self.ssh_address} "
                "--extra-args "
                f"'inst.sshd inst.webui.remote inst.webui inst.updates=http://10.0.2.2:{self.http_port}/updates.img' "
                "--network none "
                f"--qemu-commandline="
                "'-netdev user,id=hostnet0,"
                f"hostfwd=tcp:{self.ssh_address}:{self.ssh_port}-:22,"
                f"hostfwd=tcp:{self.web_address}:{self.web_port}-:80 "
                "-device virtio-net-pci,netdev=hostnet0,id=net0,addr=0x4' "
                f"--initrd-inject {self.payload_ks_path} "
                f"--extra-args 'inst.ks=file:/{os.path.basename(self.payload_ks_path)}' "
                f"--disk path={disk_image},bus=virtio,cache=unsafe "
                f"--location {os.getcwd()}/bots/images/{self.image} &"
            )
            Machine.wait_boot(self)

            for _ in range(30):
                try:
                    Machine.execute(self, "journalctl -t anaconda | grep 'anaconda: ui.webui: cockpit web view has been started'")
                    break
                except subprocess.CalledProcessError:
                    time.sleep(10)
            else:
                raise AssertionError("Webui initialization did not finish")

            # Symlink /usr/share/cockpit to /usr/local/share/cockpit so that rsync works without killing cockpit-bridge
            Machine.execute(self, "mkdir -p /usr/local/share/cockpit/anaconda-webui && mount --bind /usr/share/cockpit /usr/local/share/cockpit")
        except Exception as e:
            self.kill()
            raise e

    def kill(self):
        self._execute(f"virsh -q -c qemu:///session destroy {self.label} || true")
        self._execute(
            f"virsh -q -c qemu:///session undefine "
            f"--remove-all-storage {self.label} || true"
        )
        os.remove(self.payload_ks_path)
        if self.http_server:
            self.http_server.kill()
        if self.http_payload_server:
            self.http_payload_server.kill()

    # pylint: disable=arguments-differ  # this fails locally if you have bots checked out
    def add_disk(self, size=2):
        image = self._create_disk_image(size)
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
            raise AssertionError("Test VM did not shut off")
