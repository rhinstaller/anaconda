from gtk import *
from iw import *
from thread import *
from gui import _

FSEDIT_CLEAR_LINUX  = (1 << 0)
FSEDIT_CLEAR_ALL    = (1 << 2)
FSEDIT_USE_EXISTING = (1 << 3)

class AutoPartitionWindow (InstallWindow):

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        self.todo = ics.getToDo ()
        ics.setTitle (_("Auto partition"))
	ics.setNextEnabled (TRUE)

    def getNext (self):
        attempt = [
        ( "/boot",      16,     0x83, 0, -1 ),
        ( "/",          256,    0x83, 0, -1 ),
        ( "/usr",       512,    0x83, 1, -1 ),
        ( "/var",       256,    0x83, 0, -1 ),
        ( "/home",      512,    0x83, 1, -1 ),
        ( "Swap-auto",  64,     0x82,   0, -1 ),
        ]

        ret = self.todo.ddruid.attempt (attempt, _("Workstation"), self.type)
        return None

    def typeSelected (self, button, data):
        self.type = data
        
    def getScreen (self):
	box = GtkVBox (FALSE)

	group = GtkRadioButton (None, _("Remove all data"))
        group.connect ("clicked", self.typeSelected, FSEDIT_CLEAR_ALL)
	box.pack_start (group, FALSE)
	item = GtkRadioButton (group, _("Remove Linux partitions"))
        item.connect ("clicked", self.typeSelected, FSEDIT_CLEAR_LINUX)
	box.pack_start (item, FALSE)
	item = GtkRadioButton (group, _("Use existing free space"))
        item.connect ("clicked", self.typeSelected, FSEDIT_USE_EXISTING)
	box.pack_start (item, FALSE)
	item.set_active (TRUE)

	return box
