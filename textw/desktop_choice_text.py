#
# desktop_choice_text.py: choose desktop
#
# Copyright 2002 Red Hat, Inc.
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
from constants import productName
from installclass import DEFAULT_DESKTOP_LABEL_1, DEFAULT_DESKTOP_LABEL_2

class DesktopChoiceWindow:
    def __call__(self, screen, intf, dispatch):

	bb = ButtonBar (screen, (TEXT_OK_BUTTON, TEXT_BACK_BUTTON))
	
	toplevel = GridFormHelp (screen, _("Workstation Defaults"),
				 "wsdefaults", 1, 5)
	
	label1 = DEFAULT_DESKTOP_LABEL_1
	label2 = "    GNOME Desktop shell             Nautilus file manager\n"+"    Mozilla web browser             Evolution mail client\n"+"    CD authoring software           Multimedia applications\n"+"    Open Office(tm) office suite"
	
	label3 = DEFAULT_DESKTOP_LABEL_2 % (productName, productName)

	toplevel.add (TextboxReflowed(55, label1+"\n\n"+label2+"\n\n"+label3), 0, 0, (0, 0, 0, 1))
	custom = not dispatch.stepInSkipList("package-selection")
	customize = Checkbox (_("Customize software selection"), custom)
	toplevel.add (customize, 0, 3, (0, 0, 0, 1))	 
	toplevel.add (bb, 0, 4, (0, 0, 0, 0), growx = 1)

	rc = toplevel.run()
	if rc == TEXT_BACK_CHECK:
	    screen.popWindow()
	    return INSTALL_BACK

	if customize.selected():
	    dispatch.skipStep("package-selection", skip = 0)
	else:
	    dispatch.skipStep("package-selection")
	    
	screen.popWindow()
				 
        return INSTALL_OK

