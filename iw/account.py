from gtk import *
from iw import *
import gettext

cat = gettext.Catalog ("anaconda", "/usr/share/locale")
_ = cat.gettext

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
        table = GtkTable (2, 2)
        table.attach (GtkLabel (_("Root Password: ")), 0, 1, 0, 1)
        table.attach (GtkLabel (_("Confirm: ")), 0, 1, 1, 2)
        self.pw = GtkEntry (8)
        self.pw.connect ("changed", self.passwordsMatch)
        self.pw.set_visibility (FALSE)
        self.confirm = GtkEntry (8)
        self.confirm.set_visibility (FALSE)
        self.confirm.connect ("changed", self.passwordsMatch)
        table.attach (self.pw, 1, 2, 0, 1)
        table.attach (self.confirm, 1, 2, 1, 2)

        box.pack_start (table, FALSE)

        return box
