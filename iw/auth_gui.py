#
# auth_gui.py: gui authentication configuration dialog
#
# Copyright 2001 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

from gtk import *
from iw_gui import *
from translate import _, N_

class AuthWindow (InstallWindow):

    htmlTag = "authconf"
    windowTitle = N_("Authentication Configuration")

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
        self.ldapTLS.set_sensitive (ldapactive)

        krb5active = self.krb5.get_active()
        self.krb5RealmLabel.set_sensitive (krb5active)
        self.krb5Realm.set_sensitive (krb5active)
        self.krb5KdcLabel.set_sensitive (krb5active)
        self.krb5Kdc.set_sensitive (krb5active)
        self.krb5AdminLabel.set_sensitive (krb5active)
        self.krb5Admin.set_sensitive (krb5active)

        sambaactive = self.samba.get_active()
        self.sambaLabel1.set_sensitive(sambaactive)
        self.sambaLabel2.set_sensitive(sambaactive)
        self.sambaServer.set_sensitive(sambaactive)
        self.sambaWorkgroup.set_sensitive(sambaactive)

    def getNext(self):
	if not self.__dict__.has_key("md5"):
	    return None

        self.auth.useMD5 = self.md5.get_active ()
        self.auth.useShadow = self.shadow.get_active ()

        self.auth.useNIS = self.nis.get_active ()
        self.auth.nisuseBroadcast = self.nisBroadcast.get_active ()
        self.auth.nisDomain = self.nisDomain.get_text ()
        self.auth.nisServer = self.nisServer.get_text ()

        self.auth.useLdap = self.ldap.get_active ()
        self.auth.useLdapauth = self.ldap.get_active ()
        self.auth.ldapServer = self.ldapServer.get_text ()
        self.auth.ldapBasedn = self.ldapBasedn.get_text ()
        self.auth.ldapTLS = self.ldapTLS.get_active ()

        self.auth.useKrb5 = self.krb5.get_active ()
        self.auth.krb5Realm = self.krb5Realm.get_text ()
        self.auth.krb5Kdc = self.krb5Kdc.get_text ()
        self.auth.krb5Admin = self.krb5Admin.get_text ()

        self.auth.useSamba = self.samba.get_active ()
        self.auth.sambaServer = self.sambaServer.get_text()
        self.auth.sambaWorkgroup = self.sambaWorkgroup.get_text()

    def getScreen (self, auth):
	self.auth = auth

        box = VBox (FALSE, 10)

        nb = GtkNotebook ()

        self.md5 = GtkCheckButton (_("Enable MD5 passwords"))
        self.shadow = GtkCheckButton (_("Enable shadow passwords"))

        # nis
        self.nis = GtkCheckButton (_("Enable NIS"))
        self.nisBroadcast = GtkCheckButton (_("Use broadcast to find NIS server"))
        self.nisDomain = GtkEntry ()
        self.nisServer = GtkEntry ()

        self.md5.set_active (self.auth.useMD5)
        self.shadow.set_active (self.auth.useShadow)

        self.nis.set_active (self.auth.useNIS)
        self.nisDomain.set_text (self.auth.nisDomain)
        self.nisBroadcast.set_active (self.auth.nisuseBroadcast)
        self.nisServer.set_text (self.auth.nisServer )

        self.nisDomainLabel = GtkLabel (_("NIS Domain: "))
        self.nisDomainLabel.set_alignment (0, 0)
        self.nisServerLabel = GtkLabel (_("NIS Server: "))
        self.nisServerLabel.set_alignment (0, 0)

        self.nis.connect ("toggled", self.setSensitivities)
        self.nisBroadcast.connect ("toggled", self.setSensitivities)

        a = GtkAlignment (0, 0)
        a.add (self.nisBroadcast)

        nistable = GtkTable (10, 4, FALSE)
        nistable.attach (self.nis, 0, 10, 0, 1, FILL, SHRINK, 0.0, 0.5)

	spacer = GtkLabel("")
	spacer.set_usize(10, 1)
        nistable.attach (spacer, 0, 1, 1, 2, SHRINK, SHRINK, 0.0, 0.5)
        
        nistable.attach (self.nisDomainLabel, 2, 3, 1, 2, FILL, SHRINK, 0.0, 0.5)
        nistable.attach (self.nisDomain, 3, 15, 1, 2, SHRINK, SHRINK, 0.0, 0.5)
        nistable.attach (a, 2, 10, 2, 3, SHRINK, SHRINK, 0.0, 0.5)
        nistable.attach (self.nisServerLabel, 2, 5, 3, 4, FILL, SHRINK, 0.0, 0.5)
        nistable.attach (self.nisServer, 3, 10, 3, 4, SHRINK, SHRINK, 0.0, 0.5)

        # ldap
        self.ldap = GtkCheckButton (_("Enable LDAP"))
        self.ldapServer = GtkEntry ()
        self.ldapBasedn = GtkEntry ()
        self.ldapTLS = GtkCheckButton (_("Use TLS lookups"))
        self.ldapServerLabel = GtkLabel (_("LDAP Server:"))
        self.ldapServerLabel.set_alignment (0, 0)
        self.ldapBasednLabel = GtkLabel (_("LDAP Base DN:"))
        self.ldapBasednLabel.set_alignment (0, 0)

	# restore ldap settings
        self.ldap.set_active (self.auth.useLdap)
	self.ldapServer.set_text (self.auth.ldapServer)
        self.ldapBasedn.set_text (self.auth.ldapBasedn)
         
        ldaptable = GtkTable (10, 4, FALSE)

        ldaptable.attach (self.ldap, 0, 10, 0, 1, FILL, SHRINK, 0.0, 0.5)

	spacer = GtkLabel("")
	spacer.set_usize(10, 1)
        ldaptable.attach (spacer, 0, 1, 1, 2, SHRINK, SHRINK, 0.0, 0.5)
        ldaptable.attach (self.ldapServerLabel, 2, 3, 1, 2, FILL, SHRINK, 0.0, 0.5)
        ldaptable.attach (self.ldapServer, 3, 10, 1, 2, SHRINK, SHRINK, 0.0, 0.5)

        ldaptable.attach (self.ldapBasednLabel, 2, 3, 2, 3, FILL, SHRINK, 0.0, 0.5)
        ldaptable.attach (self.ldapBasedn, 3, 10, 2, 3, SHRINK, SHRINK, 0.0, 0.5)
        a = GtkAlignment (0, 0)
        a.add (self.ldapTLS)
        ldaptable.attach (a, 2, 3, 3, 4, SHRINK, SHRINK, 0.0, 0.5) 
        
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

        # restore krb5 settings
        self.krb5.set_active (self.auth.useKrb5)
        self.krb5Realm.set_text (self.auth.krb5Realm)
        self.krb5Kdc.set_text (self.auth.krb5Kdc)
        self.krb5Admin.set_text (self.auth.krb5Admin)
        
        krb5table = GtkTable (10, 4, FALSE)

        krb5table.attach (self.krb5, 0, 10, 0, 1, FILL, SHRINK, 0.0, 0.5)

	spacer = GtkLabel("")
	spacer.set_usize(10, 1)
        krb5table.attach (spacer, 0, 1, 1, 2, SHRINK, SHRINK, 0.0, 0.5)
        krb5table.attach (self.krb5RealmLabel, 2, 3, 1, 2, FILL, SHRINK, 0.0, 0.5)
        krb5table.attach (self.krb5Realm, 3, 10, 1, 2, SHRINK, SHRINK, 0.0, 0.5)

        krb5table.attach (self.krb5KdcLabel, 2, 3, 2, 3, FILL, SHRINK, 0.0, 0.5)
        krb5table.attach (self.krb5Kdc, 3, 10, 2, 3, SHRINK, SHRINK, 0.0, 0.5)

        krb5table.attach (self.krb5AdminLabel, 2, 3, 3, 4, FILL, SHRINK, 0.0, 0.5)
        krb5table.attach (self.krb5Admin, 3, 10, 3, 4, SHRINK, SHRINK, 0.0, 0.5)

        self.krb5.connect ("toggled", self.setSensitivities)

        # samba
        self.samba = GtkCheckButton (_("Enable SMB Authentication"))
        self.sambaServer = GtkEntry ()
        self.sambaWorkgroup = GtkEntry ()
        self.sambaLabel1 = GtkLabel (_("SMB Server:"))
        self.sambaLabel1.set_alignment (0, 0)
        self.sambaLabel2 = GtkLabel (_("SMB Workgroup:"))
        self.sambaLabel2.set_alignment (0, 0)

 	# restore ldap settings
        self.samba.set_active (self.auth.useSamba)
 	self.sambaServer.set_text (self.auth.sambaServer)
        self.sambaWorkgroup.set_text (self.auth.sambaWorkgroup)
         
        sambatable = GtkTable (10, 3, FALSE)

        sambatable.attach (self.samba, 0, 10, 0, 1, FILL, SHRINK, 0.0, 0.5)

        spacer = GtkLabel("")
        spacer.set_usize(10, 1)
        sambatable.attach (spacer, 0, 1, 1, 2, SHRINK, SHRINK, 0.0, 0.5)
        sambatable.attach (self.sambaLabel1, 2, 3, 1, 2, FILL, SHRINK, 0.0, 0.5)
        sambatable.attach (self.sambaServer, 3, 10, 1, 2, SHRINK, SHRINK, 0.0, 0.5)

        sambatable.attach (self.sambaLabel2, 2, 3, 2, 3, FILL, SHRINK, 0.0, 0.5)
        sambatable.attach (self.sambaWorkgroup, 3, 10, 2, 3, SHRINK, SHRINK, 0.0, 0.5)
        
        self.samba.connect ("toggled", self.setSensitivities)

# pack everything

	self.setSensitivities()

        nisLabel = GtkLabel (_("NIS"))
        ldapLabel = GtkLabel (_("LDAP"))
        krb5Label = GtkLabel (_("Kerberos 5"))
        sambaLabel = GtkLabel (_("SMB"))

        nb.append_page(nistable, nisLabel)
        nb.append_page(ldaptable, ldapLabel)
        nb.append_page(krb5table, krb5Label)
        nb.append_page(sambatable, sambaLabel)


        box.pack_start (self.md5, FALSE)
        box.pack_start (self.shadow, FALSE)
        box.pack_start (nb, TRUE)
        
	box.set_border_width (5)
        
        return box

