#
# Martin Kolman <mkolman@redhat.com>
#
# Copyright 2016 Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use, modify,
# copy, or redistribute it subject to the terms and conditions of the GNU
# General Public License v.2.  This program is distributed in the hope that it
# will be useful, but WITHOUT ANY WARRANTY expressed or implied, including the
# implied warranties of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.  Any Red Hat
# trademarks that are incorporated in the source code or documentation are not
# subject to the GNU General Public License and may only be used or replicated
# with the express permission of Red Hat, Inc.
#
# Test the Python-based signal and slot implementation.
#

import unittest

from pyanaconda.core.signal import Signal

class FooClass(object):
    def __init__(self):
        self._var = None

    @property
    def var(self):
        return self._var

    def set_var(self, value):
        self._var = value

class SignalTestCase(unittest.TestCase):

    def setUp(self):
        self.var = None

    def method_test(self):
        """Test if a method can be correctly connected to a signal."""
        signal = Signal()
        foo = FooClass()
        self.assertIsNone(foo.var)
        # connect the signal
        signal.connect(foo.set_var)
        # trigger the signal
        signal.emit("bar")
        # check if the callback triggered correctly
        self.assertEqual(foo.var, "bar")
        # try to trigger the signal again
        signal.emit("baz")
        self.assertEqual(foo.var, "baz")
        # now try to disconnect the signal
        signal.disconnect(foo.set_var)
        # check that calling the signal again
        # no longer triggers the callback
        signal.emit("anaconda")
        self.assertEqual(foo.var, "baz")

    def function_test(self):
        """Test if a local function can be correctly connected to a signal."""

        # create a local function
        def set_var(value):
            self.var = value

        signal = Signal()
        self.assertIsNone(self.var)
        # connect the signal
        signal.connect(set_var)
        # trigger the signal
        signal.emit("bar")
        # check if the callback triggered correctly
        self.assertEqual(self.var, "bar")
        # try to trigger the signal again
        signal.emit("baz")
        self.assertEqual(self.var, "baz")
        # now try to disconnect the signal
        signal.disconnect(set_var)
        # check that calling the signal again
        # no longer triggers the callback
        signal.emit("anaconda")
        self.assertEqual(self.var, "baz")

    def lambda_test(self):
        """Test if a lambda can be correctly connected to a signal."""
        foo = FooClass()
        signal = Signal()
        self.assertIsNone(foo.var)
        # connect the signal
        # pylint: disable=unnecessary-lambda
        lambda_instance = lambda x: foo.set_var(x)
        signal.connect(lambda_instance)
        # trigger the signal
        signal.emit("bar")
        # check if the callback triggered correctly
        self.assertEqual(foo.var, "bar")
        # try to trigger the signal again
        signal.emit("baz")
        self.assertEqual(foo.var, "baz")
        # now try to disconnect the signal
        signal.disconnect(lambda_instance)
        # check that calling the signal again
        # no longer triggers the callback
        signal.emit("anaconda")
        self.assertEqual(foo.var, "baz")

    def clear_test(self):
        """Test if the clear() method correctly clears any connected callbacks."""
        def set_var(value):
            self.var = value

        signal = Signal()
        foo = FooClass()
        lambda_foo = FooClass()
        self.assertIsNone(foo.var)
        self.assertIsNone(lambda_foo.var)
        self.assertIsNone(self.var)
        # connect the callbacks
        signal.connect(set_var)
        signal.connect(foo.set_var)
        # pylint: disable=unnecessary-lambda
        signal.connect(lambda x: lambda_foo.set_var(x))
        # trigger the signal
        signal.emit("bar")
        # check that the callbacks were triggered
        self.assertEqual(self.var, "bar")
        self.assertEqual(foo.var, "bar")
        self.assertEqual(lambda_foo.var, "bar")
        # clear the callbacks
        signal.clear()
        # trigger the signal again
        signal.emit("anaconda")
        # check that the callbacks were not triggered
        self.assertEqual(self.var, "bar")
        self.assertEqual(foo.var, "bar")
        self.assertEqual(lambda_foo.var, "bar")

    def signal_chain_test(self):
        """Check if signals can be chained together."""
        foo = FooClass()
        self.assertIsNone(foo.var)
        signal1 = Signal()
        signal1.connect(foo.set_var)
        signal2 = Signal()
        signal2.connect(signal1.emit)
        signal3 = Signal()
        signal3.connect(signal2.emit)
        # trigger the chain
        signal3.emit("bar")
        # check if the initial callback was triggered
        self.assertEqual(foo.var, "bar")
