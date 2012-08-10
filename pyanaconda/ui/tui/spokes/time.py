from pyanaconda.ui.tui.spokes import NormalTUISpoke
from pyanaconda.ui.tui.simpleline import TextWidget, ColumnWidget
from pyanaconda import localization

class TimeZoneSpoke(NormalTUISpoke):
    title = "Timezone settings"
    category = "localization"

    def __init__(self, app, data, storage, payload, instclass):
        NormalTUISpoke.__init__(self, app, data, storage, payload, instclass)

    def initialize(self):
        self._timezones = dict([(k, sorted(v)) for k,v in localization.get_all_regions_and_timezones().iteritems()])
        self._regions = [r for r in self._timezones]
        self._lower_regions = [r.lower() for r in self._timezones]

        self._zones = ["%s/%s" % (region, z) for region in self._timezones for z in self._timezones[region]]
        self._lower_zones = [z.lower() for region in self._timezones for z in self._timezones[region]] # for lowercase lookup

        self._selection = ""

    @property
    def completed(self):
        return self.data.timezone.timezone or self._selection

    @property
    def status(self):
        if self.data.timezone.timezone:
            return _("%s timezone") % self.data.timezone.timezone
        elif self._selection:
            return _("%s timezone") % self._selection
        else:
            return _("Timezone is not set.")


    def refresh(self, args = None):
        """args is None if we want a list of zones or "zone" to show all timezones in that zone."""
        NormalTUISpoke.refresh(self, args)

        if args and args in self._timezones:
            self._window += [TextWidget(_("Available timezones in region %s") % args)]
            displayed = [TextWidget(z) for z in self._timezones[args]]
        else:
            self._window += [TextWidget(_("Available regions"))]
            displayed = [TextWidget(z) for z in self._regions]

        def _prep(i, w):
            number = TextWidget("%2d)" % i)
            return ColumnWidget([(4, [number]), (None, [w])], 1)

        # split zones to three columns
        middle = len(displayed) / 3
        left = [_prep(i, w) for i,w in enumerate(displayed) if i <= middle]
        center = [_prep(i, w) for i,w in enumerate(displayed) if i > middle and i <= 2*middle]
        right = [_prep(i, w) for i,w in enumerate(displayed) if i > 2*middle]

        c = ColumnWidget([(24, left), (24, center), (24, right)], 3)
        self._window.append(c)

        return True

    def input(self, args, key):
        try:
            keyid = int(key)
            if args:
                self._selection = "%s/%s" % (args, self._timezones[args][keyid])
                self.apply()
                self.close()
            else:
                if len(self._timezones[self._regions[keyid]]) == 1:
                    self._selection = "%s/%s" % (self._regions[keyid],
                                                 self._timezones[self._regions[keyid]][0])
                    self.apply()
                    self.close()
                else:
                    self.app.switch_screen(self, self._regions[keyid])
            return True
        except ValueError:
            pass

        if key.lower() in self._lower_zones:
            id = self._lower_zones.index(key.lower())
            self._selection = self._zones[id]
            self.apply()
            self.close()
            return True

        elif key.lower() in self._lower_regions:
            id = self._lower_regions.index(key.lower())
            if len(self._timezones[self._regions[id]]) == 1:
                self._selection = "%s/%s" % (self._regions[id],
                                             self._timezones[self._regions[id]][0])
                self.apply()
                self.close()
            else:
                self.app.switch_screen(self, self._regions[id])
            return True

        elif key.lower() == "b":
            self.app.switch_screen(self, None)
            return True

        else:
            return key

    def prompt(self, args):
        return _("Please select the timezone.\nUse numbers or type names directly [b to region list, q to quit]: ")

    def apply(self):
        self.data.timezone.timezone = self._selection
