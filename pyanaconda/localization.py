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

import gettext
import os
import re
import langtable
import locale as locale_mod
import glob
from collections import namedtuple
import sys
import io

from pyanaconda.core import constants
from pyanaconda.core.util import upcase_first_letter, setenv, execWithRedirect

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

LOCALE_CONF_FILE_PATH = "/etc/locale.conf"

SCRIPTS_SUPPORTED_BY_CONSOLE = {'Latn', 'Cyrl', 'Grek'}

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

def locale_supported_in_console(locale):
    """
    Function that tells if the given locale can be displayed by the Linux console.

    The Linux console can display Latin, Cyrillic and Greek characters reliably,
    but others such as Japanese, can't be correctly installed.

    :param str locale: locale to test
    :return: whether the given locale is supported by the console or not
    :rtype: bool
    :raise InvalidLocaleSpec: if an invalid locale is given (see LANGCODE_RE)

    """

    locale_scripts = get_locale_scripts(locale)
    return set(locale_scripts).issubset(SCRIPTS_SUPPORTED_BY_CONSOLE)

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

    SCORE_MAP = {"language" : 1000,
                 "territory":  100,
                 "script"   :   10,
                 "encoding" :    1}

    def get_match_score(locale, langcode):
        score = 0

        locale_parts = parse_langcode(locale)
        langcode_parts = parse_langcode(langcode)
        if not locale_parts or not langcode_parts:
            return score

        for part, part_score in SCORE_MAP.items():
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
    if sorted_langcodes and sorted_langcodes[0][1] > SCORE_MAP["territory"]:
        return sorted_langcodes[0][0]
    else:
        return None

def setup_locale(locale, localization_proxy=None, text_mode=False):
    """
    Procedure setting the system to use the given locale and store it in to the
    localization module (if given). DOES NOT PERFORM ANY CHECKS OF THE GIVEN
    LOCALE.

    $LANG must be set by the caller in order to set the language used by gettext.
    Doing this in a thread-safe way is up to the caller.

    We also try to set a proper console font for the locale in text mode.
    If the font for the locale can't be displayed in the Linux console,
    we fall back to the English locale.

    This function returns the locale that was used in the setlocale call, which,
    depending on what the environment and interface is able to support, may be
    different from the locale requested.

    :param str locale: locale to setup
    :param localization_proxy: DBus proxy of the localization module or None
    :param bool text_mode: if the locale is being setup for text mode
    :return: the locale that was actually set
    :rtype: str

    """

    if localization_proxy:
        localization_proxy.SetLanguage(locale)

    # not all locales might be displayable in text mode
    if text_mode:
        # check if the script corresponding to the locale/language
        # can be displayed by the Linux console
        # * all scripts for the given locale/language need to be
        #   supported by the linux console
        # * otherwise users might get a screen full of white rectangles
        #   (also known as "tofu") in text mode
        # then we also need to check if we have information about what
        # font to use for correctly displaying the given language/locale

        script_supported = locale_supported_in_console(locale)
        log.debug("scripts found for locale %s: %s", locale, get_locale_scripts(locale))

        console_fonts = get_locale_console_fonts(locale)
        log.debug("console fonts found for locale %s: %s", locale, console_fonts)

        font_set = False
        if script_supported and console_fonts:
            # try to set console font
            for font in console_fonts:
                if set_console_font(font):
                    # console font set successfully, skip the rest
                    font_set = True
                    break

        if not font_set:
            log.warning("can't set console font for locale %s", locale)
            # report what exactly went wrong
            if not(script_supported):
                log.warning("script not supported by console for locale %s", locale)
            if not(console_fonts):  # no fonts known for locale
                log.warning("no console font found for locale %s", locale)
            if script_supported and console_fonts:
                log.warning("none of the suggested fonts can be set for locale %s", locale)
            log.warning("falling back to the English locale")
            locale = constants.DEFAULT_LANG
            os.environ["LANG"] = locale  # pylint: disable=environment-modify

    # set the locale to the value we have selected
    # Since glibc does not install all locales, an installable locale may not
    # actually be available right now. Give it a shot and fallback.
    log.debug("setting locale to: %s", locale)
    setenv("LANG", locale)

    try:
        locale_mod.setlocale(locale_mod.LC_ALL, locale)
    except locale_mod.Error as e:
        log.debug("setlocale failed: %s", e)
        locale = constants.DEFAULT_LANG
        setenv("LANG", locale)
        locale_mod.setlocale(locale_mod.LC_ALL, locale)

    # This part is pretty gross:
    # In python3, sys.stdout and friends are TextIOWrapper objects that translate
    # betwen str types (in python) and byte types (used to actually read from or
    # write to the console). These wrappers are configured at startup using the
    # locale at startup, which means that if anaconda starts with LANG=C or LANG
    # unset, sys.stdout.encoding will be "ascii". And if the language is then changed,
    # because anaconda read the kickstart or parsed the command line or whatever,
    # say, to Czech, text mode will crash because it's going to try to print non-ASCII
    # characters and sys.stdout doesn't know what to do with them. So, when changing
    # the locale, create new objects for the standard streams so they are created with
    # the new locale's encoding.

    # Replacing stdout is about as stable as it looks, and it seems to break when done
    # after the GUI is started. Only make the switch if the encoding actually changed.
    if locale_mod.getpreferredencoding() != sys.stdout.encoding:
        sys.stdin = io.TextIOWrapper(sys.stdin.detach())
        sys.stdout = io.TextIOWrapper(sys.stdout.detach())
        sys.stderr = io.TextIOWrapper(sys.stderr.detach())

    return locale

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
                                   territoryIdQuery=parts.get("territory", ""),
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

