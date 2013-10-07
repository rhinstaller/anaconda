# Base classes for the Anaconda TUI framework.
#
# Copyright (C) 2012  Red Hat, Inc.
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
# Red Hat Author(s): Martin Sivak <msivak@redhat.com>
#

__all__ = ["App", "UIScreen", "Widget"]

import sys
import Queue
import getpass
import threading
from pyanaconda.threads import threadMgr, AnacondaThread
from pyanaconda.ui.communication import hubQ
from pyanaconda import constants
from pyanaconda.i18n import _, N_

RAW_INPUT_LOCK = threading.Lock()


def send_exception(queue, ex):
    queue.put((hubQ.HUB_CODE_EXCEPTION, [ex]))


class ExitMainLoop(Exception):
    """This exception ends the outermost mainloop. Used internally when dialogs
       close."""
    pass

class ExitAllMainLoops(ExitMainLoop):
    """This exception ends the whole App mainloop structure. App.run() returns
       False after the exception is processed."""
    pass

class App(object):
    """This is the main class for TUI screen handling. It is responsible for
       mainloop control and keeping track of the screen stack.

       Screens are organized in stack structure so it is possible to return
       to caller when dialog or sub-screen closes.

       It supports four window transitions:
       - show new screen replacing the current one (linear progression)
       - show new screen keeping the current one in stack (hub & spoke)
       - show new screen and wait for it to end (dialog)
       - close current window and return to the next one in stack
       """

    START_MAINLOOP = True
    STOP_MAINLOOP = False
    NOP = None

    def __init__(self, title, yes_or_no_question = None, width = 80, queue = None,
                 quit_message = None):
        """
        :param title: application title for whenever we need to display app name
        :type title: unicode

        :param yes_or_no_question: UIScreen object class used for Quit dialog
        :type yes_or_no_question: class UIScreen accepting additional message arg

        :param width: screen width for rendering purposes
        :type width: int
        """

        self._header = title
        self._redraw = True
        self._spacer = "\n".join(2*[width*"="])
        self._width = width
        self.quit_question = yes_or_no_question
        self.quit_message = quit_message or N_(u"Do you really want to quit?")

        # async control queue
        if queue:
            self.queue = queue
        else:
            self.queue = Queue.Queue()

        # ensure unique thread names
        self._in_thread_counter = 0

        # event handlers
        # key: event id
        # value: list of tuples (callback, data)
        self._handlers = {}

        # screen stack contains triplets
        #  UIScreen to show
        #  arguments for it's show method
        #  value indicating whether new mainloop is needed
        #   - None = do nothing
        #   - True = execute new loop
        #   - False = already running loop, exit when window closes
        self._screens = []

    def register_event_handler(self, event, callback, data = None):
        """This method registers a callback which will be called
           when message "event" is encountered during process_events.

           The callback has to accept two arguments:
             - the received message in the form of (type, [arguments])
             - the data registered with the handler

           :param event: the id of the event we want to react on
           :type event: number|string

           :param callback: the callback function
           :type callback: func(event_message, data)

           :param data: optional data to pass to callback
           :type data: anything
        """
        if not event in self._handlers:
            self._handlers[event] = []
        self._handlers[event].append((callback, data))

    def _thread_input(self, queue, prompt, hidden):
        """This method is responsible for interruptible user input. It is expected
        to be used in a thread started on demand by the App class and returns the
        input via the communication Queue.

        :param queue: communication queue to be used
        :type queue: Queue.Queue instance

        :param prompt: prompt to be displayed
        :type prompt: str

        :param hidden: whether typed characters should be echoed or not
        :type hidden: bool

        """

        if hidden:
            data = getpass.getpass(prompt)
        else:
            sys.stdout.write(prompt)
            sys.stdout.flush()
            # XXX: only one raw_input can run at a time, don't schedule another
            # one as it would cause weird behaviour and block other packages'
            # raw_inputs
            if not RAW_INPUT_LOCK.acquire(False):
                # raw_input is already running
                return
            else:
                # lock acquired, we can run raw_input
                data = raw_input()
                RAW_INPUT_LOCK.release()

        queue.put((hubQ.HUB_CODE_INPUT, [data]))

    def switch_screen(self, ui, args = None):
        """Schedules a screen to replace the current one.

        :param ui: screen to show
        :type ui: instance of UIScreen

        :param args: optional argument to pass to ui's refresh method (can be used to select what item should be displayed or so)
        :type args: anything

        """

        # (oldscr, oldattr, oldloop)
        oldloop = self._screens.pop()[2]

        # we have to keep the oldloop value so we stop
        # dialog's mainloop if it ever uses switch_screen
        self._screens.append((ui, args, oldloop))
        self.redraw()

    def switch_screen_with_return(self, ui, args = None):
        """Schedules a screen to show, but keeps the current one in stack
           to return to, when the new one is closed.

        :param ui: screen to show
        :type ui: UIScreen instance

        :param args: optional argument, please see switch_screen for details
        :type args: anything
        """

        self._screens.append((ui, args, self.NOP))

        self.redraw()

    def switch_screen_modal(self, ui, args = None):
        """Starts a new screen right away, so the caller can collect data back.
        When the new screen is closed, the caller is redisplayed.

        This method does not return until the new screen is closed.

        :param ui: screen to show
        :type ui: UIScreen instance

        :param args: optional argument, please see switch_screen for details
        :type args: anything
        """

        # set the third item to True so new loop gets started
        self._screens.append((ui, args, self.START_MAINLOOP))
        self._do_redraw()

    def schedule_screen(self, ui, args = None):
        """Add screen to the bottom of the stack. This is mostly usefull
        at the beginning to prepare the first screen hierarchy to display.

        :param ui: screen to show
        :type ui: UIScreen instance

        :param args: optional argument, please see switch_screen for details
        :type args: anything
        """
        self._screens.insert(0, (ui, args, self.NOP))

    def close_screen(self, scr = None):
        """Close the currently displayed screen and exit it's main loop
        if necessary. Next screen from the stack is then displayed.

        :param scr: if an UIScreen instance is passed it is checked to be the screen we are trying to close.
        :type scr: UIScreen instance
        """

        oldscr, _oldattr, oldloop = self._screens.pop()
        if scr is not None:
            assert oldscr == scr

        # this cannot happen, if we are closing the window,
        # the loop must have been running or not be there at all
        assert oldloop != self.START_MAINLOOP

        # we are in modal window, end it's loop
        if oldloop == self.STOP_MAINLOOP:
            raise ExitMainLoop()

        if self._screens:
            self.redraw()
        else:
            raise ExitMainLoop()

    def _do_redraw(self):
        """Draws the current screen and returns True if user input is requested.
           If modal screen is requested, starts a new loop and initiates redraw after it ends.

           :return: this method returns True if user input processing is requested
           :rtype: bool
           """

        # there is nothing to display, exit
        if not self._screens:
            raise ExitMainLoop()

        # get the screen from the top of the stack
        screen, args, newloop = self._screens[-1]

        # new mainloop is requested
        if newloop == self.START_MAINLOOP:
            # change the record to indicate mainloop is running
            self._screens.pop()
            self._screens.append((screen, args, self.STOP_MAINLOOP))
            # start the mainloop
            self._mainloop()
            # after the mainloop ends, set the redraw flag
            # and skip the input processing once, to redisplay the screen first
            self.redraw()
            input_needed = False
        elif self._redraw:
            # get the widget tree from the screen and show it in the screen
            try:
                input_needed = screen.refresh(args)
                screen.window.show_all()
                self._redraw = False
            except ExitMainLoop:
                raise
            except Exception:
                send_exception(self.queue, sys.exc_info())
                return False

        else:
            # this can happen only in case there was invalid input and prompt
            # should be shown again
            input_needed = True

        return input_needed

    def run(self):
        """This methods starts the application. Do not use self.mainloop() directly
        as run() handles all the required exceptions needed to keep nested mainloops
        working."""

        try:
            self._mainloop()
            return True
        except ExitAllMainLoops:
            return False

    def _mainloop(self):
        """Single mainloop. Do not use directly, start the application using run()."""

        # ask for redraw by default
        self._redraw = True

        # inital state
        last_screen = None
        error_counter = 0

        # run until there is nothing else to display
        while self._screens:
            # process asynchronous events
            self.process_events()

            # if redraw is needed, separate the content on the screen from the
            # stuff we are about to display now
            if self._redraw:
                print self._spacer

            try:
                # draw the screen if redraw is needed or the screen changed
                # (unlikely to happen separately, but just be sure)
                if self._redraw or last_screen != self._screens[-1][0]:
                    # we have fresh screen, reset error counter
                    error_counter = 0
                    if not self._do_redraw():
                        # if no input processing is requested, go for another cycle
                        continue

                last_screen = self._screens[-1][0]

                # get the screen's prompt
                try:
                    prompt = last_screen.prompt(self._screens[-1][1])
                except ExitMainLoop:
                    raise
                except Exception:
                    send_exception(self.queue, sys.exc_info())
                    continue

                # None means prompt handled the input by itself
                # ask for redraw and continue
                if prompt is None:
                    self.redraw()
                    continue

                # get the input from user
                c = self.raw_input(prompt)

                # process the input, if it wasn't processed (valid)
                # increment the error counter
                if not self.input(self._screens[-1][1], c):
                    error_counter += 1
                else:
                    # input was successfully processed, but no other screen was
                    # scheduled, just redraw the screen to display current state
                    self.redraw()

                # redraw the screen after 5 bad inputs
                if error_counter >= 5:
                    self.redraw()

            # propagate higher to end all loops
            # not really needed here, but we might need
            # more processing in the future
            except ExitAllMainLoops:
                raise

            # end just this loop
            except ExitMainLoop:
                break

    def process_events(self, return_at = None):
        """This method processes incoming async messages and returns
           when a specific message is encountered or when the queue
           is empty.

           If return_at message was specified, the received
           message is returned.

           If the message does not fit return_at, but handlers are
           defined then it processes all handlers for this message
        """
        while return_at or not self.queue.empty():
            event = self.queue.get()
            if event[0] == return_at:
                return event
            elif event[0] in self._handlers:
                for handler, data in self._handlers[event[0]]:
                    try:
                        handler(event, data)
                    except ExitMainLoop:
                        raise
                    except Exception:
                        send_exception(self.queue, sys.exc_info())

    def raw_input(self, prompt, hidden=False):
        """This method reads one input from user. Its basic form has only one
        line, but we might need to override it for more complex apps or testing."""

        thread_name = "%s%d" % (constants.THREAD_INPUT_BASENAME,
                                self._in_thread_counter)
        self._in_thread_counter += 1
        input_thread = AnacondaThread(name=thread_name,
                                      target=self._thread_input,
                                      args=(self.queue, prompt, hidden))
        input_thread.daemon = True
        threadMgr.add(input_thread)
        event = self.process_events(return_at=hubQ.HUB_CODE_INPUT)
        return event[1][0] # return the user input

    def input(self, args, key):
        """Method called internally to process unhandled input key presses.
        Also handles the main quit and close commands.

        :param args: optional argument passed from switch_screen calls
        :type args: anything

        :param key: the string entered by user
        :type key: unicode

        :return: True if key was processed, False if it was not recognized
        :rtype: True|False

        """

        # delegate the handling to active screen first
        if self._screens:
            try:
                key = self._screens[-1][0].input(args, key)
                if key is None:
                    return True
            except ExitMainLoop:
                raise
            except Exception:
                send_exception(self.queue, sys.exc_info())
                return False

        # global refresh command
        # TRANSLATORS: 'r' to refresh
        if self._screens and (key == _('r')):
            self._do_redraw()
            return True

        # global close command
        # TRANSLATORS: 'c' to continue
        if self._screens and (key == _('c')):
            self.close_screen()
            return True

        # global quit command
        # TRANSLATORS: 'q' to quit
        elif self._screens and (key == _('q')):
            if self.quit_question:
                d = self.quit_question(self, _(self.quit_message))
                self.switch_screen_modal(d)
                if d.answer:
                    raise ExitAllMainLoops()
            return True

        return False

    def redraw(self):
        """Set the redraw flag so the screen is refreshed as soon as possible."""
        self._redraw = True

    @property
    def header(self):
        return self._header

    @property
    def width(self):
        """Return the total width of screen space we have available."""
        return self._width

