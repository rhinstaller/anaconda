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
import gzread

class i18n:
    def __init__(self, langs=None, unicode=0):
        self.unicode = unicode
        if langs:
            self.langs = langs
        else:
            self.langs = ['C']
        mofile = None
        searchpath = ('po/%s.mo',
                      '/usr/share/locale/%s/LC_MESSAGES/anaconda.mo')
        for lang in self.langs:
            for path in searchpath:
                try:
                    mofile = gzread.open(path % (lang))
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
        except:
            print 'unable to translate from', self.cat.charset(), 'to utf-8'
            self.iconv = iconv.open('utf-8', 'iso-8859-1')

    def setunicode(self, value):
        self.unicode = value

    def getunicode(self):
        return self.unicode

    def getlangs(self):
	return self.langs
        
    def setlangs(self, langs):
        self.__init__(langs, self.unicode)

    def utf8(self, string):
        try:
            return self.iconv.iconv(string)
        except:
            return string

    def gettext(self, string):
        if self.unicode:
            if not self.cat:
                return self.utf8(string)
            return self.utf8(self.cat.gettext(string))
        else: 
            if not self.cat:
                return string
            return self.cat.gettext(string)

def N_(str):
    return str

cat = i18n()
_ = cat.gettext
utf8 = cat.utf8


