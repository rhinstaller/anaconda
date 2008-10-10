#
# getlangnames.py
#
# Copyright (C) 2007  Red Hat, Inc.  All rights reserved.
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

import sys
sys.path.append("..")
import language

import gettext

langs = language.Language()
names = {}
for k in langs.localeInfo.keys():
    found = False
    for l in language.expandLangs(k):
        try:
            f = open("po/%s.mo" %(l,))
        except (OSError, IOError):
            continue
        cat = gettext.GNUTranslations(f)
        cat.set_output_charset("utf-8")
        names[langs.localeInfo[k][0]] = cat.lgettext(langs.localeInfo[k][0])
        found = True
        break
    if not found:
        names[langs.localeInfo[k][0]] = langs.localeInfo[k][0]

nameList = names.keys()
nameList.sort()

for k in nameList:
    print("%s\t%s" % (k, names[k]))
