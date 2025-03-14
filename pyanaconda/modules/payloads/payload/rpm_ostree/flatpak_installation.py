#
# Copyright (C) 2021  Red Hat, Inc.
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
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.i18n import _
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager import (
    FlatpakManager,
)

__all__ = ["InstallFlatpaksTask"]


class InstallFlatpaksTask(Task):
    """Task to install flatpaks from the local source on Silverblue."""

    def __init__(self, sysroot):
        """Create a new task.

        :param str sysroot: path to the system root
        """
        super().__init__()
        self._sysroot = sysroot

    @property
    def name(self):
        return "Install Flatpak applications"

    def run(self):
        self.report_progress(_("Installing Flatpak applications"))

        flatpak_manager = FlatpakManager(
            sysroot=self._sysroot,
            callback=self.report_progress
        )

        # Initialize new repo on the installed system
        flatpak_manager.initialize_with_system_path()
        flatpak_manager.install_all()

        self.report_progress(_("Performing post-installation Flatpak tasks"))
        remote_name, remote_url = conf.payload.flatpak_remote
        flatpak_manager.add_remote(remote_name, remote_url)
        flatpak_manager.replace_installed_refs_remote(remote_name)
        flatpak_manager.remove_remote(FlatpakManager.LOCAL_REMOTE_NAME)

        self.report_progress(_("Flatpak installation has finished"))
