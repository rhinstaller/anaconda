# The main file for anaconda TUI interface
#
# Copyright (C) (2012)  Red Hat, Inc.
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
from pyanaconda import ui
from pyanaconda.core.constants import IPMI_ABORTED, QUIT_MESSAGE
from pyanaconda.flags import flags
from pyanaconda.core.threads import thread_manager
from pyanaconda.core.util import ipmi_report
from pyanaconda.ui.tui.hubs.summary import SummaryHub
from pyanaconda.ui.tui.signals import SendMessageSignal
from pyanaconda.ui.tui.spokes import StandaloneSpoke
from pyanaconda.ui.tui.tuiobject import IpmiErrorDialog

from simpleline import App
from simpleline.event_loop.glib_event_loop import GLibEventLoop
from simpleline.event_loop.signals import ExceptionSignal
from simpleline.input.input_handler import InputHandler
from simpleline.render.adv_widgets import YesNoDialog
from simpleline.render.screen_handler import ScreenHandler

import os
import sys
import site
import queue
import meh.ui.text
from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

exception_processed = False


def exception_msg_handler(signal, data):
    """
    Handler for the ExceptionSignal signal.

    :param signal: event data
    :type signal: (event_type, message_data)
    :param data: additional data
    :type data: any
    """
    global exception_processed
    if exception_processed:
        # get data from the event data structure
        exception_info = signal.exception_info

        stack_trace = "\n" + App.get_scheduler().dump_stack()
        log.error(stack_trace)
        # exception_info is a list
        sys.excepthook(*exception_info)
    else:
        # show only the first exception do not spam user with others
        exception_processed = True
        loop = App.get_event_loop()
        # start new loop for handling the exception
        # this will stop processing all the old signals and prevent raising new exceptions
        loop.execute_new_loop(signal)


def tui_quit_callback(data):
    ipmi_report(IPMI_ABORTED)


