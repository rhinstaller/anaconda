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

import gettext
import iconvcodec

class i18n:
    def __init__(self):
        try:
            self.cat = gettext.translation("anaconda")
        except IOError:
            self.cat = None

    def getlangs(self):
	return self.langs
        
    def setlangs(self, langs):
        self.__init__()
	self.langs = langs

    def gettext(self, string):
        if not self.cat:
            return string
        try:
            return self.cat.ugettext(string)
        except TypeError:
            return string

def N_(str):
    return str

cat = i18n()
_ = cat.gettext
