from gtk import *
from iw import *

class AuthWindow (InstallWindow):

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        self.todo = ics.getToDo ()
        ics.setTitle ("Authentication Configuration")
        ics.setHTML ("<HTML><BODY>Select authentication methods"
                     "</BODY></HTML>")
	ics.setNextEnabled (TRUE)

    def getScreen (self):
        box = GtkVBox (FALSE, 10)
        self.md5 = GtkCheckButton ("Enable MD5 passwords")
        self.shadow = GtkCheckButton ("Enable shadow passwords")

        self.nis = GtkCheckButton ("Enable NIS")
        self.nisBroadcast = GtkCheckButton ("Use broadcast to find NIS server")
        self.nisDomain = GtkEntry ()
        self.nisServer = GtkEntry ()

        domainLabel = GtkLabel ("NIS Domain: ")
        domainLabel.set_alignment (0, 0)
        serverLabel = GtkLabel ("NIS Server: ")
        serverLabel.set_alignment (0, 0)

        hbox1 = GtkHBox ()
        hbox1.pack_start (domainLabel, FALSE)
        hbox1.pack_start (self.nisDomain)

        hbox2 = GtkHBox ()
        hbox2.pack_start (serverLabel, FALSE)
        hbox2.pack_start (self.nisServer)

        a = GtkAlignment (0, 0)
        a.add (self.nisBroadcast)

        table = GtkTable (10, 4)
        table.attach (self.nis, 0, 10, 0, 1)
        table.attach (hbox1, 2, 10, 1, 2)
        table.attach (a, 2, 10, 2, 3, xoptions = EXPAND|FILL)
        table.attach (hbox2, 4, 10, 3, 4)

        box.pack_start (self.md5, FALSE)
        box.pack_start (self.shadow, FALSE)
        box.pack_start (table, FALSE)

        return box

