from iw import *
from gtk import *
import gettext

cat = gettext.Catalog ("anaconda-text", "/usr/share/locale")
_ = cat.gettext

class BootdiskWindow (InstallWindow):

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setTitle ("Bootdisk Creation")
        ics.setPrevEnabled (0)
        ics.setNextEnabled (1)
        BootdiskWindow.initial = 1

    def getNext (self):
        if self.bootdisk.get_active (): return None
        

        threads_leave ()
        try:
            self.todo.makeBootdisk ()
        except:
            threads_enter ()
            BootdiskWindow.initial = 0
            return BootdiskWindow

        threads_enter ()
        return None

    def getScreen (self):
        if not self.todo.bootdisk: return None

        box = GtkVBox (FALSE, 5)
        label = None
        if BootdiskWindow.initial:
            label = GtkLabel (_("Insert a blank floppy in the first floppy drive. "
                                "All data on this disk will be erased during creation "
                                "of the boot disk."))
        else:
            label = GtkLabel (_("An error occured while making the boot disk. "
                                "Please make sure that there is a formatted floppy "
                                "in the first floppy drive."))

        label.set_line_wrap (TRUE)
        box.pack_start (label, FALSE)
        
        self.bootdisk = GtkCheckButton ("Skip boot disk creation")
        self.bootdisk.set_active (FALSE)
        box.pack_start (GtkHSeparator (), FALSE, padding=3)
        box.pack_start (self.bootdisk, FALSE)

        return box
