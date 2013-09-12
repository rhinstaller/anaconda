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
#            Chris Lumens <clumens@redhat.com>
#

import os
from pyanaconda.constants import ROOT_PATH, RUNLEVELS

import logging
log = logging.getLogger("anaconda")

class Desktop(object):
    def __init__(self):
        self._runlevel = 3
        self.desktop = None

    @property
    def runlevel(self):
        return self._runlevel

    @runlevel.setter
    def runlevel(self, runlevel):
        if int(runlevel) not in RUNLEVELS:
            raise RuntimeError("Desktop::setDefaultRunLevel() - Must specify runlevel as one of %s" % RUNLEVELS.keys())

        self._runlevel = runlevel

    def write(self):
        if self.desktop:
            with open(ROOT_PATH + "/etc/sysconfig/desktop", "w") as f:
                f.write("DESKTOP=%s\n" % self.desktop)

        if not os.path.isdir(ROOT_PATH + '/etc/systemd/system'):
            log.warning("there is no /etc/systemd/system directory, cannot update default.target!")
            return

        default_target = ROOT_PATH + '/etc/systemd/system/default.target'
        if os.path.islink(default_target):
            os.unlink(default_target)
        os.symlink('/lib/systemd/system/%s' % RUNLEVELS[self.runlevel],
                   default_target)
