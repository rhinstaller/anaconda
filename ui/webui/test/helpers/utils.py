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

def add_public_key(machine):
    with open(machine.identity_file + '.pub', 'r') as pub:
        public_key = pub.read()

    sysroot_ssh = '/mnt/sysroot/root/.ssh'
    authorized_keys = os.path.join(sysroot_ssh, 'authorized_keys')
    machine.execute(f"chmod 700 {sysroot_ssh}")
    machine.write(authorized_keys, public_key, perm="0600")

def pretend_live_iso(test):
    test.restore_file('/run/anaconda/anaconda.conf')
    test.machine.execute("sed -i 's/type = BOOT_ISO/type = LIVE_OS/g' /run/anaconda/anaconda.conf")

def get_pretty_name(machine):
    return machine.execute("cat /etc/os-release | grep PRETTY_NAME | cut -d '\"' -f 2 | tr -d '\n'")
