#
# complete_text.py: text mode congratulations windows
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

from snack import *
from constants_text import *
from translate import _
import iutil
import isys
import string


class FinishedWindow:

  import string

  if (iutil.getArch() != "s390" and iutil.getArch() != "s390x"):

    def __call__ (self, screen):
        screen.pushHelpLine (string.center(_("<Enter> to reboot"),
                                           screen.width))

        if iutil.getArch() != "ia64":
            bootstr = _("If you created a boot disk to use to boot your "
                        "Red Hat Linux system, insert it before you "
                        "press <Enter> to reboot.\n\n")
        else:
            bootstr = ""

	rc = ButtonChoiceWindow (screen, _("Complete"), 
             _("Congratulations, your Red Hat Linux installation is "
               "complete.\n\n"
               "Remove any floppy diskettes you used during the "
               "installation process and press <Enter> to reboot your system. "
               "\n\n"
               "%s"
               "For information on errata (updates and bug fixes), visit "
               "http://www.redhat.com/errata.\n\n"
               "Information on using your "
               "system is available in the Red Hat Linux manuals at "
               "http://www.redhat.com/support/manuals.") % bootstr,
		[ _("OK") ], help = "finished", width=60)

        return INSTALL_OK

  else:

    def __call__ (self, screen):
	screen.pushHelpLine (string.center(_("<Enter> to continue"),
				screen.width))
	rc = ButtonChoiceWindow (screen, _("Complete"),
		_("Congratulations, package installation is complete.\n\n"
		"Press return to continue.\n\n"
		"Information on configuring and using your Red Hat "
		"Linux system is contained in the Red Hat Linux "
		"manuals."),
		[ _("OK") ], help = "finished")
	f = open("/proc/mounts", "r")
	lines = f.readlines()
	f.close()
	umounts = []
	for line in lines:
	   if string.find(line, "/mnt/sysimage") > -1:
		tokens = string.split(line)
		umounts.append(tokens[1])
	umounts.sort()
	umounts.reverse()
	for part in umounts:
	    try:
		isys.umount(part)
	    except:
		print part + "is busy, couldn't umount."

	
	return INSTALL_OK


class ReconfigFinishedWindow:
    def __call__ (self, screen):
        screen.pushHelpLine (string.center(_("<Enter> to exit"),
                                           screen.width))

        rc = ButtonChoiceWindow (screen, _("Complete"), 
                _("Congratulations, configuration is complete.\n\n"
                  "For information on errata (updates and bug fixes), visit "
                  "http://www.redhat.com/errata.\n\n"
                  "Information on using your "
                  "system is available in the Red Hat Linux manuals at "
                  "http://www.redhat.com/support/manuals."),
                   [ _("OK") ], help = "reconfigfinished")

        f = open("/proc/mounts", "r")
        lines = f.readlines()
        f.close()
        umounts = []
        for line in lines:
           if string.find(line, "/mnt/sysimage") > -1:
                tokens = string.split(line)
                umounts.append(tokens[1])
        umounts.sort()
        umounts.reverse()
        for part in umounts:
            try:
                isys.umount(part)
            except:
                print part + "is busy, couldn't umount."
        return INSTALL_OK
