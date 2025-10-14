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
import signal
import textwrap
import time
from collections import namedtuple

import blivet
from simpleline import App
from simpleline.render.screen_handler import ScreenHandler
from systemd import journal

from pyanaconda import startup_utils
from pyanaconda.anaconda_loggers import get_module_logger, get_stdout_logger
from pyanaconda.core import constants, hw, util
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.i18n import _
from pyanaconda.core.process_watchers import WatchProcesses
from pyanaconda.flags import flags
from pyanaconda.gnome_remote_desktop import GRDServer
from pyanaconda.modules.common.constants.objects import USER_INTERFACE
from pyanaconda.modules.common.constants.services import NETWORK, RUNTIME
from pyanaconda.modules.common.structures.rdp import RdpData
from pyanaconda.mutter_display import MutterConfigError, MutterDisplay
from pyanaconda.ui.tui import tui_quit_callback
from pyanaconda.ui.tui.spokes.askrd import AskRDSpoke, RDPAuthSpoke

log = get_module_logger(__name__)
stdout_log = get_stdout_logger()


rdp_credentials = namedtuple("rdp_credentials", ["username", "password"])


WAYLAND_TIMEOUT_ADVICE = \
    "Do not load the stage2 image over a slow network link.\n" \
    "Wait longer for Wayland startup with the inst.xtimeout=<SECONDS> boot option." \
    "The default is 60 seconds.\n" \
    "Load the stage2 image into memory with the rd.live.ram boot option to decrease access " \
    "time.\n" \
    "Enforce text mode when installing from remote media with the inst.text boot option."
#  on RHEL also: "Use the customer portal download URL in ilo/drac devices for greater speed."

# RDP

def ask_rd_question(anaconda, message):
    """ Ask the user if TUI or GUI-over-RDP should be started.

    Return Tuple(should use RDP, NameTuple rdp_credentials(username, password))

    e.g.:
    (True, rdp_credentials)
    rdp_credentials.username
    rdp_credentials.password

    :param anaconda: instance of the Anaconda class
    :param str message: a message to show to the user together
                        with the question
    :return: (use_rd, rdp_credentials(username, password))
    :rtype: Tuple(bool, NameTuple(username, password))
    """
    App.initialize()
    loop = App.get_event_loop()
    loop.set_quit_callback(tui_quit_callback)
    # Get current RDP data from DBUS
    ui_proxy = RUNTIME.get_proxy(USER_INTERFACE)
    rdp_data = RdpData.from_structure(ui_proxy.Rdp)
    spoke = AskRDSpoke(anaconda.ksdata, rdp_data, message=message)
    ScreenHandler.schedule_screen(spoke)
    App.run()

    return (spoke.use_remote_desktop, rdp_credentials(spoke.rdp_username, spoke.rdp_password))


def ask_for_rd_credentials(anaconda, username=None, password=None):
    """ Ask the user to provide RDP credentials interactively.

    :param anaconda: instance of the Anaconda class
    :param str username: user set username (if any)
    :param str password: user set password (if any)

    :return: (use_rd, rdp_credentials(username, password))
    :rtype: Tuple(bool, NameTuple(username, password))
    """
    App.initialize()
    loop = App.get_event_loop()
    loop.set_quit_callback(tui_quit_callback)
    ui_proxy = RUNTIME.get_proxy(USER_INTERFACE)
    rdp_data = RdpData.from_structure(ui_proxy.Rdp)
    spoke = RDPAuthSpoke(anaconda.ksdata, rdp_data, username=username, password=password)
    ScreenHandler.schedule_screen(spoke)
    App.run()

    return (True, rdp_credentials(spoke._username, spoke._password))


def check_rd_can_be_started(anaconda):
    """Check if we can start an RDP session in the current environment.

    :returns: if RDP session can be started and list of possible reasons
              why the session can't be started
    :rtype: (boot, list)
    """

    error_messages = []
    rd_startup_possible = True

    # disable remote desktop over text question when not enough memory is available
    min_gui_ram = hw.minimal_memory_needed(with_gui=True)
    if blivet.util.total_memory() < min_gui_ram:
        error_messages.append("Not asking for remote desktop session because current memory "
                              "(%d) < MIN_GUI_RAM (%d)" %
                              (blivet.util.total_memory(), min_gui_ram))
        rd_startup_possible = False

    # disable remote desktop question if text mode is requested and this is a ks install
    if anaconda.tui_mode and flags.automatedInstall:
        error_messages.append(
            "Not asking for remote desktop session because of an automated install"
        )
        rd_startup_possible = False

    # disable remote desktop question if we were explicitly asked for text in kickstart
    proxy = RUNTIME.get_proxy(USER_INTERFACE)
    if proxy.DisplayModeTextKickstarted:
        error_messages.append("Not asking for remote desktop session because text mode "
                              "was explicitly asked for in kickstart")
        rd_startup_possible = False

    # disable remote desktop question if we don't have network
    network_proxy = NETWORK.get_proxy()
    if not network_proxy.IsConnecting() and not network_proxy.Connected:
        error_messages.append("Not asking for RDP mode because we don't have a network")
        rd_startup_possible = False

    # disable remote desktop question if we don't have GNOME remote desktop
    if not os.access('/usr/bin/grdctl', os.X_OK):
        error_messages.append("Not asking for remote desktop because we don't have grdctl")
        rd_startup_possible = False

    return rd_startup_possible, error_messages


