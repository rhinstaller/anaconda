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
from pyanaconda.modules.common.base import KickstartBaseModule

__all__ = ["RuntimeCommandsModule"]


class RuntimeCommandsModule(KickstartBaseModule):
    """The Runtime commands module."""

    def __init__(self):
        super().__init__()
        self._logging_host = None
        self._logging_port = None
        self._rescue = False
        self._rescue_nomount = False
        self._rescue_romount = False
        self._eula_agreed = False

    def process_kickstart(self, data):
        """Process the kickstart data."""
        self._logging_host = data.logging.host
        self._logging_port = data.logging.port
        self._rescue = data.rescue.rescue
        self._rescue_nomount = data.rescue.nomount
        self._rescue_romount = data.rescue.romount
        self._eula_agreed = data.eula.agreed

    def setup_kickstart(self, data):
        """Set up the kickstart data."""
        data.logging.host = self._logging_host
        data.logging.port = self._logging_port
        data.rescue.rescue = self._rescue
        data.rescue.nomount = self._rescue_nomount
        data.rescue.romount = self._rescue_romount
        data.eula.agreed = self._eula_agreed
