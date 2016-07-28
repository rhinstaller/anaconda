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

import os
from pyanaconda.constants import TEXT_ONLY_TARGET, GRAPHICAL_TARGET
from pyanaconda import iutil

import logging
log = logging.getLogger("anaconda")

class Desktop(object):
    def __init__(self):
        self._default_target = TEXT_ONLY_TARGET
        self.desktop = None

    @property
    def default_target(self):
        return self._default_target

    @default_target.setter
    def default_target(self, target):
        supported_targets = [TEXT_ONLY_TARGET, GRAPHICAL_TARGET]
        if target not in supported_targets:
            raise RuntimeError("Desktop::default_target - Must specify a systemd default target"
                               "as one of %s" % supported_targets)
        else:
            log.debug("Setting systemd default target to: %s", target)

        self._default_target = target

    def write(self):
        """Write the desktop & default target settings to disk."""
        if self.desktop:
            with open(iutil.getSysroot() + "/etc/sysconfig/desktop", "w") as f:
                f.write("DESKTOP=%s\n" % self.desktop)

        if not os.path.isdir(iutil.getSysroot() + '/etc/systemd/system'):
            log.warning("There is no /etc/systemd/system directory, cannot update default.target!")
            return

        default_target = iutil.getSysroot() + '/etc/systemd/system/default.target'
        if os.path.islink(default_target):
            os.unlink(default_target)
        os.symlink('/lib/systemd/system/%s' % self.default_target, default_target)
