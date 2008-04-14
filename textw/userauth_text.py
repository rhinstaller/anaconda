#
# userauth_text.py: text mode authentication setup dialogs
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

from snack import *
from constants_text import *
from rhpl.translate import _
import iutil
from flags import flags

def has_bad_chars(pw):
    allowed = string.digits + string.ascii_letters + string.punctuation + " "
    for letter in pw:
        if letter not in allowed:
            return 1
    return 0

class RootPasswordWindow:
    def __call__ (self, screen, intf, rootPw):
        toplevel = GridFormHelp (screen, _("Root Password"), "rootpw", 1, 3)

        toplevel.add (TextboxReflowed(37, _("Pick a root password. You must "
				"type it twice to ensure you know "
				"what it is and didn't make a mistake "
				"in typing. Remember that the "
				"root password is a critical part "
				"of system security!")), 0, 0, (0, 0, 0, 1))

	pw = rootPw.getPure()
	if not pw: pw = ""

        entry1 = Entry (24, password = 1, text = pw)
        entry2 = Entry (24, password = 1, text = pw)
        passgrid = Grid (2, 2)
        passgrid.setField (Label (_("Password:")), 0, 0, (0, 0, 1, 0), anchorLeft = 1)
        passgrid.setField (Label (_("Password (confirm):")), 0, 1, (0, 0, 1, 0), anchorLeft = 1)
        passgrid.setField (entry1, 1, 0)
        passgrid.setField (entry2, 1, 1)
        toplevel.add (passgrid, 0, 1, (0, 0, 0, 1))
        
        bb = ButtonBar (screen, (TEXT_OK_BUTTON, TEXT_BACK_BUTTON))
        toplevel.add (bb, 0, 2, growx = 1)

        while 1:
            toplevel.setCurrent (entry1)
            result = toplevel.run ()
            rc = bb.buttonPressed (result)
            if rc == TEXT_BACK_CHECK:
                screen.popWindow()
                return INSTALL_BACK
            if len (entry1.value ()) < 6:
                ButtonChoiceWindow(screen, _("Password Length"),
		       _("The root password must be at least 6 characters "
			 "long."),
		       buttons = [ TEXT_OK_BUTTON ], width = 50)
            elif entry1.value () != entry2.value ():
                ButtonChoiceWindow(screen, _("Password Mismatch"),
		       _("The passwords you entered were different. Please "
			 "try again."),
		       buttons = [ TEXT_OK_BUTTON ], width = 50)
            elif has_bad_chars(entry1.value()):
                ButtonChoiceWindow(screen, _("Error with Password"),
		       _("Requested password contains non-ascii characters "
                         "which are not allowed for use in password."),
		       buttons = [ TEXT_OK_BUTTON ], width = 50)
            else:
                break

            entry1.set ("")
            entry2.set ("")

        screen.popWindow()
        rootPw.set (entry1.value ())
        return INSTALL_OK

