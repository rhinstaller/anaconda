#
# confirm_text.py: text mode install/upgrade confirmation window
#
# Copyright 2001-2003 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
import sys

from snack import *
from constants_text import *
from rhpl.translate import _
from image import presentRequiredMediaMessage

class BeginInstallWindow:
    def __call__ (self, screen, anaconda):
        rc = ButtonChoiceWindow (screen, _("Installation to begin"),
                                _("A complete log of your installation will be in "
                                  "%s after rebooting your system. You "
                                  "may want to keep this file for later reference.") %("/root/install.log",),
                                buttons = [ _("OK"), _("Back") ],
				help = "begininstall")
        if rc == string.lower (_("Back")):
            return INSTALL_BACK

        if anaconda.methodstr.startswith("cdrom://") and not anaconda.isKickstart:
	    rc = presentRequiredMediaMessage(anaconda)

	    if rc == 0:
		rc2 = anaconda.intf.messageWindow(_("Reboot?"),
					_("The system will be rebooted now."),
					type="custom", custom_icon="warning",
					custom_buttons=[_("_Back"), _("_Reboot")])
		if rc2 == 1:
		    sys.exit(0)
		else:
		    return INSTALL_BACK
            elif rc == 1: # they asked to go back
                return INSTALL_BACK
	
        return INSTALL_OK

class BeginUpgradeWindow:
    def __call__ (self, screen, anaconda):
        rc = ButtonChoiceWindow (screen, _("Upgrade to begin"),
                                _("A complete log of your upgrade will be in "
                                  "%s after rebooting your system. You "
                                  "may want to keep this file for later reference." %("/root/upgrade.log",)),
                                buttons = [ _("OK"), _("Back") ],
				help = "beginupgrade")
        if rc == string.lower (_("Back")):
            return INSTALL_BACK

        if anaconda.methodstr.startswith("cdrom://") and not anaconda.isKickstart:
	    rc = presentRequiredMediaMessage(anaconda)

	    if rc == 0:
		rc2 = anaconda.intf.messageWindow(_("Reboot?"),
					_("The system will be rebooted now."),
					type="custom", custom_icon="warning",
					custom_buttons=[_("_Back"), _("_Reboot")])
		if rc2 == 1:
		    sys.exit(0)
		else:
		    return INSTALL_BACK
            elif rc == 1: # they asked to go back
                return INSTALL_BACK

        return INSTALL_OK
