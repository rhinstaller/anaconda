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
from pylint.checkers.utils import check_messages
from pylint.interfaces import IAstroidChecker

translationMethods = ["_", "N_", "P_", "C_", "CN_", "CP_"]

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

    @check_messages("W9901")
    def visit_binop(self, node):
        if node.op != "%":
            return

        curr = node
        while curr.parent:
            if isinstance(curr.parent, astroid.CallFunc) and getattr(curr.parent.func, "name", "") in translationMethods:
                self.add_message("W9901", node=node)
                break

            curr = curr.parent

    @check_messages("W9902")
    def visit_callfunc(self, node):
        # The first test skips internal functions like getattr.
        if isinstance(node.func, astroid.Name) and node.func.name == "_":
            if isinstance(node.scope(), astroid.Module) or isinstance(node.scope(), astroid.Class):
                self.add_message("W9902", node=node)

def register(linter):
    """required method to auto register this checker """
    linter.register_checker(IntlChecker(linter))
