#
# task_gui.py: Choose tasks for installation
#
# Copyright 2006 Red Hat, Inc.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

from snack import *
from constants_text import *
from rhpl.translate import _, N_
from constants import productName

grpTaskMap = {N_("Office and Productivity"): ["graphics", "office",
                                              "games", "sound-and-video"],
              N_("Software Development"): ["development-libs", "development-tools",
                                           "gnome-software-development",
                                           "x-software-development"],
              N_("Web Server"): ["web-server"],
              N_("Virtualization (Xen)"): ["xen"] }

class TaskWindow:
    def groupsInstalled(self, lst):
        # FIXME: yum specific
        rc = False
        for gid in lst:
            g = self.backend.ayum.comps.return_group(gid)
            if g and not g.selected:
                return False
            elif g:
                rc = True
        return rc
    
    def __call__(self, screen, intf, backend, dispatch):
        self.backend = backend
        
	bb = ButtonBar (screen, (TEXT_OK_BUTTON, TEXT_BACK_BUTTON))
	
	toplevel = GridFormHelp (screen, _("Package selection"),
				 "tasksel", 1, 5)

	labeltxt = _("The default installation of %s includes a set of software applicable for general internet usage.  What additional tasks would you like your system to include  support for?") %(productName,)
	toplevel.add (TextboxReflowed(55, labeltxt), 0, 0, (0, 0, 0, 1))

        ct = CheckboxTree(height = 4, scroll = (len(grpTaskMap.keys()) > 4))
        for (cb, grps) in grpTaskMap.items():
            if self.groupsInstalled(grps):
                ct.append(_(cb), cb, True)
            else:
                ct.append(_(cb), cb, False)
        toplevel.add (ct, 0, 2, (0,0,0,1))
                      
	custom = not dispatch.stepInSkipList("group-selection")
	customize = Checkbox (_("Customize software selection"), custom)
	toplevel.add (customize, 0, 3, (0, 0, 0, 1))	 
	toplevel.add (bb, 0, 4, (0, 0, 0, 0), growx = 1)

	result = toplevel.run()
        rc = bb.buttonPressed (result)
	if rc == TEXT_BACK_CHECK:
	    screen.popWindow()
	    return INSTALL_BACK

	if customize.selected():
	    dispatch.skipStep("group-selection", skip = 0)
	else:
	    dispatch.skipStep("group-selection")

        sel = ct.getSelection()
        for (cb, grps) in grpTaskMap.items():
            if cb in sel:
                map(backend.selectGroup, grps)
            else:
                map(backend.deselectGroup, grps)
	screen.popWindow()
				 
        return INSTALL_OK

