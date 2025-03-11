#
# Submodule manager for kickstart services.
#
# Copyright (C) 2023 Red Hat, Inc.
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
__all__ = ["SubmoduleManager"]

class SubmoduleManager:
    """Kickstart sub-module manager.

    This class helps manage multiple kickstart service sub-modules.
    """

    def __init__(self):
        self._modules = []

    def add_module(self, module):
        """Add a module."""
        self._modules.append(module)

    def publish_modules(self):
        """Publish the modules."""
        for module in self._modules:
            module.publish()

    def process_kickstart(self, data):
        """Process the kickstart data in all modules."""
        for module in self._modules:
            module.process_kickstart(data)

    def setup_kickstart(self, data):
        """Set up the kickstart data in all modules."""
        for module in self._modules:
            module.setup_kickstart(data)

    def collect_requirements(self):
        """Collect requirements from all modules."""
        requirements = []

        for module in self._modules:
            requirements.extend(module.collect_requirements())

        return requirements

    def __iter__(self):
        return iter(self._modules)
