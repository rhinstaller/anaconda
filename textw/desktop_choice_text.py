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

class DesktopChoiceWindow:
    def __call__(self, screen, intf, instclass, dispatch, grpset):

	bb = ButtonBar (screen, (TEXT_OK_BUTTON, TEXT_BACK_BUTTON))
	
	toplevel = GridFormHelp (screen, _("Package Defaults"),
				 "wsdefaults", 1, 5)

	labeltxt = N_("The default installation environment includes our "
                      "recommended package selection.  After installation, "
                      "additional software can be added or removed using the "
                      "'system-config-packages' tool.\n\n"
		      "However %s ships with many more applications, and "
		      "you may customize the selection of software "
		      "installed if you want.")
			  
	toplevel.add (TextboxReflowed(55, _(labeltxt) % (productName,)), 0, 0, (0, 0, 0, 1))
	custom = not dispatch.stepInSkipList("package-selection")
	customize = Checkbox (_("Customize software selection"), custom)
	toplevel.add (customize, 0, 3, (0, 0, 0, 1))	 
	toplevel.add (bb, 0, 4, (0, 0, 0, 0), growx = 1)

	result = toplevel.run()
        rc = bb.buttonPressed (result)
	if rc == TEXT_BACK_CHECK:
	    screen.popWindow()
	    return INSTALL_BACK

	if customize.selected():
	    dispatch.skipStep("package-selection", skip = 0)
	else:
	    dispatch.skipStep("package-selection")
            instclass.setGroupSelection(grpset, intf)
            instclass.setPackageSelection(grpset.hdrlist, intf)
	    
	screen.popWindow()
				 
        return INSTALL_OK

