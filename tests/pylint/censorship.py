# Pylint censorship -- The smart filtering of false positives for Pylint.
#
# Copyright (C) 2020  Red Hat, Inc.

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

# Taken from:
# https://github.com/jkonecny12/pylint_censorship

"""
This module is the main implementation. It contains configuration and linter classes.

All the configuration should be handled by CensorshipConfig class instance. Linter class then
use this configuration to run the pylint and filter the results.

To be able to use this library correctly you have to add this to your pylint configuration file:
msg-template='{msg_id}({symbol}):{path}:{line},{column}: {obj}: {msg}'
"""

__all__ = ["CensorshipLinter", "CensorshipConfig"]

import sys
import re

from io import StringIO

import pylint.lint

from pylint.reporters.text import TextReporter


class FalsePositive():
    """An object used in filtering out incorrect results from pylint.

    Pass in a regular expression matching a pylint error message that should be ignored.
    This object can also be used to keep track of how often it is used, for auditing
    that false positives are still useful.
    """
    def __init__(self, regex):
        self.regex = regex
        self.used = 0


class CensorshipConfig():
    """Configuration of False Positives you want to run by Pylint."""
    def __init__(self):
        """Create a configuration object.

        Attributes:

        false_possitives: List of FalsePositive instances you want to filter out.

        pylintrc_path: Path to the Pylint configuration file. Everything except false positives
                       should be configured there. You can also pass pylintrc as argument to
                       command_line_args in that case the command_line_args rc file will
                       taken instead.

        command_line_args: Pass this list of command_line_args to pylint.
        """
        self.false_positives = []
        self.pylintrc_path = ""
        self.command_line_args = []

    @property
    def check_paths(self):
        """Get paths to check.

        These can be python modules or files.

        :return: list of paths
        """
        raise AttributeError("No test paths are specified. Please override "
                             "CensorshipConfig.check_paths property!")


class CensorshipLinter():
    """Run pylint linter and modify it's output."""

    def __init__(self, config):
        """Create CenshoreshipLinter class.

        :param config: configuration class for this Linter
        :type config: CensorshipConfig class instance
        """
        self._stdout = StringIO()
        self._config = config

    def run(self):
        """Run the pylint static linter.

        :return: return code of the linter run
        :rtype: int
        """
        args = self._prepare_args()

        print("Pylint version: ", pylint.__version__)
        print("Running pylint with args: ", args)

        pylint.lint.Run(args,
                        reporter=TextReporter(self._stdout),
                        exit=False)

        return self._process_output()

    def _prepare_args(self):
        args = []

        if self._config.command_line_args:
            args = self._config.command_line_args

        if self._config.pylintrc_path and "--rcfile" not in args:
            args.append("--rcfile")
            args.append(self._config.pylintrc_path)

        args.extend(self._config.check_paths)

        return args

    def _filter_false_positives(self, lines):
        if not self._config.false_positives:
            return lines

        lines = lines.split("\n")

        temp_line = ""
        retval = []

        for line in lines:

            # This is not an error message.  Ignore it.
            if line.startswith("Using config file"):
                retval.append(line)
            elif not line.strip():
                retval.append(line)
            elif line.startswith("*****"):
                temp_line = line
            else:
                if self._check_false_positive(line):
                    if temp_line:
                        retval.append(temp_line)
                        temp_line = ""

                    retval.append(line)

        return "\n".join(retval)

    def _check_false_positive(self, line):
        valid_error = True

        for regex in self._config.false_positives:
            if re.search(regex.regex, line):
                # The false positive was hit, so record that and ignore
                # the message from pylint.
                regex.used += 1
                valid_error = False
                break

        # If any false positive matched the error message, it's a valid
        # error from pylint.
        return valid_error

    def _report_unused_false_positives(self):
        unused = []

        for fp in self._config.false_positives:
            if fp.used == 0:
                unused.append(fp.regex)

        if unused:
            print("************* Unused False Positives Found:")

            for fp in unused:
                print(fp)

    def _process_output(self):
        stdout = self._stdout.getvalue()
        self._stdout.close()

        rc = 0

        if stdout:
            filtered_stdout = self._filter_false_positives(stdout)
            if filtered_stdout:
                print(filtered_stdout)
                sys.stdout.flush()
                rc = 1

        self._report_unused_false_positives()

        return rc
