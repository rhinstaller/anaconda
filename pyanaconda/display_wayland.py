#
# display_wayland.py:  Wayland graphical display setup for the Anaconda GUI
#
# Copyright (C) 2024 Neal Gompa.
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
# Author(s):  Neal Gompa <neal@gompa.dev>
#
import configparser
import glob
import os
import subprocess
import time
import textwrap
import pkgutil
import signal

from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.process_watchers import WatchProcesses
from pyanaconda import startup_utils
from pyanaconda.core import util, constants, hw
from pyanaconda.core.i18n import _
from pyanaconda.flags import flags
from pyanaconda.modules.common.constants.services import NETWORK
from pyanaconda.ui.tui.spokes.askvnc import AskVNCSpoke
from pyanaconda.ui.tui import tui_quit_callback
# needed for checking if the pyanaconda.ui.gui modules are available
import pyanaconda.ui

import blivet

from pykickstart.constants import DISPLAY_MODE_TEXT

from simpleline import App
from simpleline.render.screen_handler import ScreenHandler

from pyanaconda.anaconda_loggers import get_module_logger, get_stdout_logger
log = get_module_logger(__name__)
stdout_log = get_stdout_logger()

WAYLAND_TIMEOUT_ADVICE = \
    "Do not load the stage2 image over a slow network link.\n" \
    "Wait longer for the compositor startup with the inst.xtimeout=<SECONDS> boot option." \
    "The default is 60 seconds.\n" \
    "Load the stage2 image into memory with the rd.live.ram boot option to decrease access " \
    "time.\n" \
    "Enforce text mode when installing from remote media with the inst.text boot option."
#  on RHEL also: "Use the customer portal download URL in ilo/drac devices for greater speed."


def start_user_systemd():
    """Start the user instance of systemd.

    The service org.a11y.Bus runs the dbus-broker-launch in
    the user scope that requires the user instance of systemd.
    """
    if not conf.system.can_start_user_systemd:
        log.debug("Don't start the user instance of systemd.")
        return

    childproc = util.startProgram(["/usr/lib/systemd/systemd", "--user"])
    WatchProcesses.watch_process(childproc, "systemd")


# Spice

def start_spice_vd_agent():
    """Start the spice vdagent.

    For certain features to work spice requires that the guest os
    is running the spice vdagent.
    """
    try:
        status = util.execWithRedirect("spice-vdagent", [])
    except OSError as e:
        log.warning("spice-vdagent failed: %s", e)
        return

    if status:
        log.info("spice-vdagent exited with status %d", status)
    else:
        log.info("Started spice-vdagent.")


# VNC

def ask_vnc_question(anaconda, message):
    """ Ask the user if TUI or GUI-over-VNC should be started.

    :param anaconda: instance of the Anaconda class
    :param vnc_server: instance of the VNC server object
    :param str message: a message to show to the user together
                        with the question
    """
    App.initialize()
    loop = App.get_event_loop()
    loop.set_quit_callback(tui_quit_callback)
    spoke = AskVNCSpoke(anaconda.ksdata, message=message)
    ScreenHandler.schedule_screen(spoke)
    App.run()

    if anaconda.ksdata.vnc.enabled:
        if not anaconda.gui_mode:
            log.info("VNC requested via VNC question, switching Anaconda to GUI mode.")
        anaconda.display_mode = constants.DisplayModes.GUI
        flags.usevnc = True


def check_vnc_can_be_started(anaconda):
    """Check if we can start VNC in the current environment.

    :returns: if VNC can be started and list of possible reasons
              why VNC can't be started
    :rtype: (boot, list)
    """

    error_messages = []
    vnc_startup_possible = True

    # disable VNC over text question when not enough memory is available
    min_gui_ram = hw.minimal_memory_needed(with_gui=True)
    if blivet.util.total_memory() < min_gui_ram:
        error_messages.append("Not asking for VNC because current memory (%d) < MIN_GUI_RAM (%d)" %
                              (blivet.util.total_memory(), min_gui_ram))
        vnc_startup_possible = False

    # disable VNC question if text mode is requested and this is a ks install
    if anaconda.tui_mode and flags.automatedInstall:
        error_messages.append("Not asking for VNC because of an automated install")
        vnc_startup_possible = False

    # disable VNC question if we were explicitly asked for text in kickstart
    if anaconda.ksdata.displaymode.displayMode == DISPLAY_MODE_TEXT:
        error_messages.append("Not asking for VNC because text mode was explicitly asked for in kickstart")
        vnc_startup_possible = False

    # disable VNC question if we don't have network
    network_proxy = NETWORK.get_proxy()
    if not network_proxy.IsConnecting() and not network_proxy.Connected:
        error_messages.append("Not asking for VNC because we don't have a network")
        vnc_startup_possible = False

    # disable VNC question if we don't have Weston's VNC backend
    if not glob.glob("/usr/lib*/libweston*/vnc-backend.so"):
        error_messages.append("Not asking for VNC because we don't have weston-vnc")
        vnc_startup_possible = False

    return vnc_startup_possible, error_messages


# Wayland

def start_weston(wconfig, wltimeout):
    """Start Weston for the Anaconda GUI"""

    # Start Weston and wait for it to become ready
    # Switch to vt6 only if not using vnc
    if "vnc" not in wconfig:
        util.vtActivate(6)
    started = util.startWl(weston_config=wconfig,
                           output_redirect=subprocess.DEVNULL,
                           timeout=wltimeout)
    if started:
        return True
    else:
        return False


def do_extra_display_actions():
    """Perform graphics startup actions not related to startup."""

    start_user_systemd()
    start_spice_vd_agent()


