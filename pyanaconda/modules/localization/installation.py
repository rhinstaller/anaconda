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
from pyanaconda.core.constants import DEFAULT_VC_FONT, DEFAULT_KEYBOARD
from pyanaconda.keyboard import LocaledWrapper, InvalidLayoutVariantSpec
from pyanaconda.anaconda_loggers import get_module_logger

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
            raise LanguageInstallationError(msg)


class KeyboardInstallationTask(Task):
    """Installation task for the keyboard configuration."""

    def __init__(self, sysroot, x_layouts, switch_options, vc_keymap):
        """Create a new task,

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
        self._x_layouts = x_layouts
        self._switch_options = switch_options
        self._vc_keymap = vc_keymap

    @property
    def name(self):
        return "Configure keyboard"

    def run(self):
        if self._x_layouts:
            write_x_configuration(
                self._x_layouts,
                self._switch_options,
                self._sysroot
            )
        if self._vc_keymap:
            write_vc_configuration(
                self._vc_keymap,
                self._sysroot
            )


def write_x_configuration(x_layouts, switch_options, root):
    """Write X keyboard layout configuration to the configuration files.

    :param x_layouts: list of x layout specifications
    :type x_layouts: list(str)
    :param switch_options: list of options for layout switching
    :type switch_options: list(str)
    :param root: root path of the configured system
    :type root: str
    """

    localed_wrapper = LocaledWrapper()
    xconf_file_path = os.path.normpath(X_CONF_DIR + "/" + X_CONF_FILE_NAME)
    errors = []

    try:
        if not os.path.isdir(X_CONF_DIR):
            os.makedirs(X_CONF_DIR)
    except OSError:
        errors.append("Cannot create directory {}".format(X_CONF_DIR))

    if root != "/":
        # writing to a different root, we need to save these values, so that
        # we can restore them when we have the file written out
        layouts_variants = localed_wrapper.layouts_variants
        options = localed_wrapper.options

        # set systemd-localed's layouts, variants and switch options, which
        # also generates a new conf file
        localed_wrapper.set_layouts(x_layouts, switch_options)

        # make sure the right directory exists under the given root
        rooted_xconf_dir = os.path.normpath(root + "/" + X_CONF_DIR)
        try:
            if not os.path.isdir(rooted_xconf_dir):
                os.makedirs(rooted_xconf_dir)
        except OSError:
            errors.append("Cannot create directory {}".format(rooted_xconf_dir))

        # copy the file to the chroot
        try:
            shutil.copy2(xconf_file_path, os.path.normpath(root + "/" + xconf_file_path))
        except IOError as ioerr:
            log.debug("Cannot copy X layouts configuration %s file to target system: %s.",
                      xconf_file_path, ioerr.strerror)

        # restore the original values
        localed_wrapper.set_layouts(layouts_variants, options)
    else:
        try:
            # just let systemd-localed write out the conf file
            localed_wrapper.set_layouts(x_layouts, switch_options)
        except InvalidLayoutVariantSpec as ilvs:
            # some weird value appeared as a requested X layout
            log.error("Failed to write out config file: %s, using default %s",
                      ilvs, DEFAULT_KEYBOARD)

            # try default
            x_layouts = [DEFAULT_KEYBOARD]
            localed_wrapper.set_layouts(x_layouts, switch_options)

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

        with open(fpath, "w") as fobj:
            fobj.write('KEYMAP="%s"\n' % vc_keymap)

            # systemd now defaults to a font that cannot display non-ascii
            # characters, so we have to tell it to use a better one
            fobj.write('FONT="%s"\n' % DEFAULT_VC_FONT)

    except IOError as ioerr:
        msg = "Cannot write vconsole configuration file: {}".format(ioerr.strerror)
        raise KeyboardInstallationError(msg)
