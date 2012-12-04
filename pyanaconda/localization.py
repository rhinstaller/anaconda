# Localization classes and functions
#
# Copyright (C) 2012  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Martin Gracik <mgracik@redhat.com>
#

from collections import defaultdict, deque, OrderedDict
import gettext
import locale
import os
import re

import babel


LOCALE_PREFERENCES = {}

LOCALE_CONF_FILE_PATH = "/etc/locale.conf"

class LocalizationConfigError(Exception):
    """Exception class for localization configuration related problems"""

    pass

class LocaleInfo(object):

    def __init__(self, localedata, encoding="", script=""):
        """
        @param encoding: encoding from the locale specification, e.g. UTF-8
                         (localedata object has no attribute for that)
        @param script: script from the locale specification (e.g. latin)
                       (changing localedata.script attribute results in
                       problems)

        """

        self._localedata = localedata
        self._encoding = encoding or "UTF-8"
        self._script = script

    @property
    def language(self):
        return self._localedata.language

    @property
    def territory(self):
        return self._localedata.territory

    @property
    def script(self):
        return self._script

    @property
    def variant(self):
        return self._localedata.variant

    @property
    def encoding(self):
        return self._encoding

    @property
    def english_name(self):
        return self._localedata.english_name or u''

    @property
    def display_name(self):
        # some languages don't have a display_name
        display_name = self._localedata.display_name or self.english_name
        # some start with lowercase
        display_name = display_name.title()
        return display_name

    @property
    def short_name(self):
        return self.__repr__()

    def __repr__(self):
        formatstr = '{0.language}'
        if self.territory is not None:
            formatstr += '_{0.territory}'
        if self.encoding:
            formatstr += '.{0.encoding}'
        if self.script:
            formatstr += '@{0.script}'
        if self.variant is not None:
            formatstr += '#{0.variant}'

        return formatstr.format(self)

    def __str__(self):
        return self.english_name.encode('ascii', 'replace')

    def __unicode__(self):
        return self.english_name

    def __eq__(self, other):
        return repr(self) == repr(other)

def mangleLocale(inLocale):
    mangleMap = {"af":  "af_ZA",  "am":  "am_ET",  "ar":  "ar_SA",  "as":  "as_IN",
                 "ast": "ast_ES", "be":  "be_BY",  "bg":  "bg_BG",  "bn":  "bn_BD",
                 "bs":  "bs_BA",  "ca":  "ca_ES",  "cs":  "cs_CZ",  "cy":  "cy_GB",
                 "da":  "da_DK",  "de":  "de_DE",  "el":  "el_GR",  "en":  "en_US",
                 "es":  "es_ES",  "et":  "et_EE",  "eu":  "eu_ES",  "fa":  "fa_IR",
                 "fi":  "fi_FI",  "fr":  "fr_FR",  "gl":  "gl_ES",  "gu":  "gu_IN",
                 "he":  "he_IL",  "hi":  "hi_IN",  "hr":  "hr_HR",  "hu":  "hu_HU",
                 "hy":  "hy_AM",  "id":  "id_ID",  "ilo": "ilo_PH", "is":  "is_IS",
                 "it":  "it_IT",  "ja":  "ja_JP",  "ka":  "ka_GE",  "kk":  "kk_KZ",
                 "kn":  "kn_IN",  "ko":  "ko_KR",  "lt":  "lt_LT",  "lv":  "lv_LV",
                 "mai": "mai_IN", "mk":  "mk_MK",  "ml":  "ml_IN",  "mr":  "mr_IN",
                 "ms":  "ms_MY",  "nb":  "nb_NO",  "nds": "nds_DE", "ne":  "ne_NP",
                 "nl":  "nl_NL",  "nn":  "nn_NO",  "nso": "nso_ZA", "or":  "or_IN",
                 "pa":  "pa_IN",  "pl":  "pl_PL",  "pt":  "pt_PT",  "ro":  "ro_RO",
                 "ru":  "ru_RU",  "si":  "si_LK",  "sk":  "sk_SK",  "sl":  "sl_SI",
                 "sq":  "sq_AL",  "sr":  "sr_RS",  "sr@latin": "sr_Latn_RS",
                 "sv":  "sv_SE",  "ta":  "ta_IN",  "te":  "te_IN",  "tg":  "tg_TJ",
                 "th":  "th_TH",  "tr":  "tr_TR",  "uk":  "uk_UA",  "ur":  "ur_PK",
                 "vi":  "vi_VN",  "zu":  "zu_ZA"}

    return mangleMap.get(inLocale, inLocale)

