#import gettext_rh
from snack import *
from constants_text import *
from translate import _
import iutil

class RootPasswordWindow:
    def __call__ (self, screen, todo):
        toplevel = GridFormHelp (screen, _("Root Password"), "rootpw", 1, 3)

        toplevel.add (TextboxReflowed(37, _("Pick a root password. You must "
				"type it twice to ensure you know "
				"what it is and didn't make a mistake "
				"in typing. Remember that the "
				"root password is a critical part "
				"of system security!")), 0, 0, (0, 0, 0, 1))

	pw = todo.rootpassword.getPure()
	if not pw: pw = ""

        entry1 = Entry (24, password = 1, text = pw)
        entry2 = Entry (24, password = 1, text = pw)
        passgrid = Grid (2, 2)
        passgrid.setField (Label (_("Password:")), 0, 0, (0, 0, 1, 0), anchorLeft = 1)
        passgrid.setField (Label (_("Password (again):")), 0, 1, (0, 0, 1, 0), anchorLeft = 1)
        passgrid.setField (entry1, 1, 0)
        passgrid.setField (entry2, 1, 1)
        toplevel.add (passgrid, 0, 1, (0, 0, 0, 1))
        
        bb = ButtonBar (screen, ((_("OK"), "ok"), (_("Back"), "back")))
        toplevel.add (bb, 0, 2, growx = 1)

        while 1:
            toplevel.setCurrent (entry1)
            result = toplevel.run ()
            rc = bb.buttonPressed (result)
            if rc == "back":
                screen.popWindow()
                return INSTALL_BACK
            if len (entry1.value ()) < 6:
                ButtonChoiceWindow(screen, _("Password Length"),
		       _("The root password must be at least 6 characters "
			 "long."),
		       buttons = [ _("OK") ], width = 50)
            elif entry1.value () != entry2.value ():
                ButtonChoiceWindow(screen, _("Password Mismatch"),
		       _("The passwords you entered were different. Please "
			 "try again."),
		       buttons = [ _("OK") ], width = 50)
            else:
                break

            entry1.set ("")
            entry2.set ("")

        screen.popWindow()
        todo.rootpassword.set (entry1.value ())
        return INSTALL_OK

