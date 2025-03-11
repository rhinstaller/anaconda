#
# Command utilities for working with scripts
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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import os
import tempfile

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import util
from pyanaconda.core.path import open_with_perm

log = get_module_logger(__name__)

script_log = log.getChild("script")


__all__ = ["run_script"]


def run_script(script, chroot):
    """ Run the kickstart script

    This will write the script to a file named /tmp/ks-script- before
    execution.
    Output is logged by the program logger, the path specified by --log
    or to /tmp/ks-script-\\*.log
    @param chroot directory path to chroot into before execution
    """
    if script.inChroot:
        scriptRoot = chroot
    else:
        scriptRoot = "/"

    (fd, path) = tempfile.mkstemp("", "ks-script-", scriptRoot + "/tmp")

    os.write(fd, script.script.encode("utf-8"))
    os.close(fd)
    os.chmod(path, 0o700)

    # Always log stdout/stderr from scripts.  Using --log just lets you
    # pick where it goes.  The script will also be logged to program.log
    # because of execWithRedirect.
    if script.logfile:
        if script.inChroot:
            messages = "%s/%s" % (scriptRoot, script.logfile)
        else:
            messages = script.logfile

        d = os.path.dirname(messages)
        if not os.path.exists(d):
            os.makedirs(d)
    else:
        # Always log outside the chroot, we copy those logs into the
        # chroot later.
        messages = "/tmp/%s.log" % os.path.basename(path)

    with open_with_perm(messages, "w", 0o600) as fp:
        rc = util.execWithRedirect(script.interp, ["/tmp/%s" % os.path.basename(path)],
                                   stdout=fp,
                                   root=scriptRoot)

    if rc != 0:
        script_log.error("Error code %s running the kickstart script at line %s",
                         rc, script.lineno)

    return rc, messages
