#!/usr/bin/python
#
# Copyright 2002  Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# general public license.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import os, sys
import string
import re
import language


defaultTerritory = {}
# This table is used to eliminate things like French (France)
defaultTerritory["Albanian"] = "Albania"
defaultTerritory["Belarusian"] = "Belarus"
defaultTerritory["Bulgarian"] = "Bulgaria"
defaultTerritory["Croatian"] = "Croatia"
defaultTerritory["Czech"] = "Czech Republic"
defaultTerritory["Danish"] = "Denmark"
defaultTerritory["Estonian"] = "Estonia"
defaultTerritory["Finnish"] = "Finland"
defaultTerritory["Greek"] = "Greece"
defaultTerritory["Hungarian"] = "Hungary"
defaultTerritory["Icelandic"] = "Iceland"
defaultTerritory["Indonesian"] = "Indonesia"
defaultTerritory["Irish"] = "Ireland"
defaultTerritory["Japanese"] = "Japan"
defaultTerritory["Lithuanian"] = "Lithuania"
defaultTerritory["Macedonian"] = "Macedonia"
defaultTerritory["Norwegian"] = "Norway"
defaultTerritory["Polish"] = "Poland"
defaultTerritory["Romanian"] = "Romania"
defaultTerritory["Russian"] = "Russia"
defaultTerritory["Slovak"] = "Slovak"
defaultTerritory["Slovenian"] = "Slovenian"
defaultTerritory["Ukrainian"] = "Ukraine"
defaultTerritory["Vietnamese"] = "Vietnam"
defaultTerritory["Turkish"] = "Turkey"
defaultTerritory["Thai"] = "Thailand"

charMap = {}
charMap["GB2312"] =  "8859-15"
charMap["GB18030"] = "8859-15"
charMap["BIG5"] =  "8859-15"
charMap["EUC-JP"] =  "8859-15"
charMap["EUC-TW"] =  "8859-15"
charMap["EUC-KR"] =  "8859-15"
charMap["GB2312"] =  "8859-15"
charMap["BIG5"] =  "8859-15"
charMap["KOI8-U"] =  "koi8-u"
charMap["KOI8-R"] =  "koi8-u"
charMap["ISO-8859-1"] =  "8859-15"
charMap["ISO-8859-2"] =  "8859-2"
charMap["ISO-8859-3"] =  "8859-3"
charMap["ISO-8859-5"] =  "8859-5"
charMap["ISO-8859-6"] =  "8859-6"
charMap["ISO-8859-7"] =  "8859-7"
charMap["ISO-8859-8"] =  "8859-8"
charMap["ISO-8859-9"] =  "8859-9"
charMap["ISO-8859-15"] =  "8859-15"
charMap["UTF-8"] = "utf8"

charFont = {}
charFont["EUC-JP"] =  "lat0-sun16"
charFont["EUC-TW"] =  "lat0-sun16"
charFont["EUC-KR"] =  "lat0-sun16"
charFont["GB2312"] =  "lat0-sun16"
charFont["GB18030"] = "lat0-sun16"
charFont["BIG5"] =  "lat0-sun16"
charFont["KOI8-U"] =  "cyr-sun16"
charFont["KOI8-R"] =  "cyr-sun16"
charFont["ISO-8859-1"] =  "lat0-sun16"
charFont["ISO-8859-2"] =  "lat2-sun16"
#charFont["ISO-8859-3"] =  "iso03"		mk_MK -- no font available
charFont["ISO-8859-5"] =  "cyr-sun16"
charFont["ISO-8859-6"] =  "latarcyrheb-sun16"
charFont["ISO-8859-7"] =  "iso07.16"
charFont["ISO-8859-8"] =  "latarcyrheb-sun16"
charFont["ISO-8859-9"] =  "lat5-sun16"
charFont["ISO-8859-15"] =  "lat0-sun16"
charFont["UTF-8"] = "latarcyrheb-sun16"

prefNotUtf8 = {}


f = os.popen("locale -a", "r")
lines = f.readlines()
f.close()


langList = {}
charmapList = {}
nameList = {}

for line in lines:
    line = line[:-1]
    line = line.strip()

    # limit to items of the form xx_.*
    if not re.search("^[a-zA-Z][a-zA-Z]_", line):
        continue

    lang = line
    lang = lang.replace("eucjp", "eucJP")
    lang = lang.replace("euckr", "eucKR")
    lang = lang.replace("gb18030", "GB18030")
    lang = re.sub("^zh_CN$", "zh_CN.GB18030", lang)
    lang = re.sub("^zh_TW$", "zh_TW.Big5", lang)
    lang = re.sub("^ja_JP$", "ja_JP.eucJP", lang)
    lang = re.sub("^ko_KR$", "ko_KR.eucKR", lang)
    lang = lang.replace("utf8", "UTF-8")

    # we don't want @euro locales for utf8
    lang = lang.replace("UTF-8@euro", "UTF-8")

    # someone put no_NO in locale.alias.  yuck.  We don't want
    # to offer that
    if lang.startswith("no_") or lang.startswith("iw_"):
        continue

    f = os.popen("LANG=%s locale language territory charmap" %(lang,), "r")
    name = f.readline()
    territory = f.readline()
    charmap = f.readline()
    f.close()

    name = name[:-1].strip()
    territory = territory[:-1].strip()
    charmap = charmap[:-1].strip()
    
    # some languages names are the same as their iso id
    if name == lang[:2]:
        continue

    if defaultTerritory.has_key(name) and defaultTerritory[name] == territory:
        fullName = name
    else:
        fullName = "%s (%s)" %(name, territory)

    if nameList.has_key(fullName):
        # we want the en_US form
        nick = language.expandLangs(nameList[fullName])[-2]
#	if prefNotUtf8.has_key(nick):
#		print prefNotUtf8[nick]
#	else:
#		print
        if (prefNotUtf8.has_key(nick) and
            (charmap != prefNotUtf8[nick])):
#	    print "have nick, but this isn't the right charmap"
            continue
        elif charmap != "UTF-8":
            continue
        elif len(lang) < len(nameList[fullName]):
            continue
    elif charmap != "UTF-8": # this doesn't handle the prefNotUtf8 stuff
        continue
            
    nameList[fullName] = lang
    langList[lang] = fullName
    charmapList[lang] = charmap
    

names = nameList.keys()
names.sort()

for name in names:
    short = nameList[name]
    map = charmapList[short]

    if charMap.has_key(map) and charFont.has_key(map):
        print "%s\t%s\t%s\t%s" %(short, charMap[map], charFont[map], name)
