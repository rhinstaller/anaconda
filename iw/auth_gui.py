from gtk import *
from iw_gui import *
from translate import _

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
	    self.nisDomainLabel.set_sensitive (FALSE)
	    self.nisServerLabel.set_sensitive (FALSE)
	else:
	    self.nisDomain.set_sensitive (TRUE)
	    self.nisDomainLabel.set_sensitive (TRUE)
	    self.nisBroadcast.set_sensitive (TRUE)

	    if (self.nisBroadcast.get_active()):
		self.nisServerLabel.set_sensitive (FALSE)
		self.nisServer.set_sensitive (FALSE)
	    else:
		self.nisServerLabel.set_sensitive (TRUE)
		self.nisServer.set_sensitive (TRUE)

        ldapactive = self.ldap.get_active()
        self.ldapServerLabel.set_sensitive (ldapactive)
        self.ldapServer.set_sensitive (ldapactive)
        self.ldapBasednLabel.set_sensitive (ldapactive)
        self.ldapBasedn.set_sensitive (ldapactive)

        krb5active = self.krb5.get_active()
        self.krb5RealmLabel.set_sensitive (krb5active)
        self.krb5Realm.set_sensitive (krb5active)
        self.krb5KdcLabel.set_sensitive (krb5active)
        self.krb5Kdc.set_sensitive (krb5active)
        self.krb5AdminLabel.set_sensitive (krb5active)
        self.krb5Admin.set_sensitive (krb5active)


    def getNext(self):
	if not self.__dict__.has_key("md5"):
	    return None

        self.todo.auth.useMD5 = self.md5.get_active ()
        self.todo.auth.useShadow = self.shadow.get_active ()

        self.todo.auth.useNIS = self.nis.get_active ()
        self.todo.auth.nisuseBroadcast = self.nisBroadcast.get_active ()
        self.todo.auth.nisDomain = self.nisDomain.get_text ()
        self.todo.auth.nisServer = self.nisServer.get_text ()

        self.todo.auth.useLdap = self.ldap.get_active ()
        self.todo.auth.ldapServer = self.ldapServer.get_text ()
        self.todo.auth.ldapBasedn = self.ldapBasedn.get_text ()

        self.todo.auth.useKrb5 = self.krb5.get_active ()
        self.todo.auth.krb5Realm = self.krb5Realm.get_text ()
        self.todo.auth.krb5Kdc = self.krb5Kdc.get_text ()
        self.todo.auth.krb5Admin = self.krb5Admin.get_text ()
        
    def getScreen (self):
        box = GtkVBox (FALSE, 10)
        self.md5 = GtkCheckButton (_("Enable MD5 passwords"))
        self.shadow = GtkCheckButton (_("Enable shadow passwords"))

        # nis
        self.nis = GtkCheckButton (_("Enable NIS"))
        self.nisBroadcast = GtkCheckButton (_("Use broadcast to find NIS server"))
        self.nisDomain = GtkEntry ()
        self.nisServer = GtkEntry ()

        self.md5.set_active (self.todo.auth.useMD5)
        self.shadow.set_active (self.todo.auth.useShadow)

        self.nis.set_active (self.todo.auth.useNIS)
        self.nisDomain.set_text (self.todo.auth.nisDomain)
        self.nisBroadcast.set_active (self.todo.auth.nisuseBroadcast)
        self.nisServer.set_text (self.todo.auth.nisServer )

        self.nisDomainLabel = GtkLabel (_("NIS Domain: "))
        self.nisDomainLabel.set_alignment (0, 0)
        self.nisServerLabel = GtkLabel (_("NIS Server: "))
        self.nisServerLabel.set_alignment (0, 0)

        self.nis.connect ("toggled", self.setSensitivities)
        self.nisBroadcast.connect ("toggled", self.setSensitivities)

        hbox1 = GtkHBox ()
        hbox1.pack_start (self.nisDomainLabel, FALSE)
        hbox1.pack_start (self.nisDomain)

        hbox2 = GtkHBox ()
        hbox2.pack_start (self.nisServerLabel, FALSE)
        hbox2.pack_start (self.nisServer)

        a = GtkAlignment (0, 0)
        a.add (self.nisBroadcast)

        nistable = GtkTable (10, 4)
        nistable.attach (self.nis, 0, 10, 0, 1)
        nistable.attach (hbox1, 2, 10, 1, 2)
        nistable.attach (a, 2, 10, 2, 3, xoptions = EXPAND|FILL)
        nistable.attach (hbox2, 4, 10, 3, 4)

        # ldap
        self.ldap = GtkCheckButton (_("Enable LDAP"))
        self.ldapServer = GtkEntry ()
        self.ldapBasedn = GtkEntry ()
        self.ldapServerLabel = GtkLabel (_("LDAP Server:"))
        self.ldapServerLabel.set_alignment (0, 0)
        self.ldapBasednLabel = GtkLabel (_("LDAP Base DN:"))
        self.ldapBasednLabel.set_alignment (0, 0)

        ldaptable = GtkTable (10, 4)

        ldaptable.attach (self.ldap, 0, 10, 0, 1)

	spacer = GtkLabel("")
	spacer.set_usize(10, 1)
        ldaptable.attach (spacer, 0, 1, 1, 2)
        ldaptable.attach (self.ldapServerLabel, 2, 3, 1, 2)
        ldaptable.attach (self.ldapServer, 3, 10, 1, 2)

	spacer = GtkLabel("")
	spacer.set_usize(10, 1)
        ldaptable.attach (spacer, 0, 1, 2, 3)
        ldaptable.attach (self.ldapBasednLabel, 2, 3, 2, 3)
        ldaptable.attach (self.ldapBasedn, 3, 10, 2, 3)

        self.ldap.connect ("toggled", self.setSensitivities)

        # krb5
        self.krb5 = GtkCheckButton (_("Enable Kerberos"))
        self.krb5Realm = GtkEntry ()
        self.krb5Kdc = GtkEntry ()
        self.krb5Admin = GtkEntry ()
        self.krb5RealmLabel = GtkLabel (_("Realm:"))
        self.krb5RealmLabel.set_alignment (0, 0)
        self.krb5KdcLabel = GtkLabel (_("KDC:"))
        self.krb5KdcLabel.set_alignment (0, 0)
        self.krb5AdminLabel = GtkLabel (_("Admin Server:"))
        self.krb5AdminLabel.set_alignment (0, 0)

        krb5table = GtkTable (10, 4)

        krb5table.attach (self.krb5, 0, 10, 0, 1)

	spacer = GtkLabel("")
	spacer.set_usize(10, 1)
        krb5table.attach (spacer, 0, 1, 1, 2)
        krb5table.attach (self.krb5RealmLabel, 2, 3, 1, 2)
        krb5table.attach (self.krb5Realm, 3, 10, 1, 2)

	spacer = GtkLabel("")
	spacer.set_usize(10, 1)
        krb5table.attach (spacer, 0, 1, 2, 3)
        krb5table.attach (self.krb5KdcLabel, 2, 3, 2, 3)
        krb5table.attach (self.krb5Kdc, 3, 10, 2, 3)

	spacer = GtkLabel("")
	spacer.set_usize(10, 1)
        krb5table.attach (spacer, 0, 1, 3, 4)
        krb5table.attach (self.krb5AdminLabel, 2, 3, 3, 4)
        krb5table.attach (self.krb5Admin, 3, 10, 3, 4)

        self.krb5.connect ("toggled", self.setSensitivities)

# pack everything

	self.setSensitivities()

        box.pack_start (self.md5, FALSE)
        box.pack_start (self.shadow, FALSE)
        box.pack_start (nistable, FALSE)
        box.pack_start (ldaptable, FALSE)
        box.pack_start (krb5table, FALSE)
        
	box.set_border_width (5)

        
        return box

