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
import pkgutil

from pyanaconda.i18n import _

import logging
log = logging.getLogger("anaconda")
stdout_log = logging.getLogger("anaconda.stdout")

from pyanaconda import constants
from pyanaconda import iutil
from pyanaconda import vnc
from pyanaconda.flags import flags
from pyanaconda import isys
from pyanaconda import startup_utils
from pyanaconda.nm import nm_is_connected, nm_is_connecting

from pyanaconda.ui.tui.simpleline import App
from pyanaconda.ui.tui.spokes.askvnc import AskVNCSpoke

# needed for checking if the pyanaconda.ui.gui modules are available
import pyanaconda.ui

import blivet

from pykickstart.constants import DISPLAY_MODE_TEXT

# Spice

def start_spice_vd_agent():
    """Start the spice vdagent.

    For certain features to work spice requires that the guest os
    is running the spice vdagent.
    """
    status = iutil.execWithRedirect("spice-vdagent", [])
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
    app = App("VNC Question")
    spoke = AskVNCSpoke(app, anaconda.ksdata, message)
    app.schedule_screen(spoke)
    app.run()

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
    if not nm_is_connecting() and not nm_is_connected():
        error_messages.append("Not asking for VNC because we don't have a network")
        vnc_startup_possible = False

    # disable VNC question if we don't have Xvnc
    if not os.access('/usr/bin/Xvnc', os.X_OK):
        error_messages.append("Not asking for VNC because we don't have Xvnc")
        vnc_startup_possible = False

    return vnc_startup_possible, error_messages

# X11

def start_x11():
    """Start the X server for the Anaconda GUI."""

    # Start Xorg and wait for it become ready
    iutil.startX(["Xorg", "-br", "-logfile", "/tmp/X.log",
                  ":%s" % constants.X_DISPLAY_NUMBER, "vt6", "-s", "1440", "-ac",
                  "-nolisten", "tcp", "-dpi", "96",
                  "-noreset"], output_redirect=subprocess.DEVNULL)

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

    childproc = iutil.startProgram(["metacity", "--display", ":1", "--sm-disable"],
                                   env_add={'XDG_DATA_DIRS': xdg_data_dirs})
    iutil.watchProcess(childproc, "metacity")

def set_x_resolution(runres):
    """Set X server screen resolution.

    :param str runres: a resolution specification string
    """
    try:
        log.info("Setting the screen resolution to: %s.", runres)
        iutil.execWithRedirect("xrandr", ["-d", ":1", "-s", runres])
    except RuntimeError:
        log.error("The X resolution was not set")
        iutil.execWithRedirect("xrandr", ["-d", ":1", "-q"])

def do_extra_x11_actions(runres, gui_mode):
    """Perform X11 actions not related to startup.

    :param str runres: a resolution specification string
    :param display_mode: an Anaconda display mode
    """
    if runres and gui_mode and not flags.usevnc:
        set_x_resolution(runres)

    # Load the system-wide Xresources
    iutil.execWithRedirect("xrdb", ["-nocpp", "-merge", "/etc/X11/Xresources"])

    start_spice_vd_agent()

# general display startup

def setup_display(anaconda, options, addon_paths=None):
    """Setup the display for the installation environment.

    :param anaconda: instance of the Anaconda class
    :param options: command line/boot options
    :param addon_paths: Anaconda addon paths
    """

    vnc_server = vnc.VncServer()  # The vnc Server object.
    vnc_server.anaconda = anaconda

    anaconda.display_mode = options.display_mode
    anaconda.interactive_mode = not options.noninteractive
    anaconda.isHeadless = blivet.arch.is_s390()

    if anaconda.nui_mode:
        flags.automatedInstall = True
        flags.ksprompt = False
        anaconda.interactive_mode = False

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
        anaconda.xdriver = options.xdriver
        anaconda.writeXdriver(root="/")

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

    # X on a headless (e.g. s390) system? Nonsense!
    if want_x and anaconda.isHeadless:
        stdout_log.warning(_("DISPLAY variable not set. Starting text mode."))
        anaconda.display_mode = constants.DisplayModes.TUI
        anaconda.gui_startup_failed = True
        time.sleep(2)
        want_x = False

    # Is Xorg is actually available?
    if want_x and not os.access("/usr/bin/Xorg", os.X_OK):
        stdout_log.warning(_("Graphical installation is not available. "
                             "Starting text mode."))
        time.sleep(2)
        anaconda.display_mode = constants.DisplayModes.TUI
        want_x = False

    if anaconda.tui_mode and flags.vncquestion:
        #we prefer vnc over text mode, so ask about that
        message = _("Text mode provides a limited set of installation "
                    "options. It does not offer custom partitioning for "
                    "full control over the disk layout. Would you like "
                    "to use VNC mode instead?")
        ask_vnc_question(anaconda, vnc_server, message)
        if not anaconda.ksdata.vnc.enabled:
            # user has explicitly specified text mode
            flags.vncquestion = False

    display_mode_name = anaconda.display_mode.value
    if display_mode_name:
        log.info("Display mode = %s", anaconda.display_mode)
    elif anaconda.display_mode:
        log.error("Unknown display mode: %s", anaconda.display_mode)
    else:
        log.error("Display mode not set!")

    startup_utils.check_memory(anaconda, options)

    # check_memory may have changed the display mode
    want_x = want_x and (anaconda.gui_mode)
    if want_x:
        try:
            start_x11()
            do_startup_x11_actions()
        except (OSError, RuntimeError) as e:
            log.warning("X startup failed: %s", e)
            stdout_log.warning("X startup failed, falling back to text mode")
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
    anaconda.initInterface(addon_paths=addon_paths)
    # and the install class
    anaconda.instClass.configure(anaconda)
