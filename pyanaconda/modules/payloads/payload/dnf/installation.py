#
# Copyright (C) 2021  Red Hat, Inc.
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
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import util
from pyanaconda.modules.common.task import Task

log = get_module_logger(__name__)


class UpdateDNFConfigurationTask(Task):
    """The installation task to update the dnf.conf file."""

    def __init__(self, sysroot, data):
        """Create a new task.

        :param sysroot: a path to the system root
        :param data: a kickstart data
        """
        super().__init__()
        self._sysroot = sysroot
        self._data = data

    @property
    def name(self):
        return "Update DNF configuration"

    def run(self):
        """Run the task."""
        if self._data.packages.multiLib:
            self._set_option("multilib_policy", "all")

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
