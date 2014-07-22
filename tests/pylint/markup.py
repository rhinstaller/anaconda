# Pango markup pylint module
#
# Copyright (C) 2014  Red Hat, Inc.
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
# Red Hat Author(s): David Shea <dhsea@redhat.com>
#

import astroid

from pylint.checkers import BaseChecker
from pylint.checkers.utils import check_messages
from pylint.interfaces import IAstroidChecker

import types
import sys
import os

import xml.etree.ElementTree as ET

# markup_necessary not used yet
from pangocheck import markup_nodes, is_markup, markup_match #, markup_necessary

markupMethods = ["set_markup"]
escapeMethods = ["escape_markup"]

# Used for checking translations
podicts = None

i18n_funcs = ["_", "N_", "P_", "C_", "CN_", "CP_"]
i18n_ctxt_funcs = ["C_", "CN_", "CP_"]

class MarkupChecker(BaseChecker):
    __implements__ = (IAstroidChecker,)
    name = "pango-markup"
    msgs = {"W9920" : ("Found invalid pango markup",
                       "invalid-markup",
                       "Pango markup could not be parsed"),
            "W9921" : ("Found pango markup with invalid element %s",
                       "invalid-markup-element",
                       "Pango markup contains invalid elements"),
            "W9922" : ("Found % in markup with unescaped parameters",
                       "unescaped-markup",
                       "Parameters passed to % in markup not escaped"),
            "W9923" : ("Found invalid pango markup in %s translation",
                       "invalid-translated-markup",
                       "Translated Pango markup could not be parsed"),
            "W9924" : ("Found pango markup with invalid element %s in %s translation",
                       "invalid-translated-markup-element",
                       "Translated pango markup contains invalid elements"),
            "W9925" : ("Found mis-translated pango markup for language %s",
                       "invalid-pango-translation",
                       "The elements or attributes do not match between a pango markup string and its translation"),
            "W9926" : ("Found unnecessary pango markup",
                       "unnecessary-markup",
                       "Pango markup could be expressed as attribute list"),
           }

    options = (('translate-markup',
                {'default': False, 'type' : 'yn', 'metavar' : '<y_or_n>',
                 'help' : "Check translations of markup strings"
                }),
              )

    # Check a parsed markup string for invalid tags
    def _validate_pango_markup(self, node, root, lang=None):
        if root.tag not in markup_nodes:
            if lang:
                self.add_message("W9924", node=node, args=(root.tag, lang))
            else:
                self.add_message("W9921", node=node, args=(root.tag,))
        else:
            for child in root:
                self._validate_pango_markup(node, child)

    # Attempt to parse a markup string as XML
    def _validate_pango_markup_string(self, node, string, lang=None):
        try:
            # QUIS CUSTODIET IPSOS CUSTODES
            # pylint: disable=unescaped-markup
            tree = ET.fromstring("<markup>%s</markup>" % string)

            # Check if the markup is necessary
            # TODO: Turn this on after it's possible to actually do
            # anything about it. See https://bugzilla.gnome.org/show_bug.cgi?id=725681
            #if not markup_necessary(tree):
            #    self.add_message("W9926", node=node)
        except ET.ParseError:
            if lang:
                self.add_message("W9923", node=node, args=(lang,))
            else:
                self.add_message("W9920", node=node)
        else:
            # Check that all of the elements are valid for pango
            self._validate_pango_markup(node, tree)

    def __init__(self, linter=None):
        BaseChecker.__init__(self, linter)

    @check_messages("invalid-markup", "invalid-markup-element", "unescaped-markup", "invalid-translated-markup", "invalid-translated-markup-element", "invalid-pango-translation", "unnecessary-markup")
    def visit_const(self, node):
        if type(node.value) not in (types.StringType, types.UnicodeType):
            return

        if not is_markup(node.value):
            return

        self._validate_pango_markup_string(node, node.value)

        # Check translated versions of the string if requested
        if self.config.translate_markup:
            global podicts

            # Check if this is a translatable string
            curr = node
            i18nFunc = None
            while curr.parent:
                if isinstance(curr.parent, astroid.CallFunc) and \
                        getattr(curr.parent.func, "name", "") in i18n_funcs:
                    i18nFunc = curr.parent
                    break
                curr = curr.parent

            if i18nFunc:
                # If not done already, import polib and read the translations
                if not podicts:
                    try:
                        from translatepo import translate_all
                    except ImportError:
                        print("Unable to load po translation module")
                        sys.exit(99)
                    else:
                        podicts = translate_all(os.path.join(os.environ.get('top_srcdir', '.'), 'po'))

                if i18nFunc.func.name in i18n_ctxt_funcs:
                    msgctxt = i18nFunc.args[0].value
                else:
                    msgctxt = None

                # Loop over all translations for the string
                for podict in podicts.values():
                    try:
                        node_values = podict.get(node.value, msgctxt)
                    except KeyError:
                        continue

                    for value in node_values:
                        self._validate_pango_markup_string(node, value, podict.metadata['Language'])

                        # Check that the markup matches, roughly
                        if not markup_match(node.value, value):
                            self.add_message("W9925", node=node, args=(podict.metadata['Language'],))

        # Check if this the left side of a % operation
        curr = node
        formatOp = None
        while curr.parent:
            if isinstance(curr.parent, astroid.BinOp) and curr.parent.op == "%" and \
                    curr.parent.left == curr:
                formatOp = curr.parent
                break
            curr = curr.parent

        # Check whether the right side of the % operation is escaped
        if formatOp:
            if isinstance(formatOp.right, astroid.CallFunc):
                if getattr(formatOp.right.func, "name", "") not in escapeMethods:
                    self.add_message("W9922", node=formatOp.right)
            # If a tuple, each item in the tuple must be escaped
            elif isinstance(formatOp.right, astroid.Tuple):
                for elt in formatOp.right.elts:
                    if not isinstance(elt, astroid.CallFunc) or\
                            getattr(elt.func, "name", "") not in escapeMethods:
                        self.add_message("W9922", node=elt)
            # If a dictionary, each value must be escaped
            elif isinstance(formatOp.right, astroid.Dict):
                for item in formatOp.right.items:
                    if not isinstance(item[1], astroid.CallFunc) or\
                            getattr(item[1].func, "name", "") not in escapeMethods:
                        self.add_message("W9922", node=item[1])
            else:
                self.add_message("W9922", node=formatOp)

def register(linter):
    """required method to auto register this checker """
    linter.register_checker(MarkupChecker(linter))
