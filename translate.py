import gettext_rh

class i18n:
    def __init__(self):
	self.langs = []
        self.cat = gettext_rh.Catalog ("anaconda", "/usr/share/locale")

    def getlangs(self):
	return self.langs
        
    def setlangs(self, langs):
	self.langs = langs
        gettext_rh.setlangs (langs)
        self.cat = gettext_rh.Catalog ("anaconda", "/usr/share/locale")

    def gettext(self, string):
        return self.cat.gettext(string)

def N_(str):
    return str

cat = i18n()
_ = cat.gettext
