#
# display.py:  graphical display setup for the Anaconda GUI
#
# Copyright (C) 2016
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
# Author(s):  Martin Kolman <mkolman@redhat.com>
#
import os
import subprocess
import time
import textwrap
import pkgutil

from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.process_watchers import WatchProcesses
from pyanaconda import isys
from pyanaconda import startup_utils
from pyanaconda.core import util, constants
from pyanaconda import vnc
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


X_TIMEOUT_ADVICE = \
    "Do not load the stage2 image over a slow network link.\n" \
    "Wait longer for the X server startup with the inst.xtimeout=<SECONDS> boot option." \
    "The default is 60 seconds.\n" \
    "Load the stage2 image into memory with the rd.live.ram boot option to decrease access " \
    "time.\n" \
    "Enforce text mode when installing from remote media with the inst.text boot option.\n" \
    "Use the customer portal download URL in ilo/drac devices for greater speed."


# Spice

def start_spice_vd_agent():
    """Start the spice vdagent.

    For certain features to work spice requires that the guest os
    is running the spice vdagent.
    """
    status = util.execWithRedirect("spice-vdagent", [])
    if status:
        log.info("spice-vdagent exited with status %d", status)
    else:
        log.info("Started spice-vdagent.")


# VNC

def ask_vnc_question(anaconda, vnc_server, message):
    """ Ask the user if TUI or GUI-over-VNC should be started.

    :param anaconda: instance of the Anaconda class
    :param vnc_server: instance of the VNC server object
    :param str message: a message to show to the user together
                        with the question
    """
    App.initialize()
    loop = App.get_event_loop()
    loop.set_quit_callback(tui_quit_callback)
    spoke = AskVNCSpoke(anaconda.ksdata, message)
    ScreenHandler.schedule_screen(spoke)
    App.run()

    if anaconda.ksdata.vnc.enabled:
        if not anaconda.gui_mode:
            log.info("VNC requested via VNC question, switching Anaconda to GUI mode.")
        anaconda.display_mode = constants.DisplayModes.GUI
        flags.usevnc = True
        vnc_server.password = anaconda.ksdata.vnc.password


def check_vnc_can_be_started(anaconda):
    """Check if we can start VNC in the current environment.

    :returns: if VNC can be started and list of possible reasons
              why VNC can't be started
    :rtype: (boot, list)
    """

    error_messages = []
    vnc_startup_possible = True

    # disable VNC over text question when not enough memory is available
    if blivet.util.total_memory() < isys.MIN_GUI_RAM:
        error_messages.append("Not asking for VNC because current memory (%d) < MIN_GUI_RAM (%d)" %
                              (blivet.util.total_memory(), isys.MIN_GUI_RAM))
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

    # disable VNC question if we don't have Xvnc
    if not os.access('/usr/bin/Xvnc', os.X_OK):
        error_messages.append("Not asking for VNC because we don't have Xvnc")
        vnc_startup_possible = False

    return vnc_startup_possible, error_messages


# X11

def start_x11(xtimeout):
    """Start the X server for the Anaconda GUI."""

    # Start Xorg and wait for it become ready
    util.startX(["Xorg", "-br", "-logfile", "/tmp/X.log",
                 ":%s" % constants.X_DISPLAY_NUMBER, "vt6", "-s", "1440", "-ac",
                 "-nolisten", "tcp", "-dpi", "96",
                 "-noreset"],
                output_redirect=subprocess.DEVNULL, timeout=xtimeout)


# function to handle X startup special issues for anaconda

def do_startup_x11_actions():
    """Start the window manager.

    When metacity actually connects to the X server is unknowable, but
    fortunately it doesn't matter. metacity does not need to be the first
    connection to Xorg, and if anaconda starts up before metacity, metacity
    will just take over and maximize the window and make everything right,
    fingers crossed.
    Add XDG_DATA_DIRS to the environment to pull in our overridden schema
    files.
    """
    datadir = os.environ.get('ANACONDA_DATADIR', '/usr/share/anaconda')
    if 'XDG_DATA_DIRS' in os.environ:
        xdg_data_dirs = datadir + '/window-manager:' + os.environ['XDG_DATA_DIRS']
    else:
        xdg_data_dirs = datadir + '/window-manager:/usr/share'

    childproc = util.startProgram(["metacity", "--display", ":1", "--sm-disable"],
                                  env_add={'XDG_DATA_DIRS': xdg_data_dirs})
    WatchProcesses.watch_process(childproc, "metacity")


def set_x_resolution(runres):
    """Set X server screen resolution.

    :param str runres: a resolution specification string
    """
    try:
        log.info("Setting the screen resolution to: %s.", runres)
        util.execWithRedirect("xrandr", ["-d", ":1", "-s", runres])
    except RuntimeError:
        log.error("The X resolution was not set")
        util.execWithRedirect("xrandr", ["-d", ":1", "-q"])


