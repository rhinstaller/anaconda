#
# base.py
# Base classes for Anaconda modules.
#
# Copyright (C) 2017 Red Hat, Inc.
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
from abc import ABC

from pyanaconda.core.event_loop import EventLoop
from pyanaconda.core.async_utils import run_in_loop
from pyanaconda.core.timer import Timer
from pyanaconda.dbus import DBus
from pyanaconda.task import publish_task
from pyanaconda.core.signal import Signal
from pyanaconda.core.kickstart import NoKickstartSpecification, \
    KickstartSpecificationHandler, KickstartSpecificationParser

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class BaseModule(ABC):
    """Base implementation of a module."""

    def __init__(self):
        self._loop = EventLoop()

    @property
    def loop(self):
        """Return the loop."""
        return self._loop

    def run(self):
        """Run the module's loop."""
        log.debug("Schedule publishing.")
        run_in_loop(self.publish)
        log.debug("Start the loop.")
        self._loop.run()

    def publish(self):
        """Publish DBus objects and register a DBus service.

        Nothing is published by default.
        """
        pass

    def stop(self):
        """Stop the module's loop."""
        DBus.disconnect()
        Timer().timeout_sec(1, self.loop.quit)


class KickstartModule(BaseModule):
    """Base implementation of a kickstart module.

    Instances of this class can be published with a DBus interface
    defined by KickstartModuleInterface.
    """

    def __init__(self):
        super().__init__()
        self._published_tasks = []
        self._module_properties_changed = Signal()

        self.kickstarted_changed = Signal()
        self._kickstarted = False

    @property
    def module_properties_changed(self):
        """Signal that module might have changed.

        If someone changes properties of this module
        on the python level (and not from DBus), he
        should emit this signal once he is done.

        Example of the callback:

            def callback():
                pass
        """
        return self._module_properties_changed

    @property
    def published_tasks(self):
        """Returns a list of published tasks."""
        return self._published_tasks

    def publish_task(self, implementation, module_path):
        """Publish a task."""
        published = publish_task(implementation, module_path)
        self._published_tasks.append(published)

    @property
    def kickstart_specification(self):
        """Return a kickstart specification.

        Every kickstart module that is interested in processing
        kickstart files, should provide its own specification.

        :return: a subclass of KickstartSpecification
        """
        return NoKickstartSpecification

    @property
    def kickstart_command_names(self):
        """Return a list of kickstart command names."""
        return list(self.kickstart_specification.commands.keys())

    @property
    def kickstart_section_names(self):
        """Return a list of kickstart section names."""
        return list(self.kickstart_specification.sections.keys())

    @property
    def kickstart_addon_names(self):
        """Return a list of kickstart addon names."""
        # TODO: We need to add support for addons.
        return list()

    @property
    def kickstarted(self):
        """Was this module set up by the kickstart?"""
        return self._kickstarted

    @kickstarted.setter
    def kickstarted(self, value):
        self._kickstarted = value
        self.kickstarted_changed.emit()
        log.debug("Kickstarted is set to %s.", value)

    def get_kickstart_handler(self):
        """Return a kickstart handler.

        :return: a kickstart handler
        """
        return KickstartSpecificationHandler(self.kickstart_specification)

    def get_kickstart_parser(self, handler):
        """Return a kickstart parser.

        :param handler: a kickstart handler
        :return: a kickstart parser
        """
        return KickstartSpecificationParser(handler, self.kickstart_specification)

    def read_kickstart(self, s):
        """Read the given kickstart string.

        The kickstart string should contain only commands and
        sections that are defined by the kickstart specification.

        :param s: a kickstart string
        :raises: instances of KickstartError
        """
        log.debug("Reading kickstart...")
        handler = self.get_kickstart_handler()
        parser = self.get_kickstart_parser(handler)

        parser.readKickstartFromString(s)
        self.process_kickstart(handler)
        self.kickstarted = True

    def process_kickstart(self, data):
        """Process the kickstart data.

        :param data: a kickstart handler defined by the specification
        """
        pass

    def generate_kickstart(self):
        """Return a kickstart representation of this module.

        The kickstart string should contain only commands and
        sections that are defined by the kickstart specification.

        :return: a kickstart string
        """
        return ""
