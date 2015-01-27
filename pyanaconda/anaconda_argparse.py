#
# anaconda_argparse.py: option parsing for anaconda (CLI and boot args)
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
#   Martin Kolman <mkolman@redhat.com>

DESCRIPTION = "Anaconda is the installation program used by Fedora," \
              "Red Hat Enterprise Linux and some other distributions."

import itertools
import os
import sys
import fcntl
import termios
import struct

from argparse import ArgumentParser, ArgumentError, HelpFormatter, Namespace

from pyanaconda.flags import BootArgs

import logging
log = logging.getLogger("anaconda")

# Help text formatting constants

LEFT_PADDING = 8  # the help text will start after 8 spaces
RIGHT_PADDING = 8  # there will be 8 spaces left on the right
DEFAULT_HELP_WIDTH = 80

def get_help_width():
    """
    Try to detect the terminal window width size and use it to
    compute optimal help text width. If it can't be detected
    a default values is returned.

    :returns: optimal help text width in number of characters
    :rtype: int
    """
    # don't do terminal size detection on s390, it is not supported
    # by its arcane TTY system and only results in cryptic error messages
    # ending on the standard output
    # (we do the s390 detection here directly to avoid
    #  the delay caused by importing the Blivet module
    #  just for this single call)
    is_s390 = os.uname()[4].startswith('s390')
    if is_s390:
        return DEFAULT_HELP_WIDTH

    help_width = DEFAULT_HELP_WIDTH
    try:
        data = fcntl.ioctl(sys.stdout, termios.TIOCGWINSZ, '1234')
        columns = int(struct.unpack('hh', data)[1])
        # apply the right padding
        columns = columns - RIGHT_PADDING
        if columns > 0:
            help_width = columns
    # pylint: disable=broad-except
    except Exception as e:
        # detection failed, use the default
        # NOTE: this could be caused by the COLUMNS string having a value
        # that can't be converted to an integer
        print("anaconda argparse: terminal size detection failed, using default width")
        print(e)
    return help_width

