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

from pyanaconda.modules.common.errors.installation import LanguageInstallationError
from pyanaconda.modules.common.task import Task


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
