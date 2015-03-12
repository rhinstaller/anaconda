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
# Red Hat Author(s): David Shea <dshea@redhat.com>

kernel_args() {
    echo vnc
}

prepare() {
    ks=$1
    tmpdir=$2

    if [[ "${TEST_ADDON_NFS_REPO}" == "" ]]; then
        echo \$TEST_ADDON_NFS_REPO is not set.
        return 1
    fi

    if [[ "${TEST_ADDON_HTTP_REPO}" == "" ]]; then
        echo \$TEST_ADDON_HTTP_REPO is not set.
        return 1
    fi

    if [[ "${TEST_NFS_SERVER}" == "" ]]; then
        echo \$TEST_NFS_SERVER is not set
        return 1
    fi

    if [[ "${TEST_NFS_PATH}" == "" ]]; then
        echo \$TEST_NFS_PATH is not set
        return 1
    fi

    sed -e "/^nfs/ s|NFS-SERVER|${TEST_NFS_SERVER}|" \
        -e "/^nfs/ s|NFS-PATH|${TEST_NFS_PATH}|" \
        -e "/^repo/ s|NFS-ADDON-REPO|${TEST_ADDON_NFS_REPO}|" \
        -e "/^repo/ s|HTTP-ADDON-REPO|${TEST_ADDON_HTTP_REPO}|" ${ks} > ${tmpdir}/kickstart.ks
    echo ${tmpdir}/kickstart.ks
}

validate() {
    img=$1

    # Check the /root/RESULT file for whether the test succeeded or not
    result=$(virt-cat -a ${img} -m /dev/sda2 /root/RESULT)
    if [[ $? != 0 ]]; then
        status=1
        echo '*** /root/RESULT does not exist in VM image.'
    elif [[ "${result}" != "SUCCESS" ]]; then
        status=1
        echo "${result}"
    fi

    return ${status}
}
