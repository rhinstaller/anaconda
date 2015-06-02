# setenv pylint module
#
# Copyright (C) 2015  Red Hat, Inc.
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
# Red Hat Author(s): David Shea <dshea@redhat.com>
#

import astroid

from pylint.checkers import BaseChecker
from pylint.checkers.utils import check_messages, safe_infer
from pylint.interfaces import IAstroidChecker

import os

class EnvironChecker(BaseChecker):
    __implements__ = (IAstroidChecker,)
    name = "environ"
    msgs = {"W9940" : ("Found potentially unsafe modification of environment",
                       "environment-modify",
                       "Potentially thread-unsafe modification of environment")}

    def _is_environ(self, node):
        # Guess whether a node being modified is os.environ

        if isinstance(node, astroid.Getattr):
            if node.attrname == "environ":
                expr_node = safe_infer(node.expr)
                if isinstance(expr_node, astroid.Module) and expr_node.name == "os":
                    return True

        # If the node being modified is just "environ" assume that it's os.environ
        if isinstance(node, astroid.Name):
            if node.name == "environ":
                return True

        return False

    @check_messages("environment-modify")
    def visit_assign(self, node):
        if not isinstance(node, astroid.Assign):
            return

        # Look for os.environ["WHATEVER"] = something
        for target in node.targets:
            if not isinstance(target, astroid.Subscript):
                continue

            if self._is_environ(target.value):
                self.add_message("environment-modify", node=node)

    @check_messages("environment-modify")
    def visit_callfunc(self, node):
        # Check both for uses of os.putenv and os.setenv and modifying calls
        # to the os.environ object, such as os.environ.update

        if not isinstance(node, astroid.CallFunc):
            return

        function_node = safe_infer(node.func)
        if not isinstance(function_node, (astroid.Function, astroid.BoundMethod)):
            return

        # If the function is from the os or posix modules, look for calls that
        # modify the environment
        if function_node.root().name in ("os", os.name) and \
                function_node.name in ("putenv", "unsetenv"):
            self.add_message("environment-modify", node=node)

        # Look for methods bound to the environ dict
        if isinstance(function_node, astroid.BoundMethod) and \
                isinstance(function_node.bound, astroid.Dict) and \
                function_node.bound.root().name in ("os", os.name) and \
                function_node.bound.name == "environ" and \
                function_node.name in ("clear", "pop", "popitem", "setdefault", "update"):
            self.add_message("environment-modify", node=node)

    @check_messages("environment-modify")
    def visit_delete(self, node):
        if not isinstance(node, astroid.Delete):
            return

        # Look for del os.environ["WHATEVER"]
        for target in node.targets:
            if not isinstance(target, astroid.Subscript):
                continue

            if self._is_environ(target.value):
                self.add_message("environment-modify", node=node)

def register(linter):
    """required method to auto register this checker """
    linter.register_checker(EnvironChecker(linter))
