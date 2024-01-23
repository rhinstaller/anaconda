#
# flags.py: global anaconda flags
#
# Copyright (C) 2001  Red Hat, Inc.  All rights reserved.
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
from pyanaconda.core.constants import ANACONDA_ENVIRON

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


# A lot of effort, but it only allows a limited set of flags to be referenced
class Flags(object):
    def __setattr__(self, attr, val):
        # pylint: disable=no-member
        if attr not in self.__dict__ and not self._in_init:
            raise AttributeError(attr)
        else:
            self.__dict__[attr] = val

    def __init__(self):
        self.__dict__['_in_init'] = True
        self.usevnc = False
        self.vncquestion = True
        self.preexisting_x11 = False
        self.wayland = False
        self.automatedInstall = False
        self.eject = True
        # ksprompt is whether or not to prompt for missing ksdata
        self.ksprompt = True
        self.rescue_mode = False
        self.kexec = False
        # current runtime environments
        self.environs = [ANACONDA_ENVIRON]
        # Lock it down: no more creating new flags!
        self.__dict__['_in_init'] = False


flags = Flags()
