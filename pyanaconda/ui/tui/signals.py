# Anaconda custom signals used in the Simpleline library.
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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Author(s): Jiri Konecny <jkonecny@redhat.com>
#

from simpleline.event_loop.signals import AbstractSignal


class SendMessageSignal(AbstractSignal):
    """Send message to the main thread."""

    def __init__(self, source, msg_fn, args, ret_queue):
        """
        :param source: source of this signal
        :type source: class which emits this signal
        :param msg_fn: message dialog function requested to be called
        :type msg_fn: a function taking the same number of arguments as is the
                      length of the args param
        :param args: arguments to be passed to the message dialog function
        :type args: any
        :param ret_queue: the queue which the return value of the message dialog
                          function should be put
        :type ret_queue: a queue.Queue instance
        """
        super().__init__(source)

        self.msg_fn = msg_fn
        self.args = args
        self.ret_queue = ret_queue
