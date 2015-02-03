#
# Copyright (C) 2014  Red Hat, Inc.
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
# Red Hat Author(s): Martin Kolman <mkolman@redhat.com>
#
"""
Anaconda built-in help module
"""
import os

from pyanaconda.flags import flags
from pyanaconda.localization import find_best_locale_match
from pyanaconda.constants import DEFAULT_LANG
from pyanaconda.iutil import startProgram

import logging
log = logging.getLogger("anaconda")

yelp_process = None

def _get_best_help_file(help_folder, help_file):
    """Return the path to the best help file for the current language and available
    help content

    :param str help_folder: a path to folder where we should look for the help files
    :param str help_file: name of the requested help file
    :return: path to the best help file or None is no match is found
    :rtype: str or NoneType

    """
    current_lang = os.environ["LANG"]
    # list all available languages for the Anaconda help
    # * content is stored in folders named after the given language code
    #   (en-US, cs-CZ, jp-JP, etc.)
    # * we check if the given folder contains the currently needed help file
    #   and only consider it fit to use if it does have the file
    if not os.path.exists(help_folder):
        log.warning("help folder %s for help file %s does not exist", help_folder, help_file)
        return None

    help_langs = [l for l in os.listdir(help_folder) if os.path.isfile(os.path.join(help_folder, l, help_file))]

    best_lang = find_best_locale_match(current_lang, help_langs)
    if not best_lang and current_lang != DEFAULT_LANG:
        # nothing found for current language, fallback to the default language,
        # if available & different from current language
        log.warning("help file %s not found in lang %s, falling back to default lang (%s)",
                    help_file, current_lang, DEFAULT_LANG)
        best_lang = find_best_locale_match(DEFAULT_LANG, help_langs)

    # did we get something usable ?
    if best_lang:
        # we already checked that the full path exists when enumerating suitable
        # help content above, so we can just return the part here without
        # checking it again
        return os.path.join(help_folder, best_lang, help_file)
    else:
        log.warning("no help content found for file %s", help_file)
        return None

def get_help_path(help_file, instclass):
    """Return the full path for the given help file name,
    if the help file path does not exist a fallback path is returned.
    There are actually two possible fallback paths that might be returned:
    * first we try to return path to the main page of the installation guide
      (if it exists)
    * if we can't find the main page of the installation page, path to a
      "no help found" placeholder bundled with Anaconda is returned

    Regarding help l10n, we try to respect the current locale as defined by the
    "LANG" environmental variable, but fallback to English if localized content
    is not available.

    :param help_file: help file name
    :type help_file: str or NoneType
    :param instclass: current install class instance
    :return str: full path to the help file requested or to a placeholder
    """
    # help l10n handling

    if help_file:
        help_path = _get_best_help_file(instclass.help_folder, help_file)
        if help_path is not None:
            return help_path

    # the screen did not have a helpFile defined or the defined help file
    # does not exist, so next try to check if we can find the main page
    # of the installation guide and use it instead
    help_path = _get_best_help_file(instclass.help_folder, instclass.help_main_page)
    if help_path is not None:
        return help_path

    # looks like the installation guide is not available, so just return
    # a placeholder page, which should be always present
    if flags.livecdInstall:
        return _get_best_help_file(instclass.help_folder, instclass.help_placeholder_with_links)
    else:
        return _get_best_help_file(instclass.help_folder, instclass.help_placeholder)

def start_yelp(help_path):
    """Start a new yelp process and make sure to kill any existing ones

    :param help_path: path to the help file yelp should load
    :type help_path: str or NoneType
    """

    kill_yelp()
    log.debug("starting yelp")
    global yelp_process
    # under some extreme circumstances (placeholders missing)
    # the help path can be None and we need to prevent Popen
    # receiving None as an argument instead of a string
    yelp_process = startProgram(["yelp", help_path or ""], reset_lang=False)

def kill_yelp():
    """Try to kill any existing yelp processes"""

    global yelp_process
    if not yelp_process:
        return False

    log.debug("killing yelp")
    yelp_process.kill()
    yelp_process = None
    return True

