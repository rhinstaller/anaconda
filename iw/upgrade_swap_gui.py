from gtk import *
from iw_gui import *
from translate import _
import string
import isys 
import iutil
from log import log
import upgrade
from gnome.ui import *
import gui

class UpgradeSwapWindow (InstallWindow):		

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setTitle (_("Upgrade Swap Partition"))
        ics.setNextEnabled (1)
        ics.readHTML ("upswapfile")
        #self.todo = ics.getToDo ()

    def getNext (self):
        mnt, part, size = self.clist.get_row_data(self.row)
        val = int(self.entry.get_text())
        size = int(size)
        val = int(val)

        if self.option2.get_active():
            threads_leave()
            rc = self.warning()
            threads_enter()

            if rc == 1:
                raise gui.StayOnScreen

        elif val > 2000 or val < 0:
            threads_leave()
            rc = self.swapWrongSize()
            threads_enter()
            raise gui.StayOnScreen

        elif val > size:
            threads_leave()
            rc = self.swapTooBig()
            threads_enter()
            raise gui.StayOnScreen            

        else:
            threads_leave()
            upgrade.createSwapFile(self.todo.instPath, self.todo.fstab, mnt, val,
                                   self.todo.intf.progressWindow)
            threads_enter()
        return None

    def toggle (self, data):
        self.swapbox.set_sensitive(self.option1.get_active())

    def clist_cb(self, clist, row, col, data):
        self.row = row
    
    def getScreen (self):
        self.row = 0
        box = GtkVBox (FALSE, 5)
        box.set_border_width (5)

	label = GtkLabel (_("The 2.4 kernel needs significantly more swap than older "
		 "kernels, as much as twice as much swap space as RAM on the "
		 "system. You currently have %dMB of swap configured, but "
		 "you may create additional swap space on one of your "
		 "file systems now." % (iutil.swapAmount() / 1024)))

        label.set_alignment (0.5, 0.0)
        label.set_usize(400, 80)
        label.set_line_wrap (TRUE)
        box.pack_start(label, FALSE)

        hs = GtkHSeparator()
        box.pack_start(hs, FALSE)

        self.option1 = GtkRadioButton(None, (_("I want to create a swap file")))
        box.pack_start(self.option1, FALSE)

        rc = upgrade.swapSuggestion(self.todo.instPath, self.todo.fstab)
	if not rc:
	    self.todo.upgradeFindPackages ()
	    return INSTALL_OK

        (fsList, suggSize, suggMntPoint) = rc

        self.swapbox = GtkVBox(FALSE, 5)
        box.pack_start(self.swapbox, FALSE)
        

        label = GtkLabel (_("Select the partition to put the swap file on:"))
        a = GtkAlignment(0.2, 0.5)
        a.add(label)
        self.swapbox.pack_start(a, FALSE)

        titles = [(_("Mount Point")), (_("Partition")), (_("Free Space (MB)"))]        
        self.clist = GtkCList(3, titles)
        self.clist.connect("select-row", self.clist_cb)
        a = GtkAlignment(0.5, 0.5)
        a.add(self.clist)
        self.swapbox.pack_start(a, FALSE, TRUE, 10)

        count = 0
        for (mnt, part, size) in fsList:
            self.clist.append([mnt, part, str(size)])
            self.clist.set_row_data(count, [mnt, part, size])
            count = count + 1

        self.clist.select_row(0, 0)
        suggSize = 128

        label = GtkLabel (_("It is recommended that your swap file be at least %d MB.  Please enter a size for the swap file:" % suggSize))
        label.set_usize(400, 40)
        label.set_line_wrap (TRUE)
        a = GtkAlignment(0.5, 0.5)
        a.add(label)
        self.swapbox.pack_start(a, FALSE, TRUE, 10)


        hbox = GtkHBox(FALSE, 5)
        a = GtkAlignment(0.4, 0.5)
        a.add(hbox)
        self.swapbox.pack_start(a, FALSE)

        label = GtkLabel (_("Swap file size (MB):"))
        hbox.pack_start(label, FALSE)

        self.entry = GtkEntry(4)
        self.entry.set_usize(40, 25)
        self.entry.set_text(str(suggSize))
        hbox.pack_start(self.entry, FALSE, TRUE, 10)

        self.option2 = GtkRadioButton(self.option1, (_("I don't want to create a swap file")))
        box.pack_start(self.option2, FALSE, TRUE, 20)

        self.option1.connect("toggled", self.toggle)
        return box


    def warning(self):
        
        rc = self.todo.intf.messageWindow(_("Warning"), 
                    _("It is stongly recommended that you create a swap file.  "
                            "Failure to do so could cause the installer to abort "
                            "abnormally.  Are you sure that you wish to continue?"),
                             type = "yesno").getrc()
        return rc

    def swapWrongSize(self):
        
        rc = self.todo.intf.messageWindow(_("Warning"), 
                    _("The swap file must be between 0 and 2000 MB in size."),
                       type = "okcancel").getrc()
        return rc

    def swapTooBig(self):
        
        rc = self.todo.intf.messageWindow(_("Warning"), 
                    _("There is not enough space on the device you "
			  "selected for the swap partition."),
                       type = "okcancel").getrc()
        return rc
