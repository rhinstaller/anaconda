#
# Copyright (C) 2021  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
import os
from pyanaconda.core.configuration.anaconda import conf


def set_system_root(path):
    """Change the OS root path.

    The path defined by conf.target.system_root will be bind mounted at the given
    path, so conf.target.system_root can be used to access the root of the new OS.

    We always call it after the root device is mounted at conf.target.physical_root
    to set the physical root as the current system root.

    Then, it can be used by Payload subclasses which install operating systems to
    non-default roots.

    If the given path is None, then conf.target.system_root is only unmounted.

    :param path: the new OS root path or None
    :type path: str or None
    """
    from pyanaconda.core.util import execWithRedirect

    sysroot = conf.target.system_root

    if sysroot == path:
        return

    # Unmount the mount point if necessary.
    rc = execWithRedirect("findmnt", ["-rn", sysroot])

    if rc == 0:
        execWithRedirect("mount", ["--make-rprivate", sysroot])
        execWithRedirect("umount", ["--recursive", sysroot])

    if not path:
        return

    # Create a directory for the mount point.
    if not os.path.exists(sysroot):
        make_directories(sysroot)

    # Mount the mount point.
    rc = execWithRedirect("mount", ["--rbind", path, sysroot])

    if rc != 0:
        raise OSError("Failed to mount sysroot to {}.".format(path))


def make_directories(directory):
    """Make a directory and all of its parents. Don't fail if part of the path already exists.

    :param str directory: The directory path to create
    """
    os.makedirs(directory, 0o755, exist_ok=True)


def get_mount_paths(devnode):
    """Given a device node, return a list of all active mountpoints."""
    devno = os.stat(devnode).st_rdev
    majmin = "%d:%d" % (os.major(devno), os.minor(devno))
    mountinfo = (line.split() for line in open("/proc/self/mountinfo"))
    return [info[4] for info in mountinfo if info[2] == majmin]
