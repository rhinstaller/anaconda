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
from pyanaconda.modules.common.errors.kickstart import SplitKickstartSectionParsingError, \
    SplitKickstartMissingIncludeError
from pyanaconda.modules.boss.kickstart_manager.parser import SplitKickstartParser,\
    VALID_SECTIONS_ANACONDA
from pykickstart.version import makeVersion
from pykickstart.errors import KickstartError, KickstartParseError

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

__all__ = ['KickstartManager']


class KickstartManager(object):
    """Distributes kickstart to modules and collects it back."""

    def __init__(self):
        self._module_observers = []

    @property
    def module_observers(self):
        """Get all module observers for kickstart distribution."""
        return self._module_observers

    def on_module_observers_changed(self, observers):
        """Set module observers for kickstart distribution."""
        self._module_observers = list(observers)

    def read_kickstart_file(self, path):
        """Read the specified kickstart file.

        :param path: a path to a file
        :returns: a list of errors
        """
        elements = self._split_to_elements(path)
        errors = self._distribute_to_modules(elements)
        return errors

    def _split_to_elements(self, path):
        """Split the kickstart given by path into elements."""
        handler = makeVersion()
        parser = SplitKickstartParser(handler, valid_sections=VALID_SECTIONS_ANACONDA)

        try:
            result = parser.split(path)
        except KickstartParseError as e:
            raise SplitKickstartSectionParsingError(e)
        except KickstartError as e:
            raise SplitKickstartMissingIncludeError(e)

        return result

    def _distribute_to_modules(self, elements):
        """Distribute split kickstart to modules synchronously.

        :returns: list of (Line number, Message) errors reported by modules when
                  distributing kickstart
        :rtype: list((int, str))
        """
        errors = []

        for observer in self._module_observers:
            if not observer.is_service_available:
                log.warning("Module %s not available!", observer.service_name)
                continue

            commands = observer.proxy.KickstartCommands
            sections = observer.proxy.KickstartSections
            addons = observer.proxy.KickstartAddons

            log.info("%s handles commands %s sections %s addons %s.",
                     observer.service_name, commands, sections, addons)

            module_elements = elements.get_and_process_elements(
                commands=commands,
                sections=sections,
                addons=addons
            )

            module_kickstart = elements.get_kickstart_from_elements(
                module_elements
            )

            if not module_kickstart:
                log.info("There are no kickstart data for %s.", observer.service_name)
                continue

            result = observer.proxy.ReadKickstart(
                module_kickstart
            )

            if not result["success"]:
                line_references = elements.get_references_from_elements(module_elements)
                line_number, file_name = line_references[result["line_number"]]
                result["line_number"] = line_number
                result["file_name"] = file_name
                result["module_name"] = observer.service_name

                log.error("distribute kickstart: %s", result)
                errors.append(result)

        return errors

    def collect(self):
        """Collect kickstarts from configured modules."""
        pass
