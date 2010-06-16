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
from pyanaconda.constants import *
import gettext
from pyanaconda import platform
_ = lambda x: gettext.ldgettext("anaconda", x)

class FinishedWindow:
  
  def __call__ (self, screen, anaconda):
        bootstr = ""
        buttonstr = _("Reboot")

        bottomstr = _("<Enter> to exit")

        screen.pushHelpLine (string.center(bottomstr, screen.width))

        if isinstance(anaconda.platform, platform.S390):
            txt = _("Congratulations, your %s installation is complete.\n\n") % (productName,)

            if not anaconda.canReIPL:
                buttonstr = _("Shutdown")

                txt = txt + _("Please shutdown to use the installed system.\n")
            else:
                txt = txt + _("Please reboot to use the installed system.\n")

            if not anaconda.reIPLMessage is None:
                txt = txt + "\n" + anaconda.reIPLMessage + "\n\n"

            txt = txt + _("Note that updates may be available to ensure the proper "
                          "functioning of your system and installation of these "
                          "updates is recommended after the reboot.")
        else:
            txt = _("Congratulations, your %s installation is complete.\n\n"
                    "Please reboot to use the installed system.  "
                    "Note that updates may be available to ensure the proper "
                    "functioning of your system and installation of these "
                    "updates is recommended after the reboot.") %(productName,)


        rc = ButtonChoiceWindow (screen, _("Complete"), txt,
                                 [ buttonstr ], help = "finished", width=60)

        return INSTALL_OK
