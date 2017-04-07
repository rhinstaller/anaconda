# The main file for anaconda none UI interface
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
import os
import site
import sys
import time

import meh.ui.text

from pyanaconda import ui
from pyanaconda.iutil import collect
from pyanaconda.progress import progressQ
from pyanaconda.ui.communication import hubQ
from pyanaconda.ui.communication_lib import process_progress, register_event_handler, process_events, send_exception
from pyanaconda.ui.configuration import Configuration
from pyanaconda.ui.installer import Installer
from pyanaconda.ui.validators import BaseValidator

log = logging.getLogger("anaconda")

__all__ = ["NoneUserInterface"]


class NoneUserInterface(ui.UserInterface):
    """Base class for none ui interface."""

    ENVIRONMENT = "anaconda"

    # Set up paths to validators:
    basemask = "pyanaconda.ui"
    basepath = os.path.dirname(os.path.dirname(__file__))
    updatepath = "/tmp/updates/pyanaconda/ui"
    sitepackages = [os.path.join(dir, "pyanaconda", "ui")
                    for dir in site.getsitepackages()]
    pathlist = set([updatepath, basepath] + sitepackages)

    # As list comprehension can't reference class level variables in Python 3
    # we need to use a for cycle (http://bugs.python.org/issue21161).

    _validators = []

    for path in pathlist:
        _validators.append((basemask + ".validators.%s",
                            os.path.join(path, "validators")))

    paths = ui.UserInterface.paths + {"validators": _validators}

    def __init__(self, storage, payload, instclass):
        super(NoneUserInterface, self).__init__(storage, payload, instclass)
        self.config = None
        self.validators = []
        self._meh_interface = meh.ui.text.TextIntf()

        # a queue for async communication
        self._queue_instance = hubQ.q

        # progress and event handlers
        # key: event id
        # value: list of tuples (callback, data)
        self._event_handlers = {}
        self._progress_handlers = {}

        # Register handlers for hubQ messages.
        register_event_handler(self._event_handlers,
                               hubQ.HUB_CODE_EXCEPTION,
                               self._handle_exception_message)

        register_event_handler(self._event_handlers,
                               hubQ.HUB_CODE_SHOW_MESSAGE,
                               self._handle_show_message)

        # Register handlers for progressQ messages.
        register_event_handler(self._progress_handlers,
                               progressQ.PROGRESS_CODE_STEP,
                               self._handle_progress_step)

        register_event_handler(self._progress_handlers,
                               progressQ.PROGRESS_CODE_MESSAGE,
                               self._handle_progress_message)

    @property
    def tty_num(self):
        return 1

    @property
    def meh_interface(self):
        """Return an interface for exception handling."""
        return self._meh_interface

    def showError(self, message):
        """Log and print the given error message."""
        print(message)
        log.error(message)

    def showDetailedError(self, message, details, buttons=None):
        """Log and print the given detailed error message."""
        self.showError(message + " (" + details + ")")

    def showYesNoQuestion(self, message):
        """Always answer no."""
        return False

    def setup(self, data):
        """Construct all the objects required to implement this interface."""
        # Create a configuration of the installation.
        self.config = Configuration(data, self.storage, self.payload, self.instclass)

        # Get the validation classes.
        klasses = self._collectActionClasses(self.paths["validators"], BaseValidator)
        klasses = self._orderActionClasses(klasses)

        # Initialize the validators.
        self._initialize_validators(klasses)

        # Setup the validators.
        self._setup_validators()

    def run(self):
        """Run the interface."""

        if self._is_valid_config():
            self._run_installation()
            print("Success!")
            return True

        else:
            self._show_errors()
            print("Failure!")
            return False

    def _collectActionClasses(self, module_pattern_w_path, action_klass):
        """Collect all the action classes which should be enqueued for processing."""
        klasses = []

        for module_pattern, path in module_pattern_w_path:
            klasses.extend(collect(module_pattern, path, lambda obj: issubclass(obj, action_klass)))

        return klasses

    def _orderActionClasses(self, klasses, hubs=None):
        """Order all the action classes which should be enqueued for processing
        according to their dependencies.

        Validators are sorted by their dependencies, so no validator can be processed
        before all the validators it depends on.

        Cyclic dependencies don't have to checked, because they will be discovered during
        the import of the classes.
        """
        # The ordered list of klasses.
        result = list()
        # The set of klasses with solved dependencies.
        solved = set()

        # The list of klasses with unsolved dependencies.
        unsolved = list(klasses)
        # The list of klasses that cannot be solved yet.
        dependent = list()

        # While there are unsolved classes.
        while unsolved or dependent:
            # Switch the unsolved list with the dependent list.
            if not unsolved:
                empty = unsolved
                unsolved = dependent
                dependent = empty

            # Get an unsolved klass.
            klass = unsolved.pop()

            # If the dependencies are already solved, add to the list.
            if all(dependency in solved for dependency in klass.depends_on):
                solved.add(klass)
                result.append(klass)
            # Otherwise the klass depends on an unsolved klass.
            else:
                dependent.append(klass)

        return result

    def _initialize_validators(self, klasses):
        """Create a list of initialized validators.

        :param klasses: the classes that are going to be instantiated
        :type klasses: list of BaseValidator subclasses
        """
        for klass in klasses:
            log.debug("Initializing %s.", klass.title)

            # Should the class be instantiated?
            if klass.should_create(self.config):

                # Create an instance.
                validator = klass(self.config)

                # Should the instance run?
                if validator.should_validate():
                    # Add validators to the list.
                    self.validators.append(validator)
                else:
                    # Otherwise delete.
                    log.debug("%s is deleted.", klass.title)
                    del validator
            else:
                log.debug("%s is not created.", klass.title)

    def _setup_validators(self):
        """Set up validators and wait until they are ready."""
        sys.stdout.write("Setting up.")

        # Setup the validators.
        for validator in self.validators:
            validator.setup()

        # Wait for validators to get ready.
        while any(not validator.ready() for validator in self.validators):
            # Catch any asynchronous events (like storage crashing).
            self._process_events()
            # Wait for a second.
            sys.stdout.write(".")
            sys.stdout.flush()
            time.sleep(1)

        # Print the newline.
        sys.stdout.write("\n")

    def _is_valid_config(self):
        """Is the configuration valid?

        It is necessary to ask EVERY validator, so the errors are reported correctly.
        """
        valid = True

        for validator in self.validators:
            if not validator.validate():
                valid = False

        return valid

    def _run_installation(self):
        """Run the installation."""
        sys.stdout.write("Installing.")

        # Initialize an installer.
        installer = Installer(self.config)

        # Start the installation.
        installer.start_installation()

        # Install the system.
        installer.install_system()
        self._show_progress()

        # Configure the system.
        installer.configure_system()
        self._show_progress()

        # Finish the installation.
        installer.finish_installation()

        # Print a new line
        sys.stdout.write("\n")

    def _show_errors(self):
        """Print the validation errors."""
        print("The configuration is not valid:\n")

        for validator in self.validators:
            if validator.errors:
                # Print the title of the validator.
                print("   " + validator.title)

                # Print the list of errors.
                for error in validator.errors:
                    print("   [!] " + error)

                # Print a newline.
                print("")

    def _show_progress(self):
        """Process the progressQ messages."""
        process_progress(
            handlers=self._progress_handlers,
            periodic_handler=(self._process_events, None))

    def _process_events(self, data=None):
        """Process the hubQ messages."""
        process_events(
            queue_instance=self._queue_instance,
            handlers=self._event_handlers,
            exception_handler=(self._handle_exception, None))

    @staticmethod
    def _handle_exception(queue_instance, exception, data):
        """Handler of the exceptions in process_events.

        :param queue_instance: a queue for async communication
        :type queue_instance: instance of queue

        :param exception: an exception
        :type exception: subclass of Exception
        """
        send_exception(queue_instance, sys.exc_info())

    @staticmethod
    def _handle_exception_message(event, data):
        """Handler for the HUB_CODE_EXCEPTION message in the hubQ.

        :param event: event data
        :type event: (event_type, message_data)

        :param data: additional data
        :type data: any
        """
        # Get data from the event data structure.
        msg_data = event[1]
        # msg_data is a list
        sys.excepthook(*msg_data[0])

    @staticmethod
    def _handle_show_message(event, data):
        """Handler for the HUB_CODE_SHOW_MESSAGE message in the hubQ.

        :param event: event data
        :type event: (event_type, message_data)

        :param data: additional data
        :type data: any
        """
        # event_type, message_data
        msg_data = event[1]
        msg_fn, args, ret_queue = msg_data
        # Put the data to the queue.
        ret_queue.put(msg_fn(*args))

    @staticmethod
    def _handle_progress_step(code, args, data):
        """Handler for the PROGRESS_CODE_STEP message of progressQ.

        :param code: the id of the message
        :param args: the arguments of the message
        :param data: extra information
        """
        sys.stdout.write(".")
        sys.stdout.flush()

    @staticmethod
    def _handle_progress_message(code, args, data):
        """Handler for the PROGRESS_CODE_MESSAGE message of progressQ.

        :param code: the id of the message
        :param args: the arguments of the message
        :param data: extra information
        """
        log.debug(args)
        sys.stdout.write(".")
        sys.stdout.flush()
