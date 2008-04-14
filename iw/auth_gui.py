#
# auth_gui.py: gui authentication configuration dialog
#
# Copyright 2000-2002 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import gtk
import gui
from iw_gui import *
from rhpl.translate import _, N_

class AuthWindow (InstallWindow):

    htmlTag = "authconf"
    windowTitle = N_("Authentication Configuration")

    def setSensitivities (self, *args):
	if (not self.nis.get_active()):
	    self.nisDomain.set_sensitive (gtk.FALSE)
	    self.nisBroadcast.set_sensitive (gtk.FALSE)
	    self.nisServer.set_sensitive (gtk.FALSE)
	    self.nisDomainLabel.set_sensitive (gtk.FALSE)
	    self.nisServerLabel.set_sensitive (gtk.FALSE)
	else:
	    self.nisDomain.set_sensitive (gtk.TRUE)
	    self.nisDomainLabel.set_sensitive (gtk.TRUE)
	    self.nisBroadcast.set_sensitive (gtk.TRUE)

	    if (self.nisBroadcast.get_active()):
		self.nisServerLabel.set_sensitive (gtk.FALSE)
		self.nisServer.set_sensitive (gtk.FALSE)
	    else:
		self.nisServerLabel.set_sensitive (gtk.TRUE)
		self.nisServer.set_sensitive (gtk.TRUE)

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

        if self.md5.get_active ():
            self.auth.salt = 'md5'
        else:
            self.auth.salt = None
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

        box = gtk.VBox (gtk.FALSE, 10)

        nb = gtk.Notebook ()

        self.md5 = gtk.CheckButton (_("Enable _MD5 passwords"))
        self.shadow = gtk.CheckButton (_("Enable shado_w passwords"))

        # nis
        self.nis = gtk.CheckButton (_("Enable N_IS"))
        self.nisBroadcast = gtk.CheckButton (_("Use _broadcast to find NIS server"))
        self.nisDomain = gtk.Entry ()
        self.nisServer = gtk.Entry ()

        self.md5.set_active (self.auth.salt == 'md5')
        self.shadow.set_active (self.auth.useShadow)

        self.nis.set_active (self.auth.useNIS)
        self.nisDomain.set_text (self.auth.nisDomain)
        self.nisBroadcast.set_active (self.auth.nisuseBroadcast)
        self.nisServer.set_text (self.auth.nisServer )

        self.nisDomainLabel = gui.MnemonicLabel (_("NIS _Domain: "))
        self.nisDomainLabel.set_alignment (0, 0)
        self.nisDomainLabel.set_mnemonic_widget(self.nisDomain)
        self.nisServerLabel = gui.MnemonicLabel (_("NIS _Server: "))
        self.nisServerLabel.set_alignment (0, 0)
        self.nisServerLabel.set_mnemonic_widget(self.nisServer)

        self.nis.connect ("toggled", self.setSensitivities)
        self.nisBroadcast.connect ("toggled", self.setSensitivities)

        a = gtk.Alignment (0, 0)
        a.add (self.nisBroadcast)

        nistable = gtk.Table (10, 4, gtk.FALSE)
        nistable.attach (self.nis, 0, 10, 0, 1, gtk.FILL, gtk.SHRINK, 0.0, 0.5)

	spacer = gtk.Label("")
	spacer.set_size_request(10, 1)
        nistable.attach (spacer, 0, 1, 1, 2, gtk.SHRINK, gtk.SHRINK, 0.0, 0.5)
        
        nistable.attach (self.nisDomainLabel, 2, 3, 1, 2, gtk.FILL, gtk.SHRINK, 0.0, 0.5)
        nistable.attach (self.nisDomain, 3, 15, 1, 2, gtk.SHRINK, gtk.SHRINK, 0.0, 0.5)
        nistable.attach (a, 2, 10, 2, 3, gtk.SHRINK, gtk.SHRINK, 0.0, 0.5)
        nistable.attach (self.nisServerLabel, 2, 5, 3, 4, gtk.FILL, gtk.SHRINK, 0.0, 0.5)
        nistable.attach (self.nisServer, 3, 10, 3, 4, gtk.SHRINK, gtk.SHRINK, 0.0, 0.5)

        # ldap
        self.ldap = gtk.CheckButton (_("Enable _LDAP"))
        self.ldapServer = gtk.Entry ()
        self.ldapBasedn = gtk.Entry ()
        self.ldapTLS = gtk.CheckButton (_("Use _TLS lookups"))
        self.ldapServerLabel = gui.MnemonicLabel (_("LDAP _Server:"))
        self.ldapServerLabel.set_alignment (0, 0)
        self.ldapServerLabel.set_mnemonic_widget(self.ldapServer)
        self.ldapBasednLabel = gui.MnemonicLabel (_("LDAP _Base DN:"))
        self.ldapBasednLabel.set_alignment (0, 0)
        self.ldapBasednLabel.set_mnemonic_widget(self.ldapBasedn)

	# restore ldap settings
        self.ldap.set_active (self.auth.useLdap)
	self.ldapServer.set_text (self.auth.ldapServer)
        self.ldapBasedn.set_text (self.auth.ldapBasedn)
         
        ldaptable = gtk.Table (10, 4, gtk.FALSE)

        ldaptable.attach (self.ldap, 0, 10, 0, 1, gtk.FILL, gtk.SHRINK, 0.0, 0.5)

	spacer = gtk.Label("")
	spacer.set_size_request(10, 1)
        ldaptable.attach (spacer, 0, 1, 1, 2, gtk.SHRINK, gtk.SHRINK, 0.0, 0.5)
        ldaptable.attach (self.ldapServerLabel, 2, 3, 1, 2, gtk.FILL, gtk.SHRINK, 0.0, 0.5)
        ldaptable.attach (self.ldapServer, 3, 10, 1, 2, gtk.SHRINK, gtk.SHRINK, 0.0, 0.5)

        ldaptable.attach (self.ldapBasednLabel, 2, 3, 2, 3, gtk.FILL, gtk.SHRINK, 0.0, 0.5)
        ldaptable.attach (self.ldapBasedn, 3, 10, 2, 3, gtk.SHRINK, gtk.SHRINK, 0.0, 0.5)
        a = gtk.Alignment (0, 0)
        a.add (self.ldapTLS)
        ldaptable.attach (a, 2, 3, 3, 4, gtk.SHRINK, gtk.SHRINK, 0.0, 0.5) 
        
        self.ldap.connect ("toggled", self.setSensitivities)

        # krb5
        self.krb5 = gtk.CheckButton (_("Enable _Kerberos"))
        self.krb5Realm = gtk.Entry ()
        self.krb5Kdc = gtk.Entry ()
        self.krb5Admin = gtk.Entry ()
        self.krb5RealmLabel = gui.MnemonicLabel (_("R_ealm:"))
        self.krb5RealmLabel.set_alignment (0, 0)
        self.krb5RealmLabel.set_mnemonic_widget(self.krb5Realm)        
        self.krb5KdcLabel = gui.MnemonicLabel (_("K_DC:"))
        self.krb5KdcLabel.set_alignment (0, 0)
        self.krb5KdcLabel.set_mnemonic_widget(self.krb5Kdc)
        self.krb5AdminLabel = gui.MnemonicLabel (_("_Admin Server:"))
        self.krb5AdminLabel.set_alignment (0, 0)
        self.krb5AdminLabel.set_mnemonic_widget(self.krb5Admin)

        # restore krb5 settings
        self.krb5.set_active (self.auth.useKrb5)
        self.krb5Realm.set_text (self.auth.krb5Realm)
        self.krb5Kdc.set_text (self.auth.krb5Kdc)
        self.krb5Admin.set_text (self.auth.krb5Admin)
        
        krb5table = gtk.Table (10, 4, gtk.FALSE)

        krb5table.attach (self.krb5, 0, 10, 0, 1, gtk.FILL, gtk.SHRINK, 0.0, 0.5)

	spacer = gtk.Label("")
	spacer.set_size_request(10, 1)
        krb5table.attach (spacer, 0, 1, 1, 2, gtk.SHRINK, gtk.SHRINK, 0.0, 0.5)
        krb5table.attach (self.krb5RealmLabel, 2, 3, 1, 2, gtk.FILL, gtk.SHRINK, 0.0, 0.5)
        krb5table.attach (self.krb5Realm, 3, 10, 1, 2, gtk.SHRINK, gtk.SHRINK, 0.0, 0.5)

        krb5table.attach (self.krb5KdcLabel, 2, 3, 2, 3, gtk.FILL, gtk.SHRINK, 0.0, 0.5)
        krb5table.attach (self.krb5Kdc, 3, 10, 2, 3, gtk.SHRINK, gtk.SHRINK, 0.0, 0.5)

        krb5table.attach (self.krb5AdminLabel, 2, 3, 3, 4, gtk.FILL, gtk.SHRINK, 0.0, 0.5)
        krb5table.attach (self.krb5Admin, 3, 10, 3, 4, gtk.SHRINK, gtk.SHRINK, 0.0, 0.5)

        self.krb5.connect ("toggled", self.setSensitivities)

        # samba
        self.samba = gtk.CheckButton (_("Enable SMB _Authentication"))
        self.sambaServer = gtk.Entry ()
        self.sambaWorkgroup = gtk.Entry ()
        self.sambaLabel1 = gui.MnemonicLabel (_("SMB _Server:"))
        self.sambaLabel1.set_alignment (0, 0)
        self.sambaLabel1.set_mnemonic_widget(self.sambaServer)
        self.sambaLabel2 = gui.MnemonicLabel (_("SMB Work_group:"))
        self.sambaLabel2.set_alignment (0, 0)
        self.sambaLabel2.set_mnemonic_widget(self.sambaWorkgroup)

 	# restore ldap settings
        self.samba.set_active (self.auth.useSamba)
 	self.sambaServer.set_text (self.auth.sambaServer)
        self.sambaWorkgroup.set_text (self.auth.sambaWorkgroup)
         
        sambatable = gtk.Table (10, 3, gtk.FALSE)

        sambatable.attach (self.samba, 0, 10, 0, 1, gtk.FILL, gtk.SHRINK, 0.0, 0.5)

        spacer = gtk.Label("")
        spacer.set_size_request(10, 1)
        sambatable.attach (spacer, 0, 1, 1, 2, gtk.SHRINK, gtk.SHRINK, 0.0, 0.5)
        sambatable.attach (self.sambaLabel1, 2, 3, 1, 2, gtk.FILL, gtk.SHRINK, 0.0, 0.5)
        sambatable.attach (self.sambaServer, 3, 10, 1, 2, gtk.SHRINK, gtk.SHRINK, 0.0, 0.5)

        sambatable.attach (self.sambaLabel2, 2, 3, 2, 3, gtk.FILL, gtk.SHRINK, 0.0, 0.5)
        sambatable.attach (self.sambaWorkgroup, 3, 10, 2, 3, gtk.SHRINK, gtk.SHRINK, 0.0, 0.5)
        
        self.samba.connect ("toggled", self.setSensitivities)

# pack everything

	self.setSensitivities()

        nisLabel = gtk.Label (_("NIS"))
        ldapLabel = gtk.Label (_("LDAP"))
        krb5Label = gtk.Label (_("Kerberos 5"))
        sambaLabel = gtk.Label (_("SMB"))

        nb.append_page(nistable, nisLabel)
        nb.append_page(ldaptable, ldapLabel)
        nb.append_page(krb5table, krb5Label)
        nb.append_page(sambatable, sambaLabel)


        box.pack_start (self.md5, gtk.FALSE)
        box.pack_start (self.shadow, gtk.FALSE)
        box.pack_start (nb, gtk.TRUE)
        
	box.set_border_width (5)
        
        return box

