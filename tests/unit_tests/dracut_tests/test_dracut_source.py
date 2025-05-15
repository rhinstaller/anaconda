#
# Copyright 2020 Red Hat, Inc.
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
import unittest
from functools import reduce
from os.path import dirname

import pyanaconda
from pyanaconda.core.util import join_paths

REPO_DIR = dirname(os.path.realpath(pyanaconda.__file__))


@unittest.skipIf(REPO_DIR.startswith("/usr/lib"), "Could be run only on source files. Skipping.")
class SourcesTestCase(unittest.TestCase):

    def test_find_rw_mounts(self):
        """Test that only RO mounts of install sources are in Dracut."""
        # everything what starts by string in this list will not be tested
        ignore_prefixes = ("Makefile", "README", "python-deps", "module-setup.sh")
        # define false positives
        false_positives = (re.compile(r'\bmount +(--move|--make-rprivate)'),
                           re.compile(r'\bmount /dev/mapper/live-rw'),
                           re.compile(r'\bmount +-t *overlay'))

        # filter not interesting content
        comment_regex = re.compile(r'#[^\n]*')
        log_regex = re.compile(r'\b(info|warn|error) +"[^"]*')

        # remove pyanaconda dir
        dracut_dir_path = join_paths(os.path.split(REPO_DIR)[0], "dracut")
        files = os.listdir(dracut_dir_path)

        # helper function to ignore prefixes specified above
        def _filter_ignore_files(result, file_name):
            for ignore_prefix in ignore_prefixes:
                if file_name.startswith(ignore_prefix):
                    print("ignoring", file_name)
                    return result

            if os.path.isdir(file_name):
                print("ignoring directory", file_name)
                return result

            result.append(file_name)
            return result

        files = reduce(_filter_ignore_files, files, [])

        mount_line_regex = re.compile(r'\bmount ')

        for f in files:
            path = join_paths(dracut_dir_path, f)
            if path.endswith("__pycache__"):
                continue
            with open(path, "rt") as fd:
                print("reading content of", path)
                content = fd.read()
                content = comment_regex.sub("", content)
                content = log_regex.sub("", content)

                for num, line in enumerate(content.split('\n'), start=1):
                    # remove false positives from the line string
                    for fp in false_positives:
                        line = fp.sub("", line)

                    # skip empty lines
                    if not line:
                        continue
                    # skip every line which doesn't contain mount string
                    if not mount_line_regex.search(line):
                        continue

                    # skip all lines which are just logging
                    if line.strip().startswith("log.debug"):
                        continue

                    # fail on every line which does not have 'mount -o ro'
                    assert re.search(r'\bmount +-o *[a-z,]*ro', line), \
                        "Dracut mount in '{}' on line '{}' is not read-only!" \
                        .format(path, num)
