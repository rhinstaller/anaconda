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
	    self.root = newPart

    def getNext (self):
        threads_leave ()
        self.todo.upgradeMountFilesystems (self.root)
        threads_enter ()

# do this via skiplist, made individialpackageselectionwindow a member
# of upgrade steps.
#
#        if self.individualPackages.get_active ():
#            # XXX fix me
#            from package_gui import IndividualPackageSelectionWindow
#            return IndividualPackageSelectionWindow

        if self.individualPackages.get_active ():
            self.todo.instClass.removeFromSkipList("indivpackage")
        else:
            self.todo.instClass.addToSkipList("indivpackage")

        return None

    #UpgradeExamineWindow tag = "upgrade"
    def getScreen (self):
        threads_leave ()
        self.parts = self.todo.upgradeFindRoot ()
        threads_enter ()

	box = GtkVBox (FALSE)
        if not self.parts:
            box.pack_start (GtkLabel (_("You don't have any Linux partitions.\n You can't upgrade this sytem!")),
                            FALSE)
            self.ics.setNextEnabled (FALSE)
            return box

        vbox = GtkVBox (FALSE, 10)
	vbox.set_border_width (8)

        if self.parts and len (self.parts) > 1:
	    label = GtkLabel (_("Please select the device containing the root filesystem: "))
	    label.set_alignment(0.0, 0.5)
	    box.pack_start(label, FALSE)

	    table = GtkTable(2, 6)
	    table.set_border_width (10)
            box.pack_start (table, FALSE)
	    box.pack_start (GtkHSeparator ())
	    spacer = GtkLabel("")
	    spacer.set_usize(15, 1)
	    table.attach(spacer, 0, 1, 2, 4, FALSE)

            self.ics.setNextEnabled (TRUE)
            self.root = self.parts[0]
            group = None
	    row = 1
            for (part, filesystem) in self.parts:
                group = GtkRadioButton (group, part)
                group.connect ("toggled", self.toggled, (part, filesystem))
		table.attach(group, 1, 2, row, row+1)
		row = row + 1

	    vbox.pack_start (box, FALSE)
        else:
            # if there is only one partition, go on.
            self.ics.setNextEnabled (TRUE)
            self.root = self.parts[0]
	    label = GtkLabel (_("Upgrading the Red Hat Linux installation on partition /dev/") + self.root[0] + "\n\n")
	    label.set_alignment(0.0, 0.5)
	    vbox.pack_start(label, FALSE)
            
        self.individualPackages = GtkCheckButton (_("Customize packages to be upgraded"))
        if self.todo.instClass.skipStep("indivpackage"):
            self.individualPackages.set_active (FALSE)
        else:
            self.individualPackages.set_active (TRUE)
            
        align = GtkAlignment (0.0, 0.5)
        align.add (self.individualPackages)

        vbox.pack_start (align, FALSE)

        return vbox