class AnacondaArgumentParser(ArgumentParser):
    """
    Subclass of ArgumentParser that also examines boot arguments.
    """

    def __init__(self, *args, **kwargs):
        """
        If the "bootarg_prefix" keyword argument is set, it's assumed that all
        bootargs will start with that prefix.

        "require_prefix" is a bool:
            False: accept the argument with or without the prefix.
            True: ignore the argument without the prefix. (default)
        """
        help_width = get_help_width()
        self._boot_arg = dict()
        self.deprecated_bootargs = []
        self.bootarg_prefix = kwargs.pop("bootarg_prefix", "")
        self.require_prefix = kwargs.pop("require_prefix", True)
        ArgumentParser.__init__(self, description=DESCRIPTION,
                                formatter_class=lambda prog: HelpFormatter(
                                    prog, max_help_position=LEFT_PADDING, width=help_width),
                                *args, **kwargs)

    def add_argument(self, *args, **kwargs):
        """
        Add a new option - like ArgumentParser.add_argument.

        The long options will be added to the list of boot args, unless
        the keyword argument 'bootarg' is set to False.

        Positional arguments that don't start with '-' are considered extra
        boot args to look for.

        NOTE: conflict_handler is currently ignored for boot args - they will
        always raise ArgumentError if they conflict.
        """
        # TODO: add kwargs to make an option commandline-only or boot-arg-only
        flags = [a for a in args if a.startswith('-')]
        bootargs = [a for a in args if not a.startswith('-')]
        do_bootarg = kwargs.pop("bootarg", True)
        option = super(AnacondaArgumentParser, self).add_argument(*flags, **kwargs)
        # make a generator that returns only the long opts without the -- prefix
        long_opts = (o[2:] for o in option.option_strings if o.startswith("--"))
        bootargs += (flag for flag in long_opts)
        if do_bootarg:
            for b in bootargs:
                if b in self._boot_arg:
                    raise ArgumentError(
                        "conflicting bootopt string: %s" % b, option)
                else:
                    self._boot_arg[b] = option
        return option

    def _get_bootarg_option(self, arg):
        """
        Find the correct Option for a given bootarg (if one exists)

        :param string arg: boot option

        :returns: argparse option object or None if no suitable option is found
        :rtype argparse option or None
        """
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

    def parse_boot_cmdline(self, boot_cmdline):
        """
        Parse the boot cmdline and create an appropriate Namespace instance
        according to the option definitions set by add_argument.

        boot_cmdline can be given as a string (to be parsed by BootArgs), or a
        dict (or any object with .items()) of {bootarg:value} pairs.

        If boot_cmdline is None, the boot_cmdline data will be whatever BootArgs reads
        by default (/proc/cmdline, /run/initramfs/etc/cmdline, /etc/cmdline).

        If an option requires a value but the boot arg doesn't provide one,
        we'll quietly not set anything in the Namespace. We also skip any boot options
        that were not specified by add_argument as we don't care about them
        (there will usually be quite a lot of them (rd.*, etc.).

        :param boot_cmdline: the Anaconda boot command line arguments
        :type boot_cmdline: string, dict or None

        :returns: an argparse Namespace instance
        :rtype: Namespace
        """
        namespace = Namespace()
        if boot_cmdline is None or type(boot_cmdline) is str:
            bootargs = BootArgs(boot_cmdline)
        else:
            bootargs = boot_cmdline
        self.deprecated_bootargs = []
        # go over all options corresponding to current boot cmdline
        # and do any modifications necessary
        # NOTE: program cmdline overrides boot cmdline
        for arg, val in bootargs.items():
            option = self._get_bootarg_option(arg)
            if option is None:
                # this boot option is unknown to Anaconda, skip it
                continue
            if option.nargs != 0 and val is None:
                # nargs == 0 -> the option expects one or more arguments but the
                # boot option was not given any, so we skip it
                log.warning("boot option specified without expected number of "
                            "arguments and will be ignored: %s", arg)
                continue
            if option.nargs == 0 and option.const is not None:
                # nargs == 0 & constr == True -> store_true
                # (we could also check the class, but it begins with an
                # underscore, so it would be ugly)
                # special case: "mpath=0" would otherwise set mpath to True
                if option.const is True and val in ("0", "no", "off"):
                    setattr(namespace, option.dest, False)
                # Set all other set_const cases to the const specified
                else:
                    setattr(namespace, option.dest, option.const)

                # anaconda considers cases such as noselinux=off to be a negative
                # concord, which is to say that selinux will be set to False and
                # we hate you.

                continue
            setattr(namespace, option.dest, val)
        return namespace

    # pylint: disable=arguments-differ
    def parse_args(self, args=None, boot_cmdline=None):
        """
        Like ArgumentParser.parse_args(), but also parses the boot cmdline.
        (see parse_boot_cmdline for details on that process.)
        Program cmdline arguments will override boot cmdline arguments.

        :param args: program command line arguments
        :type args: string or None

        :param boot_cmdline: the Anaconda boot command line arguments
        :type boot_cmdline: string, dict or None

        :returns: an argparse Namespace instance
        :rtype: Namespace
        """
        # parse boot options first
        namespace = self.parse_boot_cmdline(boot_cmdline)
        # parse CLI arguments (if any) and add them to the namespace
        # created from parsing boot options, overriding any options
        # with the same destination already present in the namespace
        # NOTE: this means that CLI options override boot options
        namespace = ArgumentParser.parse_args(self, args, namespace)
        return namespace

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
            name = next(itertools.dropwhile(lambda n: n in names_seen, names))
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
                    for parsed_option, parsed_text in self.read(lines):
                        self._help_text[parsed_option] = parsed_text
            except Exception:  # pylint: disable=broad-except
                log.error("error reading help text file %s", self._path)

        return self._help_text.get(option, "")
