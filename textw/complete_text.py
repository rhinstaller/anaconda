#
# complete_text.py: text mode congratulations windows
#
# Copyright (C) 2001, 2002, 2003, 2004, 2005, 2006  Red Hat, Inc.
# All rights reserved.
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

from snack import *
from constants_text import *
from constants import *
import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

class FinishedWindow:
  
  def __call__ (self, screen, anaconda):
        bootstr = ""

        floppystr = _("Press <Enter> to end the installation process.\n\n")
        bottomstr = _("<Enter> to exit")

        screen.pushHelpLine (string.center(bottomstr, screen.width))

        txt = _("Congratulations, your %s installation is "
                "complete.\n\n"
                "%s%s") %(productName, floppystr, bootstr)
        foo = _("For information on errata (updates and bug fixes), visit "
                "http://www.redhat.com/errata/.\n\n"
                "Information on using your "
                "system is available in the %s manuals at "
                "http://www.redhat.com/docs/.") %(productName,)

        rc = ButtonChoiceWindow (screen, _("Complete"), txt,
                                 [ _("Reboot") ], help = "finished", width=60)

        return INSTALL_OK
