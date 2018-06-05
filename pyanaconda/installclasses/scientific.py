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
from pyanaconda.kickstart import RepoData
from pyanaconda.product import productName, productVersion, productArch
from pyanaconda.payload import PackagePayload

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

    help_placeholder = "SLPlaceholder.html"
    help_placeholder_with_links = "SLPlaceholder.html"

    def configurePayload(self, payload):  # pylint: disable=line-too-long
        '''
            Load SL specific payload repos
        '''
        if isinstance(payload, PackagePayload):
            major_version = productVersion.replace('rolling','').split('.')[0]

            # A number of users like EPEL, seed it disabled
            payload.addDisabledRepo(RepoData(name='epel', metalink="https://mirrors.fedoraproject.org/metalink?repo=epel-"+major_version+"&arch="+productArch))
            # ELRepo provides handy hardware drivers, seed it disabled
            payload.addDisabledRepo(RepoData(name='elrepo', mirrorlist="http://mirrors.elrepo.org/mirrors-elrepo.el"+major_version))

        super().configurePayload(payload)