class UIScreen(object):
    """Base class representing one TUI Screen. Shares some API with anaconda's GUI
    to make it easy for devs to create similar UI with the familiar API."""

    # title line of the screen
    title = u"Screen.."

    def __init__(self, app, screen_height = 25):
        """
        :param app: reference to application main class
        :type app: instance of class App

        :param screen_height: height of the screen (useful for printing long widgets)
        :type screen_height: int
        """

        self._app = app
        self._screen_height = screen_height

        # list that holds the content to be printed out
        self._window = []

        # index of the page (subset of screen) shown during show_all
        # indexing starts with 0
        self._page = 0

    def setup(self, environment):
        """
        Do additional setup right before this screen is used.

        :param environment: environment (see pyanaconda.constants) the UI is running in
        :type environment: either FIRSTBOOT_ENVIRON or ANACONDA_ENVIRON
        :return: whether this screen should be scheduled or not
        :rtype: bool

        """

        return True

    def refresh(self, args = None):
        """Method which prepares the content desired on the screen to self._window.

        :param args: optional argument passed from switch_screen calls
        :type args: anything

        :return: has to return True if input processing is requested, otherwise
                 the screen will get printed and the main loop will continue
        :rtype: True|False
        """

        self._window = [self.title, u""]
        return True

    @property
    def window(self):
        """Return reference to the window instance. In TUI, just return self."""
        return self

    def _print_long_widget(self, widget):
        """Prints a long widget (possibly longer than the screen height) with
           user interaction (when needed).

           :param widget: possibly long widget to print
           :type widget: Widget instance

        """

        pos = 0
        lines = widget.get_lines()
        num_lines = len(lines)

        if num_lines < self._screen_height - 2:
            # widget plus prompt are shorter than screen height, just print the widget
            print u"\n".join(lines)
            return

        # long widget, print it in steps and prompt user to continue
        last_line = num_lines - 1
        while pos <= last_line:
            if pos + self._screen_height - 2 > last_line:
                # enough space to print the rest of the widget plus regular
                # prompt (2 lines)
                for line in lines[pos:]:
                    print line
                pos += self._screen_height - 1
            else:
                # print part with a prompt to continue
                for line in lines[pos:(pos + self._screen_height - 2)]:
                    print line
                self._app.raw_input(_("Press ENTER to continue"))
                pos += self._screen_height - 1

    def show_all(self):
        """Prepares all elements of self._window for output and then prints
        them on the screen."""

        for w in self._window:
            if hasattr(w, "render"):
                # pylint: disable-msg=E1101
                w.render(self.app.width)
            if isinstance(w, Widget):
                self._print_long_widget(w)
            else:
                # not a widget, just print its unicode representation
                print unicode(w)
    show = show_all

    def hide(self):
        """This does nothing in TUI, it is here to make API similar."""
        pass

    def input(self, args, key):
        """Method called to process input. If the input is not handled here, return it.

        :param key: input string to process
        :type key: unicode

        :param args: optional argument passed from switch_screen calls
        :type args: anything

        :return: return True or INPUT_PROCESSED (None) if key was handled,
                 INPUT_DISCARDED (False) if the screen should not process input
                 on the App and key if you want it to.
        :rtype: True|False|None|unicode
        """

        return key

    def prompt(self, args = None):
        """Return the text to be shown as prompt or handle the prompt and return None.

        :param args: optional argument passed from switch_screen calls
        :type args: anything

        :return: returns text to be shown next to the prompt for input or None
                 to skip further input processing
        :rtype: unicode|None
        """
        return _(u"  Please make your choice from above ['q' to quit | 'c' to continue |\n  'r' to refresh]: ")

    @property
    def app(self):
        """The reference to this Screen's assigned App instance."""
        return self._app

    def close(self):
        """Close the current screen."""
        self.app.close_screen(self)

