from iw import *
from gtk import *

class LiloWindow (InstallWindow):

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setTitle ("Lilo Configuration")
        ics.setNextEnabled (1)
        self.type = None

    def getNext (self):
        self.type = self.list.selection[0]
        if self.list.selection[0] == 0:
            self.todo.setLiloLocation (self.boothd)
        else:
            self.todo.setLiloLocation (self.bootpart)

    def getScreen (self):
        if '/' not in self.todo.mounts.keys (): return None

        if self.todo.mounts.has_key ('/boot'):
            self.bootpart = self.todo.mounts['/boot'][0]
        else:
            self.bootpart = self.todo.mounts['/'][0]
        i = len (self.bootpart) - 1
        while i < 0 and self.bootpart[i] in digits:
            i = i - 1
        self.boothd = self.bootpart[0:i]
            
        format = "/dev/%s"
        sw = GtkScrolledWindow ()
        sw.set_border_width (5)
        sw.set_policy (POLICY_AUTOMATIC, POLICY_AUTOMATIC)

        self.list = GtkCList (2, ("Device", "Location"))
        self.list.freeze ()
        self.list.append ((format % (self.boothd,), "Master Boot Record (MBR)"))
        self.list.append ((format % (self.bootpart,), "First sector of boot partition"))
        self.list.columns_autosize ()
        self.list.set_selection_mode (SELECTION_BROWSE)
        self.list.set_column_resizeable (0, FALSE)
        self.list.set_column_resizeable (1, FALSE)
        self.list.column_titles_passive ()
        if self.type:
            self.list.select_row (self.type, 0)
        self.list.thaw ()
        sw.add (self.list)

        return sw
