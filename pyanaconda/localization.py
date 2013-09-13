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

from pyanaconda.iutil import upcase_first_letter

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

    if not langcode:
        return None

    match = LANGCODE_RE.match(langcode)
    if match:
        return match.groupdict()
    else:
        return None

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

def langcode_matches_locale(langcode, locale):
    """
    Function that tells if the given langcode matches the given locale. I.e. if
    all parts of appearing in the langcode (language, territory, script and
    encoding) are the same as the matching parts of the locale.

    :param langcode: a langcode (e.g. en, en_US, en_US@latin, etc.)
    :type langcode: str
    :param locale: a valid locale (e.g. en_US.UTF-8 or sr_RS.UTF-8@latin, etc.)
    :type locale: str
    :return: whether the given langcode matches the given locale or not
    :rtype: bool

    """

    langcode_parts = parse_langcode(langcode)
    locale_parts = parse_langcode(locale)

    if not langcode_parts or not locale_parts:
        # to match, both need to be valid langcodes (need to have at least
        # language specified)
        return False

    # Check parts one after another. If some part appears in the langcode and
    # doesn't match the one from the locale (or is missing in the locale),
    # return False, otherwise they match
    for part in ("language", "territory", "script", "encoding"):
        if langcode_parts[part] and langcode_parts[part] != locale_parts.get(part):
            return False

    return True

def find_best_locale_match(locale, langcodes):
    """
    Find the best match for the locale in a list of langcodes. This is useful
    when e.g. pt_BR is a locale and there are possibilities to choose an item
    (e.g. rnote) for a list containing both pt and pt_BR or even also pt_PT.

    :param locale: a valid locale (e.g. en_US.UTF-8 or sr_RS.UTF-8@latin, etc.)
    :type locale: str
    :param langcodes: a list or generator of langcodes (e.g. en, en_US, en_US@latin, etc.)
    :type langcodes: list(str) or generator(str)
    :return: the best matching langcode from the list of None if none matches
    :rtype: str or None

    """

    score_map = { "language" : 1000,
                  "territory":  100,
                  "script"   :   10,
                  "encoding" :    1 }

    def get_match_score(locale, langcode):
        score = 0

        locale_parts = parse_langcode(locale)
        langcode_parts = parse_langcode(langcode)
        if not locale_parts or not langcode_parts:
            return score

        for part, part_score in score_map.iteritems():
            if locale_parts[part] and langcode_parts[part]:
                if locale_parts[part] == langcode_parts[part]:
                    # match
                    score += part_score
                else:
                    # not match
                    score -= part_score
            elif langcode_parts[part] and not locale_parts[part]:
                # langcode has something the locale doesn't have
                score -= part_score

        return score

    scores = []

    # get score for each langcode
    for langcode in langcodes:
        scores.append((langcode, get_match_score(locale, langcode)))

    # find the best one
    sorted_langcodes = sorted(scores, key=lambda item_score: item_score[1], reverse=True)

    # matches matching only script or encoding or both are not useful
    if sorted_langcodes and sorted_langcodes[0][1] > score_map["territory"]:
        return sorted_langcodes[0][0]
    else:
        return None

def setup_locale(locale, lang=None):
    """
    Procedure setting the system to use the given locale and store it in to the
    ksdata.lang object (if given). DOES NOT PERFORM ANY CHECKS OF THE GIVEN
    LOCALE.

    :param locale: locale to setup
    :type locale: str
    :param lang: ksdata.lang object or None
    :return: None
    :rtype: None

    """

    if lang:
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

    return upcase_first_letter(name)

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

    return upcase_first_letter(name)

def get_available_translations(localedir=None):
    """
    Method that generates (i.e. returns a generator) available translations for
    the installer in the given localedir.

    :type localedir: str
    :return: generator yielding available translations (languages)
    :rtype: generator yielding strings

    """

    localedir = localedir or gettext._default_localedir

    # usually there are no message files for en
    messagefiles = sorted(glob.glob(localedir + "/*/LC_MESSAGES/anaconda.mo") +
                          ["blob/en/blob/blob"])
    trans_gen = (path.split(os.path.sep)[-3] for path in messagefiles)

    langs = set()

    for trans in trans_gen:
        parts = parse_langcode(trans)
        lang = parts.get("language", "")
        if lang and lang not in langs:
            langs.add(lang)
            # check if there are any locales for the language
            locales = get_language_locales(lang)
            if not locales:
                continue

            yield lang

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
