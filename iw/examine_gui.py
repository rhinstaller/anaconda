

from gtk import *
from iw_gui import *
from package_gui import *
from translate import _, N_
from upgrade import *

class UpgradeExamineWindow (InstallWindow):		

    windowTitle = N_("Upgrade Examine")
    htmlTag = "upgrade"

    def toggled (self, widget, newPart):
        if widget.get_active ():
	    self.root = newPart

    def getNext (self):
        upgradeMountFilesystems (self.intf, self.root, self.id.fsset,
                                 self.chroot)
	if self.individualPackages.get_active():
	    self.dispatch.skipStep("indivpackage", skip = 0)
	else:
	    self.dispatch.skipStep("indivpackage")

        return None

    #UpgradeExamineWindow tag = "upgrade"
    def getScreen (self, dispatch, intf, id, chroot):
        self.dispatch = dispatch
        self.intf = intf
        self.id = id
        self.chroot = chroot
        
        self.parts = findExistingRoots(intf, id, chroot)

	box = GtkVBox (FALSE)
        if not self.parts:
            box.pack_start (GtkLabel (_("You don't have any Linux partitions."
                                        "\nYou can't upgrade this sytem!")),
                            FALSE)
            self.ics.setNextEnabled (FALSE)
            return box

        vbox = GtkVBox (FALSE, 10)
	vbox.set_border_width (8)

        if self.parts and len (self.parts) > 1:
	    label = GtkLabel (_("Please select the device containing the root "
                                "filesystem: "))
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
	    label = GtkLabel (_("Upgrading the Red Hat Linux installation "
                                "on partition /dev/%s")
                              % (self.root[0] + "\n\n",))
	    label.set_alignment(0.0, 0.5)
	    vbox.pack_start(label, FALSE)
            
        self.individualPackages = GtkCheckButton (_("Customize packages to be "
                                                    "upgraded"))
        self.individualPackages.set_active (not dispatch.stepInSkipList("indivpackage"))
            
        align = GtkAlignment (0.0, 0.5)
        align.add (self.individualPackages)

        vbox.pack_start (align, FALSE)

        return vbox
