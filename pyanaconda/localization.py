# Localization classes and functions
#
# Copyright (C) 2012-2013 Red Hat, Inc.
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
#                    Vratislav Podzimek <vpodzime@redhat.com>
#

import gettext
import os
import re
import langtable
import glob

import logging
log = logging.getLogger("anaconda")

LOCALE_CONF_FILE_PATH = "/etc/locale.conf"

#e.g. 'SR_RS.UTF-8@latin'
LANGCODE_RE = re.compile(r'(?P<language>[A-Za-z]+)'
                         r'(_(?P<territory>[A-Za-z]+))?'
                         r'(\.(?P<encoding>[-A-Za-z0-9]+))?'
                         r'(@(?P<script>[-A-Za-z0-9]+))?')

class LocalizationConfigError(Exception):
    """Exception class for localization configuration related problems"""

    pass

class InvalidLocaleSpec(LocalizationConfigError):
    """Exception class for the errors related to invalid locale specs"""

    pass

def _upcase_first_letter(string):
    """
    Helper function that upcases the first letter of the string. Python's
    standard string.capitalize() not only upcases the first letter but also
    lowercases all the others. string.title() capitalizes all words in the
    string.

    :type string: either a str or unicode object
    :return: the given string with the first letter upcased
    :rtype: str or unicode (depends on the input)

    """

    if not string:
        # cannot change anything
        return string
    elif len(string) == 1:
        return string.upper()
    else:
        return string[0].upper() + string[1:]

def parse_langcode(langcode):
    """
    For a given langcode (e.g. 'SR_RS.UTF-8@latin') returns a dictionary
    with the following keys and example values:

    'language' : 'SR'
    'territory' : 'RS'
    'encoding' : 'UTF-8'
    'script' : 'latin'

    or None if the given string doesn't match the LANGCODE_RE.

    """

    match = LANGCODE_RE.match(langcode)
    if match:
        return match.groupdict()
    else:
        return None

def expand_langs(astring):
    """
    Converts a single language into a "language search path". For example,
    for "fr_FR.UTF-8@euro" would return set containing:
    "fr", "fr_FR", "fr_FR.UTF-8@euro", "fr.UTF-8@euro", "fr_FR@euro",
    "fr_FR.UTF-8", "fr@euro", "fr.UTF-8"

    :rtype: list of strings

    """

    langs = set([astring])

    lang_dict = parse_langcode(astring)

    if not lang_dict:
        return list(langs)

    base, loc, enc, script = [lang_dict[key] for key in ("language",
                                      "territory", "encoding", "script")]

    if not base:
        return list(langs)

    if not enc:
        enc = "UTF-8"

    langs.add(base)
    langs.add("%s.%s" % (base, enc))

    if loc:
        langs.add("%s_%s" % (base, loc))
        langs.add("%s_%s.%s" %(base, loc, enc))
    if script:
        langs.add("%s@%s" % (base, script))
        langs.add("%s.%s@%s" % (base, enc, script))

    if loc and script:
        langs.add("%s_%s@%s" % (base, loc, script))

    return list(langs)

def is_supported_locale(locale):
    """
    Function that tells if the given locale is supported by the Anaconda or
    not. We consider locales supported by the langtable as supported by the
    Anaconda.

    :param locale: locale to test
    :type locale: str
    :return: whether the given locale is supported or not
    :rtype: bool
    :raise InvalidLocaleSpec: if an invalid locale is given (see LANGCODE_RE)

    """

    en_name = get_english_name(locale)
    return bool(en_name)

def setup_locale(locale, lang):
    """
    Procedure setting the system to use the given locale and store it in to the
    ksdata.lang object. DOES NOT PERFORM ANY CHECKS OF THE GIVEN LOCALE.

    :param locale: locale to setup
    :type locale: str
    :param lang: ksdata.lang object
    :return: None
    :rtype: None

    """

    lang.lang = locale
    os.environ["LANG"] = locale

def get_english_name(locale):
    """
    Function returning english name for the given locale.

    :param locale: locale to return english name for
    :type locale: str
    :return: english name for the locale or empty string if unknown
    :rtype: st
    :raise InvalidLocaleSpec: if an invalid locale is given (see LANGCODE_RE)

    """

    parts = parse_langcode(locale)
    if "language" not in parts:
        raise InvalidLocaleSpec("'%s' is not a valid locale" % locale)

    name = langtable.language_name(languageId=parts["language"],
                                   territoryId=parts.get("territory", ""),
                                   scriptId=parts.get("script", ""),
                                   languageIdQuery="en")

    return _upcase_first_letter(name)

def get_native_name(locale):
    """
    Function returning native name for the given locale.

    :param locale: locale to return native name for
    :type locale: str
    :return: english name for the locale or empty string if unknown
    :rtype: st
    :raise InvalidLocaleSpec: if an invalid locale is given (see LANGCODE_RE)

    """

    parts = parse_langcode(locale)
    if "language" not in parts:
        raise InvalidLocaleSpec("'%s' is not a valid locale" % locale)

    name = langtable.language_name(languageId=parts["language"],
                                   territoryId=parts.get("territory", ""),
                                   scriptId=parts.get("script", ""),
                                   languageIdQuery=parts["language"],
                                   scriptIdQuery=parts.get("script", ""))

    return _upcase_first_letter(name)

