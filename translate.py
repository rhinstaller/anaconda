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
import iconv
import os

class i18n:
    def __init__(self, langs=None):
        if langs:
            self.langs = langs
        else:
            self.langs = ['C']
        mofile = None
        for lang in self.langs:
            try:
                mofile = open('/usr/share/locale/%s/LC_MESSAGES/anaconda.mo'
                              % (lang), 'rb')
            except IOError:
                try:
                    mofile = open('po/%s.mo' % (lang,), 'rb')
                except IOError:
                    pass
            if mofile:
                break
        if not mofile:
            self.cat = None
            self.iconv = iconv.open('utf-8', 'iso-8859-1')
            return

        self.cat = gettext.GNUTranslations(mofile)
        try:
            self.iconv = iconv.open('utf-8', self.cat.charset())
            print 'unable to translate from', self.cat.charset(), 'to utf-8'
        except:
            self.iconv = iconv.open('utf-8', 'iso-8859-1')

    def getlangs(self):
	return self.langs
        
    def setlangs(self, langs):
        self.__init__(langs)

    def utf8(self, string):
        try:
            return self.iconv.iconv(string)
        except:
            return string

    def gettext(self, string):
        if not self.cat:
            return self.utf8(string)
        return self.utf8(self.cat.gettext(string))

def N_(str):
    return str

cat = i18n()
_ = cat.gettext
utf8 = cat.utf8


