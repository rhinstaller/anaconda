from iw import *
from gtk import *
from gui import _

class BootdiskWindow (InstallWindow):

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setTitle (_("Bootdisk Creation"))
        ics.setPrevEnabled (0)
        ics.setNextEnabled (1)
        ics.readHTML ("bootdisk")
        BootdiskWindow.initial = 1
        self.bootdisk = None

    def getNext (self):
        if not self.todo.needBootdisk():
            return None
        
        if self.bootdisk and self.bootdisk.get_active ():
            return None

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
        im = self.ics.readPixmap ("gnome-floppy.png")
        if im:
            im.render ()
            pix = im.make_pixmap ()
            a = GtkAlignment ()
            a.add (pix)
            a.set (0.0, 0.0, 0.0, 0.0)
            box.pack_start (a, FALSE)
        
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
        
        self.bootdisk = GtkCheckButton (_("Skip boot disk creation"))
        self.bootdisk.set_active (FALSE)
        box.pack_start (GtkHSeparator (), FALSE, padding=3)
        box.pack_start (self.bootdisk, FALSE)

	if self.todo.fstab.rootOnLoop():
	    self.bootdisk.set_sensitive(FALSE)

        return box
