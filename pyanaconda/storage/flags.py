# flags.py
#
# Copyright (C) 2013  Red Hat, Inc.
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
# Red Hat Author(s): David Lehman <dlehman@redhat.com>
#

import shlex
import selinux

class Flags(object):
    def __init__(self):
        #
        # mode of operation
        #
        self.testing = False
        self.installer_mode = False

        #
        # minor modes (installer-specific)
        #
        self.automated_install = False
        self.live_install = False
        self.image_install = False

        #
        # enable/disable functionality
        #
        self.selinux = selinux.is_selinux_enabled()
        self.multipath = True
        self.dmraid = True
        self.ibft = False
        self.noiswmd = False

        self.gfs2 = True
        self.jfs = True
        self.reiserfs = True

        self.arm_platform = None

        self.gpt = False

        self.boot_cmdline = {}

        self.update_from_boot_cmdline()

    def get_boot_cmdline(self):
        buf = open("/proc/cmdline").read().strip()
        args = shlex.split(buf)
        for arg in args:
            (opt, equals, val) = arg.partition("=")
            self.boot_cmdline[opt] = val

    def update_from_boot_cmdline(self):
        self.get_boot_cmdline()
        if "nompath" in self.boot_cmdline:
            self.multipath = False

        if "nodmraid" in self.boot_cmdline:
            self.dmraid = False

        if "ibft" in self.boot_cmdline:
            self.ibft = True

        if "noiswmd" in self.boot_cmdline:
            self.noiswmd = True

    def update_from_anaconda_flags(self, anaconda_flags):
        self.installer_mode = True
        self.testing = anaconda_flags.testing
        self.automated_install = anaconda_flags.automatedInstall
        self.live_install = anaconda_flags.livecdInstall

        self.selinux = anaconda_flags.selinux

        self.gfs2 = "gfs2" in self.boot_cmdline
        self.jfs = "jfs" in self.boot_cmdline
        self.reiserfs = "reiserfs" in self.boot_cmdline

        self.arm_platform = anaconda_flags.armPlatform
        self.gpt = anaconda_flags.gpt


flags = Flags()
