#
# language.py: install data component that stores information about both
#              installer runtime language choice and installed system
#              language support.
#
# Copyright (C) 2001, 2002, 2003, 2004, 2005, 2009  Red Hat, Inc.
# All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import os
import string
import locale

import gettext
from simpleconfig import SimpleConfigFile
import system_config_keyboard.keyboard as keyboard

import logging
log = logging.getLogger("anaconda")

# Converts a single language into a "language search path". For example,
# fr_FR.utf8@euro would become "fr_FR.utf8@eueo fr_FR.utf8 fr_FR fr"
def expandLangs(astring):
    langs = [astring]
    charset = None
    base = None

    # remove charset ...
    if '.' in astring:
        langs.append(string.split(astring, '.')[0])

    if '@' in astring:
        charset = string.split(astring, '@')[1]

    if '_' in astring:
        base = string.split(astring, '_')[0]

        if charset:
            langs.append("%s@%s" % (base, charset))

        langs.append(base)
    else:
        langs.append(astring[:2])

    return langs

class Language(object):
    def _setInstLang(self, value):
        # Always store in its full form so we know what we're comparing with.
        try:
            self._instLang = self._canonLang(value)
        except ValueError:
            # If the language isn't listed in lang-table, we won't know what
            # keyboard/font/etc. to use.  However, we can still set the $LANG
            # to that and make sure it works in the installed system.
            self._instLang = value

        # If we're running in text mode, value may not be a supported language
        # to display.  We need to default to en_US.UTF-8 for now.
        if self.displayMode == 't':
            for (lang, info) in self.localeInfo.iteritems():
                # If there's no font, it's not a supported language.
                if lang == self._instLang and info[2] == "none":
                    self._instLang = self._default
                    break

        # Now set some things to make sure the language setting takes effect
        # right now.
        os.environ["LANG"] = self._instLang
        os.environ["LC_NUMERIC"] = "C"

        try:
            locale.setlocale(locale.LC_ALL, "")
        except locale.Error:
            pass

        # XXX: oh ick.  this is the sort of thing which you should never do...
        # but we switch languages at runtime and thus need to invalidate
        # the set of languages/mofiles which gettext knows about
        gettext._translations = {}

    def _getInstLang(self):
        # If we were given a language that's not in lang-table, lie and say
        # we're using the default.  This prevents us from having to check all
        # over the place.  Unfortunately, it also means anaconda will be
        # running with the wrong font and keyboard in these cases.
        if self._instLang in self.localeInfo.keys():
            return self._instLang
        else:
            return self._default

    # The language being displayed while anaconda is running.
    instLang = property(lambda s: s._getInstLang(), lambda s, v: s._setInstLang(v))

    def _setSystemLang(self, value):
        # Always store in its full form so we know what we're comparing with.
        try:
            self._systemLang = self._canonLang(value)
        except ValueError:
            # If the language isn't listed in lang-table, we won't know what
            # keyboard/font/etc. to use.  However, we can still set the $LANG
            # to that and make sure it works in the installed system.
            self._systemLang = value

        # Now set a bunch of other things that'll get written to
        # /etc/sysconfig/i18n on the installed system.
        self.info["LANG"] = self._systemLang

        if not self.localeInfo.has_key(self._systemLang):
            return

        if self.localeInfo[self._systemLang][2] == "none":
            self.info["SYSFONT"] = None
        else:
            self.info["SYSFONT"] = self.localeInfo[self._systemLang][2]

        # XXX hack - because of exceptional cases on the var - zh_CN.GB2312
        if self._systemLang == "zh_CN.GB18030":
            self.info["LANGUAGE"] = "zh_CN.GB18030:zh_CN.GB2312:zh_CN"

    # The language to use on the installed system.  This can differ from the
    # language being used during anaconda.  For instance, text installs cannot
    # display all languages (CJK, Indic, etc.).
    systemLang = property(lambda s: s._systemLang, lambda s, v: s._setSystemLang(v))

    def __init__ (self, display_mode = 'g'):
        self._default = "en_US.UTF-8"
        self.displayMode = display_mode
        self.info = {}
        self.localeInfo = {}
        self.nativeLangNames = {}

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
        search = ('lang-table', '/tmp/updates/lang-table', '/etc/lang-table',
                  '/usr/lib/anaconda/lang-table')
        for path in search:
            if os.access(path, os.R_OK):
                f = open(path, "r")
                for line in f.readlines():
                    string.strip(line)
                    l = string.split(line, '\t')

                    # throw out invalid lines
                    if len(l) < 6:
                        continue

                    self.localeInfo[l[3]] = (l[0], l[1], l[2], l[4], string.strip(l[5]))

                f.close()
                break

        # Hard code this to prevent errors in the build environment.
        self.localeInfo['C'] = self.localeInfo[self._default]

        # instLang must be set after localeInfo is populated, in case the
        # current setting is unsupported by anaconda..
        self.instLang = os.environ.get("LANG", self._default)
        self.systemLang = os.environ.get("LANG", self._default)

    def _canonLang(self, lang):
        """Convert the shortened form of a language name into the full
           version.  If it's not found, raise ValueError.

           Example:  fr    -> fr_FR.UTF-8
                     fr_FR -> fr_FR.UTF-8
                     fr_CA -> ValueError
        """
        for key in self.localeInfo.keys():
            if lang in expandLangs(key):
                return key

        raise ValueError

    def available(self):
        return self.nativeLangNames.keys()

    def dracutSetupString(self):
        args=""

        for (key, val) in self.info.iteritems():
            if val != None:
                args += " %s=%s" % (key, val)

        return args

    def getCurrentLangSearchList(self):
        return expandLangs(self.systemLang) + ['C']

    def getDefaultKeyboard(self, instPath):
        try:
            return self.localeInfo[self.systemLang][3]
        except KeyError:
            try:
                kbd = keyboard.Keyboard()
                kbd.read(instPath)
                return kbd.get()
            except:
                return self.localeInfo[self._default][3]

    def getDefaultTimeZone(self, instPath):
        try:
            return self.localeInfo[self.systemLang][4]
        except KeyError:
            # If doing an upgrade and the system language is something not
            # recognized by anaconda, we should try to see if we can figure
            # it out from the running system.
            if os.path.exists(instPath + "/etc/sysconfig/clock"):
                cfg = SimpleConfigFile()
                cfg.read(instPath + "/etc/sysconfig/clock")

                try:
                    return cfg.get("ZONE")
                except:
                    return self.localeInfo[self._default][4]
            else:
                return self.localeInfo[self._default][4]

    def getFontFile(self, lang):
        # Note: in /etc/fonts.cgz fonts are named by the map
        # name as that's unique, font names are not
        try:
            l = self._canonLang(lang)
        except ValueError:
            l = self._default

        return self.localeInfo[l][2]

    def getLangName(self, lang):
        try:
            l = self._canonLang(lang)
        except ValueError:
            l = self._default

        return self.localeInfo[l][0]

    def getLangByName(self, name):
        for (key, val) in self.localeInfo.iteritems():
            if val[0] == name:
                return key

    def getNativeLangName(self, lang):
        return self.nativeLangNames[lang]

    def write(self, instPath):
        f = open(instPath + "/etc/sysconfig/i18n", "w")

        for (key, val) in self.info.iteritems():
            if val != None:
                f.write("%s=\"%s\"\n" % (key, val))

        f.close()

    def writeKS(self, f):
        f.write("lang %s\n" % self.info['LANG'])