def get_available_translations(domain=None, localedir=None):
    """
    Method that generates (i.e. returns a generator) available translations for
    the given domain and localedir.

    :type domain: str
    :type localedir: str
    :return: generator yielding available translations
    :rtype: generator yielding strings

    """

    domain = domain or gettext._current_domain
    localedir = localedir or gettext._default_localedir

    messagefiles = sorted(glob.glob(localedir + "/*/LC_MESSAGES/anaconda.mo"))
    trans_gen = (path.split(os.path.sep)[-3] for path in messagefiles)

    # usually there are no message files for en
    langs = {"en"}
    yield "en_US.UTF-8"

    for trans in trans_gen:
        parts = parse_langcode(trans)
        lang = parts.get("language", "")
        if lang and lang not in langs:
            langs.add(lang)
            locales = get_language_locales(lang)
            if not locales:
                continue

            # take the first locale (with highest rank) for the language
            yield locales[0]

def get_language_locales(lang):
    """
    Function returning all locales available for the given language.

    :param lang: language to get available locales for
    :type lang: str
    :return: a list of available locales
    :rtype: list of strings
    :raise InvalidLocaleSpec: if an invalid locale is given (see LANGCODE_RE)

    """

    parts = parse_langcode(lang)
    if "language" not in parts:
        raise InvalidLocaleSpec("'%s' is not a valid language" % lang)

    return langtable.list_locales(languageId=parts["language"],
                                  territoryId=parts.get("territory", ""),
                                  scriptId=parts.get("script", ""))

def get_territory_locales(territory):
    """
    Function returning list of locales for the given territory. The list is
    sorted from the most probable locale to the least probable one (based on
    langtable's ranking.

    :param territory: territory to return locales for
    :type territory: str
    :return: list of locales
    :rtype: list of strings

    """

    return langtable.list_locales(territoryId=territory)

def get_locale_keyboards(locale):
    """
    Function returning preferred keyboard layouts for the given locale.

    :param locale: locale string (see LANGCODE_RE)
    :type locale: str
    :return: list of preferred keyboard layouts
    :rtype: list of strings
    :raise InvalidLocaleSpec: if an invalid locale is given (see LANGCODE_RE)

    """

    parts = parse_langcode(locale)
    if "language" not in parts:
        raise InvalidLocaleSpec("'%s' is not a valid locale" % locale)

    return langtable.list_keyboards(languageId=parts["language"],
                                    territoryId=parts.get("territory", ""),
                                    scriptId=parts.get("script", ""))

def get_locale_timezones(locale):
    """
    Function returning preferred timezones for the given locale.

    :param locale: locale string (see LANGCODE_RE)
    :type locale: str
    :return: list of preferred timezones
    :rtype: list of strings
    :raise InvalidLocaleSpec: if an invalid locale is given (see LANGCODE_RE)

    """

    parts = parse_langcode(locale)
    if "language" not in parts:
        raise InvalidLocaleSpec("'%s' is not a valid locale" % locale)

    return langtable.list_timezones(languageId=parts["language"],
                                    territoryId=parts.get("territory", ""),
                                    scriptId=parts.get("script", ""))

def get_locale_territory(locale):
    """
    Function returning locale's territory.

    :param locale: locale string (see LANGCODE_RE)
    :type locale: str
    :return: territory or None
    :rtype: str or None
    :raise InvalidLocaleSpec: if an invalid locale is given (see LANGCODE_RE)

    """

    parts = parse_langcode(locale)
    if "language" not in parts:
        raise InvalidLocaleSpec("'%s' is not a valid locale" % locale)

    return parts.get("territory", None)

def write_language_configuration(lang, root):
    """
    Write language configuration to the $root/etc/locale.conf file.

    :param lang: ksdata.lang object
    :param root: path to the root of the installed system

    """

    try:
        fpath = os.path.normpath(root + LOCALE_CONF_FILE_PATH)
        with open(fpath, "w") as fobj:
            fobj.write('LANG="%s"\n' % lang.lang)
    except IOError as ioerr:
        msg = "Cannot write language configuration file: %s" % ioerr.strerror
        raise LocalizationConfigError(msg)

def load_firmware_language(lang):
    """
    Procedure that loads firmware language information (if any). It stores the
    information in the given ksdata.lang object and sets the $LANG environment
    variable.

    :param lang: ksdata.lang object
    :return: None
    :rtype: None

    """

    if lang.lang and lang.seen:
        # set in kickstart, do not override
        return

    try:
        n = "/sys/firmware/efi/efivars/PlatformLang-8be4df61-93ca-11d2-aa0d-00e098032b8c"
        d = open(n, 'r', 0).read()
    except IOError:
        return

    # the contents of the file are:
    # 4-bytes of attribute data that we don't care about
    # NUL terminated ASCII string like 'en-US'.
    if len(d) < 10:
        log.debug("PlatformLang was too short")
        return
    d = d[4:]
    if d[2] != '-':
        log.debug("PlatformLang was malformed")
        return

    # they use - and we use _, so fix it...
    d = d[:2] + '_' + d[3:-1]

    # UEFI 2.3.1 Errata C specifies 2 aliases in common use that
    # aren't part of RFC 4646, but are allowed in PlatformLang.
    # Because why make anything simple?
    if d.startswith('zh_chs'):
        d = 'zh_Hans'
    elif d.startswith('zh_cht'):
        d = 'zh_Hant'
    d += '.UTF-8'

    if not is_supported_locale(d):
        log.debug("PlatformLang was '%s', which is unsupported.", d)
        return

    locales = get_language_locales(d)
    if not locales:
        log.debug("No locales found for the PlatformLang '%s'.", d)
        return

    log.debug("Using UEFI PlatformLang '%s' ('%s') as our language.", d, locales[0])
    setup_locale(locales[0], lang)
