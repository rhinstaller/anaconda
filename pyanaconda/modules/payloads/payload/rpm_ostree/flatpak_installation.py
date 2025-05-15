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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pyanaconda.core.i18n import _
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager import (
    FlatpakManager,
)
from pyanaconda.payload.errors import FlatpakInstallError, PayloadInstallError


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
        return "Install Flatpaks"

    def run(self):
        self.report_progress(_("Starting Flatpak installation"))

        flatpak_manager = FlatpakManager(self._sysroot)

        # Initialize new repo on the installed system
        flatpak_manager.initialize_with_system_path()

        try:
            flatpak_manager.install_all()
        except FlatpakInstallError as e:
            raise PayloadInstallError("Failed to install flatpaks: {}".format(e)) from e

        self.report_progress(_("Post-installation flatpak tasks"))

        flatpak_manager.add_remote("fedora", "oci+https://registry.fedoraproject.org")
        flatpak_manager.replace_installed_refs_remote("fedora")
        flatpak_manager.remove_remote(FlatpakManager.LOCAL_REMOTE_NAME)

        self.report_progress(_("Flatpak installation has finished"))
