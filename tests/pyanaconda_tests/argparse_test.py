# vim:set fileencoding=utf-8
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

from pyanaconda import anaconda_argparse
from pyanaconda.flags import BootArgs
import unittest

class ArgparseTest(unittest.TestCase):
    def _parseCmdline(self, argv, version="", boot_cmdline=None):
        ap = anaconda_argparse.getArgumentParser(version, boot_cmdline)
        opts = ap.parse_args(argv, boot_cmdline=boot_cmdline)
        return (opts, ap.deprecated_bootargs)

    def display_mode_test(self):
        opts, _deprecated = self._parseCmdline(['--cmdline'])
        self.assertEqual(opts.display_mode, 'c')

        opts, _deprecated = self._parseCmdline(['--graphical'])
        self.assertEqual(opts.display_mode, 'g')

        opts, _deprecated = self._parseCmdline(['--text'])
        self.assertEqual(opts.display_mode, 't')

        # Test the default
        opts, _deprecated = self._parseCmdline([])
        self.assertEqual(opts.display_mode, 'g')

        # console=whatever in the boot args defaults to --text
        opts, _deprecated = self._parseCmdline([], boot_cmdline=BootArgs("console=/dev/ttyS0"))
        self.assertEqual(opts.display_mode, 't')

    def selinux_test(self):
        from pykickstart.constants import SELINUX_DISABLED, SELINUX_ENFORCING
        from pyanaconda.constants import SELINUX_DEFAULT

        # with no arguments, use SELINUX_DEFAULT
        opts, _deprecated = self._parseCmdline([])
        self.assertEqual(opts.selinux, SELINUX_DEFAULT)

        # --selinux or --selinux=1 means SELINUX_ENFORCING
        opts, _deprecated = self._parseCmdline(['--selinux'])
        self.assertEqual(opts.selinux, SELINUX_ENFORCING)

        # --selinux=0 means SELINUX_DISABLED
        opts, _deprecated = self._parseCmdline(['--selinux=0'])
        self.assertEqual(opts.selinux, SELINUX_DISABLED)

        # --noselinux means SELINUX_DISABLED
        opts, _deprecated = self._parseCmdline(['--noselinux'])
        self.assertEqual(opts.selinux, SELINUX_DISABLED)

    def dirinstall_test(self):
        # when not specified, dirinstall should evaluate to False
        opts, _deprecated = self._parseCmdline([])
        self.assertFalse(opts.dirinstall)

        # with no argument, dirinstall should default to /mnt/sysimage
        opts, _deprecated = self._parseCmdline(['--dirinstall'])
        self.assertEqual(opts.dirinstall, "/mnt/sysimage")

        # with an argument, dirinstall should use that
        opts, _deprecated = self._parseCmdline(['--dirinstall=/what/ever'])
        self.assertEqual(opts.dirinstall, "/what/ever")