class Widget(object):
    def __init__(self, max_width = None, default = None):
        """Initializes base Widgets buffer.

           :param max_width: server as a hint about screen size to write method with default arguments
           :type max_width: int

           :param default: string containing the default content to fill the buffer with
           :type default: string
           """

        self._buffer = []
        if default:
            self._buffer = [[c for c in l] for l in default.split("\n")]
        self._max_width = max_width
        self._cursor = (0, 0) # row, col

    @property
    def height(self):
        """The current height of the internal buffer."""
        return len(self._buffer)

    @property
    def width(self):
        """The current width of the internal buffer
           (id of the first empty column)."""
        return reduce(lambda acc,l: max(acc, len(l)), self._buffer, 0)

    def clear(self):
        """Clears this widgets buffer and resets cursor."""
        self._buffer = list()
        self._cursor = (0, 0)

    @property
    def content(self):
        """This has to return list (rows) of lists (columns) with one character elements."""
        return self._buffer

    def render(self, width):
        """This method has to redraw the widget's self._buffer.

           :param width: the width of buffer requested by the caller
           :type width: int

           This method will commonly call render of child widgets and then draw and write
           methods to copy their contents to self._buffer
           """
        self.clear()

    def get_lines(self):
        """Get lines to write out in order to show this widget.

           :return: lines representing this widget
           :rtype: list(unicode)
           """

        return [unicode(u"".join(line)) for line in self._buffer]

    def setxy(self, row, col):
        """Sets cursor position.

        :param row: row id, starts with 0 at the top of the screen
        :type row: int

        :param col: column id, starts with 0 on the left side of the screen
        :type col: int
        """
        self._cursor = (row, col)

    @property
    def cursor(self):
        return self._cursor

    def setend(self):
        """Sets the cursor to first column in new line at the end."""
        self._cursor = (self.height, 0)

    def draw(self, w, row = None, col = None, block = False):
        """This method copies w widget's content to this widget's buffer at row, col position.

           :param w: widget to take content from
           :type w: class Widget

           :param row: row number to start at (default is at the cursor position)
           :type row: int

           :param col: column number to start at (default is at the cursor position)
           :type col: int

           :param block: when printing newline, start at column col (True) or at column 0 (False)
           :type block: boolean
           """

        # if the starting row is not present, start at the cursor position
        if row is None:
            row = self._cursor[0]

        # if the starting column is not present, start at the cursor position
        if col is None:
            col = self._cursor[1]

        # fill up rows to accomodate for w.height
        if self.height < row + w.height:
            for _i in range(row + w.height - self.height):
                self._buffer.append(list())

        # append columns to accomodate for w.width
        for l in range(row, row + w.height):
            l_len = len(self._buffer[l])
            w_len = len(w.content[l - row])
            if l_len < col + w_len:
                self._buffer[l] += ((col + w_len - l_len) * list(u" "))
            self._buffer[l][col:col + w_len] = w.content[l - row][:]

        # move the cursor to new spot
        if block:
            self._cursor = (row + w.height, col)
        else:
            self._cursor = (row + w.height, 0)

    def write(self, text, row = None, col = None, width = None, block = False):
        """This method emulates typing machine writing to this widget's buffer.

           :param text: text to type
           :type text: unicode

           :param row: row number to start at (default is at the cursor position)
           :type row: int

           :param col: column number to start at (default is at the cursor position)
           :type col: int

           :param width: wrap at "col" + "width" column (default is at self._max_width)
           :type width: int

           :param block: when printing newline, start at column col (True) or at column 0 (False)
           :type block: boolean
           """
        if not text:
            return

        try:
            text = text.decode("utf-8")
        except UnicodeDecodeError as e:
            raise ValueError("Unable to decode string %s" %
                    str(e.object).decode("utf-8", "replace"))

        if row is None:
            row = self._cursor[0]

        if col is None:
            col = self._cursor[1]

        if width is None and self._max_width:
            width = self._max_width - col

        x = row
        y = col

        # emulate typing machine
        for c in text:
            # process newline
            if c == "\n":
                x += 1
                if block:
                    y = col
                else:
                    y = 0
                continue

            # if the line is not in buffer, create it
            if x >= len(self._buffer):
                for _i in range(x - len(self._buffer) + 1):
                    self._buffer.append(list())

            # if the line's length is not enough, fill it with spaces
            if y >= len(self._buffer[x]):
                self._buffer[x] += ((y - len(self._buffer[x]) + 1) * list(u" "))


            # "type" character
            self._buffer[x][y] = c

            # shift to the next char
            y += 1
            if not width is None and y >= col + width:
                x += 1
                if block:
                    y = col
                else:
                    y = 0

        self._cursor = (x, y)

if __name__ == "__main__":
    class HelloWorld(UIScreen):
        def show(self, args = None):
            print """Hello World\nquit by typing 'quit'"""
            return True

    a = App("Hello World")
    s = HelloWorld(a, None)
    a.schedule_screen(s)
    a.run()
