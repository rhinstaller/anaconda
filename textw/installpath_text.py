from snack import *
from constants_text import *
from translate import _
from flags import flags
import installclass

class InstallPathWindow:
    def __call__ (self, screen, dispatch, id, method, intf):
	classes = installclass.availableClasses()

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

	if len(choices) < 3:
	    raise KeyError

	(button, choice) = ListboxChoiceWindow(screen, _("Installation Type"),
			_("What type of system would you like to install?"),
			    choices, [TEXT_OK_BUTTON, TEXT_BACK_BUTTON],
			    width = 40, default = default, help = "installpath")

        if button == TEXT_BACK_CHECK:
            return INSTALL_BACK

	needNewDruid = 0

	if needNewDruid:
	    # The last 0 on here means we don't know if it's an upgrade or
	    # not.
	    id.fstab = NewtFstab(flags.setupFilesystems(), 
                                   flags.serial(), 0, 0,
                                   intf.waitWindow,
                                   intf.messageWindow,
                                   intf.progressWindow,
                                   not flags.expert,
                                   method.protectedPartitions(),
                                   flags.expert, 0)


	if (choice != orig):
	    (name, objectClass, logo) = classes[choice]
	    c = objectClass(flags.expert)
	    c.setSteps(dispatch)
	    c.setInstallData(id)
	    needNewDruid = 1

        return INSTALL_OK

