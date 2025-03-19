#
# Copyright (C) 2020  Red Hat, Inc.
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
import os
import rpm

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import util
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import RPM_LANGUAGES_NONE, RPM_LANGUAGES_ALL, MULTILIB_POLICY_BEST
from pyanaconda.modules.common.structures.payload import PackagesConfigurationData
from pyanaconda.modules.common.task import Task

log = get_module_logger(__name__)


class SetRPMMacrosTask(Task):
    """Installation task to set RPM macros."""

    def __init__(self, data: PackagesConfigurationData):
        """Create a task.

        :param data: a packages configuration data
        """
        super().__init__()
        self._data = data
        self._macros = []

    @property
    def name(self):
        """The name of the task."""
        return "Set RPM macros"

    def run(self):
        """Run the task."""
        self._macros = self._collect_macros(self._data)
        self._install_macros(self._macros)

    def _collect_macros(self, data: PackagesConfigurationData):
        """Collect the RPM macros."""
        macros = list()

        # nofsync speeds things up at the risk of rpmdb data loss in a crash.
        # But if we crash mid-install you're boned anyway, so who cares?
        macros.append(('__dbi_htconfig', 'hash nofsync %{__dbi_other} %{__dbi_perms}'))

        if data.docs_excluded:
            macros.append(('_excludedocs', '1'))

        if data.languages == RPM_LANGUAGES_NONE:
            macros.append(('_install_langs', '%{nil}'))
        elif data.languages != RPM_LANGUAGES_ALL:
            macros.append(('_install_langs', data.languages))

        if conf.security.selinux:
            for d in ["/etc/selinux/targeted/contexts/files",
                      "/etc/security/selinux/src/policy",
                      "/etc/security/selinux"]:
                f = d + "/file_contexts"
                if os.access(f, os.R_OK):
                    macros.append(('__file_context_path', f))
                    break
        else:
            macros.append(('__file_context_path', '%{nil}'))

        return macros

    def _install_macros(self, macros):
        """Add RPM macros to the global transaction environment."""
        for name, value in macros:
            log.debug("Set '%s' to '%s'.", name, value)
            rpm.addMacro(name, value)


class ImportRPMKeysTask(Task):
    """The installation task for import of the RPM keys."""

    def __init__(self, sysroot, gpg_keys):
        """Create a new task.

        :param sysroot: a path to the system root
        :param gpg_keys: a list of gpg keys to import
        """
        super().__init__()
        self._sysroot = sysroot
        self._gpg_keys = gpg_keys

    @property
    def name(self):
        return "Import RPM keys"

    def run(self):
        """Run the task"""
        if not self._gpg_keys:
            log.debug("No GPG keys to import.")
            return

        if not os.path.exists(self._sysroot + "/usr/bin/rpm"):
            log.error(
                "Can not import GPG keys to RPM database because "
                "the 'rpm' executable is missing on the target "
                "system. The following keys were not imported:\n%s",
                "\n".join(self._gpg_keys)
            )
            return

        # Get substitutions for variables.
        # TODO: replace the interpolation with DNF once possible
        basearch = util.execWithCapture("uname", ["-i"]).strip().replace("'", "")
        releasever = util.get_os_release_value("VERSION_ID", sysroot=self._sysroot) or ""

        # Import GPG keys to RPM database.
        for key in self._gpg_keys:
            key = key.replace("$releasever", releasever).replace("$basearch", basearch)

            log.info("Importing GPG key to RPM database: %s", key)
            rc = util.execWithRedirect("rpm", ["--import", key], root=self._sysroot)

            if rc:
                log.error("Failed to import the GPG key.")


class UpdateDNFConfigurationTask(Task):
    """The installation task to update the dnf.conf file."""

    def __init__(self, sysroot, data: PackagesConfigurationData):
        """Create a new task.

        :param sysroot: a path to the system root
        :param data: a packages configuration data
        """
        super().__init__()
        self._sysroot = sysroot
        self._data = data

    @property
    def name(self):
        return "Update DNF configuration"

    def run(self):
        """Run the task."""
        if self._data.multilib_policy != MULTILIB_POLICY_BEST:
            self._set_option("multilib_policy", self._data.multilib_policy)

    def _set_option(self, option, value):
        """Set a configuration option.

        :param option: a name of the option
        :param value: a value of the option
        """
        log.debug("Setting '%s' to '%s'.", option, value)

        cmd = "dnf"
        args = [
            "config-manager",
            "--save",
            "--setopt={}={}".format(option, value),
        ]

        try:
            rc = util.execWithRedirect(cmd, args, root=self._sysroot)
        except OSError as e:
            log.warning("Couldn't update the DNF configuration: %s", e)
            return

        if rc != 0:
            log.warning("Failed to update the DNF configuration (%s).", rc)
            return
