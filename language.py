import os
import string
import locale
from simpleconfig import SimpleConfigFile
import rpm
from translate import cat

# Converts a single language into a "language search path". For example,
# fr_FR.utf8@euro would become "fr_FR.utf8@eueo fr_FR.utf8 fr_FR fr"
def expandLangs(str):
    langs = [str]
    # remove charset ...
    if '.' in str:
	langs.append(string.split(str, '.')[0])

    if '@' in str:
	langs.append(string.split(str, '@')[0])

    # also add 2 character language code ...
    if len(str) > 2:
	langs.append(str[:2])

    return langs

# This is the langauge that's being used at install time (a list of the
# choices is in lang-table). 
class InstallTimeLanguage:

    def __init__ (self):
        if os.environ.has_key("LANG"):
            self.current = os.environ["LANG"]
        else:
            self.current = "en_US"
	if os.access("lang-table", os.R_OK):
	    f = open("lang-table", "r")
	elif os.access("/etc/lang-table", os.R_OK):
	    f = open("/etc/lang-table", "r")
	else:
	    f = open("/usr/lib/anaconda/lang-table", "r")

	lines = f.readlines ()
	f.close()
	self.langNicks = {}
	self.font = {}
	self.map = {}
	self.kbd = {}
	self.tz = {}
	self.langList = []

        self.tempDefault = ""

	for line in lines:
	    string.strip(line)
	    l = string.split(line)
	    
	    longName = l[0]
	    font = l[2]
	    map = l[3]
	    shortName = l[4]
	    keyboard = l[5]
	    timezone = l[6]

	    self.langList.append(longName)
	    self.langNicks[longName] = shortName
	    self.font[longName] = font
	    self.map[longName] = map
	    self.kbd[longName] = keyboard
	    self.tz[longName] = timezone

	self.langList.sort()

    def getFontMap (self, lang):
	return self.map[lang]

    def getFontFile (self, lang):
	# Note: in /etc/fonts.cgz fonts are named by the map
	# name as that's unique, font names are not
	return self.font[lang]

    def getLangNick (self, lang):
        # returns the short locale ID
	return self.langNicks[lang]

    def getLangNameByNick(self, lang):
	# The nick we get here may be long (fr_FR@euro), when we need
	# shorter (fr_FR), so be a bit fuzzy
	for (langName, nick) in self.langNicks.items():
	    if (nick == lang) or (nick == lang[0:len(nick)]):
		return langName

        #raise KeyError, "language %s not found" % lang
        return self.getLangNameByNick("en_US")

    def getDefaultKeyboard(self):
	return self.kbd[self.getCurrent()]

    def getDefaultTimeZone(self):
	return self.tz[self.getCurrent()]

    def available (self):
        return self.langList

    def getCurrentLangSearchList(self):
	return expandLangs(self.langNicks[self.getCurrent()]) + ['C']

    def getCurrent(self):
	return self.getLangNameByNick(self.current)

    def setRuntimeDefaults(self, name):
	lang = self.langNicks[name]
        self.current = lang
        # XXX HACK HACK, I'm using an environment variable to communicate
        # between two classes (runtimelang and lang support)
        os.environ["RUNTIMELANG"] = lang

    def setRuntimeLanguage(self, name):
        if not os.environ.has_key("RUNTIMELANG"):
            self.setRuntimeDefaults(name)
        lang = self.langNicks[name]

        os.environ["LANG"] = lang
        os.environ["LC_NUMERIC"] = 'C'
        try:
            locale.setlocale(locale.LC_ALL, "")
        except locale.Error:
            pass

        newlangs = [lang]
	if len(lang) > 2:
            newlangs.append(lang[:2])
        cat.setlangs (newlangs)

    def writeKS(self, f):
	lang = self.getLangNick(self.getCurrent())
	f.write("lang %s\n" % lang);