# XXX this should probably be somewhere else
def partition(seq, func=bool, func_range=(True, False)):
    buffers = dict(((x, deque()) for x in func_range))

    def values(x, seq=iter(seq)):
        while True:
            while not buffers[x]:
                item = seq.next()
                buffers[func(item)].append(item)

            yield buffers[x].popleft()

    return tuple(values(x) for x in func_range)


def get_all_locales():
    localeset = set()
    for localename in sorted(babel.localedata.list()):
        try:
            localedata = babel.Locale.parse(localename)
        except babel.core.UnknownLocaleError:
            continue

        # BUG: babel.Locale.parse does not parse @script
        script = _get_locale_script(localename)
        encoding = _get_locale_encoding(localename)

        locale = LocaleInfo(localedata, encoding, script)
        if repr(locale) not in localeset:
            localeset.add(repr(locale))
            yield locale


def get_available_translations(domain=None, localedir=None):
    domain = domain or gettext._current_domain
    localedir = localedir or gettext._default_localedir

    langs = babel.localedata.list()
    messagefiles = gettext.find(domain, localedir, langs, all=True)
    languages = [path.split(os.path.sep)[-3] for path in messagefiles]

    # usually there are no message files for en
    if 'en' not in languages:
        languages.append('en')

    for langcode in languages:
        try:
            localedata = babel.Locale.parse(mangleLocale(langcode))
        except babel.core.UnknownLocaleError:
            continue

        encoding = _get_locale_encoding(langcode)

        # BUG: babel.Locale.parse does not parse @script
        script = _get_locale_script(langcode)

        localeinfo = LocaleInfo(localedata, encoding, script)
        yield localeinfo

def expand_langs(astring):
    """
    Converts a single language into a "language search path". For example,
    for "fr_FR.UTF-8@euro" would return set containing:
    "fr", "fr_FR", "fr_FR.UTF-8@euro", "fr.UTF-8@euro", "fr_FR@euro",
    "fr_FR.UTF-8", "fr@euro", "fr.UTF-8"

    @rtype: list of strings

    """

    langs = set([astring])

    base = None
    loc = None
    encoding = None
    script = None

    if "@" in astring:
        (astring, script) = astring.split("@", 1)

    if "." in astring:
        (astring, encoding) = astring.split(".", 1)

    if "_" in astring:
        (astring, loc) = astring.split("_", 1)

    base = astring

    if not base:
        return list(langs)

    if not encoding:
        encoding = "UTF-8"

    langs.add(base)
    langs.add("%s.%s" % (base, encoding))

    if loc:
        langs.add("%s_%s" % (base, loc))
        langs.add("%s_%s.%s" %(base, loc, encoding))
    if script:
        langs.add("%s@%s" % (base, script))
        langs.add("%s.%s@%s" % (base, encoding, script))

    if loc and script:
        langs.add("%s_%s@%s" % (base, loc, script))

    return list(langs)

def _get_locale_encoding(locale):
    """
    If locale specification includes encoding (e.g. cs_CZ.UTF-8) returns
    the encoding. Otherwise returns "".

    """

    if "@" in locale:
        # remove @script suffix
        locale = locale.split("@", -1)[0]

    if "." in locale:
        return locale.split(".", -1)[1]
    else:
        return ""

def _get_locale_script(locale):
    """Same as _get_locale_encoding but with the script."""

    if "@" in locale:
        return locale.split("@", -1)[1]
    else:
        return ""

def write_language_configuration(lang, root):
    """
    Write language configuration to the $root/etc/locale.conf file.

    @param lang: ksdata.lang object
    @param root: path to the root of the installed system

    """

    try:
        fpath = os.path.normpath(root + LOCALE_CONF_FILE_PATH)
        with open(fpath, "w") as fobj:
            fobj.write('LANG="%s"\n' % lang.lang)

    except IOError as ioerr:
        msg = "Cannot write language configuration file: %s" % ioerr.strerror
        raise LocalizationConfigError(msg)

