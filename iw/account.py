from gtk import *
from iw import *
from gui import _
import re

class AccountWindow (InstallWindow):

    userAccountMatch = re.compile("([A-Za-z])([A-Za-z0-9])*")

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        self.todo = ics.getToDo ()
        ics.setTitle (_("Account Configuration"))
        ics.readHTML ("accts")
##         ics.setHTML ("<HTML><BODY>Enter a root password.  The password "
##                      "must be at least six characters in length."
##                      "<p>The \"Next\" button will become enabled when both entry fields match."
##                      "</BODY></HTML>")

    def getNext (self):
	if not self.__dict__.has_key("pw"): return None

        self.todo.rootpassword.set (self.pw.get_text ())
	accounts = []
	for n in range(len(self.passwords.keys())):
	    accounts.append((self.userList.get_text(n, 0),
			      self.userList.get_text(n, 1),
			      self.passwords[self.userList.get_text(n, 0)]))
	self.todo.setUserList(accounts)
        return None

    def rootPasswordsMatch (self, *args):
        pw = self.pw.get_text ()
        confirm = self.confirm.get_text ()

        if pw == confirm and len (pw) >= 6:
            self.ics.setNextEnabled (TRUE)
        else:
            self.ics.setNextEnabled (FALSE)

    def userOkay(self, *args):
	accountName = self.accountName.get_text()
	password1 = self.userPass1.get_text()
	password2 = self.userPass2.get_text()

	if (password1 and password1 == password2 and
	    self.userAccountMatch.search(accountName) and
	    len(accountName) <= 8):
	    valid = 1
	else:
	    valid = 0

	if (self.editingUser != None):
	    self.edit.set_sensitive(valid)
	    self.add.set_sensitive(0)
	else:
	    self.edit.set_sensitive(0)
	    self.add.set_sensitive(valid)

    def userSelected(self, *args):
	index = self.userList.selection
	if (not index): return
	index = index[0]
	accountName = self.userList.get_text(index, 0)
	fullName = self.userList.get_text(index, 1)
	password = self.passwords[accountName]

	self.editingUser = index
	self.accountName.set_text(accountName)
	self.userPass1.set_text(password)
	self.userPass2.set_text(password)
	self.fullName.set_text(fullName)

    def addUser(self, widget, *args):
	accountName = self.accountName.get_text()
	password = self.userPass1.get_text()
	fullName = self.fullName.get_text()

        if (self.editingUser != None):
	    index = self.editingUser
	    self.userList.set_text(index, 0, accountName)
	    self.userList.set_text(index, 1, fullName)
	else:
	    index = self.userList.append((accountName, fullName))
	    
	self.passwords[accountName] = password
	self.newUser()

    def deleteUser(self, *args):
	index = self.userList.selection
	if (not index): return
	index = index[0]
	accountName = self.userList.get_text(index, 0)

	del self.passwords[accountName]
	self.userList.remove(index)
	self.newUser()

    def newUser(self, *args):
	self.editingUser = None 
	self.accountName.set_text("")
	self.userPass1.set_text("")
	self.userPass2.set_text("")
	self.fullName.set_text("")

    def getScreen (self):
	self.passwords = {}
	self.editingUser = None

        box = GtkVBox ()
        forward = lambda widget, box=box: box.focus (DIR_TAB_FORWARD)

        table = GtkTable (2, 2)
        table.attach (GtkLabel (_("Root Password: ")), 0, 1, 0, 1)
        table.attach (GtkLabel (_("Confirm: ")), 0, 1, 1, 2)
        self.pw = GtkEntry (8)
        self.pw.connect ("activate", forward)
        self.pw.connect ("changed", self.rootPasswordsMatch)
        self.pw.set_visibility (FALSE)
        self.confirm = GtkEntry (8)
        self.confirm.connect ("activate", forward)
        self.confirm.set_visibility (FALSE)
        self.confirm.connect ("changed", self.rootPasswordsMatch)
        table.attach (self.pw, 1, 2, 0, 1)
        table.attach (self.confirm, 1, 2, 1, 2)

	pw = self.todo.rootpassword.getPure()
	if pw:
	    self.pw.set_text(pw)
	    self.confirm.set_text(pw)
        

        box.pack_start (table, FALSE)

        box.pack_start (GtkHSeparator (), FALSE, padding=3)

        table = GtkTable (2, 3)
        table.set_row_spacings(5)
        table.set_col_spacings(5)

        entrytable = GtkTable (4, 4)
        entrytable.set_row_spacings(10)
        entrytable.set_col_spacings(10)

        self.accountName = GtkEntry (8)
        self.accountName.connect ("activate", forward)
        self.accountName.connect ("changed", self.userOkay)
        self.accountName.set_usize (50, -1)

        self.fullName = GtkEntry ()
        self.fullName.connect ("activate", self.addUser)
        self.userPass1 = GtkEntry (10)
        self.userPass1.connect ("activate", forward)
        self.userPass1.connect ("changed", self.userOkay)
        self.userPass2 = GtkEntry (10)
        self.userPass2.connect ("activate", forward)
        self.userPass2.connect ("changed", self.userOkay)
        self.userPass1.set_visibility (FALSE)
        self.userPass2.set_visibility (FALSE)
        self.userPass1.set_usize (50, -1)
        self.userPass2.set_usize (50, -1)

        entrytable.attach (GtkLabel (_("Account Name")), 0, 1, 0, 1)        
        entrytable.attach (self.accountName,                  1, 2, 0, 1)
        entrytable.attach (GtkLabel (_("Password")),  0, 1, 1, 2)                
        entrytable.attach (self.userPass1,                     1, 2, 1, 2)
        entrytable.attach (GtkLabel (_("Password (confirm)")),   2, 3, 1, 2)                
        entrytable.attach (self.userPass2,                     3, 4, 1, 2)
        
        entrytable.attach (GtkLabel (_("Full Name")), 0, 1, 2, 3)        
        entrytable.attach (self.fullName,                  1, 4, 2, 3)

        table.attach (entrytable, 0, 4, 0, 1,
                      xoptions = EXPAND | FILL,
                      yoptions = EXPAND | FILL)
        
        self.add = GtkButton (_("Add"))
	self.add.connect("clicked", self.addUser)
        self.edit = GtkButton (_("Edit"))
	self.edit.connect("clicked", self.addUser)
        delete = GtkButton (_("Delete"))
	delete.connect("clicked", self.deleteUser)
        new = GtkButton (_("New"))
	new.connect("clicked", self.newUser)

        table.attach (self.add,    0, 1, 1, 2, xoptions = FILL)
        table.attach (self.edit,   1, 2, 1, 2, xoptions = FILL)
        table.attach (delete, 2, 3, 1, 2, xoptions = FILL)
        table.attach (new, 3, 4, 1, 2, xoptions = FILL)
        box.pack_start (table, FALSE)
        self.userList = GtkCList (2, (_("Account Name"), _("Full Name")))
	self.userList.connect("select_row", self.userSelected)
        box.pack_start (self.userList, TRUE)

        index = 0
	for (user, name, password) in self.todo.getUserList():
	    self.userList.append((user, name))
	    self.passwords[user] = password
	    index = index + 1

	self.userOkay()

        return box
