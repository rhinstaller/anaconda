from gtk import *
from iw_gui import *
from package_gui import *
from translate import _

class UpgradeExamineWindow (InstallWindow):		

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)
        ics.setTitle (_("Upgrade Examine"))
        ics.readHTML ("upgrade")

    def toggled (self, widget, newPart):
        if widget.get_active ():
	    for (part, someFilesystem) in self.parts:
		if part == newPart:
		    self.root = (part, someFilesystem)

    def getNext (self):
        threads_leave ()
        self.todo.upgradeFindPackages (self.root)
        threads_enter ()
        
        if self.individualPackages.get_active ():
            # XXX fix me
            from package import IndividualPackageSelectionWindow
            return IndividualPackageSelectionWindow
        return None

    def getScreen (self):
        threads_leave ()
        self.parts = self.todo.upgradeFindRoot ()
        threads_enter ()

	box = GtkVBox (FALSE)
        if not self.parts:
            box.pack_start (GtkLabel (_("You don't have any Linux partitions.\n You can't upgrade this sytem!")),
                            FALSE)
            return box

        vbox = GtkVBox (FALSE, 5)

        if self.parts and len (self.parts) > 1:
            box.pack_start (GtkLabel (_("Please select the device which "
                                        "contains the root filesystem to be "
                                        "upgraded.")), FALSE)
            self.ics.setNextEnabled (TRUE)
            self.root = self.parts[0]
            group = None
            for part in self.parts:
                group = GtkRadioButton (group, part)
                group.connect ("toggled", self.toggled, part)
                box.pack_start (group, FALSE)

            sw = GtkScrolledWindow ()
            sw.set_border_width (5)
            sw.set_policy (POLICY_AUTOMATIC, POLICY_AUTOMATIC)
            sw.add_with_viewport (box)
            vbox.pack_start (sw, TRUE)
        else:
            # if there is only one partition, go on.
            self.ics.setNextEnabled (TRUE)
            self.root = self.parts[0]
            
        self.individualPackages = GtkCheckButton (_("Customize packages to be upgraded"))
        self.individualPackages.set_active (FALSE)
        align = GtkAlignment (0.5, 0.5)
        align.add (self.individualPackages)

        vbox.pack_start (align, FALSE)

        return vbox
