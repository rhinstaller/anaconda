from gtk import *
from iw import *
from language import *
from welcome import *
from progress import *
from package import *
from network import *
from account import *
from rootpartition import *
from auth import *
from mouse import *
from keyboard import *
from format import *
from congrats import *
from autopartition import *
from installtype import *
from dependencies import *
from lilo import *
from examine import *
from bootdisk import *
from gui import _

UPGRADE = 0
INSTALL = 1

class InstallPathWindow (InstallWindow):		

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setTitle (_("Install Path"))
        ics.setNextEnabled (1)

        self.commonSteps = [LanguageWindow, KeyboardWindow, MouseWindow,
                            WelcomeWindow, InstallPathWindow]

        self.installSteps = [NetworkWindow, PartitionWindow, FormatWindow, PackageSelectionWindow,
	                     UnresolvedDependenciesWindow, LiloWindow, AuthWindow, AccountWindow,
                             InstallProgressWindow, BootdiskWindow, CongratulationWindow]

	self.upgradeSteps = [UpgradeExamineWindow,
	                     UnresolvedDependenciesWindow, InstallProgressWindow,
                             CongratulationWindow]

    def toggled (self, widget, type):
        if not widget.get_active (): return
        if type == INSTALL:
            self.ics.getICW ().setStateList (self.commonSteps + self.installSteps, len (self.commonSteps)-1)
            self.todo.upgrade = 0
        else:
            self.ics.getICW ().setStateList (self.commonSteps + self.upgradeSteps, len (self.commonSteps)-1)
            self.todo.upgrade = 1

    def getScreen (self):
	box = GtkVBox (FALSE, 5)
	group = GtkRadioButton (None, _("Install"))
        group.connect ("toggled", self.toggled, INSTALL)
        self.toggled (group, INSTALL)
	box.pack_start (group, FALSE)
	group = GtkRadioButton (group, _("Upgrade"))
        group.connect ("toggled", self.toggled, UPGRADE)
        box.pack_start (group, FALSE)

        return box
