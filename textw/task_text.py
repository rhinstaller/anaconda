#
# task_gui.py: Choose tasks for installation
#
# Copyright (C) 2006  Red Hat, Inc.  All rights reserved.
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

    def groupsExist(self, lst):
        # FIXME: yum specific
        for gid in lst:
            g = self.backend.ayum.comps.return_group(gid)
            if not g:
                return False
        return True
    
    def __call__(self, screen, anaconda):
        self.backend = anaconda.backend
        tasks = anaconda.id.instClass.tasks
        
	bb = ButtonBar (screen, (TEXT_OK_BUTTON, TEXT_BACK_BUTTON))
	
	toplevel = GridFormHelp (screen, _("Package selection"),
				 "tasksel", 1, 5)

        if anaconda.id.instClass.description:
            labeltxt = anaconda.id.instClass.description
        else:
            labeltxt = _("The default installation of %s includes a set of software applicable for general internet usage.  What additional tasks would you like your system to support?") %(productName,)
	toplevel.add (TextboxReflowed(55, labeltxt), 0, 0, (0, 0, 0, 1))

        ct = CheckboxTree(height = 4, scroll = (len(tasks) > 4))
        for (txt, grps) in tasks:
            if not self.groupsExist(grps):
                continue
            
            if self.groupsInstalled(grps):
                ct.append(_(txt), txt, True)
            else:
                ct.append(_(txt), txt, False)
        toplevel.add (ct, 0, 2, (0,0,0,1))
                      
	custom = not anaconda.dispatch.stepInSkipList("group-selection")
	customize = Checkbox (_("Customize software selection"), custom)
	toplevel.add (customize, 0, 3, (0, 0, 0, 1))	 
	toplevel.add (bb, 0, 4, (0, 0, 0, 0), growx = 1)

	result = toplevel.run()
        rc = bb.buttonPressed (result)
	if rc == TEXT_BACK_CHECK:
	    screen.popWindow()
	    return INSTALL_BACK

	if customize.selected():
	    anaconda.dispatch.skipStep("group-selection", skip = 0)
	else:
	    anaconda.dispatch.skipStep("group-selection")

        sel = ct.getSelection()
        for (txt, grps) in tasks:
            if txt in sel:
                map(self.backend.selectGroup, grps)
            else:
                map(self.backend.deselectGroup, grps)
	screen.popWindow()
				 
        return INSTALL_OK

