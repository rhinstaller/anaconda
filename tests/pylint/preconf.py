# yum preconf pylint module
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

class PreconfChecker(BaseChecker):
    __implements__ = (IAstroidChecker, )
    name = "Yum preconf"
    msgs = {"W9910": ("Accessing yum.preconf outside of _resetYum",
                      "bad-preconf-access",
                      "Accessing yum.preconf outside of _resetYum will cause tracebacks"),
           }

    @check_messages("bad-preconf-access")
    def visit_getattr(self, node):
        if node.attrname == "preconf":
            if not isinstance(node.scope(), astroid.Function) or not node.scope().name == "_resetYum":
                self.add_message("W9910", node=node)

def register(linter):
    """required method to auto register this checker """
    linter.register_checker(PreconfChecker(linter))
