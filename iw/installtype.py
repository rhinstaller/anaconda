from gtk import *
from iw import *
from thread import *

WORKSTATION_GNOME = 1
WORKSTATION_KDE   = 2
SERVER            = 3
CUSTOM            = 4

class InstallTypeWindow (InstallWindow):

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        self.todo = ics.getToDo ()
        ics.setTitle (_("Installation Type"))
	ics.setNextEnabled (TRUE)

        self.installTypes = ((WORKSTATION_GNOME, _("Workstation (Gnome)")),
                             (WORKSTATION_KDE, _("Workstation (KDE)")),
                             (SERVER, _("Server")),
                             (CUSTOM, _("Custom")))

        self.type = self.installTypes[0][0]

    def typeSelected (self, button, data):
        self.type = data
        
    def getScreen (self):
        box = GtkVBox (FALSE, 10)
        group = None
        for i in range (len (self.installTypes)):
            group = GtkRadioButton (group, self.installTypes[i][1])
            group.connect ("clicked", self.typeSelected, self.installTypes[i][0])
            box.pack_start (group, FALSE)
        return box

