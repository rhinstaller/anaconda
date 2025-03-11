#
# The user interface module
#
# Copyright (C) 2023 Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from collections import namedtuple

from pyanaconda.modules.common.base import KickstartBaseModule

__all__ = ["DracutCommandsModule"]


DriverDiskLocalData = namedtuple("DriverDiskLocalData", ["partition", "source", "biospart"])
SshPwLocalData = namedtuple("SshPwLocalData", ["username", "is_crypted", "password", "lock"])


class DracutCommandsModule(KickstartBaseModule):
    """The dracut-only commands module.

    This module only stores data for these commands during the anaconda session. The data is not
    externally accessible. Thus, this module is also interface-less.
    """
    def __init__(self):
        super().__init__()
        self._driverdisks = []
        self._ssh_pws = []
        self._mediacheck = False
        self._updates_url = ""

    def process_kickstart(self, data):
        """Process the kickstart data."""
        for ks_dd_data in data.driverdisk.driverdiskList:
            dd_data = DriverDiskLocalData(
                ks_dd_data.partition,
                ks_dd_data.source,
                ks_dd_data.biospart
            )
            self._driverdisks.append(dd_data)

        for ks_sshpw_data in data.sshpw.sshUserList:
            sshpw_data = SshPwLocalData(
                ks_sshpw_data.username,
                ks_sshpw_data.isCrypted,
                ks_sshpw_data.password,
                ks_sshpw_data.lock
            )
            self._ssh_pws.append(sshpw_data)

        self._mediacheck = data.mediacheck.mediacheck
        self._updates_url = data.updates.url

    def setup_kickstart(self, data):
        """Set up the kickstart data."""
        for dd_data in self._driverdisks:
            ks_dd_data = data.DriverDiskData()
            ks_dd_data.partition = dd_data.partition
            ks_dd_data.source = dd_data.source
            ks_dd_data.biospart = dd_data.biospart
            data.driverdisk.driverdiskList.append(ks_dd_data)

        for sshpw_data in self._ssh_pws:
            ks_sshpw_data = data.SshPwData()
            ks_sshpw_data.username = sshpw_data.username
            ks_sshpw_data.isCrypted = sshpw_data.is_crypted
            ks_sshpw_data.password = sshpw_data.password
            ks_sshpw_data.lock = sshpw_data.lock
            data.sshpw.sshUserList.append(ks_sshpw_data)

        data.mediacheck.mediacheck = self._mediacheck
        data.updates.url = self._updates_url