class PreferredLocale(object):

    @staticmethod
    def from_language(language):
        locales = defaultdict(set)
        for locale in get_all_locales():
            locales[repr(locale)].add(locale)
            locales[locale.language].add(locale)

        return PreferredLocale(locales[language])

    @staticmethod
    def from_territory(territory):
        locales = defaultdict(set)
        for locale in get_all_locales():
            locales[locale.territory].add(locale)

        return PreferredLocale(locales[territory])

    def __init__(self, localeset):
        self._localedict = {repr(locale):locale for locale in localeset}

    def get_all_locales(self, preferences=[]):
        preferences = filter(self._localedict.__contains__, preferences)
        inside, outside = partition(self._localedict.keys(), func=lambda x: x in preferences)
        sorted_locales = [self._localedict[localename] for localename in list(inside) + list(outside)]
        return sorted_locales

    def get_preferred_locale(self, preferences=[]):
        try:
            return self.get_all_locales(preferences)[0]
        except IndexError:
            return None


class Language(object):

    def __init__(self, preferences={}, territory=None):
        self.translations = {repr(locale):locale for locale in get_available_translations()}
        self.locales = {repr(locale):locale for locale in get_all_locales()}
        self.preferred_translation = self.translations['en_US.UTF-8']
        self.preferred_locales = [self.locales['en_US.UTF-8']]
        self.preferred_locale = self.preferred_locales[0]

        self.all_preferences = preferences
        self.preferences = self.all_preferences.get(territory, [])
        self.territory = territory
        if self.territory:
            self._get_preferred_translation_and_locales()

    def _get_preferred_translation_and_locales(self):
        # get locales from territory
        locales_from_territory = PreferredLocale.from_territory(self.territory)
        all_locales = locales_from_territory.get_all_locales(self.preferences)

        # get preferred translation
        for locale in all_locales:
            if locale.language in self.translations:
                self.preferred_translation = self.translations[locale.language]
                break

        for locale in all_locales:
            if locale.short_name in self.translations:
                self.preferred_translation = self.translations[locale.short_name]
                break

        self.preferred_locales = all_locales

    def select_translation(self, translation):
        translation = self.translations[translation]
        self.preferences.extend(self.all_preferences.get(translation.language, []))

        # get locales from translation
        locales_from_language = PreferredLocale.from_language(translation.short_name)
        all_locales = locales_from_language.get_all_locales(self.preferences)

        # get preferred locale
        for locale in all_locales:
            if locale in self.preferred_locales:
                self.preferred_locale = locale
                break
        else:
            try:
                self.preferred_locale = all_locales[0]
            except IndexError:
                self.preferred_locale = self.preferred_locales[0]

        # add the preferred locale to the beginning of locales
        if self.preferred_locale in self.preferred_locales:
            self.preferred_locales.remove(self.preferred_locale)
        self.preferred_locales.insert(0, self.preferred_locale)

        # if territory is not set, use the one from preferred locale
        self.territory = self.territory or self.preferred_locale.territory

    @staticmethod
    def parse_langcode(langcode):
        pattern = re.compile(r'(?P<language>[A-Za-z]+)(_(?P<territory>[A-Za-z]+))?(\.(?P<codeset>[-\w]+))?(@(?P<modifier>[-\w]+))?')
        m = pattern.match(langcode)
        return m.groupdict()

    @property
    def install_lang_as_dict(self):
        self.parse_langcode(self.install_lang)

    @property
    def system_lang_as_dict(self):
        self.parse_langcode(self.system_lang)

    def set_install_lang(self, langcode):
        self.install_lang = langcode

        os.environ['LANG'] = langcode
        os.environ['LC_NUMERIC'] = 'C'

        try:
            locale.setlocale(locale.LC_ALL, '')
        except locale.Error:
            pass

        # XXX this is the sort of thing which you should never do,
        # but we switch languages at runtime and thus need to invalidate
        # the set of languages/mofiles which gettext knows about
        gettext._translations = {}

    def set_system_lang(self, langcode):
        self.system_lang = langcode
