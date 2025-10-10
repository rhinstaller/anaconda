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


def get_mount_device(mount_point, mounts_file="/proc/mounts"):
    """
    Return the device which should be mounted on `mount_point`

    :arg mount_point: The full path of the mount point
    :kwarg mounts_file: A mounts file to use.  Defaults to `/proc/mounts`

    We expect all lines in the mounts_file to have the following format::

        /dev/mapper/luks-90a6412f-c588-46ca-9118-5aca35943d25 / ext4 rw,seclabel,relatime 0 0
    """
    with open(mounts_file, "r") as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 3 and parts[1] == mount_point:
                return parts[0]

    raise ValueError("Mount point {mount_point} was not found in {mounts_file}".format(
        mount_point=mount_point,
        mounts_file=mounts_file
    ))


def get_boot_partition(partitions_file="/proc/paritions"):
    """
    Return the system's boot partition.

    :kwarg partitions_file: A filename to search for the boot partition within.  Defaults to "/proc/partitions".

    The partition file is expected to be of the format::

        major minor  #blocks  name
         259        0  500107608 nvme0n1
         259        1     204800 nvme0n1p1
         259        2    2097152 nvme0n1p2
         259        3    5244928 nvme0n1p3
    """
    # Boot partition is usually 2nd after autopart (sda2, vda2 etc)
    with open(partitions_file) as f:
        # Skip two lines of header
        next(f)
        next(f)

        for line in f:
            columns = line.split()
            if len(columns) == 4:
                _major, minor, _blocks, name = columns
                # Just find the first partition with minor number == 2
                if minor == '2':
                    return name

    raise ValueError("Unable to find a boot partition in {0}".format(partitions_file))


def open_with_perm(path, mode='r', perm=0o777, **kwargs):
    """Open a file with the given permission bits.

    This is more or less the same as using os.open(path, flags, perm), but
    with the builtin open() semantics and return type instead of a file
    descriptor.

    :param str path: The path of the file to be opened
    :param str mode: The same thing as the mode argument to open()
    :param int perm: What permission bits to use if creating a new file
    :return: Opened file-like object
    """
    def _opener(path_to_open, open_flags):
        return os.open(path_to_open, open_flags, perm)

    return open(path, mode, opener=_opener, **kwargs)


def join_paths(path, *paths):
    """Always join paths.

    The os.path.join() function has a drawback when second path is absolute. In that case it will
    instead return the second path only.

    :param path: first path we want to join
    :param paths: paths we want to merge
    :returns: return path created from all the input paths
    :rtype: str
    """
    if len(paths) == 0:
        return path

    new_paths = []
    for p in paths:
        new_paths.append(p.lstrip(os.path.sep))

    return os.path.join(path, *new_paths)


def touch(file_path):
    """Create an empty file.

    This mirrors how touch works - it does not throw an error if the given path exists,
    even when the path points to a directory.

    :param str file_path: Path to the file to create
    """
    if not os.path.exists(file_path):
        os.mknod(file_path)


def set_mode(file_path, perm=0o600):
    """Set file permission to a given file

    In case the file doesn't exists - create it.

    :param str file_path: Path to a file
    :param int perm: File permissions in format of os.chmod()
    """
    if not os.path.exists(file_path):
        touch(file_path)
    os.chmod(file_path, perm)
