#
# Setup and install Flatpaks to the prepared (installed) system.
#
# Copyright (C) 2019  Red Hat, Inc.
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
import os
import gi

gi.require_version("Flatpak", "1.0")
gi.require_version("Gio", "2.0")

from gi.repository.Flatpak import Transaction, Installation, Remote
from gi.repository.Gio import File


class FlatpakPayload(object):
    """Main class to handle flatpak installation and management."""

    def __init__(self, sysroot):
        """Create and initialize this class.

        This flatpak implementation works on a repository stored in the stage2 image specifically
        for the SilverBlue image. It will be used from the ostree payload after the installation.
        This is a temporal solution for SilverBlue use-case. It will be extended as full featured
        payload in the future.

        :param sysroot: path to the system root
        :type sysroot: str
        """
        self._remote_path = "/flatpak/repo"
        self._install_path = os.path.join(sysroot, "var/lib/flatpak")

        self._transaction = None

    @property
    def remote_path(self):
        """Path to the remote repository."""
        return self._remote_path

    @remote_path.setter
    def remote_path(self, value):
        """"Set path to the remote repository."""
        self.remote_path = value

    def setup(self):
        """Create flatpak objects and set them correct values.

        We know where is the fixed position of the repository so everything will be fixed here.
        """
        remote = self._create_flatpak_remote()

        installation = self._create_flatpak_installation(remote)

        self._transaction = self._create_flatpak_transaction(installation)

    def _create_flatpak_remote(self):
        remote = Remote.new("Anaconda")
        remote.set_gpg_verify(False)
        remote.set_url("file://{}".format(self.remote_path))

        return remote

    def _create_flatpak_installation(self, remote):
        install_path = File.new_for_path(self._install_path)
        installation = Installation.new_for_path(install_path, False, None)
        installation.add_remote(remote, False, None)

        return installation

    def _create_flatpak_transaction(self, installation):
        return Transaction.new_for_installation(installation)

    def is_available(self):
        """Test if flatpak installation source is available.

        :return: bool
        """
        return os.path.isdir(self.remote_path)
