from gtk import *
from iw import *
from gui import _

class AuthWindow (InstallWindow):

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        self.todo = ics.getToDo ()
        ics.setTitle (_("Authentication Configuration"))
##         ics.setHTML ("<HTML><BODY>Select authentication methods"
##                      "</BODY></HTML>")
        ics.readHTML ("authconf")
	ics.setNextEnabled (TRUE)

    def setSensitivities (self, *args):
	if (not self.nis.get_active()):
	    self.nisDomain.set_sensitive (FALSE)
	    self.nisBroadcast.set_sensitive (FALSE)
	    self.nisServer.set_sensitive (FALSE)
	    self.domainLabel.set_sensitive (FALSE)
	    self.serverLabel.set_sensitive (FALSE)
	else:
	    self.nisDomain.set_sensitive (TRUE)
	    self.domainLabel.set_sensitive (TRUE)
	    self.nisBroadcast.set_sensitive (TRUE)

	    if (self.nisBroadcast.get_active()):
		self.serverLabel.set_sensitive (FALSE)
		self.nisServer.set_sensitive (FALSE)
	    else:
		self.serverLabel.set_sensitive (TRUE)
		self.nisServer.set_sensitive (TRUE)

    def getNext(self):
	if not self.__dict__.has_key("md5"):
	    return None

        self.todo.auth.useMD5 = self.md5.get_active ()
        self.todo.auth.useShadow = self.shadow.get_active ()

        self.todo.auth.useNIS = self.nis.get_active ()
        self.todo.auth.useBroadcast = self.nisBroadcast.get_active ()
        self.todo.auth.domain = self.nisDomain.get_text ()
        self.todo.auth.server = self.nisServer.get_text ()

    def getScreen (self):
        box = GtkVBox (FALSE, 10)
        self.md5 = GtkCheckButton (_("Enable MD5 passwords"))
        self.shadow = GtkCheckButton (_("Enable shadow passwords"))

        self.nis = GtkCheckButton (_("Enable NIS"))
        self.nisBroadcast = GtkCheckButton (_("Use broadcast to find NIS server"))
        self.nisDomain = GtkEntry ()
        self.nisServer = GtkEntry ()

        self.md5.set_active (self.todo.auth.useMD5)
        self.shadow.set_active (self.todo.auth.useShadow)

        self.nis.set_active (self.todo.auth.useNIS)
        self.nisDomain.set_text (self.todo.auth.domain)
        self.nisBroadcast.set_active (self.todo.auth.useBroadcast)
        self.nisServer.set_text (self.todo.auth.server )

        self.domainLabel = GtkLabel (_("NIS Domain: "))
        self.domainLabel.set_alignment (0, 0)
        self.serverLabel = GtkLabel (_("NIS Server: "))
        self.serverLabel.set_alignment (0, 0)

	self.setSensitivities()

        self.nis.connect ("toggled", self.setSensitivities)
        self.nisBroadcast.connect ("toggled", self.setSensitivities)

        hbox1 = GtkHBox ()
        hbox1.pack_start (self.domainLabel, FALSE)
        hbox1.pack_start (self.nisDomain)

        hbox2 = GtkHBox ()
        hbox2.pack_start (self.serverLabel, FALSE)
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

