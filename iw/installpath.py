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
from dependencies import *
from lilo import *
from examine import *
from bootdisk import *
from timezone import *
from gui import _

UPGRADE = 0
INSTALL = 1

CUSTOM = 0
WORKSTATION_GNOME = 1
WORKSTATION_KDE = 2
SERVER = 3

class InstallPathWindow (InstallWindow):		

    installTypes = ((CUSTOM, _("Custom")),
			 (WORKSTATION_GNOME, _("GNOME Workstation")),
			 (WORKSTATION_KDE, _("KDE Workstation")),
			 (SERVER, _("Server")))

    installSteps = [ PartitionWindow,
			  LiloWindow,
			  TimezoneWindow,
			  NetworkWindow,
			  PartitionWindow,
			  FormatWindow,
			  PackageSelectionWindow,
			  UnresolvedDependenciesWindow,
			  LiloWindow,
			  AuthWindow,
			  AccountWindow,
			  InstallProgressWindow,
			  BootdiskWindow,
			  CongratulationWindow
			  ]

    upgradeSteps = [ UpgradeExamineWindow,
			  UnresolvedDependenciesWindow,
			  InstallProgressWindow,
			  CongratulationWindow
			  ]

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

	self.commonSteps = [ LanguageWindow, 
			     KeyboardWindow,
			     MouseWindow,
			     WelcomeWindow,
			     InstallPathWindow
			   ]

        ics.setTitle (_("Install Type"))
        ics.setNextEnabled (1)

    def toggled (self, widget, type):
        if not widget.get_active (): return
        if type == INSTALL:
            self.ics.getICW ().setStateList (self.commonSteps + 
				self.installSteps, len (self.commonSteps)-1)
            self.todo.upgrade = 0
	    self.installBox.set_sensitive(1)
        else:
            self.ics.getICW ().setStateList (self.commonSteps + 
				self.upgradeSteps, len (self.commonSteps)-1)
            self.todo.upgrade = 1
	    self.installBox.set_sensitive(0)

    def getScreen (self):
	box = GtkVBox (FALSE, 5)
	installButton = GtkRadioButton (None, _("Install"))
        installButton.connect ("toggled", self.toggled, INSTALL)
	upgradeButton = GtkRadioButton (installButton, _("Upgrade"))
        upgradeButton.connect ("toggled", self.toggled, UPGRADE)

        self.installBox = GtkVBox (FALSE)
        group = None
        for i in range (len (self.installTypes)):
            group = GtkRadioButton (group, self.installTypes[i][1])
            self.installBox.pack_start (group, FALSE)

	spacer = GtkLabel("")
	spacer.set_usize(15, 1)

	table = GtkTable(2, 3)
        table.attach(installButton, 0, 2, 0, 1)
        table.attach(spacer, 0, 1, 1, 2, xoptions = FALSE)
        table.attach(self.installBox, 1, 2, 1, 2, xoptions = FILL | EXPAND)
        table.attach(upgradeButton, 0, 2, 2, 3)

	box.pack_start(table, FALSE)

        self.toggled (installButton, INSTALL)

        return box
