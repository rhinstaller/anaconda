from .. import simpleline as tui
from pyanaconda.ui.tui import TUIObject
from pyanaconda.ui.tui.spokes import collect_spokes
from pyanaconda.ui import common

class TUIHub(TUIObject, common.Hub):
    categories = []
    title = "Default HUB title"

    def __init__(self, app, data, storage, payload, instclass):
        TUIObject.__init__(self, app, data)
        common.Hub.__init__(self, data, storage, payload, instclass)
        self._spokes = {}
        self._keys = {}
        self._spoke_count = 0

        for c in self.categories:
            spokes = collect_spokes(c)
            for s in sorted(spokes, key = lambda s: s.priority):
                spoke = s(app, data, storage, payload, instclass)
                spoke.initialize()

                if not spoke.showable:
                    spoke.teardown()
                    del spoke
                    continue

                self._spoke_count += 1
                self._keys[self._spoke_count] = spoke
                self._spokes[spoke.__class__.__name__] = spoke


    def refresh(self, args = None):
        TUIObject.refresh(self, args)

        def _prep(i, w):
            number = tui.TextWidget("%2d)" % i)
            return tui.ColumnWidget([(3, [number]), (None, [w])], 1)

        left = [_prep(i, w) for i,w in self._keys.iteritems() if i % 2 == 1]
        right = [_prep(i, w) for i,w in self._keys.iteritems() if i % 2 == 0]

        c = tui.ColumnWidget([(39, left), (39, right)], 2)
        self._window.append(c)

        return True

    def input(self, key):
        try:
            number = int(key)
            self.app.switch_screen_with_return(self._keys[number])
            return None

        except (ValueError, KeyError):
            return key
