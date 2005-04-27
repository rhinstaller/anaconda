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
import rpm

from rhpl.translate import cat
from rhpl.simpleconfig import SimpleConfigFile
from rhpl.log import log

# Converts a single language into a "language search path". For example,
# fr_FR.utf8@euro would become "fr_FR.utf8@eueo fr_FR.utf8 fr_FR fr"
def expandLangs(astring):
    langs = [astring]
    # remove charset ...
    if '.' in astring:
	langs.append(string.split(astring, '.')[0])

    if '@' in astring:
	langs.append(string.split(astring, '@')[0])

    # also add 2 character language code ...
    if len(astring) > 2:
	langs.append(astring[:2])

    return langs

class Language:
    def __init__ (self):
        self.info = {}
        self.info["SUPPORTED"] = None
        self.supported = []
        self.default = None

        self.allSupportedLangs = []
        self.langInfoByName = {}
        self.nativeLangNames = {}
        self.localeInfo = {}

        if os.environ.has_key("LANG"):
            self.current = os.environ["LANG"]
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

            # "bterm" and "none" are only useful for loader.
            if l[2] == "none" or l[2] == "bterm":
                font = "latarcyrheb-sun16"
            else:
                font = l[2]

            self.localeInfo[l[3]] = (l[0], l[1], font, l[4], string.strip(l[5]))

        f.close()

        # Hard code this to prevent errors in the build environment.
        self.localeInfo['C'] = self.localeInfo['en_US.UTF-8']

        # long name -> (nick, map, font) mapping
        search = ('locale-list', '/usr/share/anaconda/locale-list')
        for path in search:
            if os.access(path, os.R_OK):
                f = open(path, 'r')

                for line in f.readlines():
                    line = string.strip(line)
                    (nick, map, font, name) = string.split(line, '\t')
                    self.langInfoByName[name] = (nick, map, font)

                f.close()
                break

        # If we weren't able to find a locale-list, set a reasonable default.
        if not self.allSupportedLangs:
            self.langInfoByName['English (USA)'] = ('en_US.UTF-8', 'iso01', 'default8x16')

        self.allSupportedLangs = self.langInfoByName.keys()

        # Set the language for anaconda to be using based on current $LANG.
        self.setRuntimeLanguage(self.current)
        self.setDefault(self.current)

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

    def getNativeLangName(self, lang):
        return self.nativeLangNames[lang]

    def getLangNameByNick(self, nick):
        return self.localeInfo[self.canonLangNick(nick)][0]

    def getFontFile (self, nick):
	# Note: in /etc/fonts.cgz fonts are named by the map
	# name as that's unique, font names are not
        return self.localeInfo[self.canonLangNick(nick)][2]

    def getDefaultKeyboard(self):
        return self.localeInfo[self.canonLangNick(self.getCurrent())][3]

    def getDefaultTimeZone(self):
        return self.localeInfo[self.canonLangNick(self.getCurrent())][4]

    def available (self):
        return self.nativeLangNames.keys()

    def getSupported (self):
	return self.supported

    def getAllSupported (self):
        return self.allSupportedLangs

    def getCurrentLangSearchList(self):
	return expandLangs(self.getCurrent()) + ['C']

    def getCurrent(self):
	return self.current

    def getDefault(self):
        if self.default:
            return self.default
        elif self.current:
            nick = self.getNickByName (self.current)
            if nick not in self.getSupported():
                # the default language needs to be in the supported list!
                s = self.getSupported()
                s.append(nick)
                s.sort()
                self.setSupported(s)

            return nick
        else:
            return 'en_US.UTF-8'

    def setDefault(self, nick):
	self.default = nick
	self.info['LANG'] = nick
	self.info['SYSFONT'] = self.localeInfo[self.canonLangNick(nick)][2]

        # XXX hack - because of exceptional cases on the var - zh_CN.GB2312
	if nick == "zh_CN.GB18030":
	    self.info['LANGUAGE'] = "zh_CN.GB18030:zh_CN.GB2312:zh_CN"        

    def setSupported (self, nickList):
	if len(nickList) == len(self.allSupportedLangs):
            self.info["SUPPORTED"] = None
	    self.supported = self.getAllSupported()
        elif nickList:
	    rpmNickList = []

	    for nick in nickList:
                for sub in expandLangs(nick):
                    if not sub in rpmNickList:
                        rpmNickList.append(sub)

            linguas = string.join (rpmNickList, ':')
            self.info["SUPPORTED"] = linguas
            self.supported = rpmNickList

            shortLinguas = string.join (rpmNickList, ':')
        else:
            self.info["SUPPORTED"] = None
            self.supported = None
	
	if self.info["SUPPORTED"]:
            os.environ ["LINGUAS"] = self.info["SUPPORTED"]
	else:
            os.environ ["LINGUAS"] = ""

    def setRuntimeDefaults(self, nick):
        canonNick = self.canonLangNick(nick)
        self.current = canonNick

    def setRuntimeLanguage(self, nick):
        canonNick = self.canonLangNick(nick)
        self.setRuntimeDefaults(nick)

        os.environ["LANG"] = canonNick
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
                f.write("%s=\"%s\"\n" % (key, self.info[key]))
	f.close()

    def writeKS(self, f):
        sup = ""

        if self.info["SUPPORTED"] != None:
            for n in self.getSupported():
                sup = sup + " " + n

	f.write("lang %s\n" % self.info['LANG'])
        f.write("langsupport --default=%s%s\n" % (self.getDefault(), sup))
