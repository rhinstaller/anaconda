#
# Distributing kickstart to anaconda modules.
#
# Copyright (C) 2023  Red Hat, Inc.  All rights reserved.
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
from abc import abstractmethod

__all__ = ['KickstartHandlingObserver', 'LocalObserver']


class KickstartHandlingObserver(object):
    @property
    @abstractmethod
    def service_name(self):
        pass

    @property
    @abstractmethod
    def is_service_available(self):
        pass

    @property
    @abstractmethod
    def kickstart_commands(self):
        pass

    @property
    @abstractmethod
    def kickstart_sections(self):
        pass

    @property
    @abstractmethod
    def kickstart_addons(self):
        pass

    @abstractmethod
    def generate_kickstart(self):
        return ""

    @abstractmethod
    def read_kickstart(self, ks_string):
        pass


class LocalObserver(KickstartHandlingObserver):
    """Distributes kickstart to modules and collects it back."""

    def __init__(self, service, name):
        self._service = service
        self._name = name

    @property
    def service_name(self):
        return self._name

    @property
    def is_service_available(self):
        return True

    def generate_kickstart(self):
        return self._service.generate_kickstart()

    def read_kickstart(self, ks_string):
        self._service.read_kickstart(ks_string)

    @property
    def kickstart_commands(self):
        return self._service.kickstart_command_names

    @property
    def kickstart_sections(self):
        return self._service.kickstart_section_names

    @property
    def kickstart_addons(self):
        return self._service.kickstart_addon_names
