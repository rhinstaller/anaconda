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
from xconfig import *
from gui import _
import installclass

UPGRADE = 0
INSTALL = 1

CUSTOM = 2
WORKSTATION_GNOME = 3
WORKSTATION_KDE = 4
SERVER = 5

class InstallPathWindow (InstallWindow):		

    installTypes = ((CUSTOM, _("Custom")),
                    (WORKSTATION_GNOME, _("GNOME Workstation")),
                    (WORKSTATION_KDE, _("KDE Workstation")),
                    (SERVER, _("Server")))

    installSteps = [ ( PartitionWindow, "partition" ),
		     ( FormatWindow, "format" ),
		     ( LiloWindow, "lilo" ),
		     ( NetworkWindow, "network" ),
		     ( TimezoneWindow, "timezone" ),
		     ( AccountWindow, "accounts" ),
		     ( AuthWindow, "authentication" ),
		     ( PackageSelectionWindow, "package-selection" ), 
		     ( UnresolvedDependenciesWindow, "dependencies" ),
                     ( XConfigWindow, "xconfig" ),
		     InstallProgressWindow,
		     ( BootdiskWindow, "bootdisk" ),
		     ( CongratulationWindow, "complete" )
		   ]

    upgradeSteps = [ UpgradeExamineWindow,
		     UnresolvedDependenciesWindow,
		     InstallProgressWindow,
		     CongratulationWindow
		   ]

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

	self.commonSteps = [ ( LanguageWindow, "language" ), 
			     ( KeyboardWindow, "keyboard" ),
			     ( MouseWindow, "mouse" ),
			     ( WelcomeWindow, "welcome" ),
			     ( InstallPathWindow, "installtype" ),
			   ]

        ics.setTitle (_("Install Type"))
        ics.setNextEnabled (1)

    def getNext(self):
	if not self.__dict__.has_key("upgradeButton"):
	    print "okay"
	    return

	print "ACK"

	if self.upgradeButton.get_active():
	    self.todo.upgrade = 1
            self.ics.getICW ().setStateList (self.commonSteps + 
				self.upgradeSteps, len (self.commonSteps)-1)
	else:
            self.ics.getICW ().setStateList (self.commonSteps + 
				self.installSteps, len (self.commonSteps)-1)
	    self.todo.upgrade = 0

	    for (button, type) in self.installClasses:
		if button.get_active():
		    break

	    if type == WORKSTATION_GNOME:
		self.todo.setClass (installclass.GNOMEWorkstation ())
	    elif type == WORKSTATION_KDE:
		self.todo.setClass (installclass.KDEWorkstation ())
	    elif type == SERVER:
		self.todo.setClass (installclass.Server ())
	    else:
		self.todo.setClass (installclass.CustomInstall ())

    def toggled (self, widget, type):
        if not widget.get_active (): return
        if type == INSTALL:
	    self.installBox.set_sensitive(1)
        elif type == UPGRADE:
	    self.installBox.set_sensitive(0)

    def getScreen (self):
	if (self.todo.instClass.installType == "install"):
            self.ics.getICW ().setStateList (self.commonSteps + 
				self.installSteps, len (self.commonSteps)-1)
            self.todo.upgrade = 0
	    return None
	elif (self.todo.instClass.installType == "upgrade"):
            self.ics.getICW ().setStateList (self.commonSteps + 
				self.upgradeSteps, len (self.commonSteps)-1)
            self.todo.upgrade = 1
	    return None

	box = GtkVBox (FALSE, 5)
	installButton = GtkRadioButton (None, _("Install"))
        installButton.connect ("toggled", self.toggled, INSTALL)
	self.upgradeButton = GtkRadioButton (installButton, _("Upgrade"))
        self.upgradeButton.connect ("toggled", self.toggled, UPGRADE)

	if (self.todo.upgrade):
	    self.upgradeButton.set_active(1)
	    default = None
	else:
	    instClass = self.todo.getClass()
	    default = CUSTOM
	    installButton.set_active(1)
	    if isinstance(instClass, installclass.GNOMEWorkstation):
		default = WORKSTATION_GNOME
	    elif isinstance(instClass, installclass.KDEWorkstation):
		default = WORKSTATION_KDE
	    elif isinstance(instClass, installclass.Server):
		default = SERVER

        self.installBox = GtkVBox (FALSE)
        group = None
	self.installClasses = []
	for (type, name) in self.installTypes:
            group = GtkRadioButton (group, name)
            self.installBox.pack_start (group, FALSE)
	    self.installClasses.append ((group, type))
	    if (type == default):
		group.set_active (1)

	spacer = GtkLabel("")
	spacer.set_usize(15, 1)

	table = GtkTable(2, 3)
        table.attach(installButton, 0, 2, 0, 1)
        table.attach(spacer, 0, 1, 1, 2, xoptions = FALSE)
        table.attach(self.installBox, 1, 2, 1, 2, xoptions = FILL | EXPAND)
        table.attach(self.upgradeButton, 0, 2, 2, 3)

	box.pack_start(table, FALSE)

        self.toggled (installButton, INSTALL)
        box.set_border_width (5)
        return box
