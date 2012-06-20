#
# script.py - non-interactive, script based anaconda interface
#
# Copyright (C) 2011
# Red Hat, Inc.  All rights reserved.
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
# Author(s): Brian C. Lane <bcl@redhat.com>
#

from installinterfacebase import InstallInterfaceBase
import cmdline
from cmdline import setupProgressDisplay

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("anaconda")

stepToClasses = { "install" : "setupProgressDisplay",
                  "complete": "Finished" }

class InstallInterface(cmdline.InstallInterface):
    def enableNetwork(self):
        # Assume we want networking
        return True

    def display_step(self, step):
        if stepToClasses.has_key(step):
            s = "nextWin = %s" % (stepToClasses[step],)
            exec s
            nextWin(self.anaconda)
        else:
            errtxt = _("In interactive step can't continue. (%s)" % (step,))
            print(errtxt)
            raise RuntimeError(errtxt)

def Finished(anaconda):
    """ Install is finished. Lets just exit.
    """
    return 0

