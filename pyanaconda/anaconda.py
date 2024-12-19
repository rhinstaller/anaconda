# anaconda: The Red Hat Linux Installation program
#
# Copyright (C) 1999, 2000, 2001, 2002, 2003, 2004, 2005, 2006, 2007
# Red Hat, Inc.  All rights reserved.
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

import os
import sys
import threading
from tempfile import mkstemp

from pyanaconda.anaconda_loggers import get_stdout_logger
from pyanaconda.core import constants
from pyanaconda.core.constants import (
    ADDON_PATHS,
    PAYLOAD_TYPE_LIVE_IMAGE,
    PAYLOAD_TYPE_RPM_OSTREE,
    DisplayModes,
)
from pyanaconda.core.kernel import kernel_arguments
from pyanaconda.core.path import open_with_perm
from pyanaconda.core.startup.dbus_launcher import AnacondaDBusLauncher
from pyanaconda.modules.common.constants.services import PAYLOADS
from pyanaconda.ui.lib.addons import collect_addon_ui_paths

stdoutLog = get_stdout_logger()

from pyanaconda.anaconda_loggers import get_module_logger

log = get_module_logger(__name__)


class Anaconda:
    def __init__(self):
        self._display_mode = None
        self._interactive_mode = True
        self.gui_startup_failed = False
        self._intf = None
        self.ksdata = None
        self.opts = None
        self._payload = None
        self.mehConfig = None

        # Data for inhibiting the screensaver
        self.dbus_session_connection = None
        self.dbus_inhibit_id = None

        # This is used to synchronize Gtk.main calls between the graphical
        # interface and error dialogs. Whoever gets to their initialization code
        # first will lock gui_initializing
        self.gui_initialized = threading.Lock()

        # Create class for launching our dbus session
        self._dbus_launcher = None

    def set_from_opts(self, opts):
        """Load argument to variables from self.opts."""
        self.opts = opts

    @property
    def dbus_launcher(self):
        if not self._dbus_launcher:
            self._dbus_launcher = AnacondaDBusLauncher()

        return self._dbus_launcher

    @property
    def payload(self):
        # Try to find the payload class.  First try the install
        # class.  If it doesn't give us one, fall back to the default.
        if not self._payload:
            # Get the type of the DBus payload module if any.
            payload_type = self._get_dbus_payload_type()

            if payload_type == PAYLOAD_TYPE_RPM_OSTREE:
                from pyanaconda.payload.rpmostreepayload import RPMOSTreePayload
                payload = RPMOSTreePayload()
            elif self.opts.liveinst:
                from pyanaconda.payload.live import LiveOSPayload
                payload = LiveOSPayload()
            elif payload_type == PAYLOAD_TYPE_LIVE_IMAGE:
                from pyanaconda.payload.live import LiveImagePayload
                payload = LiveImagePayload()
            else:
                from pyanaconda.payload.dnf import DNFPayload
                payload = DNFPayload(self.ksdata)

            self._payload = payload

        return self._payload

    @staticmethod
    def _get_dbus_payload_type():
        payloads_proxy = PAYLOADS.get_proxy()
        object_path = payloads_proxy.ActivePayload

        if not object_path:
            return None

        object_proxy = PAYLOADS.get_proxy(object_path)
        return object_proxy.Type

    @property
    def display_mode(self):
        return self._display_mode

    @display_mode.setter
    def display_mode(self, new_mode):
        if isinstance(new_mode, DisplayModes):
            if self._display_mode:
                old_mode = self._display_mode
                log.debug("changing display mode from %s to %s",
                          old_mode.value, new_mode.value)
            else:
                log.debug("setting display mode to %s", new_mode.value)
            self._display_mode = new_mode
        else:  # unknown mode name - ignore & log an error
            log.error("tried to set an unknown display mode name: %s", new_mode.value)

    @property
    def interactive_mode(self):
        return self._interactive_mode

    @interactive_mode.setter
    def interactive_mode(self, value):
        if self._interactive_mode != value:
            self._interactive_mode = value
            if value:
                log.debug("working in interative mode")
            else:
                log.debug("working in noninteractive mode")

    @property
    def gui_mode(self):
        """Report if Anaconda should run with the GUI."""
        return self._display_mode == DisplayModes.GUI

    @property
    def tui_mode(self):
        """Report if Anaconda should run with the TUI."""
        return self._display_mode == DisplayModes.TUI

    @property
    def is_webui_supported(self):
        "Report if webui package is installed"
        return os.path.exists("/usr/share/cockpit/anaconda-webui")

    def log_display_mode(self):
        if not self.display_mode:
            log.error("Display mode is not set!")
            return

        log.info("Display mode is set to '%s %s'.",
                 constants.INTERACTIVE_MODE_NAME[self.interactive_mode],
                 constants.DISPLAY_MODE_NAME[self.display_mode])

    def dumpState(self):
        from inspect import stack as _stack
        from traceback import format_stack

        from meh import ExceptionInfo
        from meh.dump import ReverseExceptionDump

        # Skip the frames for dumpState and the signal handler.
        stack = _stack()[2:]
        stack.reverse()
        exn = ReverseExceptionDump(ExceptionInfo(None, None, stack),
                                   self.mehConfig)

        # gather up info on the running threads
        threads = "\nThreads\n-------\n"

        # Every call to sys._current_frames() returns a new dict, so it is not
        # modified when threads are created or destroyed. Iterating over it is
        # thread safe.
        for thread_id, frame in sys._current_frames().items():
            threads += "\nThread %s\n" % (thread_id,)
            threads += "".join(format_stack(frame))

        # dump to a unique file
        (fd, filename) = mkstemp(prefix="anaconda-tb-", dir="/tmp")
        dump_text = exn.traceback_and_object_dump(self)
        dump_text += threads
        dump_text_bytes = dump_text.encode("utf-8")
        os.write(fd, dump_text_bytes)
        os.close(fd)

        # append to a given file
        with open_with_perm("/tmp/anaconda-tb-all.log", "a+", 0o600) as f:
            f.write("--- traceback: %s ---\n" % filename)
            f.write(dump_text + "\n")

    @property
    def intf(self):
        """The user interface."""
        return self._intf

    def initialize_interface(self):
        if self._intf:
            raise RuntimeError("Second attempt to initialize the InstallInterface")

        if self.gui_mode and self.is_webui_supported:
            from pyanaconda.ui.webui import CockpitUserInterface
            self._intf = CockpitUserInterface(
                None,
                self.payload,
                "webui.remote" in kernel_arguments
            )

            # needs to be refreshed now we know if gui or tui will take place
            # FIXME - what about Cockpit based addons ?
            addon_paths = []
        elif self.gui_mode:
            from pyanaconda.ui.gui import GraphicalUserInterface
            # Run the GUI in non-fullscreen mode, so live installs can still
            # use the window manager
            self._intf = GraphicalUserInterface(None, self.payload,
                                                gui_lock=self.gui_initialized,
                                                fullscreen=False)

            # needs to be refreshed now we know if gui or tui will take place
            addon_paths = collect_addon_ui_paths(ADDON_PATHS, "gui")
        elif self.tui_mode:
            # TUI and noninteractive TUI are the same in this regard
            from pyanaconda.ui.tui import TextUserInterface
            self._intf = TextUserInterface(None, self.payload)

            # needs to be refreshed now we know if gui or tui will take place
            addon_paths = collect_addon_ui_paths(ADDON_PATHS, "tui")
        elif not self.display_mode:
            raise RuntimeError("Display mode not set.")
        else:
            # this should generally never happen, as display_mode now won't let
            # and invalid value to be set, but let's leave it here just in case
            # something ultra crazy happens
            raise RuntimeError("Unsupported display mode: %s" % self.display_mode)

        if addon_paths:
            self._intf.update_paths(addon_paths)
