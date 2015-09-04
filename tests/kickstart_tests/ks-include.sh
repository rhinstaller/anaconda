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

TESTTYPE="kickstart"

. ${KSTESTDIR}/functions.sh

prepare() {
    ks=$1
    tmpdir=$2

    # Copy the included kickstart to a directory in tmpdir
    mkdir ${tmpdir}/http
    cp $(dirname ${ks})/ks-include-post.ks ${tmpdir}/http

    # Start a http server to serve the included file
    start_httpd ${tmpdir}/http $tmpdir

    # Set the URL of the included file
    sed -e "/^%include/ s|KS-TEST-INCLUDE|${httpd_url}/ks-include-post.ks|" ${ks} > ${tmpdir}/ks.cfg
    echo ${tmpdir}/ks.cfg
}

cleanup() {
    tmpdir=$1

    if [ -f ${tmpdir}/httpd-pid ]; then
        kill $(cat ${tmpdir}/httpd-pid)
    fi
}
