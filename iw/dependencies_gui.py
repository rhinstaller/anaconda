from iw_gui import *
from gtk import *
from translate import _

class UnresolvedDependenciesWindow (InstallWindow):
    moredeps = None
    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)
        ics.setTitle (_("Unresolved Dependencies"))
        ics.setNextEnabled (1)
        ics.readHTML ("depend")
        self.dependRB = None
        self.causeRB = None

    def getNext (self):
        if (self.dependRB and self.dependRB.get_active ()
            or self.causeRB and self.causeRB.get_active ()):
            threads_leave ()
            moredeps = self.todo.verifyDeps ()
            threads_enter ()
            if moredeps and self.todo.canResolveDeps (moredeps):
                UnresolvedDependenciesWindow.moredeps = moredeps
                return UnresolvedDependenciesWindow

        return None

    def getPrev (self):
	self.todo.comps.setSelectionState(self.origSelection)
    
    def updateSize (self, *args):
        self.sizelabel.set_text (_("Total install size: %s") % self.todo.comps.sizeStr())

    def installToggled (self, widget, *args):
        self.todo.selectDepCause (self.deps)
        if widget.get_active ():
            self.todo.selectDeps (self.deps)
        else:
            self.todo.unselectDeps (self.deps)
        self.updateSize ()

    def causeToggled (self, widget, *args):
        if widget.get_active ():
            self.todo.unselectDepCause (self.deps)
        else:
            self.todo.selectDepCause (self.deps)            
        self.updateSize ()

    def ignoreToggled (self, widget, *args):
        if widget.get_active ():
            self.todo.selectDepCause (self.deps)
            self.todo.unselectDeps (self.deps)            
        self.updateSize ()

    #UnresolvedDependenciesWindow tag="depend"
    def getScreen (self):
        if not UnresolvedDependenciesWindow.moredeps:
            threads_leave ()
            self.deps = self.todo.verifyDeps ()
            threads_enter ()
            if not self.deps:
                return None
        else:
            self.deps = UnresolvedDependenciesWindow.moredeps

        sw = GtkScrolledWindow ()
        sw.set_border_width (5)
        sw.set_policy (POLICY_AUTOMATIC, POLICY_AUTOMATIC)

        list = GtkCList (2, (_("Package"), _("Requirement")))
        list.freeze ()
        for (name, suggest) in self.deps:
            list.append ((name, suggest))
	list.columns_autosize ()
        list.thaw ()
        sw.add (list)

        # save the way things were when we came in, then turn on
        # the packages so we get the right size.
	self.origSelection = self.todo.comps.getSelectionState()
        self.todo.selectDeps (self.deps)

        self.sizelabel = GtkLabel()
        self.sizelabel.set_alignment (1, .5)
        self.updateSize()

        rb = GtkVBox (FALSE)
        self.dependRB = GtkRadioButton (None, _("Install packages to "
                                                "satisfy dependencies"))
        
        self.causeRB  = GtkRadioButton (self.dependRB, _("Do not install "
                                                         "packages that "
                                                         "have dependencies"))
        
        self.ignoreRB = GtkRadioButton (self.dependRB, _("Ignore package "
                                                         "dependencies"))

        rb.pack_start (self.dependRB)
        rb.pack_start (self.causeRB)
        rb.pack_start (self.ignoreRB)
        rb.pack_start (self.sizelabel)

        self.dependRB.set_active (1)
        self.dependRB.connect('toggled', self.installToggled)
        self.causeRB.connect('toggled', self.causeToggled)
        self.ignoreRB.connect('toggled', self.ignoreToggled)

        box = GtkVBox (FALSE, 5)
        box.pack_start (sw, TRUE)
        box.pack_start (rb, FALSE)

        return box
