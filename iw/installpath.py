from gtk import *
from iw import *
#from autopartition import *

# import only screens common to both upgrade and install here.

from progress import InstallProgressWindow
from dependencies import UnresolvedDependenciesWindow
from congrats import CongratulationWindow

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

    def __init__ (self, ics):
        from language import LanguageWindow
        from mouse import MouseWindow
        from keyboard import KeyboardWindow
        from welcome import WelcomeWindow
        
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
            if not self.__dict__.has_key ("installSteps"):
                print '1'
#                from xconfig import XConfigWindow
                print '2'
                from package import PackageSelectionWindow
                print '3'
                from network import NetworkWindow
                print '4'
                from account import AccountWindow
                print '5'
                from rootpartition import PartitionWindow
                print '6'
                from auth import AuthWindow
                print '7'
                from format import FormatWindow
                print '8'
                from lilo import LiloWindow
                print '9'
                from bootdisk import BootdiskWindow
                print '10'
                from timezone import TimezoneWindow
                print '11'
                
                self.installSteps = [ #XConfigWindow,
                                      PartitionWindow,
                                      FormatWindow,
                                      LiloWindow,
                                      NetworkWindow,
                                      TimezoneWindow,
                                      AccountWindow,
                                      PackageSelectionWindow,
                                      UnresolvedDependenciesWindow,
                                      AuthWindow,
                                      #XConfigWindow,
                                      InstallProgressWindow,
                                      BootdiskWindow,
                                      CongratulationWindow
                                    ]
            
            self.ics.getICW ().setStateList (self.commonSteps + 
				self.installSteps, len (self.commonSteps)-1)
            self.todo.upgrade = 0
	    self.installBox.set_sensitive(1)
        else:
            # upgrade
            if not self.__dict__.has_key ("upgradeSteps"):
                from examine import UpgradeExamineWindow

                self.upgradeSteps = [ UpgradeExamineWindow,
                                      UnresolvedDependenciesWindow,
                                      InstallProgressWindow,
                                      CongratulationWindow
                                    ]
            
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
