from .. import simpleline as tui
from pyanaconda.ui.tui import TUIObject
from pyanaconda.ui.common import Spoke, StandaloneSpoke, NormalSpoke, PersonalizationSpoke, collect
import os

__all__ = ["TUISpoke", "StandaloneSpoke", "NormalSpoke", "PersonalizationSpoke",
           "collect_spokes", "collect_categories"]

class TUISpoke(TUIObject, tui.Widget, Spoke):
    title = u"Default spoke title"
    category = u""

    def __init__(self, app, ksdata, storage, payload, instclass):
        TUIObject.__init__(self, app, ksdata)
        tui.Widget.__init__(self)
        Spoke.__init__(self, ksdata, storage, payload, instclass)

    @property
    def status(self):
        return "testing status..."

    @property
    def completed(self):
        return True

    def refresh(self, args = None):
        TUIObject.refresh(self, args)
        return True

    def input(self, key):
        return key

    def render(self, width):
        tui.Widget.render(self, width)
        c = tui.CheckboxWidget(completed = self.completed, title = self.title, text = self.status)
        c.render(width)
        self.draw(c)

class StandaloneTUISpoke(TUISpoke, StandaloneSpoke):
    pass

class NormalTUISpoke(TUISpoke, NormalSpoke):
    pass

class PersonalizationTUISpoke(TUISpoke, PersonalizationSpoke):
    pass

def collect_spokes(category):
    """Return a list of all spoke subclasses that should appear for a given
       category.
    """
    return collect("pyanaconda.ui.tui.spokes.%s", os.path.dirname(__file__), lambda obj: hasattr(obj, "category") and obj.category != None and obj.category == category)

def collect_categories():
    classes = collect("pyanaconda.ui.tui.spokes.%s", os.path.dirname(__file__), lambda obj: hasattr(obj, "category") and obj.category != None and obj.category != "")
    categories = set([c.category for c in classes])
    return categories
