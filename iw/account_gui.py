from gtk import *
from iw_gui import *
from translate import _
import re
import string

class AccountWindow (InstallWindow):

    userAccountMatch = re.compile("([A-Za-z])([A-Za-z0-9])*")

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        self.todo = ics.getToDo ()
        ics.setTitle (_("Account Configuration"))
        ics.readHTML ("accts")

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
            self.rootStatus.set_text (_("Root password accepted."))
        else:
	    if not pw and not confirm:
                self.rootStatus.set_text (_("Please enter root password."))
            elif len (pw) < 6:
                self.rootStatus.set_text (_("Root password is too short."))
            else:
                self.rootStatus.set_text (_("Root passwords do not match."))
                
            self.ics.setNextEnabled (FALSE)

    def userOkay(self, *args):
	accountName = self.accountName.get_text()
	password1 = self.userPass1.get_text()
	password2 = self.userPass2.get_text()

	if (password1 and password1 == password2 and
	    self.userAccountMatch.search(accountName) and
	    len(accountName) <= 8 and len(password1) > 5) and accountName != "root":
	    valid = 1
	    self.userPwLabel.set_text(_("User password accepted."))
	else:
	    if not accountName:
		self.userPwLabel.set_text("")
	    elif accountName == "root":
		self.userPwLabel.set_text (_("Root account can not be added here."))
	    elif not password1 and not password2:
		self.userPwLabel.set_text (_("Please enter user password."))
	    elif len (password1) < 6:
		self.userPwLabel.set_text (_("User password is too short."))
	    else:
		self.userPwLabel.set_text (_("User passwords do not match."))

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
	password1 = self.userPass1.get_text()
        password2 = self.userPass2.get_text()
	fullName = self.fullName.get_text()

        if not (accountName and password1 and (password1 == password2)):
            return
	if accountName == "root":
	    return

        if self.passwords.has_key (accountName):
            return

        if (self.editingUser != None):
	    index = self.editingUser
	    self.userList.set_text(index, 0, accountName)
	    self.userList.set_text(index, 1, fullName)
	else:
	    index = self.userList.append((accountName, fullName))
        self.accountName.grab_focus ()
	self.passwords[accountName] = password1
	self.newUser()

    def editUser(self, widget, *args):
	index = self.userList.selection
	if (not index): return
	index = index[0]
	accountName = self.userList.get_text(index, 0)

        self.editingUser = None
	del self.passwords[accountName]
	self.userList.remove(index)
        self.addUser (None)

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
	self.userPwLabel.set_text("")

    def filter(self, widget, text, len, pos):
        # XXX this doesn't check copy/pase
        if len != 1:
            return
        
        # first character case:
        if not widget.get_text ():
            if (text[0] not in string.uppercase and
                text[0] not in string.lowercase):
                widget.emit_stop_by_name ("insert-text")

        # everything else:
        if (text[0] not in string.uppercase and
            text[0] not in string.lowercase and
            text[0] not in string.digits and
            text[0] not in [ '.', '-', '_' ]):
            widget.emit_stop_by_name ("insert-text")

    def setFocus (self, area, data):
        self.pw.grab_focus ()

    def getScreen (self):
	self.passwords = {}
	self.editingUser = None

        box = GtkVBox ()
        im = self.ics.readPixmap ("root-password.png")
        if im:
            im.render ()
            pix = im.make_pixmap ()
            a = GtkAlignment ()
            a.add (pix)
            a.set (0.0, 0.0, 0.0, 0.0)
            box.pack_start (a, FALSE)
        
        forward = lambda widget, box=box: box.focus (DIR_TAB_FORWARD)

        table = GtkTable (2, 2)
        table.set_row_spacings (5)
	table.set_col_spacings (5)

        pass1 = GtkLabel (_("Root Password: "))
        pass1.set_alignment (0.0, 0.5)
        table.attach (pass1, 0, 1, 0, 1, FILL, 0, 10)
        pass2 = GtkLabel (_("Confirm: "))
        pass2.set_alignment (0.0, 0.5)
        table.attach (pass2, 0, 1, 1, 2, FILL, 0, 10)
        self.pw = GtkEntry (128)
        self.pw.connect ("activate", forward)
        self.pw.connect ("changed", self.rootPasswordsMatch)
        self.pw.connect ("draw", self.setFocus)
        self.pw.set_visibility (FALSE)
        self.confirm = GtkEntry (128)
        self.confirm.connect ("activate", forward)
        self.confirm.set_visibility (FALSE)
        self.confirm.connect ("changed", self.rootPasswordsMatch)
        table.attach (self.pw,      1, 2, 0, 1, FILL|EXPAND, 5)
        table.attach (self.confirm, 1, 2, 1, 2, FILL|EXPAND, 5)

	pw = self.todo.rootpassword.getPure()
	if pw:
	    self.pw.set_text(pw)
	    self.confirm.set_text(pw)
        

        box.pack_start (table, FALSE)

        # root password statusbar
        self.rootStatus = GtkLabel ("")
        self.rootPasswordsMatch ()
        wrapper = GtkHBox(0, FALSE)
        wrapper.pack_start (self.rootStatus)
        box.pack_start (wrapper, FALSE)

        box.pack_start (GtkHSeparator (), FALSE, padding=3)

        table = GtkTable (2, 3)
        table.set_row_spacings(5)
        table.set_col_spacings(5)

        entrytable = GtkTable (5, 4)
        entrytable.set_row_spacings(5)
        entrytable.set_col_spacings(5)
        self.entrytable = entrytable

        self.accountName = GtkEntry (8)
        self.accountName.connect ("activate", forward)
        self.accountName.connect ("changed", self.userOkay)
        self.accountName.connect ("insert-text", self.filter)
        
        self.accountName.set_usize (50, -1)

        self.fullName = GtkEntry ()
        self.fullName.connect ("activate", self.addUser)
        self.userPass1 = GtkEntry (128)
        self.userPass1.connect ("activate", forward)
        self.userPass1.connect ("changed", self.userOkay)
        self.userPass2 = GtkEntry (128)
        self.userPass2.connect ("activate", forward)
        self.userPass2.connect ("changed", self.userOkay)
        self.userPass1.set_visibility (FALSE)
        self.userPass2.set_visibility (FALSE)
        self.userPass1.set_usize (50, -1)
        self.userPass2.set_usize (50, -1)

        label = GtkLabel (_("Account Name") + ": ")
        label.set_alignment (0.0, 0.5)
        entrytable.attach (label,            0, 1, 0, 1, FILL, 0, 10)
        entrytable.attach (self.accountName, 1, 2, 0, 1, FILL|EXPAND)
        label = GtkLabel (_("Password") + ": ")
        label.set_alignment (0.0, 0.5)
        entrytable.attach (label,            0, 1, 1, 2, FILL, 0, 10)               
        entrytable.attach (self.userPass1,   1, 2, 1, 2, FILL|EXPAND)
        label = GtkLabel (_("Password (confirm)") + ": ")
        label.set_alignment (0.0, 0.5)
        entrytable.attach (label,            2, 3, 1, 2, FILL, 0, 10)
        entrytable.attach (self.userPass2,   3, 4, 1, 2, FILL|EXPAND)

	self.userPwLabel = GtkLabel()
        self.userPwLabel.set_alignment (0.5, 0.5)
        wrapper = GtkHBox(0, FALSE)
        wrapper.pack_start (self.userPwLabel)
        entrytable.attach (wrapper, 0, 4, 2, 3, FILL, 0, 10)

        label = GtkLabel (_("Full Name") + ": ")
        label.set_alignment (0.0, 0.5)
        entrytable.attach (label,            0, 1, 3, 4, FILL, 0, 10)
        entrytable.attach (self.fullName,    1, 4, 3, 4, FILL|EXPAND)

        table.attach (entrytable, 0, 4, 0, 1,
                      xoptions = EXPAND | FILL,
                      yoptions = EXPAND | FILL)
        
        self.add = GtkButton (_("Add"))
	self.add.connect("clicked", self.addUser)
        self.edit = GtkButton (_("Edit"))
	self.edit.connect("clicked", self.editUser)
        delete = GtkButton (_("Delete"))
	delete.connect("clicked", self.deleteUser)
        new = GtkButton (_("New"))
	new.connect("clicked", self.newUser)

        bb = GtkHButtonBox ()
        bb.set_border_width (5)
        bb.pack_start (self.add)
        bb.pack_start (self.edit)
        bb.pack_start (delete)
        bb.pack_start (new)
        
        box.pack_start (table, FALSE)
        box.pack_start (bb, FALSE)
        sw = GtkScrolledWindow ()
        sw.set_policy (POLICY_AUTOMATIC, POLICY_AUTOMATIC)

        self.userList = GtkCList (2, (_("Account Name"), _("Full Name")))
        for x in range (2):
            self.userList.set_selectable (x, FALSE)

	self.userList.connect("select_row", self.userSelected)
        sw.add (self.userList)
        box.pack_start (sw, TRUE)

        index = 0
	for (user, name, password) in self.todo.getUserList():
	    self.userList.append((user, name))
	    self.passwords[user] = password
	    index = index + 1

	self.userOkay()
	box.set_border_width (5)


        return box
