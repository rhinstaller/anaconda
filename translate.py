#
# translate.py - persistent global gettext service for anaconda
#
# Matt Wilson <msw@redhat.com>
#
# Copyright 2001 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

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