def get_locale_console_fonts(locale):
    """
    Function returning preferred console fonts for the given locale.

    :param str locale: locale string (see LANGCODE_RE)
    :return: list of preferred console fonts
    :rtype: list of strings
    :raise InvalidLocaleSpec: if an invalid locale is given (see LANGCODE_RE)

    """

    parts = parse_langcode(locale)
    if "language" not in parts:
        raise InvalidLocaleSpec("'%s' is not a valid locale" % locale)

    return langtable.list_consolefonts(languageId=parts["language"],
                                       territoryId=parts.get("territory", ""),
                                       scriptId=parts.get("script", ""))

def get_locale_scripts(locale):
    """
    Function returning preferred scripts (writing systems) for the given locale.

    :param locale: locale string (see LANGCODE_RE)
    :type locale: str
    :return: list of preferred scripts
    :rtype: list of strings
    :raise InvalidLocaleSpec: if an invalid locale is given (see LANGCODE_RE)

    """

    parts = parse_langcode(locale)
    if "language" not in parts:
        raise InvalidLocaleSpec("'%s' is not a valid locale" % locale)

    return langtable.list_scripts(languageId=parts["language"],
                                  territoryId=parts.get("territory", ""),
                                  scriptId=parts.get("script", ""))

def get_xlated_timezone(tz_spec_part):
    """
    Function returning translated name of a region, city or complete timezone
    name according to the current value of the $LANG variable.

    :param tz_spec_part: a region, city or complete timezone name
    :type tz_spec_part: str
    :return: translated name of the given region, city or timezone
    :rtype: str

    """

    locale = os.environ.get("LANG", constants.DEFAULT_LANG)
    parts = parse_langcode(locale)
    if "language" not in parts:
        raise InvalidLocaleSpec("'%s' is not a valid locale" % locale)

    xlated = langtable.timezone_name(tz_spec_part, languageIdQuery=parts["language"],
                                     territoryIdQuery=parts.get("territory", ""),
                                     scriptIdQuery=parts.get("script", ""))
    return xlated

def write_language_configuration(lang, root):
    """
    Write language configuration to the $root/etc/locale.conf file.

    :param lang: value for LANG locale variable
    :param root: path to the root of the installed system

    """

    try:
        fpath = os.path.normpath(root + LOCALE_CONF_FILE_PATH)
        with open(fpath, "w") as fobj:
            fobj.write('LANG="%s"\n' % lang)
    except IOError as ioerr:
        msg = "Cannot write language configuration file: %s" % ioerr.strerror
        raise LocalizationConfigError(msg)

def get_firmware_language(text_mode=False):
    """
    Procedure that returns the firmware language information (if any).

    :param boot text_mode: if the locale is being setup for text mode
    :return: the firmware language translated into a locale string, or None
    :rtype: str
    """

    try:
        n = "/sys/firmware/efi/efivars/PlatformLang-8be4df61-93ca-11d2-aa0d-00e098032b8c"
        d = open(n, 'r').read()
    except IOError:
        return None

    # the contents of the file are:
    # 4-bytes of attribute data that we don't care about
    # NUL terminated ASCII string like 'en-US'.
    if len(d) < 10:
        log.debug("PlatformLang was too short")
        return None
    d = d[4:]
    if d[2] != '-':
        log.debug("PlatformLang was malformed")
        return None

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
        return None

    locales = get_language_locales(d)
    if not locales:
        log.debug("No locales found for the PlatformLang '%s'.", d)
        return None

    log.debug("Using UEFI PlatformLang '%s' ('%s') as our language.", d, locales[0])
    return locales[0]

_DateFieldSpec = namedtuple("DateFieldSpec", ["format", "suffix"])