class UsersWindow:
    def editWindow (self, user, text, edit = 0, cancelText = None):
	if (not cancelText):
	    cancelText = _("Cancel")

        systemUsers = ['root', 'bin', 'daemon', 'adm', 'lp', 'sync', 'shutdown', 'halt', 'mail',
                       'news', 'uucp', 'operator', 'games', 'gopher', 'ftp', 'nobody', 'nscd',
                       'mailnull', 'rpm', 'ident', 'rpc', 'rpcuser', 'radvd', 'xfs', 'gdm', 'apache',
                       'squid']

        username = Entry (16, user["id"], scroll=0)
        currentid = user["id"]
        pass1 = Entry (10, user["password"], password = 1)
        pass2 = Entry (10, user["password"], password = 1)
        fullname = Entry (20, user["name"], scroll = 1)

	if edit:
	    title = _("Edit User")
	    helptag = "edituser"
	else:
	    title = _("Add User")
	    helptag = "adduser"

        while 1:
            (rc, ent) = EntryWindow (self.screen, title, text,
			 [ (_("User Name"), username),
			   (_("Password"), pass1),
			   (_("Password (confirm)"), pass2),
                           (_("Full Name"), fullname)],
			 buttons = [ TEXT_OK_BUTTON, (cancelText, "cancel") ],
			 help = helptag)
            
            if rc == "cancel":
                return INSTALL_BACK
            
	    if not len(pass1.value()) and not len(pass2.value()) and \
	       not len(username.value()) and not len(fullname.value()):
                return INSTALL_OK

            if (not iutil.validUser(username.value())):
		ButtonChoiceWindow(self.screen, _("Bad User Name"),
                                   _("User names must "
                                     "contain only characters "
                                     "A-Z, a-z, and 0-9."),
                                   buttons = [ TEXT_OK_BUTTON ], width = 50)
		continue
                
	    if not username.value ():
		ButtonChoiceWindow(self.screen, _("Missing User Name"),
                                   _("You must provide a user name"),
                                   buttons = [ TEXT_OK_BUTTON ], width = 50)
		continue
	    if len (pass1.value ()) < 6:
		ButtonChoiceWindow(self.screen, _("Password Length"),
		       _("The password must be at least 6 characters "
			 "long."),
		       buttons = [ TEXT_OK_BUTTON ], width = 50)
		pass1.set ("")
		pass2.set ("")
		continue
	    elif pass1.value () != pass2.value ():
		ButtonChoiceWindow(self.screen, _("Password Mismatch"),
		   _("The passwords you entered were different. Please "
		     "try again."),
		   buttons = [ TEXT_OK_BUTTON ], width = 50)
		pass1.set ("")
		pass2.set ("")
		continue

	    if username.value() == "root":
                ButtonChoiceWindow(self.screen, _("User Exists"),
		       _("The root user is already configured. You don't "
		         "need to add this user here."),
			 buttons = [ TEXT_OK_BUTTON ], width = 50)
                continue

	    if username.value() in systemUsers :
                ButtonChoiceWindow(self.screen, _("User Exists"),
		       _("This system user is already configured. You don't "
		         "need to add this user here."),
			 buttons = [ TEXT_OK_BUTTON ], width = 50)
                continue

            if self.users.has_key (username.value ()) and  \
				   username.value () != currentid:
                ButtonChoiceWindow(self.screen, _("User Exists"),
		       _("This user id already exists.  Choose another."),
			 buttons = [ TEXT_OK_BUTTON], width = 50)
                continue

            # XXX FIXME - more data validity checks
            
            user["id"] = username.value ()
            user["name"] = fullname.value ()
            user["password"] = pass1.value ()
            break

	return INSTALL_OK

    def __call__ (self, screen, rootPw, accounts):
        self.users = {}
        self.screen = screen
	user = { "id" : "", "name" : "", "password" : "" }

	for (account, name, password) in accounts.getUserList():
	    user['id'] = account
	    user['name'] = name
	    user['password'] = password
	    self.users[account] = user
	    del user
	    user = { "id" : "", "name" : "", "password" : "" }

	if not self.users.keys():
	    rc = self.editWindow(user, _("You should use a normal user "
		"account for most activities on your system. By not using the "
		"root account casually, you'll reduce the chance of "
		"disrupting your system's configuration."), 
		cancelText = _("Back"))
	    if (rc == INSTALL_BACK):
		return INSTALL_BACK
	    if (not user['id']):
		return INSTALL_OK
	    self.users[user["id"]] = user
        
        g = GridFormHelp (screen, _("User Account Setup"), "newusers", 1, 4)

	t = TextboxReflowed(60, _("What other user accounts would you like "
                                  "to have on the system? You should have at "
                                  "least one non-root account for normal "
                                  "work, but multi-user systems can have "
                                  "any number of accounts set up."))
	g.add(t, 0, 0, anchorLeft = 1, padding = (0, 0, 0, 1))

        listformat = "%-15s  %-40s"
        userformat = "%(id)-15s  %(name)-40s"

	subgrid = Grid(1, 2)
        header = listformat % (_("User name"), _("Full Name"))
        label = Label (header)
        subgrid.setField (label, 0, 0, anchorLeft = 1)
        listbox = Listbox (5, scroll = 1, returnExit = 1, width = 54)
        subgrid.setField (listbox, 0, 1, (0, 0, 0, 1), anchorLeft = 1)

	g.add(subgrid, 0, 1)

        self.numusers = 0

        for user in self.users.values ():
            self.numusers = self.numusers + 1
            listbox.append (userformat % user, user["id"])

        bb = ButtonBar (screen, ((_("Add"), "add"), (_("Delete"), "delete"),
                                 (_("Edit"), "edit"), TEXT_OK_BUTTON, TEXT_BACK_BUTTON))
        
        g.add (bb, 0, 3, growx = 1)

        while 1:
            result = g.run ()
            
            rc = bb.buttonPressed (result)

            if rc == "add":
                user = { "id" : "", "name" : "", "password" : "" }
                if self.editWindow (user, 
                    _("Enter the information for the user."), 0) != INSTALL_BACK:
                    listbox.append (userformat % user, user["id"])
                    listbox.setCurrent (user["id"])
                    self.users[user["id"]] = user
                    self.numusers = self.numusers + 1
            elif rc == "delete":
                # if there are no users in the list, don't try to delete one
                if self.numusers > 0:
                    current = listbox.current ()
                    listbox.delete (current)
                    del self.users [current]
                    self.numusers = self.numusers - 1
            elif rc == "edit" or result == listbox:
                # if there are no users in the list, don't try to edit one
                if self.numusers > 0:                    
                    current = listbox.current()
                    user = self.users[current]
                    if self.editWindow (user,
                                        _("Change the information for this user."), 1) != INSTALL_BACK:
                         # if the user id changed, we need to delete the old key
                         # and insert this new one.
                         if user["id"] != current:
                             del self.users [current]
                             listbox.insert (userformat % user, user["id"], current)
                             listbox.delete (current)
                             # and if the user id didn't change, just replace the old
                             # listbox entry.
                         else:
                             listbox.replace (userformat % user, user["id"])
                         self.users [user["id"]] = user
                         listbox.setCurrent(user["id"])
            elif rc == TEXT_OK_CHECK or result == TEXT_F12_CHECK:
                dir = INSTALL_OK
                break
            elif rc == TEXT_BACK_CHECK:
                dir = INSTALL_BACK
                break
            else:
                raise RuntimeError, "I shouldn't be here w/ rc %s..." % rc
                
        screen.popWindow ()

        list = []
        for n in self.users.values():
	    info = ( n['id'], n['name'], n['password'] )
	    list.append(info)

	accounts.setUserList(list)

        return dir

