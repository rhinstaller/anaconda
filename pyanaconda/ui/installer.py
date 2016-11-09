# The installer class.
#
# Copyright (C) 2016  Red Hat, Inc.
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
# Author(s):  Vendula Poncova <vponcova@redhat.com>
#
import logging

log = logging.getLogger("anaconda")


class Installer(object):
    """The class for instalation of the configuration."""

    def __init__(self, config):
        self._data = config.data
        self._storage = config.storage
        self._payload = config.payload
        self._instclass = config.instclass

    def start_installation(self):
        """First step of the installation."""
        pass

    def install_system(self):
        """Second step of the installation."""
        from pyanaconda.threads import threadMgr, AnacondaThread
        from pyanaconda.constants import THREAD_INSTALL
        from pyanaconda.install import doInstall

        threadMgr.add(AnacondaThread(name=THREAD_INSTALL, target=doInstall,
                                     args=(self._storage, self._payload,
                                           self._data, self._instclass)))

    def configure_system(self):
        """Third step of the installation."""
        from pyanaconda.threads import threadMgr, AnacondaThread
        from pyanaconda.constants import THREAD_CONFIGURATION
        from pyanaconda.install import doConfiguration

        threadMgr.add(AnacondaThread(name=THREAD_CONFIGURATION, target=doConfiguration,
                                     args=(self._storage, self._payload,
                                           self._data, self._instclass)))

    def finish_installation(self):
        """First step of the installation."""
        from pyanaconda.constants import IPMI_FINISHED
        from pyanaconda import iutil

        iutil.ipmi_report(IPMI_FINISHED)
