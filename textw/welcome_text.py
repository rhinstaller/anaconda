#
# welcome_text.py: text mode welcome window
#
# Copyright 2001 Red Hat, Inc.
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
from translate import _
import os

class WelcomeWindow:
    def __call__(self, screen, configFileData):
        rc = ButtonChoiceWindow(screen, _("Red Hat Linux"), 
                                _("Welcome to Red Hat Linux!\n\n"
                                  "This installation process is outlined in detail in the "
                                  "Official Red Hat Linux Installation Guide available from "
                                  "Red Hat, Inc. If you have access to this manual, you "
                                  "should read the installation section before continuing.\n\n"
                                  "If you have purchased Official Red Hat Linux, be sure to "
                                  "register your purchase through our web site, "
                                  "http://www.redhat.com/."),
                                buttons = [TEXT_OK_BUTTON, TEXT_BACK_BUTTON], width = 50,
				help = "welcome")

	if rc == TEXT_BACK_CHECK:
	    return INSTALL_BACK

        return INSTALL_OK

