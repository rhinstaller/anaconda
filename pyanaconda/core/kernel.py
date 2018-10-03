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
import shlex
import glob

from collections import OrderedDict
from pyanaconda.core.constants import CMDLINE_APPEND, CMDLINE_LIST, CMDLINE_FILES


class KernelArguments(OrderedDict):
    """The kernel arguments.

    Hold boot arguments as an OrderedDict.
    """

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
            except IOError:
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

        # options might have the inst. prefix (used to differentiate
        # boot options for the installer from other boot options)
        inst_prefix = "inst."

        for i in lst:
            # drop the inst. prefix (if found), so that getbool() works
            # consistently for both "foo=0" and "inst.foo=0"
            if i.startswith(inst_prefix):
                i = i[len(inst_prefix):]

            if "=" in i:
                (key, val) = i.split("=", 1)
            else:
                key = i
                val = None

            # Some duplicate args create a space separated string
            if key in CMDLINE_APPEND and self.get(key, None):
                if val:
                    self[key] = self[key] + " " + val
            # Some arguments can contain spaces so adding them in one string is not that helpful
            elif key in CMDLINE_LIST:
                if val:
                    if not self.get(key, None):
                        self[key] = []
                    self[key].append(val)
            else:
                self[key] = val

    def getbool(self, arg, default=False):
        """Return the boolean value of the given argument.

        The rules are:
        - "arg", "arg=val": True
        - "noarg", "noarg=val", "arg=[0|off|no]": False

        :param arg: a name of the argument
        :param default: a default value
        :return: a boolean value of the argument
        """
        result = default
        for a in self:
            if a == arg:
                if self[arg] in ("0", "off", "no"):
                    result = False
                else:
                    result = True
            elif a == 'no' + arg:
                result = False  # XXX: should noarg=off -> True?
        return result
