from gtk import *
from iw import *
from language import *
from welcome import *
from progress import *
from package import *
from network import *
from account import *
from auth import *
from mouse import *
from keyboard import *
from format import *
from congrats import *
from dependencies import *
from lilo import *
from examine import *
from bootdisk import *
from timezone import *
from xconfig import *
from fdisk import *
from rootpartition import *
from gui import _
import installclass

UPGRADE = 0
INSTALL = 1

CUSTOM = 2
WORKSTATION_GNOME = 3
WORKSTATION_KDE = 4
SERVER = 5

class InstallPathWindow (InstallWindow):		

    installTypes = ((WORKSTATION_GNOME, _("GNOME Workstation"), "gnome.png"),
                    (WORKSTATION_KDE, _("KDE Workstation"), "kde.png"),
                    (SERVER, _("Server"), "server.png"),
                    (CUSTOM, _("Custom"), "custom.png"))

    installSteps = [ ( AutoPartitionWindow, "partition" ),
		     ( PartitionWindow, "partition" ),
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

        ics.readHTML ("instpath")

	self.commonSteps = [ ( LanguageWindow, "language" ), 
			     ( KeyboardWindow, "keyboard" ),
			     ( MouseWindow, "mouse" ),
			     ( WelcomeWindow, "welcome" ),
			     ( InstallPathWindow, "installtype" ),
			   ]

        ics.setTitle (_("Install Type"))
        ics.setNextEnabled (1)
        self.ics = ics

    def getNext(self):
	if not self.__dict__.has_key("upgradeButton"):
	    return

	icw = self.ics.getICW ()
	if self.upgradeButton.get_active():
	    self.todo.upgrade = 1
            icw.setStateList (self.commonSteps + 
                              self.upgradeSteps, len (self.commonSteps)-1)
	else:
            icw.setStateList (self.commonSteps + 
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

    def pixRadioButton (self, group, label, pixmap):
        im = self.ics.readPixmap (pixmap)
        if im:
            im.render ()
            pix = im.make_pixmap ()
            hbox = GtkHBox (FALSE, 5)
            hbox.pack_start (pix, FALSE, FALSE, 0)
            label = GtkLabel (label)
            label.set_alignment (0.0, 0.5)
            hbox.pack_start (label, TRUE, TRUE, 15)
            button = GtkRadioButton (group)
            button.add (hbox)
        else:
            button = GtkRadioButton (group, label)
        return button

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

	installButton = self.pixRadioButton (None, _("Install"), "install.png")
        installButton.connect ("toggled", self.toggled, INSTALL)
	self.upgradeButton = self.pixRadioButton (installButton, _("Upgrade"), "upgrade.png")
        self.upgradeButton.connect ("toggled", self.toggled, UPGRADE)

	if (self.todo.upgrade):
	    self.upgradeButton.set_active(1)
	    default = None
	else:
	    instClass = self.todo.getClass()
	    default = WORKSTATION_GNOME
	    installButton.set_active(1)
	    if isinstance(instClass, installclass.GNOMEWorkstation):
		default = WORKSTATION_GNOME
	    elif isinstance(instClass, installclass.KDEWorkstation):
		default = WORKSTATION_KDE
	    elif isinstance(instClass, installclass.Server):
		default = SERVER

        self.installBox = GtkVBox (FALSE, 0)
        group = None
	self.installClasses = []
	for (type, name, pixmap) in self.installTypes:
            group = self.pixRadioButton (group, name, pixmap)
            self.installBox.pack_start (group, FALSE)
	    self.installClasses.append ((group, type))
	    if (type == default):
		group.set_active (1)

	spacer = GtkLabel("")
	spacer.set_usize(60, 1)

	table = GtkTable(2, 3)
        table.attach(installButton, 0, 2, 0, 1)
        table.attach(spacer, 0, 1, 1, 2, xoptions = FALSE)
        table.attach(self.installBox, 1, 2, 1, 2, xoptions = FILL | EXPAND)
        table.attach(self.upgradeButton, 0, 2, 2, 3)

	box.pack_start(table, FALSE)

        if self.todo.expert:
            InstallPathWindow.fdisk = GtkCheckButton (_("Use fdisk to format drives"))
            line = GtkHSeparator ()
            box.pack_start (line, FALSE)
            box.pack_start (InstallPathWindow.fdisk, FALSE)
        else:
            InstallPathWindow.fdisk = None

        self.toggled (installButton, INSTALL)
        box.set_border_width (5)
        return box
