#
# confirm_text.py: text mode install/upgrade confirmation window
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

class BeginInstallWindow:
    def __call__ (self, screen):
        rc = ButtonChoiceWindow (screen, _("Installation to begin"),
                                _("A complete log of your installation will be in "
                                  "%s after rebooting your system. You "
                                  "may want to keep this file for later reference.") %("/root/install.log",),
                                buttons = [ _("OK"), _("Back") ],
				help = "begininstall")
        if rc == string.lower (_("Back")):
            return INSTALL_BACK
        return INSTALL_OK

class BeginUpgradeWindow:
    def __call__ (self, screen) :
        rc = ButtonChoiceWindow (screen, _("Upgrade to begin"),
                                _("A complete log of your upgrade will be in "
                                  "%s after rebooting your system. You "
                                  "may want to keep this file for later reference." %("/root/upgrade.log",)),
                                buttons = [ _("OK"), _("Back") ],
				help = "beginupgrade")
        if rc == string.lower (_("Back")):
            return INSTALL_BACK
        return INSTALL_OK
