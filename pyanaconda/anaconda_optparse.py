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

from pyanaconda.flags import BootArgs
from optparse import OptionParser, OptionConflictError

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
        self.deprecated_bootargs = []
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

    # pylint: disable-msg=W0221
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
