#!/bin/bash
#
# Copyright (C) 2015  Red Hat, Inc.
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

# This script runs a single kickstart test on a single system.  It takes
# command line arguments instead of environment variables because it is
# designed to be driven by run_kickstart_tests.sh via parallel.  It is
# not for direct use, though as long as you pass the right arguments there's
# no reason it couldn't work.

# Possible return values:
# 0  - Everything worked
# 1  - Test failed for unspecified reasons
# 2  - Test failed due to time out
# 77 - Something needed by the test doesn't exist, so skip

IMAGE=
KEEPIT=0

cleanup() {
    d=$1

    # Always remove the copy of the boot.iso.
    rm ${d}/$(basename ${IMAGE})

    if [[ ${KEEPIT} == 2 ]]; then
        return
    elif [[ ${KEEPIT} == 1 ]]; then
        rm -f ${d}/disk-*.img ${d}/*ks
    elif [[ ${KEEPIT} == 0 ]]; then
        rm -rf ${d}
    fi
}

runone() {
    t=$1

    export KSTESTDIR=$(pwd)/kickstart_tests

    ks=${t/.sh/.ks}
    . $t

    name=$(basename ${t%.sh})

    echo
    echo ===========================================================================
    echo ${ks} on $(hostname)
    echo ===========================================================================

    # qemu user needs to be able to read the directory and the boot.iso, so put that
    # into this directory as well.  It will get deleted later, regardless of the
    # KEEPIT setting.
    tmpdir=$(mktemp -d --tmpdir=/var/tmp kstest-${name}.XXXXXXXX)
    chmod 755 ${tmpdir}
    cp ${IMAGE} ${tmpdir}

    ksfile=$(prepare ${ks} ${tmpdir})
    if [[ $? != 0 ]]; then
        echo RESULT:${name}:FAILED:Test prep failed: ${ksfile}
        cleanup ${tmpdir}
        return 1
    fi

    kargs=$(kernel_args)
    if [[ "${kargs}" != "" ]]; then
        kargs="--kernel-args \"$kargs\""
    fi

    disks=$(prepare_disks ${tmpdir})
    disk_args=$(for d in $disks; do echo --disk $d; done)

    echo "PYTHONPATH=$PYTHONPATH"
    eval ${KSTESTDIR}/kstest-runner ${kargs} \
                       --iso "${tmpdir}/$(basename ${IMAGE})" \
                       --ks ${ksfile} \
                       --tmp ${tmpdir} \
                       --logfile ${tmpdir}/livemedia.log \
                       --ram 2048 \
                       --vnc vnc \
                       --timeout 60 \
                       ${disk_args}
    if [[ -f ${tmpdir}/virt-install.log && "$(grep CRIT ${tmpdir}/virt-install.log)" != "" ]]; then
        echo RESULT:${name}:FAILED:$(grep CRIT ${tmpdir}/virt-install.log)
        cleanup ${tmpdir}
        return 1
    elif [[ -f ${tmpdir}/livemedia.log ]]; then
        if [[ "$(grep 'due to timeout' ${tmpdir}/livemedia.log)" != "" ]]; then
            echo RESULT:${name}:FAILED:Test timed out.
            cleanup ${tmpdir}
            return 2
        fi

        result=$(validate ${tmpdir})
        if [[ $? != 0 ]]; then
            echo RESULT:${name}:FAILED:"${result}"
            cleanup ${tmpdir}
            return 1
        fi
    fi

    echo RESULT:${name}:SUCCESS
    cleanup ${tmpdir}
    return 0
}

# Have to be root to run this test, as it requires creating disk images.
if [[ ${EUID} != 0 ]]; then
    echo "You must be root to run this test."
    exit 77
fi

while getopts ":i:k:" opt; do
    case $opt in
        i)
            IMAGE=$OPTARG
            ;;

        k)
            KEEPIT=$OPTARG
            ;;

        *)
            echo "Usage: run_one_ks.sh -i ISO [-k KEEPIT] ks-test.sh"
            exit 1
            ;;
    esac
done

shift $((OPTIND - 1))

if [[ ! -e "${IMAGE}" ]]; then
    echo "Required boot.iso does not exist."
    exit 77
fi

if [[ $# == 0 || ! -x $1 ]]; then
    echo "Test not provided or is not executable."
    exit 1
fi

runone $1
