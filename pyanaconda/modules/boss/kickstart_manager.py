#
# Distributing kickstart to anaconda modules.
#
# Copyright (C) 2017  Red Hat, Inc.  All rights reserved.
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
#

from pydbus.error import map_error

from pyanaconda.dbus.constants import DBUS_BOSS_ANACONDA_NAME

from pyanaconda.kickstart_dispatcher.parser import SplitKickstartParser, VALID_SECTIONS_ANACONDA
from pykickstart.version import makeVersion
from pykickstart.errors import KickstartError, KickstartParseError

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


__all__ = ['KickstartManager', 'SplitKickstartError']


class SplitKickstartError(Exception):
    """Error while parsing kickstart for splitting."""
    pass


@map_error("{}.SplitKickstartSectionParsingError".format(DBUS_BOSS_ANACONDA_NAME))
class SplitKickstartSectionParsingError(SplitKickstartError):
    """Error while parsing a section in kickstart."""
    pass


@map_error("{}.SplitKickstartMissingIncludeError".format(DBUS_BOSS_ANACONDA_NAME))
class SplitKickstartMissingIncludeError(SplitKickstartError):
    """File included in kickstart was not found."""
    pass


class KickstartManager(object):
    """Distributes kickstart to modules and collects it back."""

    def __init__(self):
        self._kickstart_path = None
        self._elements = None
        self._module_observers = []

    @property
    def module_observers(self):
        """Get all module observers for kickstart distribution."""
        return self._module_observers

    @module_observers.setter
    def module_observers(self, modules):
        """Set module observers for kickstart distribution.

        :param modules: Module observers list
        :type modules: list(DBusObjectObserver)
        """
        self._module_observers = modules

    @property
    def elements(self):
        """Return all elements of split kickstart."""
        return self._elements

    @property
    def unprocessed_kickstart(self):
        """Return kickstart not processed by any module."""
        return self._elements.get_kickstart_from_elements(self._elements.unprocessed_elements)

    def split(self, path):
        """Split the kickstart given by path into elements."""
        self._elements = None
        self._kickstart_path = path
        handler = makeVersion()
        ksparser = SplitKickstartParser(handler, valid_sections=VALID_SECTIONS_ANACONDA)
        try:
            result = ksparser.split(path)
        except KickstartParseError as e:
            raise SplitKickstartSectionParsingError(e)
        except KickstartError as e:
            raise SplitKickstartMissingIncludeError(e)
        log.info("split %s: %s", path, result)
        self._elements = result

    def distribute(self):
        """Distribute split kickstart to modules synchronously.

        :returns: list of (Line number, Message) errors reported by modules when
                  distributing kickstart
        :rtype: list((int, str))
        """
        errors = []

        for observer in self._module_observers:

            if not observer.is_service_available:
                log.warning("distribute kickstart: module %s not available", observer.service_name)
                continue

            commands = observer.proxy.KickstartCommands()
            sections = observer.proxy.KickstartSections()
            addons = observer.proxy.KickstartAddons()
            log.info("distribute kickstart: %s handles commands %s sections %s addons %s",
                     observer.service_name, commands, sections, addons)

            elements = self._elements.get_and_process_elements(commands=commands,
                                                               sections=sections,
                                                               addons=addons)
            kickstart = self._elements.get_kickstart_from_elements(elements)
            log.info("distribute kickstart: %s will get kickstart elements: %s",
                     observer.service_name, elements)

            error_lineno, error_msg = observer.proxy.ConfigureWithKickstart(kickstart)
            if error_lineno:
                line_references = self._elements.get_references_from_elements(elements)
                kickstart_reference = line_references[error_lineno]
                errors.append((observer.service_name, kickstart_reference, error_msg))

        return errors

    def collect(self):
        """Collect kickstarts from configured modules."""
        pass
