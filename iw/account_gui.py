#
# account_gui.py: gui root password and user creation dialog
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
import re
import string
from gnome.ui import *
from flags import flags

class AccountWindow (InstallWindow):

    userAccountMatch = re.compile("([A-Za-z])([A-Za-z0-9])*")

    windowTitle = N_("Account Configuration")
    htmlTag = ("accts")

    def getNext (self):
	if not self.__dict__.has_key("pw"): return None

        self.rootPw.set (self.pw.get_text ())
	accounts = []

	for n in range(len(self.passwords.keys())):
	    accounts.append((self.userList.get_text(n, 0),
                             self.userList.get_text(n, 1),
                             self.passwords[self.userList.get_text(n, 0)]))
            
	self.accounts.setUserList(accounts)
        return None

    def rootPasswordsMatch (self, *args):
        pw = self.pw.get_text ()
        confirm = self.confirm.get_text ()

        if pw == confirm and len (pw) >= 6:
            self.ics.setNextEnabled (TRUE)
            self.rootStatus.set_text (_("Root password accepted."))
        else:
	    if not pw and not confirm:
                self.rootStatus.set_text ("")
            elif len (pw) < 6:
                self.rootStatus.set_text (_("Root password is too short."))
            else:
                self.rootStatus.set_text (_("Root passwords do not match."))
                
            self.ics.setNextEnabled (FALSE)

    def userOkay(self, *args):
	accountName = self.accountName.get_text()
	password1 = self.userPass1.get_text()
	password2 = self.userPass2.get_text()

        systemUsers = ['root', 'bin', 'daemon', 'adm', 'lp', 'sync', 'shutdown', 'halt', 'mail',
                       'news', 'uucp', 'operator', 'games', 'gopher', 'ftp', 'nobody', 'nscd',
                       'mailnull', 'rpm', 'ident', 'rpc', 'rpcuser', 'radvd', 'xfs', 'gdm', 'apache',
                       'squid']

	if (password1 and password1 == password2 and
	    self.userAccountMatch.search(accountName) and
	    len(password1) > 5) and accountName not in systemUsers:
	    self.userPwLabel.set_text(_("User password accepted."))
            self.win.set_sensitive(0, TRUE)
	else:
            self.win.set_sensitive(0, FALSE)
	    if not accountName:
		self.userPwLabel.set_text("")
	    elif accountName == "root":
		self.userPwLabel.set_text (_("Root account can not be added here."))
            elif accountName in systemUsers:
                self.userPwLabel.set_text (_("System accounts can not be added here."))
	    elif not password1 and not password2:
		self.userPwLabel.set_text (_("Please enter user password."))
	    elif len (password1) < 6:
		self.userPwLabel.set_text (_("User password is too short."))
	    else:
		self.userPwLabel.set_text (_("User passwords do not match."))

    def userSelected(self, *args):
	index = self.userList.selection
	if (not index): return
	index = index[0]
	accountName = self.userList.get_text(index, 0)
	fullName = self.userList.get_text(index, 1)
	password = self.passwords[accountName]
        self.edit.set_sensitive(TRUE)
        self.delete.set_sensitive(TRUE)
        #Keep track of the data in the CList so we can edit the entry when Edit button is clicked
        self.data = [index, accountName, password, password, fullName]

    def addUser_cb(self, widget, *args):
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

        self.edit.set_sensitive(FALSE)
        self.delete.set_sensitive(FALSE)
        self.win.destroy()
        
    def editUser_cb(self, widget, *args):
	index = self.userList.selection
	if (not index): return

	accountName = self.accountName.get_text()
	password1 = self.userPass1.get_text()
	fullName = self.fullName.get_text()
        index = index[0]        #Get first item in the list

        #if the username has not changed, reset the password
        if accountName in self.passwords.keys():
            self.passwords[accountName] = password1
        else:  #the username has changed, we need to remove that username from password dictionary
            currAccount = self.userList.get_text(index, 0)
            del self.passwords[currAccount]
            self.passwords[accountName] = password1

        self.userList.set_text(index, 0, accountName)
        self.userList.set_text(index, 1, fullName)

        self.edit.set_sensitive(FALSE)
        self.delete.set_sensitive(FALSE)
        self.userList.unselect_all()
        self.win.destroy()

    def addUser (self, widget):
        title = _("Add a New User")
        self.win = self.userWindow(title, None)
        self.win.append_button_with_pixmap(_("OK"), STOCK_BUTTON_OK)
        self.win.append_button_with_pixmap(_("Cancel"), STOCK_BUTTON_CANCEL)
        self.win.button_connect(0, self.addUser_cb)
        self.win.button_connect(1, self.win.destroy)
        self.win.set_sensitive(0, FALSE)
        self.win.show_all()

    def editUser (self, widget):
        title = _("Edit User")
        if self.data:   #if there is data there to edit
            self.win = self.userWindow(title, self.data)
            self.win.append_button_with_pixmap(_("OK"), STOCK_BUTTON_OK)
            self.win.append_button_with_pixmap(_("Cancel"), STOCK_BUTTON_CANCEL)
            self.win.button_connect(0, self.editUser_cb)
            self.win.button_connect(1, self.win.destroy)
            self.win.show_all()

    def userWindow (self, title, data=None):
        userWin = GnomeDialog()
        userWin.set_modal(TRUE)
        userWin.set_usize(350, 200)		
        userWin.set_position (WIN_POS_CENTER)

        userTable = GtkTable (5,2)
        userTable.set_homogeneous(FALSE)

        vbox = GtkVBox()
        vbox.pack_start(userTable)
        userAddFrame = GtkFrame (title)
        userAddFrame.add(vbox)
        userWin.vbox.pack_start(userAddFrame)

        #Labels
        label = GtkLabel (_("User Name:"))
        userTable.attach(label, 0, 1, 0, 1)
        label = GtkLabel (_("Full Name:"))
        userTable.attach(label, 0, 1, 1, 2)
        label = GtkLabel (_("Password:"))
        userTable.attach(label, 0, 1, 2, 3)
        label = GtkLabel (_("Confirm:"))
        userTable.attach(label, 0, 1, 3, 4)
        #user password label
        self.userPwLabel = GtkLabel(_("Please enter user name"))
        vbox.pack_start(self.userPwLabel)

        self.forward = lambda widget, box=userWin: box.focus (DIR_TAB_FORWARD)

        #entry boxes
        self.accountName = GtkEntry ()
        userTable.attach(self.accountName, 1, 2, 0, 1, SHRINK, SHRINK)
        self.fullName = GtkEntry ()
        userTable.attach(self.fullName, 1, 2, 1, 2, SHRINK, SHRINK)
        self.userPass1 = GtkEntry ()
        self.userPass1.set_visibility(FALSE)
        userTable.attach(self.userPass1, 1, 2, 2, 3, SHRINK, SHRINK)
        self.userPass2 = GtkEntry ()
        self.userPass2.set_visibility(FALSE)
        userTable.attach (self.userPass2, 1, 2, 3, 4, SHRINK, SHRINK)

        if data:
            index, account, password, password, name = data
            self.accountName.set_text(account)
            self.fullName.set_text(name)
            self.userPass1.set_text(password)
            self.userPass2.set_text(password)
            
        self.accountName.grab_focus()
        self.accountName.connect("changed", self.userOkay)
        self.accountName.connect("insert-text", self.filter)
        self.accountName.connect("activate", self.forward)
        self.fullName.connect("activate", self.forward)
        self.userPass1.connect("changed", self.userOkay)
        self.userPass1.connect("activate", self.forward)
        self.userPass2.connect("changed", self.userOkay)
        self.userPass2.connect("activate", self.forward)

        return userWin
        
    def deleteUser(self, *args):
	index = self.userList.selection
	if (not index): return
	index = index[0]
	accountName = self.userList.get_text(index, 0)

	del self.passwords[accountName]
	self.userList.remove(index)
        self.edit.set_sensitive(FALSE)
        self.delete.set_sensitive(FALSE)

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

    # AccountWindow tag="accts"
    def getScreen (self, rootPw, accounts):
	self.accounts = accounts
	self.rootPw = rootPw

	self.passwords = {}
	self.editingUser = None

        box = GtkVBox ()

        hbox = GtkHBox()
        pix = self.ics.readPixmap ("root-password.png")
        if pix:
            a = GtkAlignment ()
            a.add (pix)
            a.set (0.0, 0.0, 0.0, 0.0)
            hbox.pack_start (a, FALSE)

        label = GtkLabel (_("Enter the password for the root user (administrator) of this system."))
        label.set_line_wrap(TRUE)
        label.set_usize(350, -1)

        a = GtkAlignment ()
        a.add (label)
        a.set (0.0, 0.5, 0.0, 0.0)
        hbox.pack_start(a, FALSE, 20)
        box.pack_start(hbox, FALSE)
       
        self.forward = lambda widget, box=box: box.focus (DIR_TAB_FORWARD)

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
        self.pw.connect ("activate", self.forward)
        self.pw.connect ("changed", self.rootPasswordsMatch)
        self.pw.connect ("draw", self.setFocus)
        self.pw.set_visibility (FALSE)
        self.confirm = GtkEntry (128)
        self.confirm.connect ("activate", self.forward)
        self.confirm.set_visibility (FALSE)
        self.confirm.connect ("changed", self.rootPasswordsMatch)
        table.attach (self.pw,      1, 2, 0, 1, FILL|EXPAND, 5)
        table.attach (self.confirm, 1, 2, 1, 2, FILL|EXPAND, 5)

        box.pack_start (table, FALSE)

        # root password statusbar
        self.rootStatus = GtkLabel ("")
        self.rootPasswordsMatch ()
        wrapper = GtkHBox(0, FALSE)
        wrapper.pack_start (self.rootStatus)
        box.pack_start (wrapper, FALSE)

        box.pack_start (GtkHSeparator (), FALSE, padding=3)

 	pw = self.rootPw.getPure()
	if pw:
	    self.pw.set_text(pw)
	    self.confirm.set_text(pw)

        sw = GtkScrolledWindow ()
        sw.set_policy (POLICY_AUTOMATIC, POLICY_AUTOMATIC)

        self.userList = GtkCList (2, (_("Account Name"), _("Full Name")))
        self.userList.set_column_auto_resize(0, TRUE)
        for x in range (2):
            self.userList.column_title_passive (x)

	self.userList.connect("select_row", self.userSelected)
        sw.add (self.userList)

        self.add = GtkButton (_("Add"))
	self.add.connect("clicked", self.addUser)
        self.edit = GtkButton (_("Edit"))
	self.edit.connect("clicked", self.editUser)
        self.edit.set_sensitive(FALSE)
        self.delete = GtkButton (_("Delete"))
	self.delete.connect("clicked", self.deleteUser)
        self.delete.set_sensitive(FALSE)

        bb = GtkVButtonBox ()
        bb.set_border_width (5)
        bb.set_layout_default(BUTTONBOX_START)
        bb.pack_start (self.add)
        bb.pack_start (self.edit)
        bb.pack_start (self.delete)

        hbox = GtkHBox()
        pix = self.ics.readPixmap ("users.png")
        if pix:
            a = GtkAlignment ()
            a.add (pix)
            a.set (0.5, 0.5, 0, 0)
            hbox.pack_start (a, FALSE, padding=7)

        a = GtkAlignment (0.0, 0.5)
        label = GtkLabel (_("Additional accounts can be created for other "
                            "users of this system. Such accounts could be for "
                            "a personal login account, or for other "
                            "non-administrative users who need to use this "
                            "system. Use the <Add> button to enter additional "
                            "user accounts."))
        label.set_line_wrap(TRUE)
        label.set_usize(350, -1)
        a.add(label)
        hbox.pack_start(a, FALSE)

        box.pack_start(hbox, FALSE)
        
        hbox = GtkHBox(FALSE)
        hbox.pack_start(sw, TRUE)
        hbox.pack_start(bb, FALSE)
        box.pack_start(hbox)
        
        index = 0
	for (user, name, password) in self.accounts.getUserList():
	    self.userList.append((user, name))
	    self.passwords[user] = password
	    index = index + 1

        if flags.reconfig:
            label.set_sensitive(FALSE)
            self.userList.set_sensitive(FALSE)
            self.add.set_sensitive(FALSE)
            self.edit.set_sensitive(FALSE)
            self.delete.set_sensitive(FALSE)

	box.set_border_width (5)

        return box
