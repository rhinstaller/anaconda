#
# account_gui.py: gui root password and user creation dialog
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
import gobject
import re
import string
import gui
from iw_gui import *
from rhpl.translate import _, N_
from flags import flags

class AccountWindow (InstallWindow):

    userAccountMatch = re.compile("([A-Za-z])([A-Za-z0-9])*")

    windowTitle = N_("Account Configuration")
    htmlTag = ("accts")

    def getNext (self):
	if not self.__dict__.has_key("pw"): return None

        self.rootPw.set (self.pw.get_text ())
	accounts = []

        # XXX hack
        if self.users == 0:
            self.accounts.setUserList(accounts)
            return None

	iter = self.userstore.get_iter_first()
	while iter:
	    accounts.append((self.userstore.get_value(iter, 0),
                             self.userstore.get_value(iter, 1),
                             self.passwords[self.userstore.get_value(iter, 0)]))

	    iter = self.userstore.iter_next(iter)
            
	self.accounts.setUserList(accounts)
        return None

    def rootPasswordsMatch (self, *args):
        pw = self.pw.get_text ()
        confirm = self.confirm.get_text ()

        if pw == confirm and len (pw) >= 6:
            self.ics.setNextEnabled (gtk.TRUE)
            self.rootStatus.set_text (_("Root password accepted."))
        else:
	    if not pw and not confirm:
                self.rootStatus.set_text ("")
            elif len (pw) < 6:
                self.rootStatus.set_text (_("Root password is too short."))
            else:
                self.rootStatus.set_text (_("Root passwords do not match."))
                
            self.ics.setNextEnabled (gtk.FALSE)

    def userOkay(self, *args):
	accountName = self.accountName.get_text()
	password1 = self.userPass1.get_text()
	password2 = self.userPass2.get_text()

        systemUsers = ('root', 'bin', 'daemon', 'adm', 'lp', 'sync',
                       'shutdown', 'halt', 'mail', 'news', 'uucp',
                       'operator', 'games', 'gopher', 'ftp', 'nobody',
                       'nscd', 'mailnull', 'rpm', 'ident', 'rpc',
                       'rpcuser', 'radvd', 'xfs', 'gdm', 'apache',
                       'squid')

	if ((password1 and password1 == password2 and
             self.userAccountMatch.search(accountName) and
             len(accountName) <= 8 and len(password1) > 5) and
            accountName != "root" and accountName not in systemUsers):
	    self.userPwLabel.set_text(_("User password accepted."))
	else:
	    if not accountName:
		self.userPwLabel.set_text("")
	    elif accountName == "root":
		self.userPwLabel.set_text (
                    _("Root account can not be added here."))
            elif accountName in systemUsers:
                self.userPwLabel.set_text (
                    _("System accounts can not be added here."))
	    elif not password1 and not password2:
		self.userPwLabel.set_text (_("Please enter user password."))
	    elif len (password1) < 6:
		self.userPwLabel.set_text (_("User password is too short."))
	    else:
		self.userPwLabel.set_text (_("User passwords do not match."))

    def getSelectedIter(self):
	selection = self.userlist.get_selection()
        (model, iter) = selection.get_selected()
        if iter is None:
            return None
	
	return iter

    def getSelectedData(self):
	iter = self.getSelectedIter()

	if iter is None:
	    return None
	
	accountName = self.userstore.get_value(iter, 0)
	fullName = self.userstore.get_value(iter, 1)
	password = self.passwords[accountName]
	return (accountName, fullName, password)

    def userSelected(self, selection, *args):
        self.edit.set_sensitive(gtk.TRUE)
        self.delete.set_sensitive(gtk.TRUE)


    def addUser_cb(self):
	accountName = self.accountName.get_text()
	password1 = self.userPass1.get_text()
        password2 = self.userPass2.get_text()
	fullName = self.fullName.get_text()

        if not (accountName and password1 and (password1 == password2)):
            return
	if accountName == "root":
	    return
        if len(password1) < 6:
            return

        if self.passwords.has_key (accountName):
            return

	iter = self.userstore.append()
	self.userstore.set_value(iter, 0, accountName)
	self.userstore.set_value(iter, 1, fullName)

	self.passwords[accountName] = password1

        # XXX hack
        self.users = self.users + 1        

	self.userlist.get_selection().select_iter(iter)
        self.win.destroy()
        
    def editUser_cb(self, *args):
	accountName = self.accountName.get_text()
	password1 = self.userPass1.get_text()
	fullName = self.fullName.get_text()

	iter = self.getSelectedIter()
	if iter is None:
	    print "bad no selection and we're in editUser_cb"
	    return None
	
        # if the username has not changed, reset the password
        if accountName in self.passwords.keys():
            self.passwords[accountName] = password1
        else:
            # the username has changed, we need to remove that
            # username from password dictionary
            currAccount = self.userstore.get_value(iter, 0)
            del self.passwords[currAccount]
            self.passwords[accountName] = password1

        self.userstore.set_value(iter, 0, accountName)
        self.userstore.set_value(iter, 1, fullName)

        self.win.destroy()
        
    def close (self, widget, button, flag):
        if button == 1:
            if flag == "addUser":
                self.addUser_cb()
            elif flag == "editUser":
                self.editUser_cb()
        else:
            pass
        self.win.destroy()

    def addUser (self, widget):
        title = _("Add a New User")
        self.win = self.userWindow(title, 0)
        self.win.add_button('gtk-cancel', 0)
        self.win.add_button('gtk-ok', 1)
        self.win.connect("response", self.close, "addUser")
        self.win.show_all()

    def editUser (self, widget):
        title = _("Edit User")

	iter = self.getSelectedIter()
	if iter is None:
	    return
	
        # if there is data there to edit
	self.win = self.userWindow(title, 1)
	self.win.add_button('gtk-cancel', 1)
	self.win.add_button('gtk-ok', 0)
	self.win.connect("response", self.close, "editUser")
	self.win.show_all()

    def userWindow (self, title, editting):
        userWin = gtk.Dialog(_("Add a User Account"), flags=gtk.DIALOG_MODAL)
        gui.addFrame(userWin)
        userWin.set_modal(gtk.TRUE)
        userWin.set_position (gtk.WIN_POS_CENTER)

        userTable = gtk.Table (5, 2)
        userTable.set_homogeneous(gtk.FALSE)
        userTable.set_border_width(5)
        userTable.set_row_spacings(5)
        userTable.set_col_spacings(5)

        vbox = gtk.VBox()
        vbox.pack_start(userTable)
        userAddFrame = gtk.Frame (title)
        userAddFrame.add(vbox)
        userWin.vbox.pack_start(userAddFrame)

        label = gui.MnemonicLabel (_("Enter a user _name:"))
        a = gtk.Alignment(0.0, 0.5, 0, 1)
        a.add(label)
        userTable.attach(a, 0, 1, 0, 1, gtk.FILL)
        self.accountName = gtk.Entry (8)
        label.set_mnemonic_widget(self.accountName)
        userTable.attach(self.accountName, 1, 2, 0, 1, gtk.EXPAND, gtk.EXPAND)

        label = gui.MnemonicLabel (_("Enter a user _password:"))
        a = gtk.Alignment(0.0, 0.5, 0, 1)
        a.add(label)
        userTable.attach(a, 0, 1, 1, 2, gtk.FILL)
        self.userPass1 = gtk.Entry ()
        self.userPass1.set_visibility(gtk.FALSE)
        label.set_mnemonic_widget(self.userPass1)        
        userTable.attach(self.userPass1, 1, 2, 1, 2, gtk.EXPAND, gtk.EXPAND)

        label = gui.MnemonicLabel (_("Pass_word (confirm):"))
        a = gtk.Alignment(0.0, 0.5, 0, 1)
        a.add(label)
        userTable.attach(a, 0, 1, 2, 3, gtk.FILL)
        self.userPass2 = gtk.Entry ()
        self.userPass2.set_visibility(gtk.FALSE)
        label.set_mnemonic_widget(self.userPass2)        
        userTable.attach(self.userPass2, 1, 2, 2, 3, gtk.EXPAND, gtk.EXPAND)
        
        label = gui.MnemonicLabel (_("_Full Name:"))
        a = gtk.Alignment(0.0, 0.5, 0, 1)
        a.add(label)
        userTable.attach(a, 0, 1, 3, 4, gtk.FILL)
        self.fullName = gtk.Entry ()
        label.set_mnemonic_widget(self.fullName)                
        userTable.attach(self.fullName, 1, 2, 3, 4, gtk.EXPAND, gtk.EXPAND)

        self.userPwLabel = gtk.Label(_("Please enter user name"))
        vbox.pack_start(self.userPwLabel)


	rc = self.getSelectedData()
	if rc and editting:
            (account, name, password) = rc
            self.accountName.set_text(account)
            self.fullName.set_text(name)
            self.userPass1.set_text(password)
            self.userPass2.set_text(password)
            
        self.accountName.grab_focus()
        self.accountName.connect("changed", self.userOkay)
        self.accountName.connect("insert-text", self.filter)
        self.accountName.connect("activate", self.forward)
        self.userPass1.connect("changed", self.userOkay)
        self.userPass2.connect("changed", self.userOkay)
       
        return userWin
        
    def deleteUser(self, *args):
	selection = self.userlist.get_selection()
        (model, iter) = selection.get_selected()
        if iter is None:
            return
	
	accountName = self.userstore.get_value(iter, 0)

	del self.passwords[accountName]

	self.userstore.remove(iter)
        self.edit.set_sensitive(gtk.FALSE)
        self.delete.set_sensitive(gtk.FALSE)

        # XXX hack
        self.users = self.users - 1

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

    def userlistActivateCb(self, view, path, col):
        self.editUser(view)

    # AccountWindow tag="accts"
    def getScreen (self, rootPw, accounts):
	self.accounts = accounts
	self.rootPw = rootPw

	self.passwords = {}

        # XXX hack because store.get_iter_first ALWAYS returns a
        # GtkTreeIter so we can't just iterate over them and find the empty one
        self.users = 0

        box = gtk.VBox ()

        hbox = gtk.HBox()
        pix = self.ics.readPixmap ("root-password.png")
        if pix:
            a = gtk.Alignment ()
            a.add (pix)
            a.set (0.0, 0.0, 0.0, 0.0)
            hbox.pack_start (a, gtk.FALSE)

        label = gtk.Label (_("Enter the root (administrator) password "
                             "for the system."))
        label.set_line_wrap(gtk.TRUE)
        label.set_size_request(350, -1)

        a = gtk.Alignment ()
        a.add (label)
        a.set (0.0, 0.5, 0.0, 0.0)
        hbox.pack_start(a, gtk.FALSE, 20)
        box.pack_start(hbox, gtk.FALSE)
       
        self.forward = lambda widget, box=box: box.emit('focus', gtk.DIR_TAB_FORWARD)
        
        table = gtk.Table (2, 2)
        table.set_row_spacings (5)
	table.set_col_spacings (5)

        pass1 = gui.MnemonicLabel (_("Root _Password: "))
        pass1.set_alignment (0.0, 0.5)
        table.attach (pass1, 0, 1, 0, 1, gtk.FILL, 0, 10)
        pass2 = gui.MnemonicLabel (_("_Confirm: "))
        pass2.set_alignment (0.0, 0.5)
        table.attach (pass2, 0, 1, 1, 2, gtk.FILL, 0, 10)
        self.pw = gtk.Entry (128)
        pass1.set_mnemonic_widget(self.pw)
        
        self.pw.connect ("activate", self.forward)
        self.pw.connect ("changed", self.rootPasswordsMatch)
        self.pw.connect ("map-event", self.setFocus)
        self.pw.set_visibility (gtk.FALSE)
        self.confirm = gtk.Entry (128)
        pass2.set_mnemonic_widget(self.confirm)
        self.confirm.connect ("activate", self.forward)
        self.confirm.set_visibility (gtk.FALSE)
        self.confirm.connect ("changed", self.rootPasswordsMatch)
        table.attach (self.pw,      1, 2, 0, 1, gtk.FILL|gtk.EXPAND, 5)
        table.attach (self.confirm, 1, 2, 1, 2, gtk.FILL|gtk.EXPAND, 5)

        box.pack_start (table, gtk.FALSE)

        # root password statusbar
        self.rootStatus = gtk.Label ("")
        self.rootPasswordsMatch ()
        wrapper = gtk.HBox(0, gtk.FALSE)
        wrapper.pack_start (self.rootStatus)
        box.pack_start (wrapper, gtk.FALSE)

        box.pack_start (gtk.HSeparator (), gtk.FALSE, padding=3)

 	pw = self.rootPw.getPure()
	if pw:
	    self.pw.set_text(pw)
	    self.confirm.set_text(pw)

        sw = gtk.ScrolledWindow ()
        sw.set_policy (gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.set_shadow_type(gtk.SHADOW_ETCHED_IN)

	self.userstore = gtk.ListStore(gobject.TYPE_STRING,
				       gobject.TYPE_STRING)
	self.userlist = gtk.TreeView(self.userstore)

	column = gtk.TreeViewColumn(_("Account Name"),
				    gtk.CellRendererText(), text = 0)
	self.userlist.append_column(column)
	column = gtk.TreeViewColumn(_("Full Name"),
				    gtk.CellRendererText(), text = 1)
	self.userlist.append_column(column)
        self.userlist.connect('row-activated', self.userlistActivateCb)

	selection = self.userlist.get_selection()
	selection.connect("changed", self.userSelected)

        sw.add (self.userlist)

        self.add = gtk.Button (_("_Add"))
	self.add.connect("clicked", self.addUser)
        self.edit = gtk.Button (_("_Edit"))
	self.edit.connect("clicked", self.editUser)
        self.edit.set_sensitive(gtk.FALSE)
        self.delete = gtk.Button (_("_Delete"))
	self.delete.connect("clicked", self.deleteUser)
        self.delete.set_sensitive(gtk.FALSE)

        bb = gtk.VButtonBox ()
        bb.set_border_width (5)
        bb.set_layout(gtk.BUTTONBOX_START)
        bb.pack_start (self.add)
        bb.pack_start (self.edit)
        bb.pack_start (self.delete)

        hbox = gtk.HBox()
        pix = self.ics.readPixmap ("users.png")
        if pix:
            a = gtk.Alignment ()
            a.add (pix)
            a.set (0.5, 0.5, 0, 0)
            hbox.pack_start (a, gtk.FALSE, padding=7)

        a = gtk.Alignment (0.0, 0.5)
        label = gui.WrappingLabel(
            _("It is recommended that you create a personal account "
	      "for normal (non-administrative) use. Accounts can also "
	      "be created for additional users."))
        label.set_line_wrap(gtk.TRUE)
        a.add(label)
        hbox.pack_start(a, gtk.FALSE)

        box.pack_start(hbox, gtk.FALSE)
        
        hbox = gtk.HBox(gtk.FALSE)
        hbox.pack_start(sw, gtk.TRUE)
        hbox.pack_start(bb, gtk.FALSE)
        box.pack_start(hbox)
        
	for (user, name, password) in self.accounts.getUserList():
	    iter = self.userstore.append()
	    self.userstore.set_value(iter, 0, user)
	    self.userstore.set_value(iter, 1, name)
	    self.passwords[user] = password

            # XXX hack
            self.users = self.users + 1

	box.set_border_width (5)

        return box
