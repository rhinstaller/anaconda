#
# Copyright (C) 2017  Red Hat, Inc.
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
# Red Hat Author(s): Vendula Poncova <vponcova@redhat.com>
#

import unittest
from pyanaconda.dbus.interface import XMLGenerator


class XMLGeneratorTestCase(unittest.TestCase):

    def _compare(self, element, xml):
        self.assertEqual(XMLGenerator.element_to_xml(element), xml)

    def node_test(self):
        """Test the node element."""
        self._compare(XMLGenerator.get_node_element(), '<node />')

    def interface_test(self):
        """Test the interface element."""
        self._compare(
            XMLGenerator.get_interface_element("InterfaceName"),
            '<interface name="InterfaceName" />'
        )

    def parameter_test(self):
        """Test the parameter element."""
        self._compare(
            XMLGenerator.create_parameter("ParameterName",
                                          "ParameterType",
                                          "ParameterDirection"),
            '<arg '
            'direction="ParameterDirection" '
            'name="ParameterName" '
            'type="ParameterType" />')

    def property_test(self):
        """Test the property element."""
        self._compare(
            XMLGenerator.create_property("PropertyName",
                                         "PropertyType",
                                         "PropertyAccess"),
            '<property '
            'access="PropertyAccess" '
            'name="PropertyName" '
            'type="PropertyType" />'
        )

    def method_test(self):
        """Test the method element."""
        element = XMLGenerator.get_method_element("MethodName")
        xml = '<method name="MethodName" />'
        self._compare(element, xml)

    def signal_test(self):
        """Test the signal element."""
        element = XMLGenerator.get_signal_element("SignalName")
        xml = '<signal name="SignalName" />'
        self._compare(element, xml)
