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
from pykickstart.errors import KickstartError
from pykickstart.version import makeVersion

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.modules.boss.kickstart_manager.parser import (
    VALID_SECTIONS_ANACONDA,
    SplitKickstartParser,
)
from pyanaconda.modules.common.constants.services import BOSS
from pyanaconda.modules.common.structures.kickstart import (
    KickstartMessage,
    KickstartReport,
)

log = get_module_logger(__name__)

__all__ = ['KickstartManager']


class KickstartManager:
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
        :returns: a kickstart report
        """
        report = KickstartReport()

        try:
            elements = self._split_to_elements(path)
            reports = self._distribute_to_modules(elements)
        except KickstartError as e:
            data = KickstartMessage.for_error(e)
            data.module_name = BOSS.service_name
            data.file_name = path
            report.error_messages.append(data)
        else:
            self._merge_module_reports(report, reports)

        return report

    def _split_to_elements(self, path):
        """Split the kickstart given by path into elements."""
        handler = makeVersion()
        parser = SplitKickstartParser(handler, valid_sections=VALID_SECTIONS_ANACONDA)
        return parser.split(path)

    def _distribute_to_modules(self, elements):
        """Distribute split kickstart to modules synchronously.

        :returns: list of (Line number, Message) errors reported by modules when
                  distributing kickstart
        :rtype: list of kickstart reports
        """
        reports = []

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

            module_report = KickstartReport.from_structure(
                observer.proxy.ReadKickstart(module_kickstart)
            )

            line_references = elements.get_references_from_elements(
                module_elements
            )

            for message in module_report.get_messages():
                line_number, file_name = line_references[message.line_number]
                message.line_number = line_number
                message.file_name = file_name
                message.module_name = observer.service_name

            reports.append(module_report)

        return reports

    def _merge_module_reports(self, report, module_reports):
        """Merge the module reports into the final report."""
        for module_report in module_reports:
            report.error_messages.extend(module_report.error_messages)
            report.warning_messages.extend(module_report.warning_messages)

    def generate_kickstart(self):
        """Return a kickstart representation of modules.

        :return: a kickstart string
        """
        kickstarts = self._generate_from_modules()
        return self._merge_module_kickstarts(kickstarts)

    def _generate_from_modules(self):
        """Generate kickstart from modules.

        :return: a map of module names and kickstart strings
        """
        result = {}

        for observer in self._module_observers:
            if not observer.is_service_available:
                log.warning("Module %s not available!", observer.service_name)
                continue

            module_name = observer.service_name
            module_kickstart = observer.proxy.GenerateKickstart()
            result[module_name] = module_kickstart

        return result

    def _merge_module_kickstarts(self, module_kickstarts):
        """Merge kickstart from modules

        :param module_kickstarts: a map of modules names and kickstart strings
        :return: a complete kickstart string
        """
        parts = []

        for name in sorted(module_kickstarts):
            part = module_kickstarts[name].strip()

            if not part:
                continue

            parts.append(part)

        return "\n\n".join(parts)
