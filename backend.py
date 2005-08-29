#
# backend.py: Interface for installation backends
#
# Paul Nasrat <pnasrat@redhat.com> 
# Copyright (c) 2005 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import logging
log = logging.getLogger("anaconda")

class AnacondaBackend:
    def __init__(self, method):
        self.method = method

    def readPackages(self, intf, id):
        """Set id.grpset and id.pkglist"""
        id.grpset = []
        id.pkglist = []

    def doPreSelection(self):
        pass

    def doPostSelection(self):
        pass

    def doPreInstall(self):
        pass

    def doPostInstall(self):
        pass
