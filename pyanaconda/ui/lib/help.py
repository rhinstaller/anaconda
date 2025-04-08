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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
"""
Anaconda built-in help module
"""
import functools
import os
import json
from collections import namedtuple

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import DEFAULT_LANG, DisplayModes
from pyanaconda.core.util import startProgram, join_paths
from pyanaconda.localization import find_best_locale_match

log = get_module_logger(__name__)

__all__ = [
    "show_graphical_help_for_screen",
    "get_help_path_for_screen",
    "localize_help_file",
    "show_graphical_help",
]

# Arguments of the built-in help for one screen:
#
#   path    An absolute path to the localized help file.
#   file    An relative path to the help file.
#   anchor  A name of the anchor in the help file.
#
HelpArguments = namedtuple("HelpArguments", ["path", "file", "anchor"])

# An identifier of the default help content.
DEFAULT_HELP_ID = "_default_"

# The running yelp process.
yelp_process = None


def show_graphical_help_for_screen(screen_id):
    """Show a help file of the specified screen in the GUI display mode.

    :param str screen_id: an identifier of a ui screen
    """
    log.info("Requested a graphical help for the '%s' screen.", screen_id)
    help_args = _get_help_args_for_screen(DisplayModes.GUI, screen_id)

    if not help_args:
        log.debug("There is no help for the '%s' screen.", screen_id)
        return

    show_graphical_help(help_args.path, help_args.anchor)


def get_help_path_for_screen(screen_id, display_mode=DisplayModes.TUI):
    """Return a path to the help file for the specified screen.

    :param str screen_id: an identifier of a ui screen
    :param DisplayModes display_mode: a type of the display mode
    :return str: an absolute path to the help file or None
    """
    log.info("Requested a help path for the '%s' screen.", screen_id)
    help_args = _get_help_args_for_screen(display_mode, screen_id)

    if not help_args:
        log.debug("There is no help for the '%s' screen.", screen_id)
        return None

    return help_args.path


def _get_help_args_for_screen(display_mode, screen_id):
    """Return help arguments for the specified screen.

    Use the default help if there is no help for the screen.
    If there is also no default help, return None.

    :param str screen_id: an identifier of a ui screen
    :param DisplayModes display_mode: a type of the display mode
    :return HelpArguments: help arguments for the screen or None
    """
    help_mapping = _get_help_mapping(display_mode)

    for help_id in (screen_id, DEFAULT_HELP_ID):
        help_args = _get_help_args(help_mapping, help_id)

        if help_args.path:
            return help_args

        log.debug("There is no help for the '%s' help id.", help_id)

    return None


@functools.cache
def _get_help_mapping(display_mode):
    """Parse the json file containing the help mapping.

    The mappings files are located in the root of the help directory.
    For example for RHEL, they are expected to be at:

        /usr/share/anaconda/help/rhel/anaconda-gui.json
        /usr/share/anaconda/help/rhel/anaconda-tui.json

    :param DisplayModes display_mode: a type of the display mode
    :return dict: a help mapping dictionary
    """
    help_directory = conf.ui.help_directory

    name = "anaconda-{}.json".format(display_mode.value.lower())
    path = join_paths(help_directory, name)

    if not os.path.exists(path):
        log.error("The help mapping file is not found at %s.", path)
        return {}

    mapping = {}

    try:
        with open(path, "rt") as f:
            mapping = json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        log.error("Failed to parse the help mapping file at %s: %s", path, str(e))

    return mapping


def _get_help_args(help_mapping, help_id):
    """Return a help arguments for the specified help id.

    :param dict help_mapping: a help mapping dictionary
    :param str help_id: an identifier of a help content
    :return HelpArguments: arguments of the help content
    """
    item = help_mapping.get(help_id, {})
    file = item.get("file") or ""
    anchor = item.get("anchor") or ""
    path = localize_help_file(file) or ""

    return HelpArguments(
        path=path,
        file=file,
        anchor=anchor,
    )


def localize_help_file(help_file, help_directory=None, current_locale=None):
    """Return an absolute path to the localized help file.

    Get the path to a localized help file for specified language.

    List all available languages for the Anaconda help. Content is stored in
    directories named after the given language code (en-US, cs-CZ, jp-JP, etc.).
    We check if the given folder contains the currently needed help file and
    only consider it fit to use if it does have the file

    :param str help_file: a relative path to the requested help file
    :param str help_directory: a path to directory with help files or None
    :param str current_locale: a valid locale (e.g. en_US.UTF-8) or None
    :return str: a path to the localized file or None
    """
    # Collect languages and files that provide the help content.
    if help_directory is None:
        help_directory = conf.ui.help_directory

    available_files = _collect_help_files(help_directory, help_file)

    # Find the best help file for the current locale.
    if current_locale is None:
        current_locale = os.environ.get("LANG", "")

    return _find_best_help_file(current_locale, available_files)


def _collect_help_files(help_directory, help_file):
    """Collect available help files.

    :param str help_directory: a path to directory with help files or None
    :param str help_file: a relative path to the requested help file
    :return dict: a dictionary of langcodes and absolute paths to the help files
    """
    if not help_file:
        return {}

    if not help_directory or not os.path.exists(help_directory):
        log.debug("The %s help directory does not exist.", help_directory)
        return {}

    files = {}

    for lang in os.listdir(help_directory):
        # Does the help file exist for this language?
        path = join_paths(help_directory, lang, help_file)
        if not os.path.isfile(path):
            continue

        # Create a valid langcode. For example, use en_US instead of en-US.
        code = lang.replace('-', '_')
        files[code] = path

    return files


def _find_best_help_file(current_locale, available_files):
    """Find the best help file for the specified locale.

    :param str current_locale: a valid locale (e.g. en_US.UTF-8)
    :param dict available_files: a dictionary of langcodes and help paths
    :return str: a path to the best help file or None
    """
    for locale in (current_locale, DEFAULT_LANG):
        best_lang = find_best_locale_match(locale, available_files.keys())
        best_path = available_files.get(best_lang, None)

        if best_path:
            return best_path

    return None


def show_graphical_help(help_path, help_anchor=None):
    """Start a new yelp process and make sure to kill any existing ones.

    :param str help_path: a path to the help file yelp should load
    :param str help_anchor: a name of the anchor in the help file
    """
    global yelp_process

    # Kill the existing process.
    if yelp_process:
        yelp_process.kill()
        yelp_process.wait()
        yelp_process = None

    # Quit if there is nothing to show.
    if not help_path:
        log.error("No help file to show.")
        return

    # Start yelp and show the specified help file at the given anchor.
    args = []

    if help_anchor:
        args.append("ghelp:{}?{}".format(help_path, help_anchor))
    else:
        args.append(help_path)

    yelp_process = startProgram(["yelp", *args], reset_lang=False)
