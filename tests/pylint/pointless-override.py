# Pylint checker for pointless class attributes overrides.
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
# Red Hat Author(s): Anne Mulhern <amulhern@redhat.com>
#

import abc

from six import add_metaclass

import astroid

from pylint.checkers import BaseChecker
from pylint.checkers.utils import check_messages
from pylint.interfaces import IAstroidChecker

@add_metaclass(abc.ABCMeta)
class PointlessData(object):

    _DEF_CLASS = abc.abstractproperty(doc="Class of interesting definitions.")
    message_id = abc.abstractproperty(doc="Pylint message identifier.")

    @classmethod
    @abc.abstractmethod
    def _retain_node(cls, node, restrict=True):
        """ Determines whether to retain a node for the analysis.

            :param node: an AST node
            :type node: astroid.Class
            :param restrict bool: True if results returned should be restricted
            :returns: True if the node should be kept, otherwise False
            :rtype: bool

            Restricted nodes are candidates for being marked as overridden.
            Only restricted nodes are put into the initial pool of candidates.
        """
        raise NotImplementedError()

    @staticmethod
    @abc.abstractmethod
    def _extract_value(node):
        """ Return the node that contains the assignment's value.

            :param node: an AST node
            :type node: astroid.Class
            :returns: the node corresponding to the value
            :rtype: bool
        """
        raise NotImplementedError()

    @staticmethod
    @abc.abstractmethod
    def _extract_targets(node):
        """ Generates the names being assigned to.

            :param node: an AST node
            :type node: astroid.Class
            :returns: a list of assignment target names
            :rtype: generator of str
        """
        raise NotImplementedError()

    @classmethod
    def get_data(cls, node, restrict=True):
        """ Find relevant nodes for this analysis.

            :param node: an AST node
            :type node: astroid.Class
            :param restrict bool: True if results returned should be restricted

            :rtype: generator of astroid.Class
            :returns: a generator of interesting nodes.

            Note that all nodes returned are guaranteed to be instances of
            some class in self._DEF_CLASS.
        """
        nodes = (n for n in node.body if isinstance(n, cls._DEF_CLASS))
        for n in nodes:
            if cls._retain_node(n, restrict):
                for name in cls._extract_targets(n):
                    yield (name, cls._extract_value(n))

    @classmethod
    @abc.abstractmethod
    def check_equal(cls, node, other):
        """ Check whether the two nodes are considered equal.

            :param node: some ast node
            :param other: some ast node

            :rtype: bool
            :returns: True if the nodes are considered equal, otherwise False

            If the method returns True, the nodes are actually equal, but it
            may return False when the nodes are equal.
        """
        raise NotImplementedError()

class PointlessFunctionDefinition(PointlessData):
    """ Looking for pointless function definitions. """

    _DEF_CLASS = astroid.Function
    message_id = "W9952"

    @classmethod
    def _retain_node(cls, node, restrict=True):
        return not restrict or \
           (len(node.body) == 1 and isinstance(node.body[0], astroid.Pass))

    @classmethod
    def check_equal(cls, node, other):
        return len(node.body) == 1 and isinstance(node.body[0], astroid.Pass) and \
           len(other.body) == 1 and isinstance(other.body[0], astroid.Pass)

    @staticmethod
    def _extract_value(node):
        return node

    @staticmethod
    def _extract_targets(node):
        yield node.name

class PointlessAssignment(PointlessData):

    _DEF_CLASS = astroid.Assign
    message_id = "W9951"

    _VALUE_CLASSES = (
        astroid.Const,
        astroid.Dict,
        astroid.List,
        astroid.Tuple
    )

    @classmethod
    def _retain_node(cls, node, restrict=True):
        return not restrict or isinstance(node.value, cls._VALUE_CLASSES)

    @classmethod
    def check_equal(cls, node, other):
        if type(node) != type(other):
            return False
        if isinstance(node, astroid.Const):
            return node.value == other.value
        if isinstance(node, (astroid.List, astroid.Tuple)):
            return len(node.elts) == len(other.elts) and \
               all(cls.check_equal(n, o) for (n, o) in zip(node.elts, other.elts))
        if isinstance(node, astroid.Dict):
            return len(node.items) == len(other.items)
        return False

    @staticmethod
    def _extract_value(node):
        return node.value

    @staticmethod
    def _extract_targets(node):
        for target in node.targets:
            yield target.name

class PointlessClassAttributeOverrideChecker(BaseChecker):
    """ If the nearest definition of the class attribute in the MRO assigns
        it the same value, then the overriding definition is said to be
        pointless.

        The algorithm for detecting a pointless attribute override is the following.

        * For each class, C:
           - For each attribute assignment,
               name_1 = name_2 ... name_n = l (where l is a literal):
              * For each n in (n_1, n_2):
                - Traverse the linearization of the MRO until the first
                   matching assignment n = l' is identified. If l is equal to l',
                   then consider that the assignment to l in C is a
                   pointless override.

        The algorithm for detecting a pointless method override has the same
        general structure, and the same defects discussed below.

        Note that this analysis is neither sound nor complete. It is unsound
        under multiple inheritance. Consider the following class hierarchy::

            class A(object):
                _attrib = False

            class B(A):
                _attrib = False

            class C(A):
                _attrib = True

            class D(B,C):
                pass

        In this  case, starting from B, B._attrib = False would be considered
        pointless. However, for D the MRO is B, C, A, and removing the assignment
        B._attrib = False would change the inherited value of D._attrib from
        False to True.

        The analysis is incomplete because it will find some values unequal when
        actually they are equal.

        The analysis is both incomplete and unsound because it expects that
        assignments will always be made by means of the same syntax.
    """

    __implements__ = (IAstroidChecker,)

    name = "pointless class attribute override checker"
    msgs = {
       "W9951":
       (
          "Assignment to class attribute %s overrides identical assignment in ancestor.",
          "pointless-class-attribute-override",
          "Assignment to class attribute  that overrides assignment in ancestor that assigns identical value has no effect."
       ),
       "W9952":
       (
          "definition of %s method overrides identical method definition in ancestor",
          "pointless-method-definition-override",
          "Overriding empty method definition with another empty method definition has no effect."
       )
    }

    @check_messages("W9951", "W9952")
    def visit_class(self, node):
        for checker in (PointlessAssignment, PointlessFunctionDefinition):
            for (name, value) in checker.get_data(node):
                for a in node.ancestors():
                    match = next((v for (n, v) in checker.get_data(a, False) if n == name), None)
                    if match is not None:
                        if checker.check_equal(value, match):
                            self.add_message(checker.message_id, node=value, args=(name,))
                        break

def register(linter):
    linter.register_checker(PointlessClassAttributeOverrideChecker(linter))