class AuthConfigWindow:
    def nissetsensitive (self):
        server = FLAGS_RESET
        flag = FLAGS_RESET
        if self.broadcast.selected ():
            server = FLAGS_SET
        if not self.nis.selected ():
            flag = FLAGS_SET
            server = FLAGS_SET

        self.nisDomain.setFlags (FLAG_DISABLED, flag)
        self.broadcast.setFlags (FLAG_DISABLED, flag)
        self.nisServer.setFlags (FLAG_DISABLED, server)

    def ldapsetsensitive (self):
        # handle other forms here...
        server = FLAGS_RESET
        if not self.ldap.selected():
            server = FLAGS_SET

        self.ldapServer.setFlags (FLAG_DISABLED, server)
        self.ldapBasedn.setFlags (FLAG_DISABLED, server)
        self.ldapTLS.setFlags (FLAG_DISABLED, server)

    def krb5setsensitive (self):
        # handle other forms here...
        server = FLAGS_RESET
        if not self.krb5.selected():
            server = FLAGS_SET

        self.krb5Realm.setFlags (FLAG_DISABLED, server)
        self.krb5Kdc.setFlags (FLAG_DISABLED, server)
        self.krb5Admin.setFlags (FLAG_DISABLED, server)

    def __call__(self, screen, auth):
        bb = ButtonBar (screen, (TEXT_OK_BUTTON, TEXT_BACK_BUTTON))

        toplevel = GridFormHelp (screen, _("Authentication Configuration"), 
				 "authconfig", 1, 10)
        self.shadow = Checkbox (_("Use Shadow Passwords"), auth.useShadow)
        toplevel.add (self.shadow, 0, 0, (0, 0, 0, 0), anchorLeft = 1)
        self.md5 = Checkbox (_("Enable MD5 Passwords"), auth.salt == 'md5')
        toplevel.add (self.md5, 0, 1, (0, 0, 0, 1), anchorLeft = 1)

        # nis support
        subgrid = Grid (3, 3)
        self.nis = Checkbox (_("Enable NIS"), auth.useNIS)
        subgrid.setField (self.nis, 0, 0)

        subgrid.setField (Label (""), 0, 1)
        subgrid.setField (Label (""), 0, 2)
        
        subgrid.setField (Label (_("NIS Domain:")),
                          1, 0, (2, 0, 1, 0), anchorRight = 1)
        subgrid.setField (Label (_("NIS Server:")),
                          1, 1, (2, 0, 1, 0), anchorRight = 1)
        subgrid.setField (Label (_("or use:")),
                          1, 2, (2, 0, 1, 0), anchorRight = 1)

        text = _("Request server via broadcast")
        entrywid = len(text) + 4
        
        self.nisDomain = Entry (entrywid)
        self.nisDomain.set (auth.nisDomain)
        self.broadcast = Checkbox (text, auth.nisuseBroadcast)
        self.nisServer = Entry (entrywid)
        self.nisServer.set (auth.nisServer)
        subgrid.setField (self.nisDomain, 2, 0, anchorLeft = 1)
        subgrid.setField (self.broadcast, 2, 1, anchorLeft = 1)
        subgrid.setField (self.nisServer, 2, 2, anchorLeft = 1)

        toplevel.add (subgrid, 0, 2, (0, 0, 0, 0), anchorLeft=1)

        # set up callbacks
        self.nis.setCallback (self.nissetsensitive)
        self.broadcast.setCallback (self.nissetsensitive)
        
        # ldap support next
        subgrid2 = Grid (3, 3)

        self.ldap = Checkbox (_("Enable LDAP"), auth.useLdap)
        subgrid2.setField(self.ldap, 0, 0)

        subgrid2.setField (Label (""), 0, 1)
        subgrid2.setField (Label (""), 0, 2)
        
        subgrid2.setField (Label (_("LDAP Server:")),
                           1, 0, (2, 0, 1, 0), anchorRight = 1)
        subgrid2.setField (Label (_("LDAP Base DN:")),
                           1, 1, (2, 0, 1, 0), anchorRight = 1)

        self.ldapServer = Entry (entrywid)
        self.ldapServer.set (auth.ldapServer)
        self.ldapBasedn = Entry (entrywid)
        self.ldapBasedn.set (auth.ldapBasedn)
        subgrid2.setField (self.ldapServer, 2, 0, anchorLeft = 1)
        subgrid2.setField (self.ldapBasedn, 2, 1, anchorLeft = 1)

        self.ldapTLS = Checkbox (_("Use TLS connections"), 0)
        subgrid2.setField (self.ldapTLS, 2, 2, anchorLeft = 1)

        toplevel.add (subgrid2, 0, 3, (0, 0, 0, 0))

        # set up callbacks
        self.ldap.setCallback (self.ldapsetsensitive)
        
        # kerberos last support next
        subgrid3 = Grid (3, 4)

        self.krb5 = Checkbox (_("Enable Kerberos"), auth.useKrb5)
        subgrid3.setField(self.krb5, 0, 0)

        subgrid3.setField (Label (""), 0, 1)
        subgrid3.setField (Label (""), 0, 2)
        subgrid3.setField (Label (""), 0, 3)
        
        subgrid3.setField (Label (_("Realm:")),
                           1, 0, (-2, 0, 1, 0), anchorRight = 1)
        subgrid3.setField (Label (_("KDC:")),
                           1, 1, (-2, 0, 1, 0), anchorRight = 1)
        subgrid3.setField (Label (_("Admin Server:")),
                           1, 2, (-2, 0, 1, 0), anchorRight = 1)
        self.krb5Realm = Entry (entrywid)
        self.krb5Realm.set (auth.krb5Realm)
        self.krb5Kdc = Entry (entrywid)
        self.krb5Kdc.set (auth.krb5Kdc)
        self.krb5Admin = Entry (entrywid)
        self.krb5Admin.set (auth.krb5Admin)
        subgrid3.setField (self.krb5Realm, 2, 0, anchorLeft = 1)
        subgrid3.setField (self.krb5Kdc, 2, 1, anchorLeft = 1)
        subgrid3.setField (self.krb5Admin, 2, 2, anchorLeft = 1)

        self.krb5.setCallback (self.krb5setsensitive)
        
        toplevel.add (subgrid3, 0, 4, (0, 0, 0, 0))

        # put button box at bottom
        toplevel.add (bb, 0, 5, growx = 1)

        # enable entire form now
        self.nissetsensitive ()
        self.ldapsetsensitive ()
        self.krb5setsensitive ()

        result = toplevel.runOnce ()
        
        if self.md5.value ():
            self.auth.salt = 'md5'
        else:
            self.auth.salt = None
        auth.useShadow = self.shadow.value ()
        auth.useNIS = self.nis.selected ()
        auth.nisDomain = self.nisDomain.value ()
        auth.nisuseBroadcast = self.broadcast.selected ()
        auth.nisServer = self.nisServer.value ()
        auth.useLdap = self.ldap.selected ()
        auth.useLdapauth = self.ldap.selected ()
        auth.ldapServer = self.ldapServer.value()
        auth.ldapBasedn = self.ldapBasedn.value()
        auth.ldapTLS = self.ldapTLS.selected ()
        auth.useKrb5 = self.krb5.selected()
        auth.krb5Realm = self.krb5Realm.value()
        auth.krb5Kdc = self.krb5Kdc.value()
        auth.krb5Admin = self.krb5Admin.value()

        rc = bb.buttonPressed (result)

        if rc == TEXT_BACK_CHECK:
            return INSTALL_BACK
        return INSTALL_OK

