#
# bootdisk_text.py: text mode bootdisk creation
#
# Copyright 2000-2002 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import iutil
from rhpl.translate import _
from snack import *
from constants_text import *
from constants import *

class BootDiskWindow:
    def __call__(self, screen, dir, disp, fsset):
	buttons = [ _("Yes"), _("No") ]

	text = _("The boot diskette allows you to boot your %s "
                 "system from a floppy diskette.  A boot diskette "
		 "allows you to boot your system in the event your "
		 "bootloader configuration stops working.\n\nIt is "
		 "highly recommended you create a boot diskette.\n\n"
		 "Would you like to create a boot diskette?") % (productName,)

	rc = ButtonChoiceWindow(screen, _("Boot Diskette"), text,
                                buttons=buttons,
				help="bootdiskquery")

	if rc == string.lower (_("No")):
	    disp.skipStep("makebootdisk")
	else:
	    disp.skipStep("makebootdisk", skip=0)
	

	return INSTALL_OK

