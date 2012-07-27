from .. import simpleline as tui
from pyanaconda.ui.tui import TUIObject

class TUIHub(TUIObject):
    spokes = []
    title = "Default HUB title"

    def __init__(self, app, data):
        TUIObject.__init__(self, app)
        self._spokes = {}
        self._spoke_count = 0

        for s in self.spokes:
            spoke = s(app, data)
            spoke.initialize()

            if not spoke.showable:
                spoke.teardown()
                del spoke
                continue

            self._spoke_count += 1
            self._spokes[self._spoke_count] = spoke

    def refresh(self, args = None):
        common.UIObject.refresh(self, args)

        def _prep(i, w):
            number = tui.TextWidget("%2d)" % i)
            return tui.ColumnWidget([(3, [number]), (None, [w])], 1)

        left = [_prep(i, w) for i,w in self._spokes.iteritems() if i % 2 == 1]
        right = [_prep(i, w) for i,w in self._spokes.iteritems() if i % 2 == 0]

        c = tui.ColumnWidget([(39, left), (39, right)], 2)
        self._window.append(c)

        return True

    def input(self, key):
        try:
            number = int(key)
            self.app.switch_screen_with_return(self._spokes[number])
            return None

        except (ValueError, KeyError):
            return key
