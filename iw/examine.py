from gtk import *
from iw import *
from package import *
from gui import _

class UpgradeExamineWindow (InstallWindow):		

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)
        ics.setTitle (_("Upgrade Examine"))

    def toggled (self, widget, part):
        if widget.get_active ():
            self.root = part

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
        parts = self.todo.upgradeFindRoot ()
        threads_enter ()

        # if there is only one partition, go on.
        if parts and len (parts) == 1:
            return None

	box = GtkVBox (FALSE)
        if not parts:
            box.pack_start (GtkLabel (_("You don't have any Linux partitions.\n You can't upgrade this sytem!")),
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
        sw.set_border_width (5)
        sw.set_policy (POLICY_AUTOMATIC, POLICY_AUTOMATIC)
        sw.add_with_viewport (box)

        vbox = GtkVBox (FALSE, 5)
        self.individualPackages = GtkCheckButton (_("Customize packages to be upgraded"))
        self.individualPackages.set_active (FALSE)
        align = GtkAlignment (0.5, 0.5)
        align.add (self.individualPackages)

        vbox.pack_start (sw, TRUE)
        vbox.pack_start (align, FALSE)

        return vbox
