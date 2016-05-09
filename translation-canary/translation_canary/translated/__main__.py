# Entry point for testing translations
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

import sys, argparse
from . import testSourceTree

ap = argparse.ArgumentParser(description='Validate translated strings')
ap.add_argument('--release', action='store_true', default=False,
        help='Run in release mode')
ap.add_argument('--test', dest='release', action='store_false',
        help='Run in test mode')
ap.add_argument('--no-modify-linguas', dest='modify_linguas', action='store_false', default=True,
        help='In release mode, do not remove failing translation from LINGUAS')
ap.add_argument('source_trees', metavar='SOURCE-TREE', nargs='+',
        help='Source directory to test')

args = ap.parse_args()

status = 0
for srcdir in args.source_trees:
    if not testSourceTree(srcdir, args.release, args.modify_linguas):
        status = 1

sys.exit(status)
