#
# task_gui.py: Choose tasks for installation
#
# Copyright (C) 2006  Red Hat, Inc.  All rights reserved.
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

from constants_text import *
from constants import *

class TaskWindow:
    def __call__(self, screen, anaconda):
        anaconda.backend.resetPackageSelections()
        anaconda.backend.selectGroup("Core")

        return INSTALL_OK
