#
# zipl_text.py: text mode z/IPL setup dialog
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

import iutil
from snack import *
from constants_text import *
from translate import _

class ZiplWindow:
    def __call__(self, screen, dispatch, bl, fsset, diskSet):
	t = TextboxReflowed(53,
                         _("The z/IPL Boot Loader will now be installed "
                           "on your system."
                           "\n"
                           "\n"
                           "The root partition will be the one you "
                           "selected previously in the partition setup."
                           "\n"
                           "\n"
                           "The kernel used to start the machine will be "
                           "the one to be installed by default."
                           "\n"
                           "\n"
                           "If you wish to make changes later after "
                           "the installation feel free to change the "
                           "/etc/zipl.conf configuration file."
                           "\n"
                           "\n"
                           "You can now enter any additional kernel parameters "
                           "which your machine or your setup may require."))

	entry = Entry(48, scroll = 1, returnExit = 1)

        if bl.args and bl.args.get():
            entry.set(bl.args.get())

	buttons = ButtonBar(screen, [TEXT_OK_BUTTON,
			     TEXT_BACK_BUTTON ] )

	grid = GridFormHelp(screen, _("z/IPL Configuration"), 
			    "zipl-s390", 1, 3)
	grid.add(t, 0, 0)
        sg = Grid(2, 1)
	sg.setField(Label(_("Kernel Parameters") + ": "), 0, 0, anchorLeft=1)
	sg.setField(entry, 1, 0, anchorLeft=1)
	grid.add(sg, 0, 1, padding = (0, 1, 0, 1))
	grid.add(buttons, 0, 2, growx = 1)

        result = grid.runOnce ()
        button = buttons.buttonPressed(result)
        
        if button == TEXT_BACK_CHECK:
            return INSTALL_BACK

	if entry.value():
            bl.args.set(string.strip(entry.value()))
	else:
            bl.args.set("")

	return INSTALL_OK
