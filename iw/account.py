from gtk import *
from iw import *
from gui import _

class AccountWindow (InstallWindow):

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        self.todo = ics.getToDo ()
        ics.setTitle (_("Account Configuration"))
        ics.setHTML ("<HTML><BODY>Enter a root password.  The password "
                     "must be at least six characters in length."
                     "<p>The \"Next\" button will become enabled when both entry fields match."
                     "</BODY></HTML>")

    def getNext (self):
        self.todo.rootpassword.set (self.pw.get_text ())
        return None

    def passwordsMatch (self, *args):
        pw = self.pw.get_text ()
        confirm = self.confirm.get_text ()

        if pw == confirm and len (pw) >= 6:
            self.ics.setNextEnabled (TRUE)
        else:
            self.ics.setNextEnabled (FALSE)

    def getScreen (self):
        box = GtkVBox ()
        forward = lambda widget, box=box: box.focus (DIR_TAB_FORWARD)

        table = GtkTable (2, 2)
        table.attach (GtkLabel (_("Root Password: ")), 0, 1, 0, 1)
        table.attach (GtkLabel (_("Confirm: ")), 0, 1, 1, 2)
        self.pw = GtkEntry (8)
        self.pw.connect ("activate", forward)
        self.pw.connect ("changed", self.passwordsMatch)
        self.pw.set_visibility (FALSE)
        self.confirm = GtkEntry (8)
        self.confirm.connect ("activate", forward)
        self.confirm.set_visibility (FALSE)
        self.confirm.connect ("changed", self.passwordsMatch)
        table.attach (self.pw, 1, 2, 0, 1)
        table.attach (self.confirm, 1, 2, 1, 2)

        box.pack_start (table, FALSE)

        box.pack_start (GtkHSeparator (), FALSE, padding=3)

        table = GtkTable (2, 3)
        table.set_row_spacings(5)
        table.set_col_spacings(5)

        entrytable = GtkTable (3, 4)
        entrytable.set_row_spacings(10)
        entrytable.set_col_spacings(10)

        username = GtkEntry (8)
        username.connect ("activate", forward)

        username.set_usize (50, -1)
        fullname = GtkEntry ()
        fullname.connect ("activate", forward)
        pass1 = GtkEntry (10)
        pass1.connect ("activate", forward)
        pass2 = GtkEntry (10)
        pass2.connect ("activate", forward)
        pass1.set_visibility (FALSE)
        pass2.set_visibility (FALSE)
        pass1.set_usize (50, -1)
        pass2.set_usize (50, -1)
        
        entrytable.attach (GtkLabel (_("User Name")), 0, 1, 0, 1)        
        entrytable.attach (username,                  1, 2, 0, 1)
        entrytable.attach (GtkLabel (_("Password")),  0, 1, 1, 2)                
        entrytable.attach (pass1,                     1, 2, 1, 2)
        entrytable.attach (GtkLabel (_("Password (confirm)")),   2, 3, 1, 2)                
        entrytable.attach (pass2,                     3, 4, 1, 2)
        
        entrytable.attach (GtkLabel (_("Full Name")), 0, 1, 2, 3)        
        entrytable.attach (fullname,                  1, 4, 2, 3)

        table.attach (entrytable, 0, 3, 0, 1,
                      xoptions = EXPAND | FILL,
                      yoptions = EXPAND | FILL)
        
        add = GtkButton (_("Add"))
        edit = GtkButton (_("Edit"))
        delete = GtkButton (_("Delete"))

        table.attach (add,    0, 1, 1, 2, xoptions = FILL)
        table.attach (edit,   1, 2, 1, 2, xoptions = FILL)
        table.attach (delete, 2, 3, 1, 2, xoptions = FILL)
        box.pack_start (table, FALSE)
        userlist = GtkCList (2, (_("User ID"), _("Full Name")))
        box.pack_start (userlist, TRUE)
        
        return box