def do_startup_wl_actions(timeout, headless=False, headless_resolution=None):
    """Start the Wayland compositor.

    Add XDG_DATA_DIRS to the environment to pull in our overridden schema
    files.

    :param bool headless: start a headless session (used for RDP access)
    :param str headless_resolution: headless virtual monitor resolution in WxH format
    """
    datadir = os.environ.get('ANACONDA_DATADIR', '/usr/share/anaconda')
    if 'XDG_DATA_DIRS' in os.environ:
        xdg_data_dirs = datadir + '/window-manager:' + os.environ['XDG_DATA_DIRS']
    else:
        xdg_data_dirs = datadir + '/window-manager:/usr/share'

    xdg_config_dirs = datadir
    if 'XDG_CONFIG_DIRS' in os.environ:
        xdg_config_dirs = datadir + ':' + os.environ['XDG_CONFIG_DIRS']
    # pylint: disable=environment-modify
    os.environ['XDG_CONFIG_DIRS'] = xdg_config_dirs
    os.environ["XDG_SESSION_TYPE"] = "wayland"

    def wl_preexec():
        # to set GUI subprocess SIGINT handler
        signal.signal(signal.SIGINT, signal.SIG_IGN)

    # lets compile arguments for the run-in-new-session script
    argv = ["/usr/libexec/anaconda/run-in-new-session",
            "--user", "root",
            "--service", "anaconda",
            "--session-type", "wayland",
            "--session-class", "user"]

    if headless:
        # headless (remote connection) - stay on VT1 where connection info is
        argv.extend(["--vt", "1"])
    else:
        # local display - switch to VT6 & show GUI there
        argv.extend(["--vt", "6"])

    # add the generic GNOME Kiosk invocation
    argv.extend(["gnome-kiosk", "--wayland", "--wayland-display", constants.WAYLAND_SOCKET_NAME])

    # remote access needs gnome-kiosk to start in headless mode
    if headless:
        argv.extend(["--headless"])

    # redirect stdout and stderr from GNOME Kiosk to journal
    gnome_kiosk_stdout_stream = journal.stream("gnome-kiosk", priority=journal.LOG_INFO)
    gnome_kiosk_stderr_stream = journal.stream("gnome-kiosk", priority=journal.LOG_ERR)

    childproc = util.startProgram(argv, env_add={'XDG_DATA_DIRS': xdg_data_dirs},
                                  preexec_fn=wl_preexec,
                                  stdout=gnome_kiosk_stdout_stream,
                                  stderr=gnome_kiosk_stderr_stream,
                                  )
    WatchProcesses.watch_process(childproc, argv[0])

    for _i in range(0, int(timeout / 0.1)):
        wl_socket_path = os.path.join(os.getenv("XDG_RUNTIME_DIR"), constants.WAYLAND_SOCKET_NAME)
        if os.path.exists(wl_socket_path):
            return

        time.sleep(0.1)

    WatchProcesses.unwatch_process(childproc)
    childproc.terminate()
    raise TimeoutError("Timeout trying to start gnome-kiosk")


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


