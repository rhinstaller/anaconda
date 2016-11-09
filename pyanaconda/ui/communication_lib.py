# The library for asynchronous communication.
#
# Copyright (C) 2016  Red Hat, Inc.
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
# Author(s):  Vendula Poncova <vponcova@redhat.com>
#
import logging
import sys

log = logging.getLogger("anaconda")


def register_event_handler(handlers, event, callback, data=None):
    """Register a callback which will be called when message
    "event" is encountered during process_events.

    The callback has to accept two arguments:
    - the received message in the form of (type, [arguments])
    - the data registered with the handler

    :param handlers: the registered handlers
    :type handlers: dict[event id] -> [list of tuples (callback, data)]

    :param event: the id of the event we want to react on
    :type event: number|string

    :param event: the id of the event we want to react on
    :type event: number|string

    :param callback: the callback function
    :type callback: func(event_message, data)

    :param data: optional data to pass to callback
    :type data: anything
    """
    if event not in handlers:
        handlers[event] = []
    handlers[event].append((callback, data))


def process_events(queue_instance, handlers, exception_handler=None, return_at=None):
    """Process the incoming async messages and return when
    a specific message is encountered or when the queue_instance
    is empty.

    If return_at message was specified, the received message
    is returned.

    If the message does not fit return_at, but handlers are
    defined then it processes all handlers for this message.

    :param queue_instance: a queue for async communication
    :type queue_instance: instance of queue

    :param handlers: the registered handlers
    :type handlers: dict[event id] -> [list of tuples (callback, data)]

    :param exception_handler: the handler of exceptions caused
    by other handlers
    :type exception_handler: func(exception, data)

    :param return_at: the id of the message we are waiting for
    :type return_at: number|string

    :rtype: None | specified event
    """
    while return_at or not queue_instance.empty():
        event = queue_instance.get()
        if event[0] == return_at:
            return event
        elif event[0] in handlers:
            for handler, data in handlers[event[0]]:
                try:
                    handler(event, data)
                except Exception as exception:  # pylint: disable=broad-except
                    if exception_handler:
                        handler, data = exception_handler
                        handler(queue_instance, exception, data)


def send_exception(queue_instance, exception):
    """Send an exception to the queue.

    :param queue_instance: a queue for async communication
    :type queue_instance: instance of queue

    :param exception: an exception
    :type exception: subclass of Exception
    """
    from pyanaconda.ui.communication import hubQ
    queue_instance.put((hubQ.HUB_CODE_EXCEPTION, [exception]))


def process_progress(handlers, periodic_handler=None):
    """Handle progress updates from progressQ.

    :param handlers: the registered handlers
    :type handlers: dict[event id] -> [list of tuples (callback, data)]

    :param periodic_handler: the handler that will be called periodically
    :type periodic_handler: func(data)
    """
    from pyanaconda.progress import progressQ
    import queue

    q = progressQ.q

    code = None
    args = None

    # Grab all messages may have appeared since last time this method ran.
    while True:
        # Attempt to get a message out of the queue for how we should update
        # the progress bar. If there's no message, don't error out.
        # Also flush the communication Queue at least once a second and
        # process it's events so we can react to async evens (like a thread
        # throwing an exception).
        while True:

            try:
                (code, args) = q.get(timeout=1)
                break
            except queue.Empty:
                pass
            finally:
                if periodic_handler:
                    handler, data = periodic_handler
                    handler(data)

        if code == progressQ.PROGRESS_CODE_COMPLETE:
            q.task_done()

        # Handle the message.
        if code in handlers:
            for handler, data in handlers[code]:
                result = handler(code, args, data)
                if result is not None:
                    return result

        # Quit the cycle.
        elif code == progressQ.PROGRESS_CODE_COMPLETE:
            break
        # Quit.
        elif code == progressQ.PROGRESS_CODE_QUIT:
            sys.exit(args[0])

        q.task_done()
    return True
