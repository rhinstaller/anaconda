import gettext_rh

class i18n:
    def __init__(self):
        self.cat = gettext_rh.Catalog ("anaconda", "/usr/share/locale")
        
    def setlangs(self, langs):
        gettext_rh.setlangs (langs)
        self.cat = gettext_rh.Catalog ("anaconda", "/usr/share/locale")

    def gettext(self, string):
        return self.cat.gettext(string)

cat = i18n()
_ = cat.gettext