class TextUserInterface(ui.UserInterface):
    """This is the main class for Text user interface.

       .. inheritance-diagram:: TextUserInterface
          :parts: 3
    """

    ENVIRONMENT = "anaconda"

    def __init__(self, storage, payload,
                 productTitle="Anaconda", isFinal=True,
                 quitMessage=QUIT_MESSAGE):
        """
        For detailed description of the arguments see
        the parent class.

        :param storage: storage backend reference
        :type storage: instance of pyanaconda.Storage

        :param payload: payload (usually dnf) reference
        :type payload: instance of payload handler

        :param productTitle: the name of the product
        :type productTitle: str

        :param isFinal: Boolean that marks the release
                        as final (True) or development
                        (False) version.
        :type isFinal: bool

        :param quitMessage: The text to be used in quit
                            dialog question. It should not
                            be translated to allow for change
                            of language.
        :type quitMessage: str
        """

        super().__init__(storage, payload)
        self._meh_interface = meh.ui.text.TextIntf()

        self.productTitle = productTitle
        self.isFinal = isFinal
        self.quitMessage = quitMessage

    basemask = "pyanaconda.ui"
    basepath = os.path.dirname(os.path.dirname(__file__))
    sitepackages = [os.path.join(dir, "pyanaconda", "ui")
                    for dir in site.getsitepackages()]
    pathlist = set([basepath] + sitepackages)

    _categories = []
    _spokes = []
    _hubs = []

    # as list comprehension can't reference class level variables in Python 3 we
    # need to use a for cycle (http://bugs.python.org/issue21161)
    for path in pathlist:
        _categories.append((basemask + ".categories.%s", os.path.join(path, "categories")))
        _spokes.append((basemask + ".tui.spokes.%s", os.path.join(path, "tui/spokes")))
        _hubs.append((basemask + ".tui.hubs.%s", os.path.join(path, "tui/hubs")))

    paths = ui.UserInterface.paths + {
        "categories": _categories,
        "spokes": _spokes,
        "hubs": _hubs,
    }

    @property
    def tty_num(self):
        return 1

    @property
    def meh_interface(self):
        return self._meh_interface

    def _list_hubs(self):
        """Returns the list of hubs to use."""
        return [SummaryHub]

    def _is_standalone(self, spoke):
        """Checks if the passed spoke is standalone."""
        return isinstance(spoke, StandaloneSpoke)

    def setup(self, data):
        """Construct all the objects required to implement this interface.

        This method must be provided by all subclasses.
        """
        # Use GLib event loop for the Simpleline TUI
        loop = GLibEventLoop()
        App.initialize(event_loop=loop)

        loop.set_quit_callback(tui_quit_callback)
        scheduler = App.get_scheduler()
        scheduler.quit_screen = YesNoDialog(self.quitMessage)

        # tell python-meh it should use our raw_input
        meh_io_handler = meh.ui.text.IOHandler(in_func=self._get_meh_input_func)
        self._meh_interface.set_io_handler(meh_io_handler)

        # register handlers for various messages
        loop = App.get_event_loop()
        loop.register_signal_handler(ExceptionSignal, exception_msg_handler)
        loop.register_signal_handler(SendMessageSignal, self._handle_show_message)

        _hubs = self._list_hubs()

        # First, grab a list of all the standalone spokes.
        spokes = self._collectActionClasses(self.paths["spokes"], StandaloneSpoke)
        actionClasses = self._orderActionClasses(spokes, _hubs)

        for klass in actionClasses:
            obj = klass(data, self.storage, self.payload)

            # If we are doing a kickstart install, some standalone spokes
            # could already be filled out.  In that case, we do not want
            # to display them.
            if self._is_standalone(obj) and obj.completed:
                del(obj)
                continue

            if hasattr(obj, "set_path"):
                obj.set_path("spokes", self.paths["spokes"])
                obj.set_path("categories", self.paths["categories"])

            should_schedule = obj.setup(self.ENVIRONMENT)

            if should_schedule:
                scheduler.schedule_screen(obj)

    def _get_meh_input_func(self, text_prompt):
        handler = InputHandler(source=self.meh_interface)
        handler.skip_concurrency_check = True
        handler.get_input(text_prompt)
        handler.wait_on_input()
        return handler.value

    def run(self):
        """Run the interface.

        This should do little more than just pass through to something else's run method,
        but is provided here in case more is needed.  This method must be provided by all subclasses.
        """
        return App.run()

    ###
    ### MESSAGE HANDLING METHODS
    ###
    def _send_show_message(self, msg_fn, args, ret_queue):
        """ Send message requesting to show some message dialog specified by the message function.

        :param msg_fn: message dialog function requested to be called
        :type msg_fn: a function taking the same number of arguments as is the
                      length of the args param
        :param args: arguments to be passed to the message dialog function
        :type args: any
        :param ret_queue: the queue which the return value of the message dialog
                          function should be put
        :type ret_queue: a queue.Queue instance
        """

        signal = SendMessageSignal(self, msg_fn=msg_fn, args=args, ret_queue=ret_queue)
        loop = App.get_event_loop()
        loop.enqueue_signal(signal)

    def _handle_show_message(self, signal, data):
        """Handler for the SendMessageSignal signal.

        :param signal: SendMessage signal
        :type signal: instance of the SendMessageSignal class
        :param data: additional data
        :type data: any
        """
        msg_fn = signal.msg_fn
        args = signal.args
        ret_queue = signal.ret_queue

        ret_queue.put(msg_fn(*args))

    def _show_message_in_main_thread(self, msg_fn, args):
        """ If running in the main thread, run the message dialog function and
        return its return value. If running in a non-main thread, request the
        message function to be called in the main thread.

        :param msg_fn: message dialog function to be run
        :type msg_fn: a function taking the same number of arguments as is the
                      length of the args param
        :param args: arguments to be passed to the message dialog function
        :type args: any
        """

        if thread_manager.in_main_thread():
            # call the function directly
            return msg_fn(*args)
        else:
            # create a queue for the result returned by the function
            ret_queue = queue.Queue()

            # request the function to be called in the main thread
            self._send_show_message(msg_fn, args, ret_queue)

            # wait and return the result from the queue
            return ret_queue.get()

    def showError(self, message):
        """Display an error dialog with the given message.

        After this dialog is displayed, anaconda will quit. There is no return value.
        This method must be implemented by all UserInterface subclasses.

        In the code, this method should be used sparingly and only for
        critical errors that anaconda cannot figure out how to recover from.
        """

        return self._show_message_in_main_thread(self._showError, (message,))

    def _showError(self, message):
        """Internal helper function that MUST BE CALLED FROM THE MAIN THREAD."""

        if flags.automatedInstall and not flags.ksprompt:
            log.error(message)
            # If we're in cmdline mode, just exit.
            return

        error_window = IpmiErrorDialog(message)
        ScreenHandler.push_screen_modal(error_window)

    def showDetailedError(self, message, details, buttons=None):
        return self._show_message_in_main_thread(self._showDetailedError, (message, details))

    def _showDetailedError(self, message, details):
        """Internal helper function that MUST BE CALLED FROM THE MAIN THREAD."""
        return self.showError(message + "\n\n" + details)

    def showYesNoQuestion(self, message):
        """Display a dialog with the given message that presents the user a yes or no choice.

        This method returns True if the yes choice is selected,
        and False if the no choice is selected.  From here, anaconda can
        figure out what to do next.  This method must be implemented by all
        UserInterface subclasses.

        In the code, this method should be used sparingly and only for those
        times where anaconda cannot make a reasonable decision.  We don't
        want to overwhelm the user with choices.

        When cmdline mode is active, the default will be to answer no.
        """

        return self._show_message_in_main_thread(self._showYesNoQuestion, (message,))

    def _showYesNoQuestion(self, message):
        """Internal helper function that MUST BE CALLED FROM THE MAIN THREAD."""

        if flags.automatedInstall and not flags.ksprompt:
            log.error(message)
            # If we're in cmdline mode, just say no.
            return False

        question_window = YesNoDialog(message)
        ScreenHandler.push_screen_modal(question_window)

        return question_window.answer
