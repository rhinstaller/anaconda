# Copyright (c) 2015 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author: Will Woods <wwoods@redhat.com>

. ${KSTESTDIR}/functions.sh

prepare_disks() {
    local diskdir="$1/disks"
    # main disk
    qemu-img create -q -f qcow2 ${diskdir}/a.img 10G
    echo "${diskdir}/a.img"

    # driverdisk image
    ${KSTESTDIR}/../lib/mkdud.py -k -b -L "TEST_DD" ${diskdir}/dd.iso >/dev/null
    echo "${diskdir}/dd.iso,device=cdrom,readonly=on"
}

#kernel_args() {
#    echo inst.dd=/dev/disk/by-label/TEST_DD
#}
