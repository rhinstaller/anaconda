#
# Copyright (C) 2024 Red Hat, Inc.
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

from dasbus.client.observer import DBusObserver

from pyanaconda.core.dbus import SessionBus
from pyanaconda.core.regexes import SCREEN_RESOLUTION_CONFIG
from pyanaconda.modules.common.constants.services import MUTTER_DISPLAY_CONFIG

__all__ = ['MutterConfigError', 'MutterDisplay']


class MutterConfigError(Exception):
    """Exception class for mutter configuration related problems"""
    pass


class MonitorId:
    """Collection of properties that identify a unique monitor."""

    def __init__(self, props):
        self.connector = props[0]
        self.vendor = props[1]
        self.product = props[2]
        self.serial = props[3]

    def __eq__(self, other):
        return self.connector == other.connector and \
               self.vendor == other.vendor and \
               self.product == other.product and \
               self.serial == other.serial


class MonitorMode:
    """Available modes for a monitor."""

    def __init__(self, props):
        self.id = props[0]
        self.width = props[1]
        self.height = props[2]
        self.refresh_rate = props[3]
        self.preferred_scale = props[4]
        self.supported_scales = props[5]
        self.properties = props[6]


class Monitor:
    """Represent a connected physical monitor."""

    def __init__(self, props):
        self.id = MonitorId(props[0])
        self.modes = list(map(MonitorMode, props[1]))
        self.properties = props[2]


class LogicalMonitor:
    """Represent the current logical monitor configuration"""

    def __init__(self, props):
        self.x = props[0]
        self.y = props[1]
        self.scale = props[2]
        self.transform = props[3]
        self.primary = props[4]
        self.monitor_ids = list(map(MonitorId, props[5]))
        self.properties = props[6]


class LogicalMonitorConfig:
    """Logical monitor configuration object"""

    def __init__(self, logical_monitor, monitors, x, y, width, height):
        """Creates a LogicalMonitorConfig setting the given resolution if available."""
        self._logical_monitor = logical_monitor
        self._monitors = monitors

        self.x = x
        self.y = y
        self.scale = logical_monitor.scale
        self.transform = logical_monitor.transform
        self.primary = logical_monitor.primary

        self.monitors = []
        for monitor_id in logical_monitor.monitor_ids:
            connector = monitor_id.connector
            mode_id = self._get_matching_monitor_mode_id(monitors, monitor_id, width, height)
            self.monitors.append((connector, mode_id, {}))

    def _get_matching_monitor_mode_id(self, monitors, monitor_id, width, height):
        monitor = next(filter(lambda m: m.id == monitor_id, monitors))
        for mode in monitor.modes:
            if mode.width == width and mode.height == height:
                return mode.id

        raise MutterConfigError('Monitor mode with selected resolution not found')

    def to_dbus(self):
        return (
            self.x,
            self.y,
            self.scale,
            self.transform,
            self.primary,
            self.monitors,
        )


class MutterDisplay:
    """Class wrapping Mutter's display configuration API."""

    def __init__(self):
        self._proxy = MUTTER_DISPLAY_CONFIG.get_proxy()

    def on_service_ready(self, callback):
        observer = DBusObserver(SessionBus, 'org.gnome.Kiosk')
        observer.service_available.connect(callback)
        observer.connect_once_available()

    def set_resolution(self, res_str):
        """Changes the screen resolution.

        :param res_str: Screen resolution configuration with format "800x600".
        :raises MutterConfigError on failure.
        """
        if not self._proxy.ApplyMonitorsConfigAllowed:
            raise MutterConfigError('Monitor configuration is not allowed')

        (width, height) = self._parse_resolution_str(res_str)
        (serial, monitor_props, logical_monitor_props, _) = self._proxy.GetCurrentState()

        # Configuration method as described in org.gnome.Mutter.DisplayConfig.xml:
        #  0: verify
        #  1: temporary
        #  2: persistent
        persistent_config = 2

        monitors = list(map(Monitor, monitor_props))
        logical_monitors = list(map(LogicalMonitor, logical_monitor_props))

        # Align the monitors in a row starting at X coordinate 0
        x = 0

        configs = []
        for logical_monitor in logical_monitors:
            config = LogicalMonitorConfig(logical_monitor, monitors, x, 0, width, height)
            x += width
            configs.append(config.to_dbus())

        self._proxy.ApplyMonitorsConfig(serial, persistent_config, configs, {})

    def _parse_resolution_str(self, res_str):
        if not SCREEN_RESOLUTION_CONFIG.match(res_str):
            raise MutterConfigError('Invalid configuration resolution')

        [width, height] = res_str.split('x')
        return (int(width, 10), int(height, 10))
