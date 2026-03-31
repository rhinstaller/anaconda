#
# remote_debugger.py: argument parsing for remote debugging via debugpy
#
# Copyright (C) 2026 Red Hat, Inc.  All rights reserved.
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

import os
import re
from argparse import Action
from pathlib import Path


class ParseRemoteDebugger(Action):
    @staticmethod
    def _get_anaconda_modules():
        """Parse module names from DBus service files.

        Returns a sorted list of module names from the service files.
        Raises ValueError if any service file cannot be read.
        """
        datadir = os.environ.get("ANACONDA_DATADIR", "/usr/share/anaconda")
        dbus_dir = Path(datadir) / "dbus"
        service_files = dbus_dir.rglob("*.service")
        modules = []
        errors = []
        exec_pattern = re.compile(r"Exec=.*start-module\s+(\S+)")

        for service in service_files:
            try:
                match = exec_pattern.search(service.read_text())
                if match:
                    module_name = match.group(1)
                    modules.append(module_name)
            except OSError as e:
                errors.append(f"{service}: {e}")

        if errors:
            raise ValueError(f"Failed to read service files: {'; '.join(errors)}")

        return sorted(modules)

    def __call__(self, parser, namespace, values, option_string=None):
        """Parse remote debugger configuration.

        Format: moduleName:port or all:startPort-endPort
        Example: --remote-debugger anaconda:50000 --remote-debugger pyanaconda.modules.boss:50001
        Example: --remote-debugger all:50000-50020
        """
        remote_debugger_config = getattr(namespace, self.dest, self.default) or {}

        if ":" not in values:
            raise ValueError(
                f"Invalid remote-debugger format '{values}'. Use: moduleName:port or all:startPort-endPort"
            )

        module, port_spec = values.split(":", 1)

        if module == "all":
            if remote_debugger_config:
                raise ValueError(
                    "Cannot use 'all' with specific module configurations. "
                    "Use either 'all:startPort-endPort' OR specific 'module:port' entries, not both."
                )

            if "-" not in port_spec:
                raise ValueError("Invalid 'all' format. Use: all:startPort-endPort")

            start_port_str, end_port_str = port_spec.split("-", 1)
            start_port = int(start_port_str.strip())
            end_port = int(end_port_str.strip())

            if end_port <= start_port:
                raise ValueError(
                    f"End port ({end_port}) must be greater than start port ({start_port})."
                )

            setattr(namespace, "_remote_debugger_all_mode", True)

            modules = self._get_anaconda_modules()

            required_ports = 1 + len(modules)
            available_ports = end_port - start_port + 1
            if required_ports > available_ports:
                raise ValueError(
                    f"Port range {start_port}-{end_port} provides {available_ports} ports, "
                    f"but {required_ports} are needed (anaconda + {len(modules)} modules)."
                )

            remote_debugger_config["anaconda"] = start_port

            for idx, mod in enumerate(modules, start=1):
                remote_debugger_config[mod] = start_port + idx
        else:
            if getattr(namespace, "_remote_debugger_all_mode", False):
                raise ValueError(
                    "Cannot use specific module configurations with 'all'. "
                    "Use either 'all:startPort-endPort' OR specific 'module:port' entries, not both."
                )

            remote_debugger_config[module] = int(port_spec.strip())

        setattr(namespace, self.dest, remote_debugger_config)
