#
# desktop.py - install data for default desktop and run level
#
# Copyright (C) 2001, 2002  Red Hat, Inc.  All rights reserved.
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
# Author(s): Matt Wilson <msw@redhat.com>
#

import os
from simpleconfig import SimpleConfigFile
from pyanaconda.constants import ROOT_PATH, RUNLEVELS

import logging
log = logging.getLogger("anaconda")

class Desktop(SimpleConfigFile):
#
# This class represents the default desktop to run and the default runlevel
# to start in
#
    def setDefaultRunLevel(self, runlevel):
        if int(runlevel) not in RUNLEVELS:
            raise RuntimeError, "Desktop::setDefaultRunLevel() - Must specify runlevel as 3 or 5!"
        self.runlevel = runlevel

    def getDefaultRunLevel(self):
        return self.runlevel

    def setDefaultDesktop(self, desktop):
        self.info["DESKTOP"] = desktop

    def getDefaultDesktop(self):
        return self.get("DESKTOP")

    def __init__(self):
        super(Desktop, self).__init__()
        self.runlevel = 3

    def write(self):
        if self.getDefaultDesktop():
            f = open(ROOT_PATH + "/etc/sysconfig/desktop", "w")
            f.write(str(self))
            f.close()

        if not os.path.isdir(ROOT_PATH + '/etc/systemd/system'):
            log.warning("there is no /etc/systemd/system directory, cannot update default.target!")
            return
        default_target = ROOT_PATH + '/etc/systemd/system/default.target'
        if os.path.islink(default_target):
            os.unlink(default_target)
        os.symlink('/lib/systemd/system/%s' % RUNLEVELS[self.runlevel],
                   default_target)
