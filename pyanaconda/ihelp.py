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
"""
Anaconda built-in help module
"""
import os
import json

from pyanaconda.flags import flags
from pyanaconda.localization import find_best_locale_match
from pyanaconda.core.constants import DEFAULT_LANG
from pyanaconda.core.util import startProgram

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

# Help structure
#
# There is a docbook file called anaconda-help.xml with sections that have anchors,
# we expect yelp to be able to show the sections when we specify them when launching
# yelp via CLI.
#
# Anaconda screens that should have documentation each have a unique help id,
# which is converted into an anchor via a dictionary loaded from the anaconda-help-anchors.json file.
#
# There are also placeholders (docbook & plain text) that are shown:
# - where screen has no help id set (None)
# - no anchor is found for a help id
# - anaconda-help.xml is missing
#
# Help in TUI
#
# The help system is disabled in TUI as we don't have any plain text help content
# suitable for TUI at the moment.

MAIN_HELP_FILE = "anaconda-help.xml"
HELP_ID_MAPPING_FILE_NAME = "anaconda-help-anchors.json"

yelp_process = None

help_id_mapping = None

def _load_anchors_file(instclass):
    """Parse the json file containing the help id -> document anchor mapping.

    The mappings file is located in the root of the current help folder,
    for example for rhel it is expected to be in:
    /usr/share/anaconda/help/rhel/anaconda-help-anchors.json

    :param instclass: currently active install class instance
    """
    mapping = {}
    anchors_file_path = os.path.join(instclass.help_folder, HELP_ID_MAPPING_FILE_NAME)
    if os.path.exists(anchors_file_path):
        try:
            with open(anchors_file_path, "rt") as f:
                mapping = json.load(f)
        except (IOError, json.JSONDecodeError):
            log.exception("failed to parse the help id -> anchors mapping file %s", anchors_file_path)
    else:
        log.error("help id -> anchors mapping file not found in %s", anchors_file_path)

    # assign help id -> anchors mapping from the anchors file (or an empty dict if the file could not be
    # loaded) to the module level property
    global help_id_mapping
    help_id_mapping = mapping

def _get_best_help_file(help_folder, help_file):
    """Return the path to the best help file for current language and help content.

    :param str help_folder: a path to folder where we should look for the help files
    :param str help_file: name of the requested help file
    :return: path to the best help file or ``None`` is no match is found
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

def get_placeholder_path(instclass, plain_text=False):
    """Get path to appropriate placeholder for given install class.

    :param instclass: currently active install class instance
    :param str plain_text: point to plain text version of the placeholder
    :returns: path to placeholder or None if no placeholder is found
    :rtype: str or None
    """
    if plain_text:
        placeholder = installclass.help_placeholder_plain_text
    else:
        placeholder = instclass.help_placeholder
    placeholder_path = _get_best_help_file(instclass.help_folder, placeholder)
    if placeholder_path:
        return placeholder_path
    else:
        log.error("placeholder %s not found in %s", instclass.help_placeholder, instclass.help_folder)
        return None

def start_yelp(help_id, instclass):
    """Start a new yelp process and make sure to kill any existing ones.

    We will try to resolve the help id to appropriate content and show it to the user.

    :param str help_id: help id to be shown to the user
    :param instclass: currently active install class instance
    """
    kill_yelp()

    log.info("help requested for help id %s", help_id)

    # first make sure the help id -> mapping has been loaded
    if help_id_mapping is None:
        _load_anchors_file(instclass)

    # we initially set the yelp string to the placeholder path, just in case
    yelp_string = get_placeholder_path(instclass)

    # resolve the help id to docbook document anchor (if there is one for the help id)
    help_anchor = help_id_mapping.get(help_id, None)
    if help_anchor is None:
        log.error("no anchor found for help id %s, starting yelp with placeholder", help_id)
    else:
        log.info("help id %s was resolved to anchor %s", help_id, help_anchor)
        # check if main help file is available
        main_help_file_path = _get_best_help_file(instclass.help_folder, MAIN_HELP_FILE)
        if main_help_file_path:
            log.info("starting yelp with anchor %s for help id %s", help_anchor, help_id)
            # construct string for yelp with anchor based document section access
            yelp_string = "ghelp:{path_to_file}?{anchor}".format(path_to_file=main_help_file_path, anchor=help_anchor)
        else:
            # main help file not found, switch to placeholder
            log.error("main help file %s not found in %s, starting yelp with placeholder", MAIN_HELP_FILE, instclass.help_folder)

    if yelp_string:
        log.debug("starting yelp with args: %s", yelp_string)
        global yelp_process
        yelp_process = startProgram(["yelp", yelp_string], reset_lang=False)
    else:
        log.error("no content found for yelp to display, not starting yelp")

def kill_yelp():
    """Try to kill any existing yelp processes"""

    global yelp_process
    if not yelp_process:
        return False

    log.debug("killing yelp")
    yelp_process.kill()
    yelp_process.wait()
    yelp_process = None
    return True
