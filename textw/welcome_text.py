#
# welcome_text.py: text mode welcome window
#
# Copyright 2001-2002 Red Hat, Inc.
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
import os

class WelcomeWindow:
    def __call__(self, screen, anaconda):
        rc = ButtonChoiceWindow(screen, _("%s") % (productName,), 
                                _("Welcome to %s!\n\n")
                                % (productName, ),
                                buttons = [TEXT_OK_BUTTON], width = 50,
				help = "welcome")

        return INSTALL_OK