class UsersWindow:
    def editWindow (self, user, text, edit = 0, cancelText = None):
	if (not cancelText):
	    cancelText = _("Cancel")

        userid = Entry (9, user["id"])
        currentid = user["id"]
        pass1 = Entry (10, user["password"], password = 1)
        pass2 = Entry (10, user["password"], password = 1)
        fullname = Entry (20, user["name"], scroll = 1)

	if edit:
	    title = _("Edit User")
	    helptag = "edituser"
	else:
	    title = _("Add User")
	    helptag = "newuser"

        while 1:
            (rc, ent) = EntryWindow (self.screen, title, text,
			 [ (_("User ID"), userid),
			   (_("Password"), pass1),
			   (_("Password (confirm)"), pass2),
			   (_("Full Name"), fullname) ],
			 buttons = [ (_("OK"), "ok"), (cancelText, "cancel") ],
			 help = helptag)
            
            if rc == "cancel":
                return INSTALL_BACK
            
	    if not len(pass1.value()) and not len(pass2.value()) and \
	       not len(userid.value()) and not len(fullname.value()):
                return INSTALL_OK

            if (not len(userid.value()) or not iutil.validUser(userid.value())):
		ButtonChoiceWindow(self.screen, _("Bad User ID"),
                                   _("User IDs must be less than 8 "
                                     "characters and contain only characters "
                                     "A-Z, a-z, and 0-9."),
                                   buttons = [ _("OK") ], width = 50)
		continue
                
	    if not userid.value ():
		ButtonChoiceWindow(self.screen, _("Missing User ID"),
                                   _("You must provide a user ID"),
                                   buttons = [ _("OK") ], width = 50)
		continue
	    if len (pass1.value ()) < 6:
		ButtonChoiceWindow(self.screen, _("Password Length"),
		       _("The password must be at least 6 characters "
			 "long."),
		       buttons = [ _("OK") ], width = 50)
		pass1.set ("")
		pass2.set ("")
		continue
	    elif pass1.value () != pass2.value ():
		ButtonChoiceWindow(self.screen, _("Password Mismatch"),
		   _("The passwords you entered were different. Please "
		     "try again."),
		   buttons = [ _("OK") ], width = 50)
		pass1.set ("")
		pass2.set ("")
		continue

	    if userid.value() == "root":
                ButtonChoiceWindow(self.screen, _("User Exists"),
		       _("The root user is already configured. You don't "
		         "need to add this user here."),
			 buttons = [ _("OK") ], width = 50)
                continue

            if self.users.has_key (userid.value ()) and  \
				   userid.value () != currentid:
                ButtonChoiceWindow(self.screen, _("User Exists"),
		       _("This user id already exists.  Choose another."),
			 buttons = [ _("OK") ], width = 50)
                continue

            # XXX FIXME - more data validity checks
            
            user["id"] = userid.value ()
            user["name"] = fullname.value ()
            user["password"] = pass1.value ()
            break

	return INSTALL_OK

    def __call__ (self, screen, todo):
        self.users = {}
        self.screen = screen
	user = { "id" : "", "name" : "", "password" : "" }

	for (account, name, password) in todo.getUserList():
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
        
        g = GridFormHelp (screen, _("User Account Setup"), "addusers", 1, 4)

	t = TextboxReflowed(60, _("What user account would you like to have "
	    "on the system? You should have at least one non-root account "
	    "for normal work, but multi-user systems can have any number "
	    "of accounts set up."))
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
                                 (_("Edit"), "edit"), (_("OK"), "ok"), (_("Back"), "back")))
        
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
            elif rc == "ok" or result == "F12":
                dir = INSTALL_OK
                break
            elif rc == "back":
                dir = INSTALL_BACK
                break
            else:
                raise NeverGetHereError, "I shouldn't be here w/ rc %s..." % rc
                
        screen.popWindow ()

        list = []
        for n in self.users.values():
	    info = ( n['id'], n['name'], n['password'] )
	    list.append(info)

	todo.setUserList(list)

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

    def __call__(self, screen, todo):
        bb = ButtonBar (screen, ((_("OK"), "ok"), (_("Back"), "back")))

        toplevel = GridFormHelp (screen, _("Authentication Configuration"), 
				 "authconfig", 1, 10)
        self.shadow = Checkbox (_("Use Shadow Passwords"), todo.auth.useShadow)
        toplevel.add (self.shadow, 0, 0, (0, 0, 0, 0), anchorLeft = 1)
        self.md5 = Checkbox (_("Enable MD5 Passwords"), todo.auth.useMD5)
        toplevel.add (self.md5, 0, 1, (0, 0, 0, 1), anchorLeft = 1)

        # nis support
        subgrid = Grid (3, 3)
        self.nis = Checkbox (_("Enable NIS"), todo.auth.useNIS)
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
        self.nisDomain.set (todo.auth.nisDomain)
        self.broadcast = Checkbox (text, todo.auth.nisuseBroadcast)
        self.nisServer = Entry (entrywid)
        self.nisServer.set (todo.auth.nisServer)
        subgrid.setField (self.nisDomain, 2, 0, anchorLeft = 1)
        subgrid.setField (self.broadcast, 2, 1, anchorLeft = 1)
        subgrid.setField (self.nisServer, 2, 2, anchorLeft = 1)

        toplevel.add (subgrid, 0, 2, (0, 0, 0, 0), anchorLeft=1)

        # set up callbacks
        self.nis.setCallback (self.nissetsensitive)
        self.broadcast.setCallback (self.nissetsensitive)
        
        # ldap support next
        subgrid2 = Grid (3, 3)

        self.ldap = Checkbox (_("Enable LDAP"), todo.auth.useLdap)
        subgrid2.setField(self.ldap, 0, 0)

        subgrid2.setField (Label (""), 0, 1)
        subgrid2.setField (Label (""), 0, 2)
        
        subgrid2.setField (Label (_("LDAP Server:")),
                           1, 0, (2, 0, 1, 0), anchorRight = 1)
        subgrid2.setField (Label (_("LDAP Base DN:")),
                           1, 1, (2, 0, 1, 0), anchorRight = 1)

        self.ldapServer = Entry (entrywid)
        self.ldapServer.set (todo.auth.ldapServer)
        self.ldapBasedn = Entry (entrywid)
        self.ldapBasedn.set (todo.auth.ldapBasedn)
        subgrid2.setField (self.ldapServer, 2, 0, anchorLeft = 1)
        subgrid2.setField (self.ldapBasedn, 2, 1, anchorLeft = 1)

        self.ldapTLS = Checkbox (_("Use TLS connections"), 0)
        subgrid2.setField (self.ldapTLS, 2, 2, anchorLeft = 1)

        toplevel.add (subgrid2, 0, 3, (0, 0, 0, 0))

        # set up callbacks
        self.ldap.setCallback (self.ldapsetsensitive)
        
        # kerberos last support next
        subgrid3 = Grid (3, 4)

        self.krb5 = Checkbox (_("Enable Kerberos"), todo.auth.useKrb5)
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
        self.krb5Realm.set (todo.auth.krb5Realm)
        self.krb5Kdc = Entry (entrywid)
        self.krb5Kdc.set (todo.auth.krb5Kdc)
        self.krb5Admin = Entry (entrywid)
        self.krb5Admin.set (todo.auth.krb5Admin)
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
        
        todo.auth.useMD5 = self.md5.value ()
        todo.auth.useShadow = self.shadow.value ()
        todo.auth.useNIS = self.nis.selected ()
        todo.auth.nisDomain = self.nisDomain.value ()
        todo.auth.nisuseBroadcast = self.broadcast.selected ()
        todo.auth.nisServer = self.nisServer.value ()
        todo.auth.useLdap = self.ldap.selected ()
        todo.auth.useLdapauth = self.ldap.selected ()
        todo.auth.ldapServer = self.ldapServer.value()
        todo.auth.ldapBasedn = self.ldapBasedn.value()
        todo.auth.ldapTLS = self.ldapTLS.selected ()
        todo.auth.useKrb5 = self.krb5.selected()
        todo.auth.krb5Realm = self.krb5Realm.value()
        todo.auth.krb5Kdc = self.krb5Kdc.value()
        todo.auth.krb5Admin = self.krb5Admin.value()

        rc = bb.buttonPressed (result)

        if rc == "back":
            return INSTALL_BACK
        return INSTALL_OK

