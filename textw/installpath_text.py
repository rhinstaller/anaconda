#
# installpath_text: text mode installation type selection dialog
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
from flags import flags
import installclass

class InstallPathWindow:
    def __call__ (self, screen, dispatch, id, method, intf):
	tmpclasses = installclass.availableClasses()

	# strip out '_' in names cause we dont do mnemonics in text mode
	classes = []
	for (n, o, l) in tmpclasses:
	    n2 = n.replace("_", "")
	    classes.append((n2, o, l))

	choices = []
	default = 0
	i = 0
	orig = None

	for (name, object, icon) in classes:
	    choices.append(_(name))

	    if isinstance(id.instClass, object):
		orig = i
	    elif object.default:
		default = i

	    i = i + 1

	if orig != None:
	    default = orig

	(button, choice) = ListboxChoiceWindow(screen, _("Installation Type"),
			_("What type of system would you like to install?"),
			    choices, [TEXT_OK_BUTTON, TEXT_BACK_BUTTON],
			    width = 40, default = default, help = "installpath")

        if button == TEXT_BACK_CHECK:
            return INSTALL_BACK

	if (choice != orig):
	    (name, objectClass, logo) = classes[choice]
	    c = objectClass(flags.expert)
	    c.setSteps(dispatch)
	    c.setInstallData(id)

        return INSTALL_OK

