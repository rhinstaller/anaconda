#import gettext_rh
from snack import *
from textw.constants import *
from translate import _
import iutil

class RootPasswordWindow:
    def __call__ (self, screen, todo):
        toplevel = GridForm (screen, _("Root Password"), 1, 3)

        toplevel.add (TextboxReflowed(37, _("Pick a root password. You must "
				"type it twice to ensure you know "
				"what it is and didn't make a mistake "
				"in typing. Remember that the "
				"root password is a critical part "
				"of system security!")), 0, 0, (0, 0, 0, 1))

	pw = todo.rootpassword.getPure()
	if not pw: pw = ""

        entry1 = Entry (24, hidden = 1, text = pw)
        entry2 = Entry (24, hidden = 1, text = pw)
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
        fullname = Entry (20, user["name"], scroll = 1)
        pass1 = Entry (10, user["password"], hidden = 1)
        pass2 = Entry (10, user["password"], hidden = 1)

	if edit:
	    title = _("Edit User")
	else:
	    title = _("Add User")

        while 1:
            (rc, ent) = EntryWindow (self.screen, title, text,
			 [ (_("User ID"), userid),
			   (_("Full Name"), fullname),
			   (_("Password"), pass1),
			   (_("Password (confirm)"), pass2) ],
			 buttons = [ (_("OK"), "ok"), (cancelText, "cancel") ])
            
            if rc == "cancel":
                return INSTALL_BACK
	    if not len(pass1.value()) and not len(pass2.value()) and \
	       not len(userid.value()) and not len(fullname.value()):
                return INSTALL_OK

            if (not iutil.validUser(userid.value())):
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
        
        g = GridForm (screen, _("User Account Setup"), 1, 4)

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

        for user in self.users.values ():
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
            elif rc == "delete":
                current = listbox.current ()
                listbox.delete (current)
                del self.users [current]
            elif rc == "edit" or result == listbox:
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
    def setsensitive (self):
        server = FLAGS_RESET
        flag = FLAGS_RESET
        if self.broadcast.selected ():
            server = FLAGS_SET
        if not self.nis.selected ():
            flag = FLAGS_SET
            server = FLAGS_SET

        self.domain.setFlags (FLAG_DISABLED, flag)
        self.broadcast.setFlags (FLAG_DISABLED, flag)
        self.server.setFlags (FLAG_DISABLED, server)

    def __call__(self, screen, todo):
        bb = ButtonBar (screen, ((_("OK"), "ok"), (_("Back"), "back")))

        toplevel = GridForm (screen, _("Authentication Configuration"), 1, 5)
        self.shadow = Checkbox (_("Use Shadow Passwords"), todo.auth.useShadow)
        toplevel.add (self.shadow, 0, 0, (0, 0, 0, 1), anchorLeft = 1)
        self.md5 = Checkbox (_("Enable MD5 Passwords"), todo.auth.useMD5)
        toplevel.add (self.md5, 0, 1, (0, 0, 0, 1), anchorLeft = 1)
        self.nis = Checkbox (_("Enable NIS"), todo.auth.useNIS)
        toplevel.add (self.nis, 0, 2, anchorLeft = 1)

        subgrid = Grid (2, 3)

        subgrid.setField (Label (_("NIS Domain:")),
                          0, 0, (0, 0, 1, 0), anchorRight = 1)
        subgrid.setField (Label (_("NIS Server:")),
                          0, 1, (0, 0, 1, 0), anchorRight = 1)
        subgrid.setField (Label (_("or use:")),
                          0, 2, (0, 0, 1, 0), anchorRight = 1)

        text = _("Request server via broadcast")
        self.domain = Entry (len (text) + 4)
        self.domain.set (todo.auth.domain)
        self.broadcast = Checkbox (text, todo.auth.useBroadcast)
        self.server = Entry (len (text) + 4)
        self.server.set (todo.auth.server)
        subgrid.setField (self.domain, 1, 0, anchorLeft = 1)
        subgrid.setField (self.broadcast, 1, 1, anchorLeft = 1)
        subgrid.setField (self.server, 1, 2, anchorLeft = 1)
        toplevel.add (subgrid, 0, 3, (2, 0, 0, 1))
        toplevel.add (bb, 0, 4, growx = 1)

        self.nis.setCallback (self.setsensitive)
        self.broadcast.setCallback (self.setsensitive)

        self.setsensitive ()

        result = toplevel.runOnce ()

        todo.auth.useMD5 = self.md5.value ()
        todo.auth.useShadow = self.shadow.value ()
        todo.auth.useNIS = self.nis.selected ()
        todo.auth.domain = self.domain.value ()
        todo.auth.useBroadcast = self.broadcast.selected ()
        todo.auth.server = self.server.value ()
                
        rc = bb.buttonPressed (result)

        if rc == "back":
            return INSTALL_BACK
        return INSTALL_OK

