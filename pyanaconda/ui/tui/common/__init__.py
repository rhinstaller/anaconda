from .. import simpleline as tui

class UIObject(tui.UIScreen):
    title = u"Default title"

    def __init__(self, app, data):
        tui.UIScreen.__init__(self, app, data)

    @property
    def showable(self):
        return True

    def teardown(self):
        pass

    def initialize(self):
        pass

    def refresh(self):
        """Put everything to display into self.window list."""
        pass

    def retranslate(self):
        # do retranslation stuff
        # redraw
        self.app.switch_screen(self)