# The languages which should be supported on the installed system, including
# which language to set as the default.
class Language (SimpleConfigFile):

    def __init__ (self, useInstalledLangs):
        self.info = {}
        self.info["SUPPORTED"] = None
	self.supported = []
	self.default = None

        self.allSupportedLangs = []
        self.langInfoByName = {}

        allSupportedLangs = []
        langInfoByName = {}
        langFilter = {}
        allInstalledFlag = 0

        if useInstalledLangs:
            # load from /etc/sysconfig/i18n
            supported = None
            if os.access("/etc/sysconfig/i18n", os.R_OK):
                f = open("/etc/sysconfig/i18n")
                lines = f.readlines()
                f.close()
                for line in lines:
                    if line[0:9] == "SUPPORTED":
                        tmpstr = line[11:]
                        supported = tmpstr[:string.find(tmpstr,'\"')]
                        break

            # if no info on current system, with RH 7.1 this means ALL
            # languages were installed
            if not supported:
                allInstalledFlag = 1
            else:
                for lang in string.split(supported, ":"):
                    langFilter[lang] = 1

        langsInstalled = []
        if os.access("/usr/share/anaconda/locale-list", os.R_OK):
            f = open("/usr/share/anaconda/locale-list")
            lines = f.readlines()
            f.close()
            for line in lines:
                line = string.strip(line)
                (lang, map, font, name) = string.split(line, ' ', 3)
                langInfoByName[name] = (lang, map, font)
                allSupportedLangs.append(name)

                if allInstalledFlag or (langFilter and langFilter.has_key(lang)):
                    langsInstalled.append(name)
        else:
            langInfoByName['English (USA)'] = ('en_US', 'iso01', 'default8x16')
            allSupportedLangs.append('English (USA)')
            langsInstalled.append('English (USA)')

        self.langInfoByName = langInfoByName
        self.allSupportedLangs = allSupportedLangs

        # set languages which were selected at install time for reconfig mode
        if useInstalledLangs:
            self.setSupported(langsInstalled)
                                             
    def getAllSupported(self):
	return self.allSupportedLangs

    def getLangNameByNick(self, nick):
	for langName in self.langInfoByName.keys():
	    (lang, map, font) = self.langInfoByName[langName]
	    if (nick == lang) or (nick == lang[0:len(nick)]):
		return langName

#	raise KeyError, "language %s not found" % nick
        return self.getLangNameByNick("en_US")

    def getLangNickByName(self, name):
	(lang, map, font) = self.langInfoByName[name]
        return lang

    def getSupported (self):
	return self.supported

    def getDefault (self):
	if self.default:
	    return self.default
        # XXX (see above comment)
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
	    return 'English (USA)'
    
    def setDefault(self, name):
	if not name:
	    self.default = None
	    return

	self.default = name
	(lang, map, font) = self.langInfoByName[name]

	self.info['LANG'] = lang
	self.info['SYSFONT'] = font
	self.info['SYSFONTACM'] = map

    def setSupported (self, langlist):
	if len(langlist) == len(self.allSupportedLangs):
            self.info["SUPPORTED"] = None
	    self.supported = langlist
            rpm.delMacro ("_install_langs")
        elif langlist:
	    rpmNickList = []
	    for name in langlist:
		(lang, map, font) = self.langInfoByName[name]
		rpmNickList = rpmNickList + expandLangs(lang)

            linguas = string.join (rpmNickList, ':')
            self.info["SUPPORTED"] = linguas
	    self.supported = langlist

            shortLinguas = string.join (rpmNickList, ':')
            rpm.addMacro("_install_langs", shortLinguas)
        else:
            self.info["SUPPORTED"] = None
            rpm.delMacro ("_install_langs")
	    self.supported = None
	
	if self.info["SUPPORTED"]:
	    os.environ ["LINGUAS"] = self.info["SUPPORTED"]
	else:
	    os.environ ["LINGUAS"] = ""
    
    def write(self, instPath):
	f = open(instPath + "/etc/sysconfig/i18n", "w")
	f.write(str (self))
	f.close()

    def writeKS(self, f):
	sup = ""
        if self.info["SUPPORTED"] != None:
            for n in self.getSupported():
                sup = sup + " " + self.getLangNickByName(n)
	
	f.write("langsupport --default %s%s\n" % 
		(self.getLangNickByName(self.getDefault()), sup))
