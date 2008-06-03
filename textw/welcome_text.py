#
# welcome_text.py: text mode welcome window
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

from snack import *
from constants_text import *
from constants import *
import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

class WelcomeWindow:
    def __call__(self, screen, anaconda):
        rc = ButtonChoiceWindow(screen, _("%s") % (productName,), 
                                _("Welcome to %s!\n\n")
                                % (productName, ),
                                buttons = [TEXT_OK_BUTTON], width = 50,
				help = "welcome")

        return INSTALL_OK
