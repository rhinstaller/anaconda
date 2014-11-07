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

# Have to be root to run this test, as yum is stupid.
if [ ${EUID} != 0 ]; then
   exit 77
fi

tmpdir=$(mktemp -d -p /var/tmp)

# The anaconda repo can come from one of two different places:
# (1) $TEST_ANACONDA_REPO, if this script is being called from "make check"
# (2) The command line, if this script is being called directly.
if [[ "${TEST_ANACONDA_REPO}" != "" ]]; then
    REPO=${TEST_ANACONDA_REPO}
elif [[ $# != 0 ]]; then
    REPO=$1
    shift
else
    echo "usage: $0 <anaconda repo>"
    exit 1
fi

status=0

cat <<EOF > ${tmpdir}/yum.conf
[anaconda]
name=anaconda \$releasever - \$basearch
baseurl=${REPO}
enabled=1

[anaconda-rawhide]
name=Fedora - Rawhide - Developmental packages for the next Fedora release
failovermethod=priority
baseurl=http://dl.fedoraproject.org/pub/fedora/linux/development/rawhide/\$basearch/os/
enabled=1
gpgcheck=0
EOF

yum install -y -c ${tmpdir}/yum.conf --installroot=${tmpdir} --releasever=rawhide \
            --disablerepo=\* --enablerepo=anaconda --enablerepo=anaconda-rawhide \
            anaconda
status=$?

# yum's return value is not especially helpful (it can return 0 even on error)
# but just in case it told us it failed, exit out here.
if [ $? != 0 ]; then
    rm -r ${tmpdir}
    exit $status
fi

# Did anaconda actually get installed?  At least rpm will set $?=1 if not.
rpm --root=${tmpdir} -q anaconda
status=$?

rm -r ${tmpdir}
exit $status
