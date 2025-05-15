#
# Copyright (C) 2015  Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.  #
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Common classes and functions for checking glade files.

Glade file tests should provide a python file containing a subclass of
GladeTest, below. When nose is run with GladePlugin, each GladeTest
implementation will be run against each glade file.
"""

# Print more helpful messages before raising ImportError
from builtins import FileNotFoundError

try:
    from lxml import etree
except ImportError:
    print("No module named lxml, you need to install the python3-lxml package")
    raise

import logging

from filelist import testfilelist

log = logging.getLogger('unittest')


def check_glade_files(testcase, method):
    """Run a method for each glade file as a sub-test of a test case.

    :param testcase: Instance of unittest.TestCase
    :param method: Method to execute for each glade tree.
    """
    assert(method is not None)
    for tree in glade_trees:
        with testcase.subTest(glade_file=tree.getroot().base):
            method(tree)


def load_glade_trees_from_files():
    """Load XML trees from glade files.

    :return: List of XML trees, as parsed by etree.
    """
    trees = []

    glade_files = testfilelist(lambda x: x.endswith('.glade'))
    if not glade_files:
        raise FileNotFoundError("Found no glade files to test.")

    # Parse all of the glade files
    log.info("Parsing glade files...")
    for glade_file in glade_files:
        trees.append(etree.parse(glade_file))

    return trees


glade_trees = load_glade_trees_from_files()
