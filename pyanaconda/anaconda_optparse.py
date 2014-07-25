#
# anaconda_optparse.py: option parsing for anaconda (CLI and boot args)
#
# Copyright (C) 2012 Red Hat, Inc.  All rights reserved.
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
# Authors:
#   Will Woods <wwoods@redhat.com>

import itertools
import os

from pyanaconda.flags import BootArgs
from optparse import OptionParser, OptionConflictError

import logging
log = logging.getLogger("anaconda")

class AnacondaOptionParser(OptionParser):
    """
    Subclass of OptionParser that also examines boot arguments.

    If the "bootarg_prefix" keyword argument is set, it's assumed that all
    bootargs will start with that prefix.

    "require_prefix" is a bool:
        False: accept the argument with or without the prefix.
        True: ignore the argument without the prefix. (default)
    """
    def __init__(self, *args, **kwargs):
        self._boot_arg = dict()
        self.bootarg_prefix = kwargs.pop("bootarg_prefix","")
        self.require_prefix = kwargs.pop("require_prefix",True)
        OptionParser.__init__(self, *args, **kwargs)

    def add_option(self, *args, **kwargs):
        """
        Add a new option - like OptionParser.add_option.

        The long options will be added to the list of boot args, unless
        the keyword argument 'bootarg' is set to False.

        Positional arguments that don't start with '-' are considered extra
        boot args to look for.

        NOTE: conflict_handler is currently ignored for boot args - they will
        always raise OptionConflictError if they conflict.
        """
        # TODO: add kwargs to make an option commandline-only or boot-arg-only
        flags = [a for a in args if a.startswith('-')]
        bootargs = [a for a in args if not a.startswith('-')]
        do_bootarg = kwargs.pop("bootarg", True)
        option = OptionParser.add_option(self, *flags, **kwargs)
        bootargs += (flag[2:] for flag in option._long_opts)
        if do_bootarg:
            for b in bootargs:
                if b in self._boot_arg:
                    raise OptionConflictError(
                          "conflicting bootopt string: %s" % b, option)
                else:
                    self._boot_arg[b] = option
        return option

    def _get_bootarg_option(self, arg):
        """Find the correct Option for a given bootarg (if one exists)"""
        if self.bootarg_prefix and arg.startswith(self.bootarg_prefix):
            prefixed_option = True
            arg = arg[len(self.bootarg_prefix):]
        else:
            prefixed_option = False
        option = self._boot_arg.get(arg)

        if self.require_prefix and not prefixed_option:
            return None
        if option and self.bootarg_prefix and not prefixed_option:
            self.deprecated_bootargs.append(arg)
        return option

    def parse_boot_cmdline(self, cmdline, values=None):
        """
        Parse the boot cmdline and set appropriate values according to
        the options set by add_option.

        cmdline can be given as a string (to be parsed by BootArgs), or a
        dict (or any object with .iteritems()) of {bootarg:value} pairs.

        If cmdline is None, the cmdline data will be whatever BootArgs reads
        by default (/proc/cmdline, /run/initramfs/etc/cmdline, /etc/cmdline).

        If an option requires a value but the boot arg doesn't provide one,
        we'll quietly not set anything.
        """
        if cmdline is None or type(cmdline) is str:
            bootargs = BootArgs(cmdline)
        else:
            bootargs = cmdline
        self.deprecated_bootargs = []
        for arg, val in bootargs.iteritems():
            option = self._get_bootarg_option(arg)
            if option is None:
                continue
            if option.takes_value() and val is None:
                continue # TODO: emit a warning or something there?
            if option.action == "store_true" and val in ("0", "no", "off"):
                # special case: "mpath=0" would otherwise set mpath to True
                setattr(values, option.dest, False)
                continue
            option.process(arg, val, values, self)
        return values

    def parse_args(self, args=None, values=None, cmdline=None):
        """
        Like OptionParser.parse_args(), but also parses the boot cmdline.
        (see parse_boot_cmdline for details on that process.)
        Commandline arguments will override boot arguments.
        """
        if values is None:
            values = self.get_default_values()
        v = self.parse_boot_cmdline(cmdline, values)
        return OptionParser.parse_args(self, args, v)

def name_path_pairs(image_specs):
    """Processes and verifies image file specifications. Generates pairs
       of names and paths.

       :param image_specs: a list of image specifications
       :type image_specs: list of str

       Each image spec in image_specs has format <path>[:<name>] where
       <path> is the path to a local file and <name> is an optional
       name used to identify the disk in UI. <name> may not contain colons
       or slashes.

       If no name given in specification, synthesizes name from basename
       of path. Since two distinct paths may have the same basename, handles
       name collisions by synthesizing a different name for the colliding
       name.

       Raises an exception if:
         * A path is empty
         * A path specifies a non-existant file
         * A path specifies a directory
         * Duplicate paths are specified
         * A name contains a "/"
    """
    image_specs = (spec.rsplit(":", 1) for spec in image_specs)
    path_name_pairs = ((image_spec[0], image_spec[1].strip() if len(image_spec) == 2 else None) for image_spec in image_specs)

    paths_seen = []
    names_seen = []
    for (path, name) in path_name_pairs:
        if path == "":
            raise ValueError("empty path specified for image file")
        path = os.path.abspath(path)
        if not os.path.exists(path):
            raise ValueError("non-existant path %s specified for image file" % path)
        if os.path.isdir(path):
            raise ValueError("directory path %s specified for image file" % path)
        if path in paths_seen:
            raise ValueError("path %s specified twice for image file" % path)
        paths_seen.append(path)

        if name and "/" in name:
            raise ValueError("improperly formatted image file name %s, includes slashes" % name)

        if not name:
            name = os.path.splitext(os.path.basename(path))[0]

        if name in names_seen:
            names = ("%s_%d" % (name, n) for n in itertools.count())
            name = itertools.dropwhile(lambda n: n in names_seen, names).next()
        names_seen.append(name)

        yield name, path

class HelpTextParser(object):
    """Class to parse help text from file and make it available to option
       parser.
    """

    def __init__(self, path):
        """ Initializer
            :param path: The absolute path to the help text file
        """
        if not os.path.isabs(path):
            raise ValueError("path %s is not an absolute path" % path)
        self._path = path

        self._help_text = None

    def read(self, lines):
        """Reads option, help text pairs from a text file.

           Each pair is separated from the next by an empty line.
           The option comes first, followed by any number of lines of help text.

           :param lines: a sequence of lines of text
        """
        if not lines:
            return
        expect_option = True
        option = None
        text = []
        for line in (line.strip() for line in lines):
            if line == "":
                expect_option = True
            elif expect_option:
                if option:
                    yield option, " ".join(text)
                option = line
                text = []
                expect_option = False
            else:
                text.append(line)
        yield option, " ".join(text)

    def help_text(self, option):
        """
        Returns the help text corresponding to the given command-line option.
        If no help text is available, returns the empty string.

        :param str option: The name of the option

        :rtype: str
        """
        if self._help_text is None:
            self._help_text = {}
            try:
                with open(self._path) as lines:
                    for option, text in self.read(lines):
                        self._help_text[option] = text
            except StandardError:
                log.error("error reading help text file %s", self._path)

        return self._help_text.get(option, "")
