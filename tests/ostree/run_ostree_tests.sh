#!/bin/bash
#
# Copyright (C) 2014  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Chris Lumens <clumens@redhat.com>

# Have to be root to run this test, as it requires creating disk iamges.
if [ ${EUID} != 0 ]; then
   exit 77
fi

# The boot.iso location can come from one of two different places:
# (1) $TEST_BOOT_ISO, if this script is being called from "make check"
# (2) The command line, if this script is being called directly.
if [[ "${TEST_BOOT_ISO}" != "" ]]; then
    IMAGE=${TEST_BOOT_ISO}
elif [[ $# != 0 ]]; then
    IMAGE=$1
    shift
fi

# The same with the ostree repo.
if [[ "${TEST_OSTREE_REPO}" != "" ]]; then
    REPO=${TEST_OSTREE_REPO}
elif [[ $# != 0 ]]; then
    REPO=$1
    shift
else
    echo "usage: $0 <boot.iso> <ostree repo>"
    exit 1
fi

if [ ! -e "${IMAGE}" ]; then
    echo "Required boot.iso does not exist."
    exit 2
fi

logdir=$(mktemp -d)

status=0
for ks in ostree/*ks; do
    # Substitute in the location of an ostree repo here.  This could be one
    # publically accessible, or a very local and private one that happens
    # to be fast.
    ksfile=$(mktemp)
    sed -e "/ostreesetup/ s|REPO|${REPO}|" ${ks} > ${ksfile}

    echo ${ks}
    echo ====================

    livemedia-creator --make-disk \
                      --iso "${IMAGE}" \
                      --ks ${ksfile} \
                      --tmp /var/tmp \
                      --logfile ${logdir}/livemedia.log \
                      --title Fedora \
                      --project Fedora \
                      --releasever 21 \
                      --ram 2048 \
                      --vcpus 2 \
                      --vnc vnc
    if [ $? != 0 ]; then
        status=1
        echo $(grep CRIT ${logdir}/virt-install.log)
    fi

    rm ${ksfile}

    if [ -f ostree/run_ostree_tests.log ]; then
        img=$(grep disk_img ostree/run_ostree_tests.log | cut -d= -f2)
        trimmed=${img## }

        if [ ! -f ${trimmed} ]; then
            status=1
            echo Disk image ${trimmed} does not exist.
            continue
        fi

        # Now attempt to boot the resulting VM and see if the install
        # actually worked.  The VM will shut itself down so there's no
        # need to worry with that here.
        /usr/bin/qemu-kvm -m 2048 \
                          -smp 2 \
                          -hda ${trimmed}

        # There should be a /root/RESULT file with results in it.  Check
        # its contents and decide whether the test finally succeeded or
        # not.
        result=$(virt-cat -a ${trimmed} -m /dev/sda2 /ostree/deploy/fedora-atomic/var/roothome/RESULT)
        if [ $? != 0 ]; then
            status=1
            echo /root/RESULT does not exist in VM image.
        elif [ "${result}" != "SUCCESS" ]; then
            status=1
            echo ${result}
        fi
    fi

    # Clean it up for the next go around.
    if [ -f ${trimmed} ]; then
        rm ${trimmed}
    fi
done

rm -r ${logdir}
exit $status
