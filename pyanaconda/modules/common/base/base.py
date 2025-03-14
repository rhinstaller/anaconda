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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import os
import warnings
from abc import ABC
from locale import LC_ALL, setlocale

from pykickstart.errors import KickstartError, KickstartParseWarning

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.dbus import DBus
from pyanaconda.core.glib import create_main_loop
from pyanaconda.core.kickstart.specification import (
    KickstartSpecificationHandler,
    KickstartSpecificationParser,
    NoKickstartSpecification,
)
from pyanaconda.core.signal import Signal
from pyanaconda.core.timer import Timer
from pyanaconda.core.util import setenv
from pyanaconda.modules.common.structures.kickstart import (
    KickstartMessage,
    KickstartReport,
)

log = get_module_logger(__name__)


class BaseModule(ABC):
    """Implementation of a base module."""

    def __init__(self):
        super().__init__()
        self._module_properties_changed = Signal()

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

    def publish(self):
        """Publish DBus objects and register a DBus service.

        Nothing is published by default.
        """
        pass


class Service(BaseModule):
    """Implementation of a DBus service.

    The service is an owner of the main loop, so it is
    able to start and stop the application.
    """

    def __init__(self):
        super().__init__()
        self._loop = create_main_loop()

    @property
    def loop(self):
        """Return the loop."""
        return self._loop

    def run(self):
        """Run the loop."""
        log.debug("Publish the service.")
        self.publish()
        log.debug("Start the loop.")
        self._loop.run()

    def stop(self):
        """Stop the loop."""
        DBus.disconnect()
        Timer().timeout_sec(1, self.loop.quit)

    def set_locale(self, locale):
        """Set the locale for the module.

        This function modifies the process environment, which is not thread-safe.
        It should be called before any threads are run.

        We cannot get around setting $LANG. Python's gettext implementation
        differs from C in that consults only the environment for the current
        language and not the data set via setlocale. If we want translations
        from python modules to work, something needs to be set in the
        environment when the language changes.

        :param str locale: locale to set
        """
        os.environ["LANG"] = locale  # pylint: disable=environment-modify
        setlocale(LC_ALL, locale)
        # Set locale for child processes
        setenv("LANG", locale)
        log.debug("Locale is set to %s.", locale)


class KickstartBaseModule(BaseModule):
    """Implementation of a base kickstart module."""

    def process_kickstart(self, data):
        """Process the kickstart data.

        Use the given kickstart data to set the module attributes.

        :param data: a kickstart handler
        """
        pass

    def setup_kickstart(self, data):
        """Set the given kickstart data.

        Use the module attributes to set the kickstart data.

        :param data: a kickstart handler
        """
        pass

    def collect_requirements(self):
        """Return installation requirements.

        :return: a list of requirements
        """
        return []


class KickstartService(Service, KickstartBaseModule):
    """Implementation of a DBus service with kickstart support.

    The kickstart service is able to parse and generate the given
    kickstart string based on its kickstart specification.
    """

    def __init__(self):
        super().__init__()
        self.kickstarted_changed = Signal()
        self._kickstarted = False

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
        return list(self.kickstart_specification.addons.keys())

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
        :return: a kickstart report
        """
        log.debug("Reading kickstart...")
        report = KickstartReport()

        try:
            handler = self.get_kickstart_handler()
            parser = self.get_kickstart_parser(handler)

            with warnings.catch_warnings(record=True) as warns:
                warnings.simplefilter(action="always", category=KickstartParseWarning)

                parser.readKickstartFromString(s)
                self.process_kickstart(handler)

                for warn in warns:
                    if issubclass(warn.category, KickstartParseWarning):
                        message = str(warn.message)
                        data = KickstartMessage.for_warning(message)
                        report.warning_messages.append(data)

        except KickstartError as e:
            data = KickstartMessage.for_error(e)
            report.error_messages.append(data)
        else:
            self.kickstarted = True

        return report

    def generate_kickstart(self):
        """Return a kickstart representation of this module.

        The kickstart string should contain only commands and
        sections that are defined by the kickstart specification.

        :return: a kickstart string
        """
        log.debug("Generating kickstart...")
        handler = self.get_kickstart_handler()
        self.setup_kickstart(handler)
        return str(handler)

    def configure_with_tasks(self):
        """Configure the runtime environment.

        Note: Addons should use it instead of the setup method.

        :return: a list of DBus paths of the installation tasks
        """
        return []

    def configure_bootloader_with_tasks(self, kernel_versions):
        """Configure the bootloader after the payload installation with a list of tasks.

        FIXME: This is a temporary workaround. The method might change.

        :param kernel_versions: a list of kernel versions
        :return: a list of tasks
        """
        return []

    def install_with_tasks(self):
        """Return installation tasks of this module.

        Note: Addons should use it instead of the execute method.

        :return: a list of DBus paths of the installation tasks
        """
        return []

    def teardown_with_tasks(self):
        """Returns teardown tasks for this module.

        :return: a list of DBus paths of the installation tasks
        """
        return []
