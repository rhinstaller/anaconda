from gtk import *
from iw import *
from isys import *

class NetworkWindow (InstallWindow):		

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setTitle ("Network Configuration")
        ics.setNextEnabled (1)
        self.todo = ics.getToDo ()
        self.calcNMHandler = None

    def focusInIP (self, *args):
        if self.nm.get_text() == "":
            self.calcNetmask ()
            self.calcNMHandler = self.ip.connect ("changed", self.calcNetmask)

    def focusOutIP (self, *args):
        if self.calcNMHandler != None:
            self.ip.disconnect (self.calcNMHandler)
            self.calcNMHandler = None
        

    def calcNetmask (self, *args):
        ip = self.ip.get_text ()
        dots = 0
        for x in ip:
            if x == '.':
                dots = dots + 1
        if dots != 3: return

        new_nm = inet_calcNetmask (self.ip.get_text ())
        if (new_nm != self.nm.get_text ()):
            self.nm.set_text (new_nm)

    def getScreen (self):
        box = GtkVBox ()
        
        devLine = GtkHBox ()
        devLabel = GtkLabel ("Device: ")
        devLabel.set_alignment (0, 0)
        devLine.pack_start (devLabel)
        menu = GtkMenu ()
        for i in self.todo.network.available ().keys ():
            menu.append (GtkMenuItem (i))
        devMenu = GtkOptionMenu ()
        devMenu.set_menu (menu)
        devLine.pack_start (devMenu)
        box.pack_start (devLine, FALSE)

        isDHCP = GtkCheckButton ("Configure using DHCP")
        isDHCP.set_active (TRUE)

        box.pack_start (isDHCP, FALSE)
        box.pack_start (GtkHSeparator (), FALSE, padding=3)

        ipTable = GtkTable (2, 2)
        self.ipTable = ipTable
        ipTable.attach (GtkLabel ("IP Address:"), 0, 1, 0, 1)
        ipTable.attach (GtkLabel ("Netmask:"), 0, 1, 1, 2)
        self.ip = GtkEntry (15)
        self.ip.connect ("focus_in_event", self.focusInIP)
        self.ip.connect ("focus_out_event", self.focusOutIP)
        self.ip.connect ("activate", lambda widget, self=self: self.ipTable.focus (DIR_TAB_FORWARD))
        self.nm = GtkEntry (15)
        ipTable.attach (self.ip, 1, 2, 0, 1)
        ipTable.attach (self.nm, 1, 2, 1, 2)
        box.pack_start (ipTable, FALSE)

        box.pack_start (GtkHSeparator (), FALSE, padding=3)
        
        ipTable = GtkTable (5, 2)
        ipTable.attach (GtkLabel ("Gateway: "), 0, 1, 0, 1)
        ipTable.attach (GtkLabel ("Primary DNS: "), 0, 1, 2, 3)
        ipTable.attach (GtkLabel ("Secondary DNS: "), 0, 1, 3, 4)
        ipTable.attach (GtkLabel ("Trinary DNS: "), 0, 1, 4, 5)
        gw = GtkEntry (15)
        dns1 = GtkEntry (15)
        dns2 = GtkEntry (15)
        dns3 = GtkEntry (15)
        ipTable.attach (gw, 1, 2, 0, 1)
        ipTable.attach (dns1, 1, 2, 2, 3)
        ipTable.attach (dns2, 1, 2, 3, 4)
        ipTable.attach (dns3, 1, 2, 4, 5)
        box.pack_start (ipTable, FALSE)

        
        return box

    
