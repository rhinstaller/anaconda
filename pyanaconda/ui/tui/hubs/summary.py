from pyanaconda.ui.tui.hubs import TUIHub

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

class SummaryHub(TUIHub):
    title = _("Install hub")
    categories = ["source", "localization", "destination", "password"]
