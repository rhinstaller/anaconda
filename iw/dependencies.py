from iw import *
from gtk import *
from gui import _

class UnresolvedDependenciesWindow (InstallWindow):

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)
        ics.setTitle (_("Unresolved Dependencies"))
        ics.setNextEnabled (1)
        self.dependCB = None

    def getNext (self):
        if self.dependCB and self.dependCB.get_active ():
            self.todo.selectDeps (self.deps)
        return None
    
    def getScreen (self):
	threads_leave ()
        self.deps = self.todo.verifyDeps ()
	threads_enter ()
        if not self.deps:
            return None

        sw = GtkScrolledWindow ()
        sw.set_border_width (5)
        sw.set_policy (POLICY_AUTOMATIC, POLICY_AUTOMATIC)

        list = GtkCList (2, (_("Package"), _("Requirement")))
        list.freeze ()
        for (name, suggest) in self.deps:
            list.append ((name, suggest))
        list.thaw ()
        sw.add (list)

        self.dependCB = GtkCheckButton (_("Install packages to satisfy dependencies"))
        self.dependCB.set_active (TRUE)
        align = GtkAlignment (0.5, 0.5)
        align.add (self.dependCB)

        box = GtkVBox (FALSE, 5)
        box.pack_start (sw, TRUE)
        box.pack_start (align, FALSE)

        return box


