from .. import simpleline as tui
from .. import common

class TUISpoke(common.UIObject, tui.Widget):
    title = u"Default spoke title"

    def __init__(self, app, data):
        common.UIObject.__init__(self, app, data)
        tui.Widget.__init__(self)

    @property
    def status(self):
        return "testing status..."

    @property
    def completed(self):
        return True

    def refresh(self, args = None):
        common.UIObject.refresh(self, args)

        return True

    def input(self, key):
        return key

    def render(self, width):
        tui.Widget.render(self, width)
        c = tui.CheckboxWidget(completed = self.completed, title = self.title, text = self.status)
        c.render(width)
        self.draw(c)

class StandaloneTUISpoke(TUISpoke):
    preForHub = False
    postForHub = False
    title = "Standalone spoke title"
