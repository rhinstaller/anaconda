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
import signal

from pyanaconda.mutter_display import MutterDisplay, MutterConfigError
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.path import join_paths
from pyanaconda.core.process_watchers import WatchProcesses
from pyanaconda import startup_utils
from pyanaconda.core import util, constants, hw
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

    # Start the user instance of systemd. This call will also cause the launch of
    # dbus-broker and start a session bus at XDG_RUNTIME_DIR/bus.
    childproc = util.startProgram(["/usr/lib/systemd/systemd", "--user"])
    WatchProcesses.watch_process(childproc, "systemd")

    # Set up the session bus address. Some services started by Anaconda might call
    # dbus-launch with the --autolaunch option to find the existing session bus (or
    # start a new one), but dbus-launch doesn't check the XDG_RUNTIME_DIR/bus path.
    xdg_runtime_dir = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
    session_bus_address = "unix:path=" + join_paths(xdg_runtime_dir, "/bus")
    os.environ["DBUS_SESSION_BUS_ADDRESS"] = session_bus_address
    log.info("The session bus address is set to %s.", session_bus_address)

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
    spoke = AskVNCSpoke(anaconda.ksdata, message=message)
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

    When window manager actually connects to the X server is unknowable, but
    fortunately it doesn't matter. Wm does not need to be the first
    connection to Xorg, and if anaconda starts up before wm, wm
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

    xdg_config_dirs = datadir
    if 'XDG_CONFIG_DIRS' in os.environ:
        xdg_config_dirs = datadir + ':' + os.environ['XDG_CONFIG_DIRS']
    os.environ['XDG_CONFIG_DIRS'] = xdg_config_dirs

    def x11_preexec():
        # to set GUI subprocess SIGINT handler
        signal.signal(signal.SIGINT, signal.SIG_IGN)

    childproc = util.startProgram(["gnome-kiosk", "--display", ":1", "--sm-disable", "--x11"],
                                  env_add={'XDG_DATA_DIRS': xdg_data_dirs},
                                  preexec_fn=x11_preexec)
    WatchProcesses.watch_process(childproc, "gnome-kiosk")


def set_resolution(runres):
    """Set the screen resolution.

    :param str runres: a resolution specification string
    """
    try:
        log.info("Setting the screen resolution to: %s.", runres)
        mutter_display = MutterDisplay()
        mutter_display.set_resolution(runres)
    except MutterConfigError as error:
        log.error("The resolution was not set: %s", error)


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
    anaconda.display_mode = options.display_mode
    anaconda.interactive_mode = not options.noninteractive

    if flags.rescue_mode:
        return

    if conf.target.is_image or conf.target.is_directory:
        anaconda.log_display_mode()
        anaconda.initialize_interface()
        return

    try:
        xtimeout = int(options.xtimeout)
    except ValueError:
        log.warning("invalid inst.xtimeout option value: %s", options.xtimeout)
        xtimeout = constants.X_TIMEOUT

    vnc_server = vnc.VncServer()  # The vnc Server object.
    vnc_server.anaconda = anaconda
    vnc_server.timeout = xtimeout

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
        except TimeoutError as e:
            log.warning("X startup failed: %s", e)
            print("\nX did not start in the expected time, falling back to text mode. There are "
                  "multiple ways to avoid this issue:")
            wrapper = textwrap.TextWrapper(initial_indent=" * ", subsequent_indent="   ",
                                           width=os.get_terminal_size().columns - 3)
            for line in X_TIMEOUT_ADVICE.split("\n"):
                print(wrapper.fill(line))
            util.vtActivate(1)
            anaconda.display_mode = constants.DisplayModes.TUI
            anaconda.gui_startup_failed = True
            time.sleep(2)

        except (OSError, RuntimeError) as e:
            log.warning("X or window manager startup failed: %s", e)
            print("\nX or window manager startup failed, falling back to text mode.")
            util.vtActivate(1)
            anaconda.display_mode = constants.DisplayModes.TUI
            anaconda.gui_startup_failed = True
            time.sleep(2)

        if not anaconda.gui_startup_failed:
            if options.runres and anaconda.gui_mode and not flags.usevnc:
                def on_mutter_ready(observer):
                    set_resolution(options.runres)
                    observer.disconnect()

                mutter_display = MutterDisplay()
                mutter_display.on_service_ready(on_mutter_ready)

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
    anaconda.initialize_interface()

    if anaconda.gui_startup_failed:
        # we need to reinitialize the locale if GUI startup failed,
        # as we might now be in text mode, which might not be able to display
        # the characters from our current locale
        startup_utils.reinitialize_locale(text_mode=anaconda.tui_mode)
