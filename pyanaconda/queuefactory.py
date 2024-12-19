#
# queue.py: factory for creating communications channels
#
# Copyright (C) 2013  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import queue

from pyanaconda.core.string import lower_ascii, upper_ascii


class QueueFactory:
    """Constructs a new object wrapping a Queue.Queue, complete with constants
       and sending functions for each type of message that can be put into the
       queue.

       Creating a new object using this class is done like so:

           q = QueueFactory("progress")

       And then adding messages to it is done like so:

           q.addMessage("init", 0)
           q.addMessage("step", 1)

       The first call will create a new constant named PROGRESS_CODE_INIT and a
       method named send_init that takes zero arguments.  The second call will
       create a new constant named PROGRESS_CODE_STEP and a method named send_step
       that takes one argument.

       Reusing names within the same class is not allowed.
    """
    def __init__(self, name):
        self.name = name

        self.__counter = 0
        self.__names = []

        self.q = queue.Queue()

    def _makeMethod(self, constant, methodName, argc):
        # pylint: disable=unused-private-member
        def __method(*args):
            if len(args) != argc:
                raise TypeError("%s() takes exactly %d arguments (%d given)" %
                                (methodName, argc, len(args)))

            self.q.put((constant, args))

        __method.__name__ = methodName
        return __method

    def addMessage(self, name, argc):
        if name in self.__names:
            raise AttributeError("%s queue already has a message named %s" % (self.name, name))

        # Add a constant.
        const_name = upper_ascii(self.name) + "_CODE_" + upper_ascii(name)
        setattr(self, const_name, self.__counter)
        self.__counter += 1

        # Add a convenience method for putting things into the queue.
        method_name = "send_" + lower_ascii(name)
        method = self._makeMethod(getattr(self, const_name), method_name, argc)
        setattr(self, method_name, method)

        self.__names.append(name)
