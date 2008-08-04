#
# compssort.py
#
# Copyright (C) 2005, 2006, 2007  Red Hat, Inc.  All rights reserved.
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

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

def _getDefaultLangs():
    languages = []
    for envar in ('LANGUAGE', 'LC_ALL', 'LC_MESSAGES', 'LANG'):
        val = os.environ.get(envar)
        if val:
            languages = val.split(':')
            break
    if 'C' not in languages:
        languages.append('C')

    # now normalize and expand the languages
    nelangs = []
    for lang in languages:
        for nelang in gettext._expand_lang(lang):
            if nelang not in nelangs:
                nelangs.append(nelang)
    return nelangs

# kind of lame caching of translations so we don't always have
# to do all the looping
strs = {}
def xmltrans(base, thedict):
    if strs.has_key(base):
        return strs[base]

    langs = _getDefaultLangs()
    for l in langs:
        if thedict.has_key(l):
            strs[base] = thedict[l]
            return strs[base]
    strs[base] = base
    return base

def ui_comps_sort(one, two):
    if one.display_order > two.display_order:
        return 1
    elif one.display_order < two.display_order:
        return -1
    elif xmltrans(one.name, one.translated_name) > \
         xmltrans(two.name, two.translated_name):
        return 1
    elif xmltrans(one.name, one.translated_name) < \
         xmltrans(two.name, two.translated_name):
        return -1
    return 0
