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

import unittest

from pyanaconda import argument_parsing
from pyanaconda.core.configuration.anaconda import AnacondaConfiguration
from pyanaconda.core.constants import DisplayModes
from pyanaconda.core.kernel import KernelArguments


class ArgparseTest(unittest.TestCase):
    def _parseCmdline(self, argv, version="", boot_cmdline=None):
        ap = argument_parsing.getArgumentParser(version, boot_cmdline)
        opts = ap.parse_args(argv, boot_cmdline=boot_cmdline)
        return (opts, ap.removed_no_inst_bootargs)

    def test_without_inst_prefix(self):
        boot_cmdline = KernelArguments.from_string("stage2=http://cool.server.com/test")
        opts, removed = self._parseCmdline([], boot_cmdline=boot_cmdline)
        assert opts.stage2 is None
        assert removed == ["stage2"]

        boot_cmdline = KernelArguments.from_string("stage2=http://cool.server.com/test "
                                                   "vnc")
        opts, removed = self._parseCmdline([], boot_cmdline=boot_cmdline)
        assert opts.stage2 is None
        assert not opts.vnc
        assert removed == ["stage2", "vnc"]

    def test_with_inst_prefix(self):
        boot_cmdline = KernelArguments.from_string("inst.stage2=http://cool.server.com/test")
        opts, removed = self._parseCmdline([], boot_cmdline=boot_cmdline)
        assert opts.stage2 == "http://cool.server.com/test"
        assert removed == []

        boot_cmdline = KernelArguments.from_string("inst.stage2=http://cool.server.com/test "
                                                   "inst.vnc")
        opts, removed = self._parseCmdline([], boot_cmdline=boot_cmdline)
        assert opts.stage2 == "http://cool.server.com/test"
        assert opts.vnc
        assert removed == []

    def test_inst_prefix_mixed(self):
        boot_cmdline = KernelArguments.from_string("inst.stage2=http://cool.server.com/test "
                                                   "vnc")
        opts, removed = self._parseCmdline([], boot_cmdline=boot_cmdline)
        assert opts.stage2 == "http://cool.server.com/test"
        assert not opts.vnc
        assert removed == ["vnc"]

    def test_display_mode(self):
        opts, _removed = self._parseCmdline(['--cmdline'])
        assert opts.display_mode == DisplayModes.TUI
        assert opts.noninteractive

        opts, _removed = self._parseCmdline(['--graphical'])
        assert opts.display_mode == DisplayModes.GUI
        assert not opts.noninteractive

        opts, _removed = self._parseCmdline(['--text'])
        assert opts.display_mode == DisplayModes.TUI
        assert not opts.noninteractive

        opts, _removed = self._parseCmdline(['--noninteractive'])
        assert opts.noninteractive

        # Test the default
        opts, _removed = self._parseCmdline([])
        assert opts.display_mode == DisplayModes.GUI
        assert not opts.noninteractive

        # console=whatever in the boot args defaults to --text
        boot_cmdline = KernelArguments.from_string("console=/dev/ttyS0")
        opts, _removed = self._parseCmdline([], boot_cmdline=boot_cmdline)
        assert opts.display_mode == DisplayModes.TUI

    def test_selinux(self):
        from pykickstart.constants import SELINUX_DISABLED, SELINUX_ENFORCING

        from pyanaconda.core.constants import SELINUX_DEFAULT

        # with no arguments, use SELINUX_DEFAULT
        opts, _removed = self._parseCmdline([])
        assert opts.selinux == SELINUX_DEFAULT

        # --selinux or --selinux=1 means SELINUX_ENFORCING
        opts, _removed = self._parseCmdline(['--selinux'])
        assert opts.selinux == SELINUX_ENFORCING

        # --selinux=0 means SELINUX_DISABLED
        opts, _removed = self._parseCmdline(['--selinux=0'])
        assert opts.selinux == SELINUX_DISABLED

        # --noselinux means SELINUX_DISABLED
        opts, _removed = self._parseCmdline(['--noselinux'])
        assert opts.selinux == SELINUX_DISABLED

    def test_dirinstall(self):
        # when not specified, dirinstall should evaluate to False
        opts, _removed = self._parseCmdline([])
        assert not opts.dirinstall

        # with no argument, dirinstall should default to /mnt/sysimage
        opts, _removed = self._parseCmdline(['--dirinstall'])
        assert opts.dirinstall == "/mnt/sysimage"

        # with an argument, dirinstall should use that
        opts, _removed = self._parseCmdline(['--dirinstall=/what/ever'])
        assert opts.dirinstall == "/what/ever"

    def test_storage(self):
        conf = AnacondaConfiguration.from_defaults()

        opts, _removed = self._parseCmdline([])
        conf.set_from_opts(opts)

        assert conf.storage.dmraid is True
        assert conf.storage.ibft is True

        opts, _removed = self._parseCmdline(['--nodmraid', '--ibft'])
        conf.set_from_opts(opts)

        assert conf.storage.dmraid is False
        assert conf.storage.ibft is True

    def test_target(self):
        conf = AnacondaConfiguration.from_defaults()

        opts, _removed = self._parseCmdline([])
        conf.set_from_opts(opts)

        assert conf.target.is_hardware is True
        assert conf.target.is_image is False
        assert conf.target.is_directory is False
        assert conf.target.physical_root == "/mnt/sysimage"

        opts, _removed = self._parseCmdline(['--image=/what/ever.img'])
        conf.set_from_opts(opts)

        assert conf.target.is_hardware is False
        assert conf.target.is_image is True
        assert conf.target.is_directory is False
        assert conf.target.physical_root == "/mnt/sysimage"

        opts, _removed = self._parseCmdline(['--dirinstall=/what/ever'])
        conf.set_from_opts(opts)

        assert conf.target.is_hardware is False
        assert conf.target.is_image is False
        assert conf.target.is_directory is True
        assert conf.target.physical_root == "/what/ever"

    def test_system(self):
        conf = AnacondaConfiguration.from_defaults()

        opts, _removed = self._parseCmdline([])
        conf.set_from_opts(opts)

        assert conf.system._is_boot_iso is True
        assert conf.system._is_live_os is False
        assert conf.system._is_unknown is False

        opts, _removed = self._parseCmdline(['--liveinst'])
        conf.set_from_opts(opts)

        assert conf.system._is_boot_iso is False
        assert conf.system._is_live_os is True
        assert conf.system._is_unknown is False

        opts, _removed = self._parseCmdline(['--dirinstall=/what/ever'])
        conf.set_from_opts(opts)

        assert conf.system._is_boot_iso is False
        assert conf.system._is_live_os is False
        assert conf.system._is_unknown is True

        opts, _removed = self._parseCmdline(['--image=/what/ever.img'])
        conf.set_from_opts(opts)

        assert conf.system._is_boot_iso is False
        assert conf.system._is_live_os is False
        assert conf.system._is_unknown is True
