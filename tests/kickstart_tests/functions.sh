#!/bin/bash
#
# Copyright (C) 2015  Red Hat, Inc.
# # This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the # source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Chris Lumens <clumens@redhat.com>

prereqs() {
    # No prereqs by default
    echo
}

kernel_args() {
    echo vnc debug=1 inst.debug
}

prepare() {
    ks=$1
    tmpdir=$2

    echo ${ks}
}

prepare_disks() {
    tmpdir=$1

    qemu-img create -q -f qcow2 ${tmpdir}/disk-a.img 10G
    echo ${tmpdir}/disk-a.img
}

validate() {
    disksdir=$1
    args=$(for d in ${disksdir}/disk-*img; do echo -a ${d}; done)

    # Grab the coverage results out of the installed system while it still
    # exists.
    virt-copy-out ${args} /root/anaconda.coverage ${disksdir}

    # There should be a /root/RESULT file with results in it.  Check
    # its contents and decide whether the test finally succeeded or
    # not.
    result=$(virt-cat ${args} -m /dev/mapper/fedora-root /root/RESULT)
    if [[ $? != 0 ]]; then
        status=1
        echo '*** /root/RESULT does not exist in VM image.'
    elif [[ "${result}" != SUCCESS* ]]; then
        status=1
        echo "${result}"
    fi

    return ${status}
}

cleanup() {
    tmpdir=$1
}

start_httpd() {
    local httpd_root=$1
    local tmpdir=$2

    # Starts a http server rooted in $httpd_root. The PID of the server will be
    # written to $tmpdir/httpd-pid, and the URL for the server will be set in
    # $httpd_url

    local scriptdir=${PWD}/kickstart_tests/scripts
    local httpd_info="$(${scriptdir}/httpd.py "${httpd_root}")"

    # Parse out the port and PID
    local httpd_port="$(echo "$httpd_info" | cut -d ' ' -f 1)"
    local httpd_pid="$(echo "$httpd_info" | cut -d ' ' -f 2)"

    # Save the PID
    echo "${httpd_pid}" > ${tmpdir}/httpd-pid

    # Construct a URL
    httpd_url="http://$(${scriptdir}/find-ip):${httpd_port}/"
}
