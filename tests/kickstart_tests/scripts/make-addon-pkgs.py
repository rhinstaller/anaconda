#!/usr/bin/python3
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

# This script creates all the packages used by nfs-repo-and-addon.ks.
# The packages are created in two directories, http and nfs. After all the rpms
# are made just copy everything to the locations set in $KSTEST_ADDON_HTTP_REPO
# and $KSTEST_ADDON_NFS_REPO.
#
# This script imports things from tests/lib/mkdud.py, so tests/lib needs to be
# in $PYTHONPATH.

# Ignore interuptible calls
# pylint: disable=interruptible-system-call

import os
from subprocess import check_call
from mkdud import make_rpm
import rpmfluff

# Start with http
os.mkdir('http')

# Empty package to be added to @core
pkg = rpmfluff.SimpleRpmBuild('testpkg-http-core', '1.0', '1')
make_rpm(pkg, 'http')

# Another empty package
pkg = rpmfluff.SimpleRpmBuild('testpkg-http-addon', '1.0', '1')
make_rpm(pkg, 'http')

# Three packages with marker files
pkg = rpmfluff.SimpleRpmBuild('testpkg-share1', '1.0', '1')
pkg.add_installed_file('/usr/share/testpkg-1/http',
        rpmfluff.SourceFile('http', ''))
make_rpm(pkg, 'http')

pkg = rpmfluff.SimpleRpmBuild('testpkg-share2', '1.0', '1')
pkg.add_installed_file('/usr/share/testpkg-2/http',
        rpmfluff.SourceFile('http', ''))
make_rpm(pkg, 'http')

pkg = rpmfluff.SimpleRpmBuild('testpkg-share3', '1.0', '1')
pkg.add_installed_file('/usr/share/testpkg-3/http',
        rpmfluff.SourceFile('http', ''))
make_rpm(pkg, 'http')

# Create a comps file and create the repo
with open('http/comps.xml', 'wt') as comps:
    comps.write('''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE comps PUBLIC "-//Red Hat, Inc.//DTD Comps info//EN" "comps.dtd">
<comps>
  <group>
    <id>core</id>
    <packagelist>
      <packagereq type="mandatory">testpkg-http-core</packagereq>
    </packagelist>
  </group>
</comps>''')

check_call(['createrepo_c', '-g', 'comps.xml', 'http'])

# Do the same thing again for nfs
os.mkdir('nfs')

# Empty package to be added to @core
pkg = rpmfluff.SimpleRpmBuild('testpkg-nfs-core', '1.0', '1')
make_rpm(pkg, 'nfs')

# Another empty package
pkg = rpmfluff.SimpleRpmBuild('testpkg-nfs-addon', '1.0', '1')
make_rpm(pkg, 'nfs')

# Three packages with marker files
pkg = rpmfluff.SimpleRpmBuild('testpkg-share1', '1.0', '1')
pkg.add_installed_file('/usr/share/testpkg-1/nfs',
        rpmfluff.SourceFile('nfs', ''))
make_rpm(pkg, 'nfs')

pkg = rpmfluff.SimpleRpmBuild('testpkg-share2', '1.0', '1')
pkg.add_installed_file('/usr/share/testpkg-2/nfs',
        rpmfluff.SourceFile('nfs', ''))
make_rpm(pkg, 'nfs')

pkg = rpmfluff.SimpleRpmBuild('testpkg-share3', '1.0', '1')
pkg.add_installed_file('/usr/share/testpkg-3/nfs',
        rpmfluff.SourceFile('nfs', ''))
make_rpm(pkg, 'nfs')

# Create a comps file and create the repo
with open('nfs/comps.xml', 'wt') as comps:
    comps.write('''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE comps PUBLIC "-//Red Hat, Inc.//DTD Comps info//EN" "comps.dtd">
<comps>
  <group>
    <id>core</id>
    <packagelist>
      <packagereq type="mandatory">testpkg-nfs-core</packagereq>
    </packagelist>
  </group>
</comps>''')

check_call(['createrepo_c', '-g', 'comps.xml', 'nfs'])
