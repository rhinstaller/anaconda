# I18N-related pylint module
#
# Copyright (C) 2013  Red Hat, Inc.
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
# Red Hat Author(s): Chris Lumens <clumens@redhat.com>
#

import astroid

from pylint.checkers import BaseChecker
from pylint.checkers.strings import StringFormatChecker
from pylint.checkers.logging import LoggingChecker
from pylint.checkers.utils import check_messages
from pylint.interfaces import IAstroidChecker

from copy import copy

translationMethods = frozenset(["_", "N_", "P_", "C_", "CN_", "CP_"])

# Returns a list of the message strings for a given translation method call
def _get_message_strings(node):
    msgstrs = []

    if node.func.name in ("_", "N_") and len(node.args) >= 1:
        if isinstance(node.args[0], astroid.Const):
            msgstrs.append(node.args[0].value)
    elif node.func.name in ("C_", "CN_") and len(node.args) >= 2:
        if isinstance(node.args[1], astroid.Const):
            msgstrs.append(node.args[1].value)
    elif node.func.name == "P_" and len(node.args) >= 2:
        if isinstance(node.args[0], astroid.Const):
            msgstrs.append(node.args[0].value)
        if isinstance(node.args[1], astroid.Const):
            msgstrs.append(node.args[1].value)
    elif node.func.name == "CP_" and len(node.args) >= 3:
        if isinstance(node.args[1], astroid.Const):
            msgstrs.append(node.args[1].value)
        if isinstance(node.args[2], astroid.Const):
            msgstrs.append(node.args[2].value)

    return msgstrs

class IntlChecker(BaseChecker):
    __implements__ = (IAstroidChecker, )
    name = "internationalization"
    msgs = {"W9901": ("Found % in a call to a _() method",
                      "found-percent-in-_",
                      "% in a call to one of the _() methods results in incorrect translations"),
            "W9902": ("Found _ call at module/class level",
                      "found-_-in-module-class",
                      "Calling _ at the module or class level results in translations to the wrong language")
           }

    @check_messages("found-percent-in-_")
    def visit_binop(self, node):
        if node.op != "%":
            return

        curr = node
        while curr.parent:
            if isinstance(curr.parent, astroid.CallFunc) and getattr(curr.parent.func, "name", "") in translationMethods:
                self.add_message("W9901", node=node)
                break

            curr = curr.parent

    @check_messages("found-_-in-module-class")
    def visit_callfunc(self, node):
        # The first test skips internal functions like getattr.
        if isinstance(node.func, astroid.Name) and node.func.name == "_":
            if isinstance(node.scope(), astroid.Module) or isinstance(node.scope(), astroid.Class):
                self.add_message("W9902", node=node)

# Extend LoggingChecker to check translated logging strings
class IntlLoggingChecker(LoggingChecker):
    __implements__ = (IAstroidChecker,)

    name = 'intl-logging'
    msgs = {'W9903': ("Fake message for translated E/W120* checks",
                      "translated-log",
                      "This message is not emitted itself, but can be used to control the display of \
                       logging format messages extended for translated strings")
           }

    options = ()

    @check_messages('translated-log')
    def visit_callfunc(self, node):
        if len(node.args) >= 1 and isinstance(node.args[0], astroid.CallFunc) and \
                getattr(node.args[0].func, "name", "") in translationMethods:
            for formatstr in _get_message_strings(node.args[0]):
                # Both the node and the args need to be copied so we don't replace args
                # on the original node.
                copynode = copy(node)
                copyargs = copy(node.args)
                copyargs[0] = astroid.Const(formatstr)
                copynode.args = copyargs
                LoggingChecker.visit_callfunc(self, copynode)

    def __init__(self, *args, **kwargs):
        LoggingChecker.__init__(self, *args, **kwargs)

        # Just set logging_modules to 'logging', instead of trying to take a parameter
        # like LoggingChecker
        self.config.logging_modules = ('logging',)

# Extend StringFormatChecker to check translated format strings
class IntlStringFormatChecker(StringFormatChecker):
    __implements__ = (IAstroidChecker,)

    name = 'intl-string'
    msgs = {'W9904': ("Fake message for translated E/W130* checks",
                      "translated-format",
                      "This message is not emitted itself, but can be used to control the display of \
                       string format messages extended for translated strings")
           }

    @check_messages('translated-format')
    def visit_binop(self, node):
        if node.op != '%':
            return

        if isinstance(node.left, astroid.CallFunc) and getattr(node.left.func, "name", "") in translationMethods:
            for formatstr in _get_message_strings(node.left):
                # Create a copy of the node with just the message string as the format
                copynode = copy(node)
                copynode.left = astroid.Const(formatstr)
                StringFormatChecker.visit_binop(self, copynode)

def register(linter):
    """required method to auto register this checker """
    linter.register_checker(IntlChecker(linter))
    linter.register_checker(IntlLoggingChecker(linter))
    linter.register_checker(IntlStringFormatChecker(linter))
