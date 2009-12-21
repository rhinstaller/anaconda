#
# complete_text.py: text mode congratulations windows
#
# Copyright 2001-2006 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

from snack import *
from constants_text import *
from rhpl.translate import _
from constants import *
import rhpl


class FinishedWindow:
  
  def __call__ (self, screen, anaconda):
        bootstr = ""
        buttonstr = _("Reboot")

        if rhpl.getArch() in ['s390', 's390x']:
          floppystr = _("Press <Enter> to end the installation process.\n\n")
          bottomstr = _("<Enter> to exit")
          if not anaconda.canReIPL:
            buttonstr = _("Shutdown")
          if not anaconda.reIPLMessage is None:
            floppystr = anaconda.reIPLMessage + "\n\n" + floppystr
        else:
          floppystr = _("Remove any media used during the installation "
                        "process and press <Enter> to reboot your system."
                        "\n\n")
          bottomstr = _("<Enter> to reboot")

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
                                 [ buttonstr ], help = "finished", width=60)

        return INSTALL_OK
