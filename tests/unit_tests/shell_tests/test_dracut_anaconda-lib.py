#
# Copyright 2025 Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use, modify,
# copy, or redistribute it subject to the terms and conditions of the GNU
# General Public License v.2.  This program is distributed in the hope that it
# will be useful, but WITHOUT ANY WARRANTY expressed or implied, including the
# implied warranties of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.  Any Red Hat
# trademarks that are incorporated in the source code or documentation are not
# subject to the GNU General Public License and may only be used or replicated
# with the express permission of Red Hat, Inc.

import os
import re
import subprocess
import unittest
from collections import namedtuple
from tempfile import NamedTemporaryFile, TemporaryDirectory

DISABLE_COMMAND_PREFIX = "disabled-command"


SubprocessReturn = namedtuple("SubprocessReturn",
                              ["returncode", "disabled_cmd_args", "stdout", "stderr"])


class AnacondaLibTestCase(unittest.TestCase):

    def setUp(self):
        self._temp_dir = TemporaryDirectory()
        self._content = ""

    def tearDown(self):
        self._temp_dir.cleanup()

    def _load_script(self, script_name):
        with open(os.path.join("../dracut/", script_name), "rt", encoding="utf-8") as f:
            self._content = f.read()

    def _disable_bash_commands(self, disabled_commands):
        disable_list = []
        # disable external and problematic commands in Dracut
        for disabled_cmd in disabled_commands:
            if isinstance(disabled_cmd, list):
                disable_list.append(f"""
{disabled_cmd[0]}() {{
    echo "{DISABLE_COMMAND_PREFIX}: {disabled_cmd} args: $@" >&2
    {disabled_cmd[1]}
}}
""")
            if isinstance(disabled_cmd, str):
                disable_list.append(f"""
{disabled_cmd}() {{
    echo "{DISABLE_COMMAND_PREFIX}: {disabled_cmd} args: $@" >&2
}}
""")

        lines = self._content.splitlines()
        self._content = lines[0] + "\n" + "\n".join(disable_list) + "\n" + "\n".join(lines[1:])

    def _run_shell_command(self, command):
        """Run a shell command and return the output

        This function will also split out disabled commands args from the stdout and returns
        it as named tuple.

        :returns: SubprocessReturn named tuple
        """
        command = f"{self._content}\n\n{command}"
        ret = subprocess.run(
            ["bash", "-c", command],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            check=False,
        )

        disabled_cmd_args, stderr = self._separate_disabled_commands_msgs(ret.stderr)

        return SubprocessReturn(
            returncode=ret.returncode,
            disabled_cmd_args=disabled_cmd_args,
            stdout=ret.stdout.strip(),
            stderr=stderr
        )

    def _separate_disabled_commands_msgs(self, stderr):
        stderr_final = ""
        disabled_cmd_args = {}
        for line in stderr.splitlines():
            if line.startswith(DISABLE_COMMAND_PREFIX):
                match = re.search(fr"{DISABLE_COMMAND_PREFIX}: ([\w-]+) args: (.*)$", line)
                if match.group(1) in disabled_cmd_args:
                    disabled_cmd_args[match.group(1)].append(match.group(2))
                else:
                    disabled_cmd_args[match.group(1)] = [match.group(2)]
                continue

            stderr_final += line + "\n"

        return disabled_cmd_args, stderr_final

    def _check_get_text_with_content(self, test_input, expected_stdout):
        with NamedTemporaryFile(mode="wt") as test_file:
            test_file.write(test_input)
            test_file.flush()
            ret = self._run_shell_command(f"config_get tree arch < {test_file.name}")
            assert ret.returncode == 0
            assert ret.stdout == expected_stdout

    def test_config_get(self):
        """Test bash config_get function to read .treeinfo file"""
        self._load_script("anaconda-lib.sh")
        self._disable_bash_commands(["command"])

        # test multiple values in file
        self._check_get_text_with_content(
            """
[tree]
arch=x86_64
[config]
abc=cde
""",
            "x86_64",
        )

        # test space before and after '='
        self._check_get_text_with_content(
            """
[tree]
arch = aarch64
[config]
abc=cde
""",
            "aarch64",
        )

        # test multiple spaces before and after '='
        self._check_get_text_with_content(
            """
[tree]
arch   =\t  ppc64
[config]
abc\t=\t\tcde
""",
            "ppc64",
        )

        # test indented section
        self._check_get_text_with_content(
            """
    [tree]
\tarch = ppc64le
""",
            "ppc64le",
        )

        # test indented value in section
        self._check_get_text_with_content(
            """
    [tree]
        arch = s390
""",
            "s390",
        )
