""" A signal/slot implementation

File:    signal.py
Author:  Thiago Marcos P. Santos
Author:  Christopher S. Case
Author:  David H. Bronke
Created: August 28, 2008
Updated: December 12, 2011
License: MIT

"""
import inspect
from weakref import WeakKeyDictionary


class Signal:
    def __init__(self):
        # The original implementation used WeakSet to store functions,
        # but that causes lambdas without any other reference to be
        # garbage collected. So we use a normal set to avoid that.
        self._functions = set()
        self._methods = WeakKeyDictionary()

    # The original implementation used __call__, so one would just call the signal itself:
    #
    # my_signal("foo")
    #
    # This has been changed to the emit() method to both be more consistent with how signals/slots
    # work in Qt & GTK and to make it more easily apparent that a signal is being triggered.
    # The correct way to trigger a signal is therefore:
    #
    # my_signal.emit("foo")
    def emit(self, *args, **kargs):
        # Call handler functions
        for func in self._functions.copy():
            func(*args, **kargs)

        # Call handler methods
        for obj, funcs in self._methods.copy().items():
            for func in funcs.copy():
                func(obj, *args, **kargs)

    def connect(self, slot):
        if inspect.ismethod(slot):
            if slot.__self__ not in self._methods:
                self._methods[slot.__self__] = set()

            self._methods[slot.__self__].add(slot.__func__)

        else:
            self._functions.add(slot)

    def disconnect(self, slot):
        if inspect.ismethod(slot):
            if slot.__self__ in self._methods:
                self._methods[slot.__self__].discard(slot.__func__)
        else:
            if slot in self._functions:
                self._functions.discard(slot)

    def clear(self):
        self._functions.clear()
        self._methods.clear()
