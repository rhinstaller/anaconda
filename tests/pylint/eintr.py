# Interuptible system call pylint module
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
from pylint.checkers.utils import check_messages, safe_infer
from pylint.interfaces import IAstroidChecker

import os

# These are all of the system calls exposed through the os module that are
# documented in SUSv4 as *may* set EINTR. Some of them probably don't in Linux,
# but who knows.  lchmod, wait3 and wait4 aren't documented much anywhere but
# are here just in case.
interruptible = ("tmpfile", "close", "dup2", "fchmod", "fchown", "fstatvfs",
                 "fsync", "ftruncate", "open", "read", "write", "fchdir",
                 "chmod", "chown", "lchmod", "lchown", "statvfs", "wait",
                 "waitpid", "wait3", "wait4")

class EintrChecker(BaseChecker):
    __implements__ = (IAstroidChecker,)
    name = "retry-interruptible"
    msgs = {"W9930" : ("Found interruptible system call %s",
                       "interruptible-system-call",
                       "A system call that may raise EINTR is not wrapped in eintr_retry_call"),
           }

    @check_messages("interruptible-system-call")
    def visit_callfunc(self, node):
        if not isinstance(node, astroid.CallFunc):
            return

        # Skip anything not a function or not in os.  os redirects most of its
        # content to an OS-dependent module, named in os.name, so check that
        # one too.
        function_node = safe_infer(node.func)
        if not isinstance(function_node, astroid.Function) or \
                function_node.root().name not in ("os", os.name):
            return

        if function_node.name in interruptible:
            self.add_message("interruptible-system-call", node=node, args=function_node.name)

def register(linter):
    """required method to auto register this checker """
    linter.register_checker(EintrChecker(linter))