# general display startup
def setup_display(anaconda, options):
    """Setup the display for the installation environment.

    :param anaconda: instance of the Anaconda class
    :param options: command line/boot options
    """

    try:
        wltimeout = int(options.xtimeout)
    except ValueError:
        log.warning("invalid inst.xtimeout option value: %s", options.xtimeout)
        wltimeout = constants.WAYLAND_TIMEOUT

    # Declare Weston configuration
    weston_core_config = constants.WESTON_CONFIG

    weston_vnc_config = {
        "vnc": {
            "port": "5900",
        },
        "output": {
            "name": "vnc",
            "resizeable": "true",
            "mode": "800x600",
        },
    }

    anaconda.display_mode = options.display_mode
    anaconda.interactive_mode = not options.noninteractive

    if options.vnc:
        flags.usevnc = True
        if not anaconda.gui_mode:
            log.info("VNC requested via boot/CLI option, switching Anaconda to GUI mode.")
            anaconda.display_mode = constants.DisplayModes.GUI

    if flags.rescue_mode:
        return

    if anaconda.ksdata.vnc.enabled:
        flags.usevnc = True
        if not anaconda.gui_mode:
            log.info("VNC requested via kickstart, switching Anaconda to GUI mode.")
            anaconda.display_mode = constants.DisplayModes.GUI

    # check if GUI without WebUI
    if anaconda.gui_mode and not anaconda.is_webui_supported:
        mods = (tup[1] for tup in pkgutil.iter_modules(pyanaconda.ui.__path__, "pyanaconda.ui."))
        if "pyanaconda.ui.gui" not in mods:
            stdout_log.warning("Graphical user interface not available, falling back to text mode")
            anaconda.display_mode = constants.DisplayModes.TUI
            flags.usevnc = False
            flags.vncquestion = False

    # check if VNC can be started
    vnc_can_be_started, vnc_error_messages = check_vnc_can_be_started(anaconda)
    if not vnc_can_be_started:
        # VNC can't be started - disable the VNC question and log
        # all the errors that prevented VNC from being started
        flags.vncquestion = False
        for error_message in vnc_error_messages:
            stdout_log.warning(error_message)

    # Are Weston and Xwayland actually available?
    have_gui = os.access("/usr/bin/weston", os.X_OK) and os.access("/usr/bin/Xwayland", os.X_OK)
    # Should we try to start the graphical environment?
    want_gui = anaconda.gui_mode and not (flags.preexisting_wayland or flags.usevnc)

    if want_gui and not have_gui:
        stdout_log.warning(_("Graphical installation is not available. "
                             "Starting text mode."))
        time.sleep(2)
        anaconda.display_mode = constants.DisplayModes.TUI
        want_gui = False

    if anaconda.tui_mode and have_gui and flags.vncquestion:
        # we prefer vnc over text mode, so ask about that
        message = _("Text mode provides a limited set of installation "
                    "options. It does not offer custom partitioning for "
                    "full control over the disk layout. Would you like "
                    "to use VNC mode instead?")
        ask_vnc_question(anaconda, vnc_server, message)
        if not anaconda.ksdata.vnc.enabled:
            # user has explicitly specified text mode
            flags.vncquestion = False

    anaconda.log_display_mode()
    startup_utils.check_memory(anaconda, options)

    # check_memory may have changed the display mode
    want_gui = want_gui and (anaconda.gui_mode)
    if want_gui:
        try:
            if flags.usevnc:
                weston_full_config = weston_core_config | weston_vnc_config
            else:
                weston_full_config = weston_core_config
            start_weston(weston_full_config, wltimeout)
        except TimeoutError as e:
            log.warning("Graphics startup failed: %s", e)
            print("\nGraphics did not start in the expected time, falling back to text mode. There are "
                  "multiple ways to avoid this issue:")
            wrapper = textwrap.TextWrapper(initial_indent=" * ", subsequent_indent="   ",
                                           width=os.get_terminal_size().columns - 3)
            for line in WAYLAND_TIMEOUT_ADVICE.split("\n"):
                print(wrapper.fill(line))
            util.vtActivate(1)
            anaconda.display_mode = constants.DisplayModes.TUI
            anaconda.gui_startup_failed = True
            time.sleep(2)

        except (OSError, RuntimeError) as e:
            log.warning("Weston startup failed: %s", e)
            print("\nWeston startup failed, falling back to text mode.")
            util.vtActivate(1)
            anaconda.display_mode = constants.DisplayModes.TUI
            anaconda.gui_startup_failed = True
            time.sleep(2)

        if not anaconda.gui_startup_failed:
            do_extra_display_actions()

    if anaconda.tui_mode and anaconda.gui_startup_failed and flags.vncquestion and not anaconda.ksdata.vnc.enabled:
        message = _("Graphics was unable to start on your machine. Would you like to start VNC to connect to "
                    "this computer from another computer and perform a graphical installation or continue "
                    "with a text mode installation?")
        ask_vnc_question(anaconda, message)

    # if they want us to use VNC do that now
    if anaconda.gui_mode and flags.usevnc:
        weston_full_config = weston_core_config | weston_vnc_config
        start_weston(weston_full_config, wltimeout)

    if os.path.isfile(constants.WAYLAND_DISPLAY_VARS_FILE):
        # We need to load the correct variables for the environment
        wl_envvars_config = configparser.ConfigParser()
        wl_envvars_config.read(constants.WAYLAND_DISPLAY_VARS_FILE)
        os.environ["WAYLAND_DISPLAY"] = wl_envvars_config["wayland_vars"]["WAYLAND_DISPLAY"]
        os.environ["DISPLAY"] = wl_envvars_config["wayland_vars"]["DISPLAY"]

    # with X running we can initialize the UI interface
    anaconda.initInterface()
