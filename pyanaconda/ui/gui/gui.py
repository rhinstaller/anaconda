from gi.repository import Gtk
from pyanaconda.ui.gui import collect
from pyanaconda.ui.gui.hubs import Hub
from pyanaconda.ui.gui.spokes import StandaloneSpoke

class AnacondaGUI(object):
    def __init__(self, data, hubClasses):
        # First, grab a list of all the standalone spokes.
        standalones = collect("spokes", lambda obj: issubclass(obj, StandaloneSpoke) and \
                                                    getattr(obj, "preForHub", False) or getattr(obj, "postForHub", False))

        actionClasses = []
        for hub in hubClasses:
            actionClasses.extend(sorted(filter(lambda obj: getattr(obj, "preForHub", None) == hub, standalones),
                                        key=lambda obj: obj.priority))
            actionClasses.append(hub)
            actionClasses.extend(sorted(filter(lambda obj: getattr(obj, "postForHub", None) == hub, standalones),
                                        key=lambda obj: obj.priority))

        self._actions = []
        for klass in actionClasses:
            obj = klass(data)
            obj.populate()

            if not obj.showable:
                continue

            obj.register_event_cb("continue", self._on_continue_clicked)
            obj.register_event_cb("quit", self._on_quit_clicked)

            self._actions.append(obj)

    def _on_continue_clicked(self):
        # If we're on the last screen, clicking Continue is the same as clicking Quit.
        if len(self._actions) == 1:
            self._on_quit_clicked()
            return

        # If the current action wants us to jump to an arbitrary point ahead,
        # look for where that is now.
        if self._actions[0].skipTo:
            found = False
            for ndx in range(1, len(self._actions)):
                if self._actions[ndx].__class__.__name__ == self._actions[0].skipTo:
                    found = True
                    break

            # If we found the point in question, compose a new actions list
            # consisting of the current action, the one to jump to, and all
            # the ones after.  That means the rest of the code below doesn't
            # have to change.
            if found:
                self._actions = [self._actions[0]] + self._actions[ndx:]

        self._actions[1].setup()
        self._actions[1].window.set_beta(self._actions[0].window.get_beta())
        self._actions[1].window.set_property("distribution", self._actions[0].window.get_property("distribution"))

        # Do this last.  Setting up curAction could take a while, and we want
        # to leave something on the screen while we work.
        self._actions[1].window.show_all()
        self._actions[0].window.hide()
        self._actions.pop(0)

    def _on_quit_clicked(self):
        Gtk.main_quit()

    def run(self):
        self._actions[0].window.show_all()
        Gtk.main()

    def setup(self):
        self._actions[0].setup()

        # If we set these values on the very first window shown, they will get
        # propagated to later ones.
        self._actions[0].window.set_beta(True)