# general display startup
def setup_display(anaconda, options):
    """Setup the display for the installation environment.

    :param anaconda: instance of the Anaconda class
    :param options: command line/boot options
    """
    anaconda.display_mode = options.display_mode
    anaconda.interactive_mode = not options.noninteractive

    # TODO: Refactor this method or maybe whole class, ideally this class should be usable only
    # on boot.iso where compositor could be set
    if flags.rescue_mode:
        return

    if conf.target.is_image or conf.target.is_directory:
        anaconda.log_display_mode()
        anaconda.initialize_interface()
        return

    # we can't start compositor so not even RDP is supported, do only base initialization
    if not conf.system.can_start_compositor:
        anaconda.log_display_mode()
        anaconda.initialize_interface()
        startup_utils.fallback_to_tui_if_gtk_ui_is_not_available(anaconda)
        startup_utils.check_memory(anaconda, options)
        return

    try:
        xtimeout = int(options.xtimeout)
    except ValueError:
        log.warning("invalid inst.xtimeout option value: %s", options.xtimeout)
        xtimeout = constants.X_TIMEOUT

    rdp_credentials_sufficient = False
    rdp_creds = rdp_credentials("", "")

    if options.rdp_enabled:
        flags.use_rd = True
        if not anaconda.gui_mode:
            log.info("RDP requested via boot/CLI option, switching Anaconda to GUI mode.")
            anaconda.display_mode = constants.DisplayModes.GUI
        rdp_creds = rdp_credentials(options.rdp_username, options.rdp_password)
        # note if we have both set
        rdp_credentials_sufficient = bool(rdp_creds.username and rdp_creds.password)

    ui_proxy = RUNTIME.get_proxy(USER_INTERFACE)
    rdp_data = RdpData.from_structure(ui_proxy.Rdp)

    if rdp_data.enabled:
        flags.use_rd = True
        if not anaconda.gui_mode:
            log.info("RDP requested via kickstart, switching Anaconda to GUI mode.")
            anaconda.display_mode = constants.DisplayModes.GUI

        rdp_creds = rdp_credentials(rdp_data.username, rdp_data.password.value)
        rdp_credentials_sufficient = bool(rdp_creds.username and rdp_creds.password)

    # check if GUI without WebUI
    startup_utils.fallback_to_tui_if_gtk_ui_is_not_available(anaconda)

    # check if remote desktop mode can be started
    rd_can_be_started, rd_error_messages = check_rd_can_be_started(anaconda)

    if rd_can_be_started:
        # if remote desktop can be started & only inst.rdp
        # or inst.rdp and insufficient credentials are provided
        # via boot options, ask interactively.
        if options.rdp_enabled and not rdp_credentials_sufficient:
            use_rd, rdp_creds = ask_for_rd_credentials(anaconda,
                                                       options.rdp_username,
                                                       options.rdp_password)
            _set_gui_mode_on_rdp(anaconda, use_rd)
    else:
        # RDP can't be started - disable the RDP question and log
        # all the errors that prevented RDP from being started
        flags.rd_question = False
        for error_message in rd_error_messages:
            stdout_log.warning(error_message)

    if anaconda.tui_mode and flags.rd_question:
        # we prefer remote desktop over text mode, so ask about that
        message = _("Text mode provides a limited set of installation "
                    "options. It does not offer custom partitioning for "
                    "full control over the disk layout. Would you like "
                    "to use remote graphical access via the RDP protocol instead?")
        use_rd, credentials = ask_rd_question(anaconda, message)
        _set_gui_mode_on_rdp(anaconda, use_rd)
        if not use_rd:
            # user has explicitly specified text mode
            flags.rd_question = False
        else:
            rdp_creds = credentials

    anaconda.log_display_mode()
    startup_utils.check_memory(anaconda, options)

    # check_memory may have changed the display mode
    want_gui = anaconda.gui_mode and not (flags.preexisting_wayland or flags.use_rd)
    if want_gui:
        try:
            do_startup_wl_actions(xtimeout)
        except TimeoutError as e:
            log.warning("Wayland startup failed: %s", e)
            print("\nWayland did not start in the expected time, falling back to text mode. "
                  "There are multiple ways to avoid this issue:")
            wrapper = textwrap.TextWrapper(initial_indent=" * ", subsequent_indent="   ",
                                           width=os.get_terminal_size().columns - 3)
            for line in WAYLAND_TIMEOUT_ADVICE.split("\n"):
                print(wrapper.fill(line))
            util.vtActivate(1)
            anaconda.display_mode = constants.DisplayModes.TUI
            anaconda.gui_startup_failed = True
            time.sleep(2)

        except (OSError, RuntimeError) as e:
            log.warning("Wayland startup failed: %s", e)
            print("\nWayland startup failed, falling back to text mode.")
            util.vtActivate(1)
            anaconda.display_mode = constants.DisplayModes.TUI
            anaconda.gui_startup_failed = True
            time.sleep(2)

        if not anaconda.gui_startup_failed:
            if options.runres and anaconda.gui_mode and not flags.use_rd:
                def on_mutter_ready(observer):
                    set_resolution(options.runres)
                    observer.disconnect()

                mutter_display = MutterDisplay()
                mutter_display.on_service_ready(on_mutter_ready)

    if anaconda.tui_mode and anaconda.gui_startup_failed and flags.rd_question:

        message = _("Wayland was unable to start on your machine. Would you like to start "
                    "an RDP session to connect to this computer from another computer and "
                    "perform a graphical installation or continue with a text mode "
                    "installation?")
        # we aren't really interested in the use_rd flag so at least mark it like this
        # to avoid linters being grumpy
        use_rd, rdp_creds = ask_rd_question(anaconda, message)
        _set_gui_mode_on_rdp(anaconda, use_rd)

    # if they want us to use RDP do that now
    if anaconda.gui_mode and flags.use_rd:
        do_startup_wl_actions(xtimeout, headless=True, headless_resolution=options.runres)
        grd_server = GRDServer(anaconda)  # The RDP server object
        grd_server.rdp_username = rdp_creds.username
        grd_server.rdp_password = rdp_creds.password
        grd_server.start_grd_rdp()

    # with Wayland running we can initialize the UI interface
    anaconda.initialize_interface()

    if anaconda.gui_startup_failed:
        # we need to reinitialize the locale if GUI startup failed,
        # as we might now be in text mode, which might not be able to display
        # the characters from our current locale
        startup_utils.reinitialize_locale(text_mode=anaconda.tui_mode)


def _set_gui_mode_on_rdp(anaconda, use_rdp):
    if not use_rdp:
        anaconda.display_mode = constants.DisplayModes.TUI
        return

    if not anaconda.gui_mode:
        log.info("RDP requested via RDP question, switching Anaconda to GUI mode.")
    anaconda.display_mode = constants.DisplayModes.GUI
    flags.use_rd = use_rdp
