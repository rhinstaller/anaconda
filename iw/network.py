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


    def getNext (self):
        self.setupTODO ()
        return None

    def focusInIP (self, *args):
        if self.nm.get_text() == "":
            self.calcNetmask ()
            self.calcNMHandler = self.ip.connect ("changed", self.calcNetmask)

    def focusOutIP (self, *args):
        if self.calcNMHandler != None:
            self.ip.disconnect (self.calcNMHandler)
            self.calcNMHandler = None
        

    def setupTODO (self):
        if self.DHCPcb.get_active ():
            self.dev.set (("bootproto", "dhcp"))
            self.dev.unset ("ipaddr", "netmask", "network", "broadcast")
        else:
            try:
                network, broadcast = inet_calcNetBroad (self.ip.get_text (), self.nm.get_text ())
                self.dev.set (("bootproto", "static"))
                self.dev.set (("ipaddr", self.ip.get_text ()), ("netmask", self.nm.get_text ()),
                              ("network", network), ("broadcast", broadcast))
                self.todo.network.gateway = self.gw.get_text ()
                self.todo.network.primaryNS = self.dns1.get_text ()
                self.todo.network.guessHostnames ()
            except:
                pass
            
        self.dev.set (("onboot", "yes"))


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

    def devSelected (self, widget, key):
        self.setupTODO ()
        self.dev = self.devs[key]
        if self.dev.get ("bootproto") == "dhcp":
            self.DHCPcb.set_active (TRUE)
            self.ip.set_text ("")
            self.nm.set_text ("")
        else:
            self.DHCPcb.set_active (FALSE)
            self.ip.set_text (self.dev.get ("ipaddr"))
            self.nm.set_text (self.dev.get ("netmask"))

    def getScreen (self):
        box = GtkVBox ()
        
        devLine = GtkHBox ()
        devLabel = GtkLabel ("Device: ")
        devLabel.set_alignment (0, 0)
        devLine.pack_start (devLabel)
        menu = GtkMenu ()
        self.devs = self.todo.network.available ()
        self.devs.keys ().sort ()
        self.dev = self.devs[self.devs.keys()[0]]
        for i in self.devs.keys ():
            menu_item = GtkMenuItem (i)
            menu_item.connect ("activate", self.devSelected, i)
            menu.append (menu_item)
        devMenu = GtkOptionMenu ()
        devMenu.set_menu (menu)
        devLine.pack_start (devMenu)
        box.pack_start (devLine, FALSE)

        self.DHCPcb = GtkCheckButton ("Configure using DHCP")
        self.DHCPcb.set_active (TRUE)

        box.pack_start (self.DHCPcb, FALSE)
        box.pack_start (GtkHSeparator (), FALSE, padding=3)

        ipTable = GtkTable (2, 2)
        self.ipTable = ipTable
        ipTable.attach (GtkLabel ("IP Address:"), 0, 1, 0, 1)
        ipTable.attach (GtkLabel ("Netmask:"), 0, 1, 1, 2)
        self.ip = GtkEntry (15)
        self.ip.connect ("focus_in_event", self.focusInIP)
        self.ip.connect ("focus_out_event", self.focusOutIP)
        self.ip.connect ("activate", lambda widget, box=box: box.focus (DIR_TAB_FORWARD))
        self.nm = GtkEntry (15)
        self.nm.connect ("activate", lambda widget, box=box: box.focus (DIR_TAB_FORWARD))
        ipTable.attach (self.ip, 1, 2, 0, 1)
        ipTable.attach (self.nm, 1, 2, 1, 2)
        box.pack_start (ipTable, FALSE)

        box.pack_start (GtkHSeparator (), FALSE, padding=3)
        
        ipTable = GtkTable (5, 2)
        ipTable.attach (GtkLabel ("Gateway: "), 0, 1, 0, 1)
        ipTable.attach (GtkLabel ("Primary DNS: "), 0, 1, 2, 3)
        ipTable.attach (GtkLabel ("Secondary DNS: "), 0, 1, 3, 4)
        ipTable.attach (GtkLabel ("Ternary DNS: "), 0, 1, 4, 5)
        self.gw = GtkEntry (15)
        self.gw.connect ("activate", lambda widget, box=box: box.focus (DIR_TAB_FORWARD))
        self.dns1 = GtkEntry (15)
        self.dns1.connect ("activate", lambda widget, box=box: box.focus (DIR_TAB_FORWARD))
        self.dns2 = GtkEntry (15)
        self.dns2.connect ("activate", lambda widget, box=box: box.focus (DIR_TAB_FORWARD))
        self.dns3 = GtkEntry (15)
        ipTable.attach (self.gw, 1, 2, 0, 1)
        ipTable.attach (self.dns1, 1, 2, 2, 3)
        ipTable.attach (self.dns2, 1, 2, 3, 4)
        ipTable.attach (self.dns3, 1, 2, 4, 5)
        box.pack_start (ipTable, FALSE)

        
        return box

    
