from gtk import *
from iw import *

class UpgradeExamineWindow (InstallWindow):		

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setTitle ("Upgrade Examine")

    def toggled (self, widget, part):
        if widget.get_active ():
            self.root = part

    def getNext (self):
        self.todo.upgradeFindPackages (self.root)
        if self.individualPackages.get_active ():
            return IndividualPackageSelectionWindow
        return None

    def getScreen (self):
        threads_leave ()
        parts = self.todo.upgradeFindRoot ()
        threads_enter ()

	box = GtkHBox (FALSE)
        if not parts:
            box.pack_start (GtkLabel ("You don't have any Linux partitions.\n You can't upgrade this sytem!"),
                            FALSE)
            return box

        self.ics.setNextEnabled (TRUE)
        self.root = parts[0]
        group = None
        for part in parts:
            group = GtkRadioButton (group, part)
            group.connect ("toggled", self.toggled, part)
            box.pack_start (group, FALSE)

        sw = GtkScrolledWindow ()
        sw.add_with_viewport (box)

        vbox = GtkVBox (FALSE, 5)
        self.individualPackages = GtkCheckButton ("Customized packages to be upgraded")
        self.individualPackages.set_active (FALSE)
        align = GtkAlignment (0.5, 0.5)
        align.add (self.individualPackages)

        vbox.pack_start (sw, TRUE)
        vbox.pack_start (align, FALSE)

        return vbox
