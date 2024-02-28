#
# The user interface module
#
# Copyright (C) 2024 Red Hat, Inc.
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
import sys
import tempfile
from pykickstart.constants import KS_SCRIPT_PRE, KS_SCRIPT_PREINSTALL

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import util
from pyanaconda.core.constants import IPMI_ABORTED
from pyanaconda.core.dbus import DBus
from pyanaconda.errors import ScriptError, errorHandler
from pyanaconda.flags import flags
from pyanaconda.modules.common.base import KickstartBaseModule
from pyanaconda.modules.common.constants.objects import SCRIPTS
from pyanaconda.modules.common.structures.scripts import Script
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.runtime.scripts.scripts_interface import ScriptsInterface

# Set up the modules logger.
log = get_module_logger(__name__)

__all__ = ["ScriptsModule"]


log = get_module_logger(__name__)

class ScriptsModule(KickstartBaseModule):
    """The scripts module.

    """
    def __init__(self):
        super().__init__()
        self._pre = None
        self._pre_install = None

    def publish(self):
        """Publish the module."""
        DBus.publish_object(SCRIPTS.object_path, ScriptsInterface(self))

    def run_pre_script_with_task(self):
        """Run the pre script"""
        log.debug("Running pre script with task")

        # FIXME
        # pylint: disable=no-member
        task = RunScriptTask(self.pre.script)
        return task

    def run_pre_install_script_with_task(self):
        """Run the pre-installation script."""
        log.debug("Running pre-installation script with task")

        task = RunScriptTask(self.pre_install.script)
        return task

    @property
    def pre(self):
        """The pre script."""
        return self._pre

    def set_pre(self, value):
        """Set the pre script."""
        self._pre = Script.to_structure(value)
        log.debug("Setting pre script to %s", value)

    @property
    def pre_install(self):
        """The pre-installation script."""
        return self.pre_install

    def set_pre_install(self, value):
        """Set the pre-installation script."""
        self._pre_install = Script.to_structure(value)
        log.debug("Setting pre-installation script to %s", value)

    def process_kickstart(self, data):
        """Process the kickstart data."""
        if data.sections.scripts.pre:
            self.set_pre(data.sections.scripts.pre)

        if data.sections.scripts.pre_install:
            self.set_pre_install(data.sections.scripts.pre_install)

    def setup_kickstart(self, data):
        """Set up the kickstart data."""
        if self.pre:
            data.sections.scripts.pre = self.pre

        if self.pre_install:
            data.sections.scripts.pre_install = self.pre_install


class RunScriptTask(Task):
    """Runs script task."""

    def __init__(self, script, inChroot=False, errorOnFail=True, logfile=None, lineno=None, chroot=None, interp="/bin/sh"):
        """Create a new task.

        :param script: KS section script
        :type script: str
        :param inChroot: whether to run the script in the chroot
        :type inChroot: bool
        :param errorOnFail: whether to abort the installation if the script fails
        :type errorOnFail: bool
        :param logfile: the file to log the output to
        :type logfile: str
        """
        super().__init__()
        self.chroot = chroot
        self.errorOnFail = errorOnFail
        self.inChroot = inChroot
        self.interp = interp
        self.lineno = lineno
        self.logfile = logfile
        self.script = script

    @property
    def name(self):
        return "Run script"

    def run(self):
        """ Run the kickstart script
            @param chroot directory path to chroot into before execution
        """
        if self.inChroot:
            scriptRoot = self.chroot
        else:
            scriptRoot = "/"

        (fd, path) = tempfile.mkstemp("", "ks-script-", scriptRoot + "/tmp")

        os.write(fd, self.script.encode("utf-8"))
        os.close(fd)
        os.chmod(path, 0o700)

        # Always log stdout/stderr from scripts.  Using --log just lets you
        # pick where it goes.  The script will also be logged to program.log
        # because of execWithRedirect.
        if self.logfile:
            if self.inChroot:
                messages = "%s/%s" % (scriptRoot, self.logfile)
            else:
                messages = self.logfile

            d = os.path.dirname(messages)
            if not os.path.exists(d):
                os.makedirs(d)
        else:
            # Always log outside the chroot, we copy those logs into the
            # chroot later.
            messages = "/tmp/%s.log" % os.path.basename(path)

        with open(messages, "w") as fp:
            rc = util.execWithRedirect(self.interp, ["/tmp/%s" % os.path.basename(path)],
                                       stdout=fp,
                                       root=scriptRoot)

        if rc != 0:
            log.error("Error code %s running the kickstart script at line %s", rc, self.lineno)
            if self.errorOnFail:
                err = ""
                with open(messages, "r") as fp:
                    err = "".join(fp.readlines())

                # Show error dialog even for non-interactive
                flags.ksprompt = True

                errorHandler.cb(ScriptError(self.lineno, err))
                util.ipmi_report(IPMI_ABORTED)
                sys.exit(0)



