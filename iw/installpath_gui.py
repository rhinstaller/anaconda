from gtk import *
from iw_gui import *
from language_gui import *
from welcome_gui import *
from progress_gui import *
from package_gui import *
from network_gui import *
from account_gui import *
from auth_gui import *
from mouse_gui import *
from keyboard_gui import *
from format_gui import *
from congrats_gui import *
from dependencies_gui import *
from lilo_gui import *
from silo_gui import *
from examine_gui import *
from bootdisk_gui import *
from timezone_gui import *
from xconfig_gui import *
from fdisk_gui import *
from rootpartition_gui import *
from confirm_gui import *
import iutil
from translate import _
import installclass

UPGRADE = 0
INSTALL = 1

CUSTOM = 2
WORKSTATION_GNOME = 3
WORKSTATION_KDE = 4
SERVER = 5

def D_(x):
    return x

class InstallPathWindow (InstallWindow):		

    installTypes = installclass.availableClasses()

    def __init__ (self, ics):
	if iutil.getArch() == 'sparc':
	    BootloaderWindow = SiloWindow
            BootloaderSkipname = "silo"
	else:
	    BootloaderWindow = LiloWindow
            BootloaderSkipname = "lilo"            

	self.installSteps = [
                     FDiskWindow,
		     ( AutoPartitionWindow, "partition" ),
		     ( PartitionWindow, "partition" ),
		     ( FormatWindow, "format" ),
		     ( BootloaderWindow, BootloaderSkipname ),
		     ( NetworkWindow, "network" ),
		     ( TimezoneWindow, "timezone" ),
		     ( AccountWindow, "accounts" ),
		     ( AuthWindow, "authentication" ),
		     ( PackageSelectionWindow, "package-selection" ), 
		     ( UnresolvedDependenciesWindow, "dependencies" ),
                     ( MonitorWindow, "monitor" ),
                     ( XConfigWindow, "xconfig" ),
                     ( ConfirmWindow, "confirm" ),
		     InstallProgressWindow,
		     ( BootdiskWindow, "bootdisk" ),
		     ( CongratulationWindow, "complete" )
		   ]

	self.upgradeSteps = [
		     ( UpgradeExamineWindow, "custom-upgrade"),
		     ( BootloaderWindow, BootloaderSkipname ),
		     UnresolvedDependenciesWindow,
                     ( ConfirmWindow, "confirm" ),
		     InstallProgressWindow,
		     ( BootdiskWindow, "bootdisk" ),
		     CongratulationWindow
		   ]

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
	from fstab import GuiFstab

	if not self.__dict__.has_key("upgradeButton"):
	    return

	# Hack to let backing out of upgrades work properly
	if self.todo.fstab:
	    self.todo.fstab.turnOffSwap()

	needNewDruid = 0
	icw = self.ics.getICW ()
	if self.upgradeButton.get_active():
	    self.todo.upgrade = 1
            icw.setStateList (self.commonSteps + 
                              self.upgradeSteps, len (self.commonSteps)-1)
	else:
            icw.setStateList (self.commonSteps + 
                              self.installSteps, len (self.commonSteps)-1)
	    self.todo.upgrade = 0

	    for (button, object) in self.installClasses:
		if button.get_active():
		    break
	    if not isinstance (self.orig, object):
                self.todo.setClass (object(self.todo.expert))
		needNewDruid = 1

	# This makes the error message delivery come at a sane place
	if needNewDruid or not self.todo.fstab:
	    self.todo.fstab = GuiFstab(self.todo.setupFilesystems, 
				       self.todo.serial, 0, 0,
				       self.todo.intf.waitWindow,
				       self.todo.intf.messageWindow,
                                       not self.todo.expert)

        # set state of disk druid to be read-only if needed
        if (InstallPathWindow.fdisk.get_active()):
            self.todo.fstab.setReadonly(1)
        else:
            self.todo.fstab.setReadonly(0)

	self.todo.fstab.setRunDruid(InstallPathWindow.fdisk.get_active())

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
            self.toggled (self.upgradeButton, UPGRADE)
	else:
	    instClass = self.todo.getClass()
	    installButton.set_active(1)

        self.installBox = GtkVBox (FALSE, 0)

        group = None
	self.installClasses = []
        
        self.orig = self.todo.getClass()

	for (name, object, pixmap) in self.installTypes:
            group = self.pixRadioButton (group, _(name), pixmap)
            self.installBox.pack_start (group, FALSE)
	    self.installClasses.append ((group, object))
            if isinstance(self.orig, object):
		group.set_active (1)

	spacer = GtkLabel("")
	spacer.set_usize(60, 1)

	InstallPathWindow.fdisk = GtkCheckButton (_("Use fdisk"))
	align = GtkAlignment ()
	align.add (InstallPathWindow.fdisk)
	align.set (0.0, 0.0, 0.0, 0.0)

	table = GtkTable(2, 4)
        table.attach(installButton, 0, 2, 0, 1, xoptions = FILL | EXPAND)
	table.attach(align, 2, 3, 0, 1, xoptions = FALSE)
	self.installBox.set_usize(300, -1)
        table.attach(self.installBox, 1, 3, 1, 2)
        table.attach(self.upgradeButton, 0, 3, 2, 3)

	box.pack_start(table, FALSE)

	hbox = GtkHBox (FALSE)
	if not InstallPathWindow.__dict__.has_key("fdisk"):
	    fdiskState = 0
	else:
	    fdiskState = InstallPathWindow.fdisk.get_active()

	InstallPathWindow.fdisk.set_active(fdiskState)

        self.toggled (installButton, INSTALL)
        self.toggled (self.upgradeButton, UPGRADE)
        box.set_border_width (5)
        return box
