#
# Copyright (C) 2019 Red Hat, Inc.
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
import stat
from collections import namedtuple

from blivet.size import Size

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.util import execWithCapture
from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.common.task import Task

log = get_module_logger(__name__)

# Mount point for the Live OS rootfsbase (mounted by the live system)
LIVE_OS_ROOTFSBASE_MOUNT = "/run/rootfsbase"

SetupLiveOSResult = namedtuple("SetupLiveOSResult", ["required_space"])


class DetectLiveOSImageTask(Task):
    """Detect a Live OS image in the system."""

    @property
    def name(self):
        return "Detect a Live OS image"

    def run(self):
        """Run the task.

        Check /run/rootfsbase to detect a squashfs+overlayfs base image.

        :return: a path of a block device or None
        """
        block_device = \
            self._check_block_device("/dev/mapper/live-base") or \
            self._check_block_device("/dev/mapper/live-osimg-min") or \
            self._check_mount_point(LIVE_OS_ROOTFSBASE_MOUNT)

        if not block_device:
            raise SourceSetupError("No Live OS image found!")

        log.debug("Detected the Live OS image '%s'.", block_device)
        return block_device

    def _check_block_device(self, block_device):
        """Check the specified block device."""
        log.debug("Checking the %s block device.", block_device)

        try:
            if stat.S_ISBLK(os.stat(block_device)[stat.ST_MODE]):
                return block_device
        except FileNotFoundError:
            pass

        return None

    def _check_mount_point(self, mount_point):
        """Check a block device at the specified mount point."""
        log.debug("Checking the %s mount point.", mount_point)

        if not os.path.exists(mount_point):
            return None

        try:
            block_device = execWithCapture("findmnt", ["-n", "-o", "SOURCE", mount_point]).strip()
            return block_device or None
        except (OSError, FileNotFoundError):
            pass

        return None


class SetUpLiveOSSourceTask(Task):
    """Task to set up a Live OS image."""

    def __init__(self, target_mount):
        """Create a new task.

        :param target_mount: a path to a mount point
        """
        super().__init__()
        self._target_mount = target_mount

    def run(self):
        """Run the task."""
        required_space = self._calculate_required_space()
        return SetupLiveOSResult(required_space=required_space)

    def _calculate_required_space(self):
        """
        Calculate the disk space required for the live OS by summing up
        the size of relevant directories using 'du -s'.
        """
        exclude_patterns = [
            "/dev/",
            "/proc/",
            "/tmp/*",
            "/sys/",
            "/run/",
            "/boot/*rescue*",
            "/boot/loader/",
            "/boot/efi/loader/",
            "/etc/machine-id",
            "/etc/machine-info"
        ]

        # Build the `du` command
        du_cmd_args = ["--bytes", "--summarize", self._target_mount]
        for pattern in exclude_patterns:
            du_cmd_args.extend(["--exclude", f"{self._target_mount}{pattern}"])

        try:
            # Execute the `du` command on the existing mount point
            result = execWithCapture("du", du_cmd_args)
            # Parse the output for the total size
            # When du has errors, it outputs error messages but the summary is on the last line
            lines = result.strip().split('\n')
            # Get the last line which contains the summary
            last_line = lines[-1]
            required_space = last_line.split()[0]  # First column is the total
            log.debug("Required space: %s", Size(required_space))
            return int(required_space)
        except (OSError, FileNotFoundError) as e:
            raise SourceSetupError(str(e)) from e

    @property
    def name(self):
        return "Set up a Live OS image"
