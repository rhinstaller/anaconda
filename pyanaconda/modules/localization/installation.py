#
# Copyright (C) 2018 Red Hat, Inc.
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
import os
import shutil

from pyanaconda.modules.common.errors.installation import LanguageInstallationError, \
    KeyboardInstallationError
from pyanaconda.modules.common.task import Task
from pyanaconda.core.constants import DEFAULT_VC_FONT
from pyanaconda.modules.localization.localed import get_missing_keyboard_configuration
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.localization import get_locale_console_fonts

log = get_module_logger(__name__)

X_CONF_DIR = "/etc/X11/xorg.conf.d"
X_CONF_FILE_NAME = "00-keyboard.conf"
VC_CONF_FILE_PATH = "/etc/vconsole.conf"


class LanguageInstallationTask(Task):
    """Installation task for the language configuration."""

    LOCALE_CONF_FILE_PATH = "/etc/locale.conf"

    def __init__(self, sysroot, lang):
        """Create a new task,

        :param sysroot: a path to the root of the installed system
        :param lang: a value for LANG locale variable
        """
        super().__init__()
        self._sysroot = sysroot
        self._lang = lang

    @property
    def name(self):
        return "Configure language"

    def run(self):
        self._write_language_configuration(self._lang, self._sysroot)

    def _write_language_configuration(self, lang, root):
        """Write language configuration to the $root/etc/locale.conf file.

        :param lang: value for LANG locale variable
        :param root: path to the root of the installed system
        """
        try:
            fpath = os.path.normpath(root + self.LOCALE_CONF_FILE_PATH)

            with open(fpath, "w") as fobj:
                fobj.write('LANG="{}"\n'.format(lang))

        except IOError as ioerr:
            msg = "Cannot write language configuration file: {}".format(ioerr.strerror)
            raise LanguageInstallationError(msg) from ioerr


class KeyboardInstallationTask(Task):
    """Installation task for the keyboard configuration."""

    def __init__(self, sysroot, localed_wrapper, x_layouts, switch_options, vc_keymap):
        """Create a new task,

        :param localed_wrapper: instance of systemd-localed service wrapper
        :type localed_wrapper: LocaledWrapper
        :param sysroot: a path to the root of the installed system
        :type sysroot: str
        :param x_layouts: list of x layout specifications
        :type x_layouts: list(str)
        :param switch_options: list of options for layout switching
        :type switch_options: list(str)
        :param vc_keymap: virtual console keyboard mapping name
        :type vc_keymap: str
        """
        super().__init__()
        self._sysroot = sysroot
        self._localed_wrapper = localed_wrapper
        self._x_layouts = x_layouts
        self._switch_options = switch_options
        self._vc_keymap = vc_keymap

    @property
    def name(self):
        return "Configure keyboard"

    def run(self):
        x_layouts = self._x_layouts
        vc_keymap = self._vc_keymap

        if not self._x_layouts or not self._vc_keymap:
            x_layouts, vc_keymap = get_missing_keyboard_configuration(
                self._localed_wrapper,
                self._x_layouts,
                self._vc_keymap
            )

        if x_layouts:
            write_x_configuration(
                self._localed_wrapper,
                x_layouts,
                self._switch_options,
                X_CONF_DIR,
                self._sysroot
            )
        if vc_keymap:
            write_vc_configuration(
                vc_keymap,
                self._sysroot
            )


def write_x_configuration(localed_wrapper, x_layouts, switch_options, x_conf_dir_path, root):
    """Write X keyboard layout configuration to the configuration files.

    :param localed_wrapper: instance of systemd-localed service wrapper
    :type localed_wrapper: LocaledWrapper
    :param x_layouts: list of X layout specifications
    :type x_layouts: list(str)
    :param switch_options: list of options for layout switching
    :type switch_options: list(str)
    :param x_conf_dir_path: path to directory holding X Layouts configuration
    :type x_conf_dir_path: str
    :param root: root path of the configured system
    :type root: str
    """

    errors = []
    try:
        if not os.path.isdir(x_conf_dir_path):
            os.makedirs(x_conf_dir_path)
    except OSError:
        # Non-fatal, systemd-localed may create the directory on its own.
        log.debug("Cannot create X Layouts configuration directory %s", x_conf_dir_path)

    if root != "/":
        # Writing to a different root, we need to save these values, so that
        # we can restore them when we have the file written out.
        saved_layouts_variants = localed_wrapper.layouts_variants
        saved_options = localed_wrapper.options

    # Set systemd-localed's layouts, variants and switch options, which
    # also generates a new conf file.
    localed_wrapper.set_layouts(x_layouts, switch_options)

    if root != "/":
        # Make sure the target directory exists under the given root.
        rooted_xconf_dir = os.path.normpath(root + "/" + x_conf_dir_path)
        try:
            if not os.path.isdir(rooted_xconf_dir):
                os.makedirs(rooted_xconf_dir)
        except OSError:
            errors.append("Cannot create directory {}".format(rooted_xconf_dir))

        # Copy the file to the chroot.
        xconf_file_path = os.path.normpath(x_conf_dir_path + "/" + X_CONF_FILE_NAME)
        rooted_xconf_file_path = os.path.normpath(root + "/" + xconf_file_path)
        try:
            shutil.copy2(xconf_file_path, rooted_xconf_file_path)
        except IOError as ioerr:
            log.error("Cannot copy X layouts configuration file %s to target system: %s.",
                      xconf_file_path, ioerr.strerror)

        # Restore the original values.
        localed_wrapper.set_layouts(saved_layouts_variants, saved_options)

    if errors:
        raise KeyboardInstallationError("\n".join(errors))


def write_vc_configuration(vc_keymap, root):
    """Write virtual console keyboard mapping configuration.

    :param vc_keymap: virtual console keyboard mapping name
    :type vc_keymap: str
    :param root: root path of the configured system
    :type root: str
    """
    try:
        fpath = os.path.normpath(root + VC_CONF_FILE_PATH)

        # "eurlatgr" may not be the best choice for all the languages,
        # for example, Russian, Urdu, Serbian, Sindhi and a few more.
        # refer: https://bugzilla.redhat.com/show_bug.cgi?id=1919486
        # assuming that LANG is set by now.
        vc_fonts = get_locale_console_fonts(os.environ["LANG"])
        vc_font = vc_fonts[0] if vc_fonts else DEFAULT_VC_FONT

        with open(fpath, "w") as fobj:
            fobj.write('KEYMAP="%s"\n' % vc_keymap)

            # systemd now defaults to a font that cannot display non-ascii
            # characters, so we have to tell it to use a better one
            fobj.write('FONT="%s"\n' % vc_font)

    except IOError as ioerr:
        msg = "Cannot write vconsole configuration file: {}".format(ioerr.strerror)
        raise KeyboardInstallationError(msg) from ioerr
