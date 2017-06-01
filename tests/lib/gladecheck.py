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
try:
    from lxml import etree
except ImportError:
    print("No module named lxml, you need to install the python3-lxml package")
    raise

try:
    from pocketlint.translatepo import translate_all
except ImportError:
    print("Unable to load po translation module. You may need to install python3-polib")
    raise

from abc import ABCMeta, abstractmethod
import os
import unittest
import copy
import nose

from filelist import testfilelist

import logging
log = logging.getLogger('nose.plugins.glade')

class GladeTest(unittest.TestCase, metaclass=ABCMeta):
    """A framework for checking glade files.

       Subclasses must implement the checkGlade method, which will be run for
       each glade file that is part of the test. The unittest assert* methods
       are available. If checkGlade returns without raising an exception it
       is considered to pass.

       If the translatable property is True and --translate was provided on the
       command line, checkGlade will also be called with translated versions of
       each glade file.
    """

    translatable = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set by the plugin in prepareTestCase, since that's easier than
        # trying to override how this object is created.
        self.glade_trees = []
        self.translated_trees = {}

    @abstractmethod
    def checkGlade(self, glade_tree):
        """Check a parsed glade file.

           :param etree.ElementTree glade_tree: The parsed glade file
        """
        pass

    def test_glade_file(self):
        """Run checkGlade for each glade file."""
        for tree in self.glade_trees:
            with self.subTest(glade_file=tree.getroot().base):
                self.checkGlade(tree)

        if self.translatable:
            for lang, trees in self.translated_trees.items():
                for tree in trees:
                    with self.subTest(glade_file=tree.getroot().base, lang=lang):
                        self.checkGlade(tree)

class GladePlugin(nose.plugins.Plugin):
    name = "glade"
    enabled = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # These are filled during configure(), after we've decided what files
        # to check and whether to translate them.
        # Translations are a dict of {'lang': [list of trees]}
        self.glade_trees = []
        self.translated_trees = {}

    def options(self, parser, env):
        # Do not call the superclass options() to skip setting up the
        # enable/disable options.

        parser.add_option("--glade-file", action="append",
                help="Glade file(s) to test. If none specified, all files will be tested")
        parser.add_option("--notranslate", dest="translate", action="store_false", default=False,
                help="Do not test translations of glade files")
        parser.add_option("--translate", action="store_true",
                help="Test glade files with translations")
        parser.add_option("--podir", action="store", type=str,
                default=os.environ.get('top_srcdir', '.') + "/po",
                metavar="PODIR", help="Directory containing .po files")

    def configure(self, options, conf):
        super().configure(options, conf)

        # If no glade files were specified, find all of them
        if options.glade_file:
            glade_files = options.glade_file
        else:
            glade_files = testfilelist(lambda x: x.endswith('.glade'))

        # Parse all of the glade files
        log.info("Parsing glade files...")
        for glade_file in glade_files:
            self.glade_trees.append(etree.parse(glade_file))

        if options.translate:
            log.info("Loading translations...")
            podicts = translate_all(options.podir)

            # Loop over each available language
            for lang, langmap in podicts.items():
                self.translated_trees[lang] = []

                # For each language, loop over the parsed glade files
                for tree in self.glade_trees:
                    # Make a copy of the tree to translate and save it to
                    # the list for this language
                    tree = copy.deepcopy(tree)
                    self.translated_trees[lang].append(tree)

                    # Save the language as an attribute of the root of the tree
                    tree.getroot().set("lang", lang)

                    # Look for all properties with translatable=yes and translate them
                    for translatable in tree.xpath('//property[@translatable="yes"]'):
                        try:
                            xlated_text = langmap.get(translatable.text, context=translatable.get('context'))[0]

                            # Add the untranslated text as an attribute to this node
                            translatable.set("original_text", translatable.text)

                            # Replace the actual text
                            translatable.text = xlated_text
                        except KeyError:
                            # No translation available for this string in this language
                            pass

    def prepareTestCase(self, testcase):
        # Add the glade files to the GladeTest object
        testcase.test.glade_trees = self.glade_trees
        testcase.test.translated_trees = self.translated_trees

    def describeTest(self, testcase):
        # Return the first line of the doc string on checkGlade instead
        # of the string for test_glade_file. If there is no doc string,
        # return the name of the class.
        doc = testcase.test.checkGlade.__doc__
        if doc:
            return doc.strip().split("\n")[0].strip()
        else:
            return testcase.test.__class__.__name__

    def wantClass(self, cls):
        # Make sure we grab all the GladeTest subclasses, and only GladeTest
        # subclasses, regardless of name.
        return issubclass(cls, GladeTest) and cls != GladeTest
