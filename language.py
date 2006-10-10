#
# language.py: install data component that stores information about both
#              installer runtime language choice and installed system
#              language support.
#
# Copyright 2001-2005 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import os
import string
import locale

from rhpl.translate import cat
from rhpl.simpleconfig import SimpleConfigFile

import logging
log = logging.getLogger("anaconda")

# Converts a single language into a "language search path". For example,
# fr_FR.utf8@euro would become "fr_FR.utf8@eueo fr_FR.utf8 fr_FR fr"
def expandLangs(astring):
    langs = [astring]
    charset = None
    # remove charset ...
    if '.' in astring:
	langs.append(string.split(astring, '.')[0])

    if '@' in astring:
        charset = string.split(astring, '@')[1]

    # also add 2 character language code ...
    if len(astring) > 2:
        if charset: langs.append("%s@%s" %(astring[:2], charset))
	langs.append(astring[:2])

    return langs

class Language:
    def __init__ (self, display_mode = "g"):
        self.info = {}
        self.default = None
        self.nativeLangNames = {}
        self.localeInfo = {}
        self.displayMode = display_mode
        self.targetLang = None

        if os.environ.has_key("LANG"):
            self.current = self.fixLang(os.environ["LANG"])
        else:
            self.current = "en_US.UTF-8"

        # English name -> native name mapping
        search = ('lang-names', '/usr/lib/anaconda/lang-names')
        for path in search:
            if os.access(path, os.R_OK):
                f = open(path, 'r')
                for line in f.readlines():
                    lang, native = string.split(line, '\t')
                    native = native.strip()
                    self.nativeLangNames[lang] = native

                f.close()
                break
        
        # nick -> (name, short name, font, keyboard, timezone) mapping
        search = ('lang-table', '/tmp/updates/lang-table',
                  '/mnt/source/RHupdates/lang-table', '/etc/lang-table',
                  '/usr/lib/anaconda/lang-table')
        for path in search:
            if os.access(path, os.R_OK):
                f = open(path, "r")
                break

        for line in f.readlines():
            string.strip(line)
            l = string.split(line, '\t')

            # throw out invalid lines
            if len(l) < 6:
                continue

            self.localeInfo[l[3]] = (l[0], l[1], l[2], l[4], string.strip(l[5]))

        f.close()

        # Hard code this to prevent errors in the build environment.
        self.localeInfo['C'] = self.localeInfo['en_US.UTF-8']

        # Set the language for anaconda to be using based on current $LANG.
        self.setRuntimeLanguage(self.fixLang(self.current))
        self.setDefault(self.fixLang(self.current))

    # Convert what might be a shortened form of a language's nick (en or
    # en_US, for example) into the full version (en_US.UTF-8).  If we
    # don't find it, return our default of en_US.UTF-8.
    def canonLangNick (self, nick):
        for key in self.localeInfo.keys():
            if nick in expandLangs(key):
                return key

        return 'en_US.UTF-8'

    def getNickByName (self, name):
        for k in self.localeInfo.keys():
            row = self.localeInfo[k]
            if row[0] == name:
                return k

    def fixLang(self, langToFix):
        ret = None

        if self.displayMode == "t":
            for lang in self.localeInfo.keys():
                if lang == langToFix:
                    (a, b, font, c, d) = self.localeInfo[lang]
                    if font == "none":
                        ret = "en_US.UTF-8"
                        self.targetLang = lang

        if ret is None:
            ret = langToFix

        return ret

    def getNativeLangName(self, lang):
        return self.nativeLangNames[lang]

    def getLangNameByNick(self, nick):
        return self.localeInfo[self.canonLangNick(nick)][0]

    def getFontFile (self, nick):
	# Note: in /etc/fonts.cgz fonts are named by the map
	# name as that's unique, font names are not
        font = self.localeInfo[self.canonLangNick(nick)][2]
        return font

    def getDefaultKeyboard(self):
        return self.localeInfo[self.canonLangNick(self.getCurrent())][3]

    def getDefaultTimeZone(self):
        return self.localeInfo[self.canonLangNick(self.getCurrent())][4]

    def available (self):
        return self.nativeLangNames.keys()

    def getCurrentLangSearchList(self):
	return expandLangs(self.getCurrent()) + ['C']

    def getCurrent(self):
	if self.targetLang is not None:
	    return self.targetLang
	else:
	    return self.current

    def getDefault(self):
        if self.default:
            return self.default
        elif self.current:
            nick = self.getNickByName (self.current)

            return nick
        else:
            return 'en_US.UTF-8'

    def setDefault(self, nick):
	self.default = nick

	dispLang = self.fixLang(self.canonLangNick(nick))
	self.info['LANG'] = dispLang

        if self.localeInfo[dispLang][2] == "none":
            self.info['SYSFONT'] = None
        else:
            self.info['SYSFONT'] = self.localeInfo[dispLang][2]

        # XXX hack - because of exceptional cases on the var - zh_CN.GB2312
	if nick == "zh_CN.GB18030":
	    self.info['LANGUAGE'] = "zh_CN.GB18030:zh_CN.GB2312:zh_CN"        

    def setRuntimeDefaults(self, nick):
        canonNick = self.fixLang(self.canonLangNick(nick))
        self.current = canonNick

    def setRuntimeLanguage(self, nick):
        canonNick = self.canonLangNick(nick)

        # Allow specifying languages in kickstart that aren't in lang-table,
        # but are still valid settings.
        if not canonNick.startswith(nick):
            self.targetLang = nick

        self.setRuntimeDefaults(nick)

        os.environ["LANG"] = self.fixLang(canonNick)
        os.environ["LC_NUMERIC"] = 'C'

        try:
            locale.setlocale(locale.LC_ALL, "")
        except locale.Error:
            pass

        cat.setlangs(expandLangs(os.environ["LANG"]))

    def write(self, instPath):
	f = open(instPath + "/etc/sysconfig/i18n", "w")
        for key in self.info.keys():
            if self.info[key] != None:
                if key == "LANG" and self.targetLang is not None:
                    f.write("%s=\"%s\"\n" % (key, self.targetLang))
                else:
                    f.write("%s=\"%s\"\n" % (key, self.info[key]))
	f.close()

    def writeKS(self, f):
        if self.targetLang is not None:
	    f.write("lang %s\n" % self.targetLang)
        else:
	    f.write("lang %s\n" % self.info['LANG'])