def resolve_date_format(year, month, day, fail_safe=True):
    """
    Puts the year, month and day objects in the right order according to the
    currently set locale and provides format specification for each of the
    fields.

    :param year: any object or value representing year
    :type year: any
    :param month: any object or value representing month
    :type month: any
    :param day: any object or value representing day
    :type day: any
    :param bool fail_safe: whether to fall back to default in case of invalid
                           format or raise exception instead
    :returns: a pair where the first field contains a tuple with the year, month
              and day objects/values put in the right order and where the second
              field contains a tuple with three :class:`_DateFieldSpec` objects
              specifying formats respectively to the first (year, month, day)
              field, e.g. ((year, month, day), (y_fmt, m_fmt, d_fmt))
    :rtype: tuple
    :raise ValueError: in case currently set locale has unsupported date
                       format and fail_safe is set to False

    """

    FAIL_SAFE_DEFAULT = "%Y-%m-%d"

    def order_terms_formats(fmt_str):
        # see date (1), 'O' (not '0') is a mystery, 'E' is Buddhist calendar, '(.*)'
        # is an arbitrary suffix
        field_spec_re = re.compile(r'([-_0OE^#]*)([yYmbBde])(.*)')

        # see date (1)
        fmt_str = fmt_str.replace("%F", "%Y-%m-%d")

        # e.g. "%d.%m.%Y" -> ['d.', 'm.', 'Y']
        fields = fmt_str.split("%")[1:]

        ordered_terms = []
        ordered_formats = []
        for field in fields:
            match = field_spec_re.match(field)
            if not match:
                # ignore fields we are not interested in (like %A for weekday name, etc.)
                continue

            prefix, item, suffix = match.groups()
            if item in ("d", "e"):
                # "e" is the same as "_d"
                ordered_terms.append(day)
            elif item in ("Y", "y"):
                # 4-digit year, 2-digit year
                ordered_terms.append(year)
            elif item in ("m", "b", "B"):
                # month number, short month name, long month name
                ordered_terms.append(month)

            # "%" + prefix + item gives a format for date/time formatting functions
            ordered_formats.append(_DateFieldSpec("%" + prefix + item, suffix.strip()))

        if len(ordered_terms) != 3 or len(ordered_formats) != 3:
            raise ValueError("Not all fields successfully identified in the format '%s'" % fmt_str)

        return (tuple(ordered_terms), tuple(ordered_formats))

    fmt_str = locale_mod.nl_langinfo(locale_mod.D_FMT)

    if not fmt_str or "%" not in fmt_str:
        if fail_safe:
            # use some sane default
            fmt_str = FAIL_SAFE_DEFAULT
        else:
            raise ValueError("Invalid date format string for current locale: '%s'" % fmt_str)

    try:
        return order_terms_formats(fmt_str)
    except ValueError:
        if not fail_safe:
            raise
        else:
            # if this call fails too, something is going terribly wrong and we
            # should be informed about it
            return order_terms_formats(FAIL_SAFE_DEFAULT)

def set_console_font(font):
    """
    Try to set console font to the given value.

    :param str font: console font name
    :returns: True on success, False on failure
    :rtype: Bool

    """
    log.debug("setting console font to %s", font)
    rc = execWithRedirect("setfont", [font])
    if rc == 0:
        log.debug("console font set successfully to %s", font)
        return True
    else:
        log.error("setting console font to %s failed", font)
        return False

def setup_locale_environment(locale=None, text_mode=False, prefer_environment=False):
    """
    Clean and configure the local environment variables.

    This function will attempt to determine the desired locale and configure
    the process environment (os.environ) in the least surprising way. If a
    locale argument is provided, it will be attempted first. After that, this
    function will attempt to use the language environment variables in a manner
    similar to gettext(3) (in order, $LANGUAGE, $LC_ALL, $LC_MESSAGES, $LANG),
    followed by the UEFI PlatformLang, followed by a default.

    When this function returns, $LANG will be set, and $LANGUAGE, $LC_ALL,
    and $LC_MESSAGES will not be set, because they get in the way when changing
    the language after startup.

    This function must be run before any threads are started. This function
    modifies the process environment, which is not thread-safe.

    :param str locale: locale to setup if provided
    :param bool text_mode: if the locale is being setup for text mode
    :param bool prefer_environment: whether the process environment, if available, overrides the locale parameter
    :return: None
    :rtype: None
    """

    # pylint: disable=environment-modify

    # Look for a locale in the environment. If the variable is setup but
    # empty it doesn't count, and some programs (KDE) actually do this.
    # If prefer_environment is set, the environment locale can override
    # the parameter passed in. This can be used, for example, by initial-setup,
    # to prefer the possibly-more-recent environment settings before falling back
    # to a locale set at install time and saved in the kickstart.
    if not locale or prefer_environment:
        for varname in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
            if varname in os.environ and os.environ[varname]:
                locale = os.environ[varname]
                break

    # Look for a locale in the firmware if there was nothing in the environment
    if not locale:
        locale = get_firmware_language(text_mode)

    # parse the locale using langtable
    if locale:
        env_langs = get_language_locales(locale)
        if env_langs:
            # the first langauge is the best match
            locale = env_langs[0]
        else:
            log.error("Invalid locale '%s' given on command line, kickstart or environment", locale)
            locale = None

    # If langtable returned no locales, or if nothing was configured, fall back to the default
    if not locale:
        locale = constants.DEFAULT_LANG

    # Save the locale in the environment
    os.environ["LANG"] = locale

    # Cleanup the rest of the environment variables
    for varname in ("LANGUAGE", "LC_ALL", "LC_MESSAGES"):
        if varname in os.environ:
            del os.environ[varname]
