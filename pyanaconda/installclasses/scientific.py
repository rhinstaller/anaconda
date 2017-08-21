#
# scientific.py
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

from pyanaconda.installclasses.rhel import RHELBaseInstallClass
from pyanaconda.product import productName

__all__ = ["ScientificBaseInstallClass"]


class ScientificBaseInstallClass(RHELBaseInstallClass):
    '''
        Scientific Linux is a Free RHEL rebuild.
        In general it should install mostly like RHEL.

        These few items are different between them.
    '''
    name = "Scientific Linux"

    hidden = not productName.startswith("Scientific")  # pylint: disable=no-member

    installUpdates = True

    efi_dir = "scientific"

    help_placeholder = "SLPlaceholder.html"
    help_placeholder_with_links = "SLPlaceholder.html"

    def __init__(self):
        RHELBaseInstallClass.__init__(self)
