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

            self.localeInfo[l[3]] = (l[0], l[1], l[2], l[4], string.strip(l[5]))

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
        self.setSupported([self.getLangNameByNick(self.current)])

    # Convert what might be a shortened form of a language's nick (en or
    # en_US, for example) into the full version (en_US.UTF-8).
    def canonLangNick (self, nick):
        try:
            for key in self.localeInfo.keys():
                if nick in expandLangs(key):
                    return key
        except:
            return 'en_US.UTF-8'

    def getNickByName (self, name):
        for k in self.localeInfo.keys():
            row = self.localeInfo[k]
            if row[0] == name:
                return k
        
    def getNativeLangName(self, lang):
        return self.nativeLangNames[lang]

    def getLangNameByNick(self, nick):
	canonNick = self.canonLangNick (nick)

        try:
            return self.localeInfo[canonNick][0]
        except KeyError:
            curNick = self.canonLangNick (self.getCurrent())
            return self.localeInfo[curNick][0]

    def getFontFile (self, lang):
	# Note: in /etc/fonts.cgz fonts are named by the map
	# name as that's unique, font names are not
        lang = self.canonLangNick (lang)
        return self.localeInfo[lang][2]

    def getDefaultKeyboard(self):
        lang = self.canonLangNick (self.getCurrent())
        return self.localeInfo[lang][3]

    def getDefaultTimeZone(self):
        lang = self.canonLangNick (self.getCurrent())
        return self.localeInfo[lang][4]

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
        elif os.environ.has_key('RUNTIMELANG'):
            lang = os.environ['RUNTIMELANG']
            name = self.getLangNameByNick(lang)
            if name not in self.getSupported():
                # the default language needs to be in the supported list!
                s = self.getSupported()
                s.append(name)
                s.sort()
                self.setSupported(s)

            return name
        else:
            return 'English'

    def setDefault(self, nick):
	canonNick = self.canonLangNick(nick)

	if not canonNick or not self.localeInfo[canonNick]:
	    self.default = None
	    return

	self.default = self.getLangNameByNick(canonNick)

	self.info['LANG'] = canonNick
	self.info['SYSFONT'] = self.localeInfo[canonNick][2]
        self.info['SYSFONTACM'] = "utf8"

        # XXX hack - because of exceptional cases on the var - zh_CN.GB2312
	if nick == "zh_CN.GB18030":
	    self.info['LANGUAGE'] = "zh_CN.GB18030:zh_CN.GB2312:zh_CN"        

    def setSupported (self, namelist):
	if len(namelist) == len(self.allSupportedLangs):
            self.info["SUPPORTED"] = None
	    self.supported = self.getAllSupported()
        elif namelist:
	    rpmNickList = []
	    for name in namelist:
                nick = self.getNickByName(name)
		rpmNickList = rpmNickList + expandLangs(nick)

            linguas = string.join (rpmNickList, ':')
            self.info["SUPPORTED"] = linguas
	    self.supported = namelist

            shortLinguas = string.join (rpmNickList, ':')
        else:
            self.info["SUPPORTED"] = None
	    self.supported = None
	
	if self.info["SUPPORTED"]:
	    os.environ ["LINGUAS"] = self.info["SUPPORTED"]
	else:
	    os.environ ["LINGUAS"] = ""

    def setRuntimeDefaults(self, nick):
        self.current = nick
        # XXX HACK HACK, I'm using an environment variable to communicate
        # between two classes (runtimelang and lang support)
        os.environ["RUNTIMELANG"] = nick

    def setRuntimeLanguage(self, nick):
        self.setRuntimeDefaults(nick)
        lang = nick

        os.environ["LANG"] = lang
        os.environ["LC_NUMERIC"] = 'C'
        try:
            locale.setlocale(locale.LC_ALL, "")
        except locale.Error:
            pass

        newlangs = [lang]
        if lang.find(".") != -1:
            newlangs.append(lang[:lang.find(".")])
	if len(lang) > 2:
            newlangs.append(lang[:2])
        cat.setlangs(newlangs)

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
                sup = sup + " " + self.getNickByName(n)

	f.write("lang %s\n" % self.getCurrent())
        f.write("langsupport --default=%s%s\n" %
		(self.getNickByName(self.getDefault()), sup))
