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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import glob
import shlex
from collections import OrderedDict

from pyanaconda.core.constants import CMDLINE_APPEND, CMDLINE_FILES, CMDLINE_LIST

__all__ = ['KernelArguments', 'kernel_arguments']


# options might have the inst. prefix (used to differentiate
# boot options for the installer from other boot options)
BOOT_ARG_PREFIX = "inst."


class KernelArguments():
    """The kernel arguments.

    Hold boot arguments as an OrderedDict.
    """

    def __init__(self):
        self._data = OrderedDict()
        self._args_with_prefix = set()

    @classmethod
    def from_defaults(cls):
        """Load the default files.

        :return: an instance of KernelArguments
        """
        args = cls()
        args.read(CMDLINE_FILES)
        return args

    @classmethod
    def from_string(cls, cmdline):
        """Load the given cmdline.

        :param cmdline: a string with the kernel cmdline
        :return: an instance of KernelArguments
        """
        args = cls()
        args.read_string(cmdline)
        return args

    def read(self, filenames):
        """Read and parse a file name (or a list of file names).

        Files that can't be read are silently ignored. The names
        can contain \\*, ?, and character ranges expressed with [].

        :param filenames: a file name or a list of file names
        :return: a list of successfully read files
        """
        readfiles = []
        if isinstance(filenames, str):
            filenames = [filenames]

        # Expand any filename globs
        filenames = [f for g in filenames for f in glob.glob(g)]

        for f in filenames:
            try:
                self.read_string(open(f).read())
                readfiles.append(f)
            except OSError:
                continue

        return readfiles

    def read_string(self, cmdline):
        """Read and parse a string.

        :param cmdline: a string with the kernel command line
        """
        cmdline = cmdline.strip()
        # if the BOOT_IMAGE contains a space, pxelinux will strip one of the
        # quotes leaving one at the end that shlex doesn't know what to do
        # with
        (left, middle, right) = cmdline.rpartition("BOOT_IMAGE=")
        if right.count('"') % 2:
            cmdline = left + middle + '"' + right

        # shlex doesn't properly handle \\ (it removes them)
        # which scrambles the spaces used in labels so use underscores
        cmdline = cmdline.replace("\\x20", "_")

        lst = shlex.split(cmdline)

        for i in lst:
            prefix_used = False
            # drop the inst. prefix (if found)
            if i.startswith(BOOT_ARG_PREFIX):
                i = i[len(BOOT_ARG_PREFIX):]
                prefix_used = True

            if "=" in i:
                (key, val) = i.split("=", 1)
            else:
                key = i
                val = None

            if prefix_used:
                self._args_with_prefix.add(key)

            # Some duplicate args create a space separated string
            if key in CMDLINE_APPEND and self._data.get(key, None):
                if val:
                    self._data[key] = self._data[key] + " " + val
            # Some arguments can contain spaces so adding them in one string is not that helpful
            elif key in CMDLINE_LIST:
                if val:
                    if not self._data.get(key, None):
                        self._data[key] = []
                    self._data[key].append(val)
            else:
                self._data[key] = val

    def is_enabled(self, arg):
        """Return boolean value for the given argument.

        Rules:
        - 0, off, not present -> False
        - the rest -> True
        """
        # None is stored when arg is present but had no value when parsing.
        # So the "miss" value must be something else.
        val = self._data.get(arg, False)
        if val in ["0", "off", False]:
            return False
        else:
            return True

    def get(self, arg, default=None):
        """Return the value of the given argument.

        Propagates the call verbatim to the underlying dictionary.
        """
        return self._data.get(arg, default)

    def __contains__(self, arg):
        """Check for presence of an argument.

        Propagates the call verbatim to the underlying dictionary.
        """
        return arg in self._data

    def items(self):
        """Return an iterator over all arguments.

        Propagates the call verbatim to the underlying dictionary.
        """
        return self._data.items()

    def items_raw(self):
        """Return an iterator over all arguments in their raw form (with prefixes).

        TODO: DO NOT USE THIS METHOD! This workaround will be removed
              when lack of 'inst.' prefix is not supported.
        """
        for key, val in self._data.items():
            if key in self._args_with_prefix:
                yield ("{}{}".format(BOOT_ARG_PREFIX, key), val)
                continue

            yield (key, val)


kernel_arguments = KernelArguments.from_defaults()