def do_extra_x11_actions(runres, gui_mode):
    """Perform X11 actions not related to startup.

    :param str runres: a resolution specification string
    :param gui_mode: an Anaconda display mode
    """
    if runres and gui_mode and not flags.usevnc:
        set_x_resolution(runres)

    # Load the system-wide Xresources
    util.execWithRedirect("xrdb", ["-nocpp", "-merge", "/etc/X11/Xresources"])

    start_spice_vd_agent()


def write_xdriver(driver, root=None):
    """Write the X driver."""
    if root is None:
        root = conf.target.system_root

    if not os.path.isdir("%s/etc/X11" % (root,)):
        os.makedirs("%s/etc/X11" % (root,), mode=0o755)

    f = open("%s/etc/X11/xorg.conf" % (root,), 'w')
    f.write('Section "Device"\n\tIdentifier "Videocard0"\n\tDriver "%s"\nEndSection\n' % driver)
    f.close()


# general display startup
def setup_display(anaconda, options):
    """Setup the display for the installation environment.

    :param anaconda: instance of the Anaconda class
    :param options: command line/boot options
    """

    try:
        xtimeout = int(options.xtimeout)
    except ValueError:
        log.warning("invalid inst.xtimeout option value: %s", options.xtimeout)
        xtimeout = constants.X_TIMEOUT

    vnc_server = vnc.VncServer()  # The vnc Server object.
    vnc_server.anaconda = anaconda
    vnc_server.timeout = xtimeout

    anaconda.display_mode = options.display_mode
    anaconda.interactive_mode = not options.noninteractive

    if options.vnc:
        flags.usevnc = True
        if not anaconda.gui_mode:
            log.info("VNC requested via boot/CLI option, switching Anaconda to GUI mode.")
            anaconda.display_mode = constants.DisplayModes.GUI
        vnc_server.password = options.vncpassword

        # Only consider vncconnect when vnc is a param
        if options.vncconnect:
            cargs = options.vncconnect.split(":")
            vnc_server.vncconnecthost = cargs[0]
            if len(cargs) > 1 and len(cargs[1]) > 0:
                if len(cargs[1]) > 0:
                    vnc_server.vncconnectport = cargs[1]

    if options.xdriver:
        write_xdriver(options.xdriver, root="/")

    if flags.rescue_mode:
        return

    if anaconda.ksdata.vnc.enabled:
        flags.usevnc = True
        if not anaconda.gui_mode:
            log.info("VNC requested via kickstart, switching Anaconda to GUI mode.")
            anaconda.display_mode = constants.DisplayModes.GUI

        if vnc_server.password == "":
            vnc_server.password = anaconda.ksdata.vnc.password

        if vnc_server.vncconnecthost == "":
            vnc_server.vncconnecthost = anaconda.ksdata.vnc.host

        if vnc_server.vncconnectport == "":
            vnc_server.vncconnectport = anaconda.ksdata.vnc.port

    if anaconda.gui_mode:
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

    # Should we try to start Xorg?
    want_x = anaconda.gui_mode and not (flags.preexisting_x11 or flags.usevnc)

    # Is Xorg is actually available?
    if want_x and not os.access("/usr/bin/Xorg", os.X_OK):
        stdout_log.warning(_("Graphical installation is not available. "
                             "Starting text mode."))
        time.sleep(2)
        anaconda.display_mode = constants.DisplayModes.TUI
        want_x = False

    if anaconda.tui_mode and flags.vncquestion:
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
    want_x = want_x and (anaconda.gui_mode)
    if want_x:
        try:
            start_x11(xtimeout)
            do_startup_x11_actions()
        except (OSError, RuntimeError) as e:
            log.warning("X startup failed: %s", e)
            stdout_log.warning("X startup failed, falling back to text mode. There are multiple "
                               "ways to help this issue:")
            wrapper = textwrap.TextWrapper(initial_indent=" * ", subsequent_indent="   ",
                                           width=os.get_terminal_size().columns - 3 - 9)
                                           # 3 for the indent, 9 for timestamp and space
            for line in X_TIMEOUT_ADVICE.split("\n"):
                stdout_log.warning(wrapper.fill(line))
            anaconda.display_mode = constants.DisplayModes.TUI
            anaconda.gui_startup_failed = True
            time.sleep(2)

        if not anaconda.gui_startup_failed:
            do_extra_x11_actions(options.runres, gui_mode=anaconda.gui_mode)

    if anaconda.tui_mode and anaconda.gui_startup_failed and flags.vncquestion and not anaconda.ksdata.vnc.enabled:
        message = _("X was unable to start on your machine. Would you like to start VNC to connect to "
                    "this computer from another computer and perform a graphical installation or continue "
                    "with a text mode installation?")
        ask_vnc_question(anaconda, vnc_server, message)

    # if they want us to use VNC do that now
    if anaconda.gui_mode and flags.usevnc:
        vnc_server.startServer()
        do_startup_x11_actions()

    # with X running we can initialize the UI interface
    anaconda.initInterface()
