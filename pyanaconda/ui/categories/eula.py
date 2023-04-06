from pyanaconda.ui.categories import SpokeCategory
from pyanaconda.core.i18n import _

__all__ = ["LicensingCategory"]

class LicensingCategory(SpokeCategory):

    @staticmethod
    def get_title():
        return _("LICENSING")

    @staticmethod
    def get_sort_order():
        return 900
