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
from yuminstall import NoSuchGroup
#import sys
import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)


class TaskWindow:
    def __call__(self, screen, anaconda):
        anaconda.backend.resetPackageSelections()
        try:
            anaconda.backend.selectGroup("Core")
        except NoSuchGroup:
            anaconda.intf.messageWindow(_("Core group missing in selected repos"),
                                        _("At least one of the software "
                                          "repositories used for the "
                                          "installation needs to contain "
                                          "the core package group. If the "
                                          "core group is not present, "
                                          "installation can't continue."))
            sys.exit(1)

        return INSTALL_OK
