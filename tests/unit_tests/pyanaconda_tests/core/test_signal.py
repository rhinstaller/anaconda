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

    def test_method(self):
        """Test if a method can be correctly connected to a signal."""
        signal = Signal()
        foo = FooClass()
        assert foo.var is None
        # connect the signal
        signal.connect(foo.set_var)
        # trigger the signal
        signal.emit("bar")
        # check if the callback triggered correctly
        assert foo.var == "bar"
        # try to trigger the signal again
        signal.emit("baz")
        assert foo.var == "baz"
        # now try to disconnect the signal
        signal.disconnect(foo.set_var)
        # check that calling the signal again
        # no longer triggers the callback
        signal.emit("anaconda")
        assert foo.var == "baz"

    def test_function(self):
        """Test if a local function can be correctly connected to a signal."""

        # create a local function
        def set_var(value):
            self.var = value

        signal = Signal()
        assert self.var is None
        # connect the signal
        signal.connect(set_var)
        # trigger the signal
        signal.emit("bar")
        # check if the callback triggered correctly
        assert self.var == "bar"
        # try to trigger the signal again
        signal.emit("baz")
        assert self.var == "baz"
        # now try to disconnect the signal
        signal.disconnect(set_var)
        # check that calling the signal again
        # no longer triggers the callback
        signal.emit("anaconda")
        assert self.var == "baz"

    def test_lambda(self):
        """Test if a lambda can be correctly connected to a signal."""
        foo = FooClass()
        signal = Signal()
        assert foo.var is None
        # connect the signal
        # pylint: disable=unnecessary-lambda
        lambda_instance = lambda x: foo.set_var(x)
        signal.connect(lambda_instance)
        # trigger the signal
        signal.emit("bar")
        # check if the callback triggered correctly
        assert foo.var == "bar"
        # try to trigger the signal again
        signal.emit("baz")
        assert foo.var == "baz"
        # now try to disconnect the signal
        signal.disconnect(lambda_instance)
        # check that calling the signal again
        # no longer triggers the callback
        signal.emit("anaconda")
        assert foo.var == "baz"

    def test_clear(self):
        """Test if the clear() method correctly clears any connected callbacks."""
        def set_var(value):
            self.var = value

        signal = Signal()
        foo = FooClass()
        lambda_foo = FooClass()
        assert foo.var is None
        assert lambda_foo.var is None
        assert self.var is None
        # connect the callbacks
        signal.connect(set_var)
        signal.connect(foo.set_var)
        # pylint: disable=unnecessary-lambda
        signal.connect(lambda x: lambda_foo.set_var(x))
        # trigger the signal
        signal.emit("bar")
        # check that the callbacks were triggered
        assert self.var == "bar"
        assert foo.var == "bar"
        assert lambda_foo.var == "bar"
        # clear the callbacks
        signal.clear()
        # trigger the signal again
        signal.emit("anaconda")
        # check that the callbacks were not triggered
        assert self.var == "bar"
        assert foo.var == "bar"
        assert lambda_foo.var == "bar"

    def test_signal_chain(self):
        """Check if signals can be chained together."""
        foo = FooClass()
        assert foo.var is None
        signal1 = Signal()
        signal1.connect(foo.set_var)
        signal2 = Signal()
        signal2.connect(signal1.emit)
        signal3 = Signal()
        signal3.connect(signal2.emit)
        # trigger the chain
        signal3.emit("bar")
        # check if the initial callback was triggered
        assert foo.var == "bar"
