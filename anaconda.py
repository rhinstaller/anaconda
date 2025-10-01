#!/usr/bin/python3
#
# anaconda: The Red Hat Linux Installation program
#
# Copyright (C) 1999-2013
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

# This toplevel file is a little messy at the moment... (2001-06-22)
# ...still messy (2013-07-12)
# A lot less messy now. :) (2016-10-13)

import atexit
import os
import signal
import sys
import time

import pid

from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.modules.common.structures.reboot import RebootData
from pyanaconda.modules.common.structures.rescue import RescueData


def exitHandler():
    # pylint: disable=possibly-used-before-assignment
    # pylint: disable=used-before-assignment
    runtime_proxy.Exit()

    data_reboot = RebootData.from_structure(runtime_proxy.Reboot)

    anaconda.dbus_launcher.stop()

    if pidfile:
        pidfile.close()

    # Do not reboot or power off in directory installation mode or if reboot is not allowed.
    if not conf.system.can_reboot:
        return

    from pykickstart.constants import KS_SHUTDOWN, KS_WAIT

    if data_reboot.kexec:
        util.execWithRedirect("systemctl", ["--no-wall", "kexec"], do_preexec=False)
        while True:
            time.sleep(10000)
    elif data_reboot.action == KS_SHUTDOWN:
        util.execWithRedirect("systemctl", ["--no-wall", "poweroff"], do_preexec=False)
    elif data_reboot.action == KS_WAIT:
        util.execWithRedirect("systemctl", ["--no-wall", "halt"], do_preexec=False)
    else:  # KS_REBOOT / default
        util.execWithRedirect("systemctl", ["--no-wall", "reboot"], do_preexec=False)

def parse_arguments(argv=None, boot_cmdline=None):
    """Parse command line/boot options and arguments.

    :param argv: command like arguments
    :param boot_cmdline: boot options
    :returns: namespace of parsed options.
    """
    from pyanaconda.argument_parsing import getArgumentParser
    from pyanaconda.core.util import get_anaconda_version_string

    ap = getArgumentParser(get_anaconda_version_string(), boot_cmdline)

    return ap.parse_args(argv, boot_cmdline=boot_cmdline)


def setup_environment():
    """Setup contents of os.environ according to Anaconda needs.

    This method is run before any threads are started, so this is the one
    point where it's ok to modify the environment.
    """
    # pylint: disable=environment-modify

    # Silly GNOME stuff
    if "HOME" in os.environ and not "XAUTHORITY" in os.environ:
        os.environ["XAUTHORITY"] = os.environ["HOME"] + "/.Xauthority"
    os.environ["HOME"] = "/tmp"
    os.environ["LC_NUMERIC"] = "C"
    os.environ["GCONF_GLOBAL_LOCKS"] = "1"

    # In theory, this gets rid of our LVM file descriptor warnings
    os.environ["LVM_SUPPRESS_FD_WARNINGS"] = "1"

    # make sure we have /sbin and /usr/sbin in our path
    os.environ["PATH"] += ":/sbin:/usr/sbin"

    # we can't let the LD_PRELOAD hang around because it will leak into
    # rpm %post and the like.  ick :/
    if "LD_PRELOAD" in os.environ:
        del os.environ["LD_PRELOAD"]

    # Go ahead and set $WAYLAND_DISPLAY whether we're going to use Wayland or not
    if "WAYLAND_DISPLAY" in os.environ:
        flags.preexisting_wayland = True # pylint: disable=possibly-used-before-assignment
    else:
        os.environ["WAYLAND_DISPLAY"] = constants.WAYLAND_SOCKET_NAME  # pylint: disable=possibly-used-before-assignment

    # Go ahead and set $DISPLAY whether we're going to use X or not
    if "DISPLAY" in os.environ:
        flags.preexisting_x11 = True
    else:
        # This line is too long, unfortunately this disable won't work when used on above line
        # pylint: disable=used-before-assignment
        os.environ["DISPLAY"] = ":%s" % constants.X_DISPLAY_NUMBER  # pylint: disable=possibly-used-before-assignment

    # We mostly don't run from bash, so it won't load the file for us, and libreport will then
    # show vi instead of nano. Resolves https://bugzilla.redhat.com/show_bug.cgi?id=1889674
    if "EDITOR" not in os.environ and os.path.isfile("/etc/profile.d/nano-default-editor.sh"):
        os.environ["EDITOR"] = "/usr/bin/nano"

if __name__ == "__main__":
    # check if the CLI help is requested and return it at once,
    # without importing random stuff and spamming stdout
    if ("--help" in sys.argv) or ("-h" in sys.argv) or ("--version" in sys.argv):
        # we skip the full logging initialisation, but we need to do at least
        # this much (redirect any log messages to stdout) to get rid of the
        # harmless but annoying "no handlers found" message on stdout
        import logging
        log = logging.getLogger("anaconda.main")
        log.addHandler(logging.StreamHandler(stream=sys.stdout))
        parse_arguments()

    if os.geteuid() != 0:
        print("anaconda must be run as root.")
        sys.exit(1)

    print("Starting installer, one moment...")

    # Allow a file to be loaded as early as possible
    try:
        # pylint: disable=import-error,unused-import
        import updates_disk_hook
    except ImportError:
        pass

    # Append Python paths to Anaconda addons at the end.
    from pyanaconda.core.constants import ADDON_PATHS

    sys.path.extend(ADDON_PATHS)

    from pyanaconda import startup_utils
    from pyanaconda.core import constants, path, util
    from pyanaconda.core.i18n import _
    from pyanaconda.core.kernel import kernel_arguments
    # init threading before Gtk can do anything and before we start using threads
    from pyanaconda.core.threads import thread_manager

    # do this early so we can set flags before initializing logging
    from pyanaconda.flags import flags
    opts = parse_arguments(boot_cmdline=kernel_arguments)

    conf.set_from_opts(opts)

    # Set up logging as early as possible.
    from pyanaconda import anaconda_loggers, anaconda_logging
    anaconda_logging.init(write_to_journal=conf.target.is_hardware)
    anaconda_logging.logger.setupVirtio(opts.virtiolog)

    # Load the remaining configuration after a logging is set up.
    if opts.profile_id:
        conf.set_from_profile(
            opts.profile_id,
        )
    else:
        conf.set_from_detected_profile(
            util.get_os_release_value("ID"),
            util.get_os_release_value("VARIANT_ID"),
        )

    conf.set_from_files()
    conf.set_from_opts(opts)

    log = anaconda_loggers.get_main_logger()
    stdout_log = anaconda_loggers.get_stdout_logger()

    # see if we're on s390x and if we've got an ssh connection
    if startup_utils.prompt_for_ssh(opts):
        sys.exit(0)

    log.info("%s %s", sys.argv[0], util.get_anaconda_version_string(build_time_version=True))
    # Do not exceed default 8K limit on message length in rsyslog
    for log_line in util.get_image_packages_info(max_string_chars=8096-120):
        log.debug("Image packages: %s", log_line)

    if opts.updates_url:
        log.info("Using updates from: %s", opts.updates_url)

    # print errors encountered during boot
    startup_utils.print_dracut_errors(stdout_log)

    util.ipmi_report(constants.IPMI_STARTED)

    if (opts.images or opts.dirinstall) and opts.liveinst:
        stdout_log.error("--liveinst cannot be used with --images or --dirinstall")
        util.ipmi_report(constants.IPMI_ABORTED)
        sys.exit(1)

    if opts.images and opts.dirinstall:
        stdout_log.error("--images and --dirinstall cannot be used at the same time")
        util.ipmi_report(constants.IPMI_ABORTED)
        sys.exit(1)

    if (opts.images or opts.dirinstall) and not opts.ksfile:
        stdout_log.error("--images and --dirinstall cannot be used without --kickstart")
        util.ipmi_report(constants.IPMI_ABORTED)
        sys.exit(1)

    if opts.images or opts.dirinstall:
        log.debug("Dir and image installations can run only in the non-interactive text mode.")
        stdout_log.info("Enforcing the non-interactive text mode for dir and image installations.")
        opts.display_mode = constants.DisplayModes.TUI
        opts.noninteractive = True

    # we are past the --version and --help shortcut so we can import display &
    # startup_utils, which import Blivet, without slowing down anything critical
    from pyanaconda import (
        display,
        kickstart,
        rescue,
        startup_utils,
    )

    # Print the usual "startup note" that contains Anaconda version
    # and short usage & bug reporting instructions.
    # The note should in most cases end on TTY1.
    startup_utils.print_startup_note(options=opts)

    from pyanaconda.anaconda import Anaconda
    anaconda = Anaconda()

    # reset python's default SIGINT handler
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, lambda num, frame: sys.exit(1))

    # synchronously-delivered signals such as SIGSEGV and SIGILL cannot be handled properly from
    # Python, so install signal handlers from the faulthandler stdlib module.
    import faulthandler
    faulthandler.enable()

    setup_environment()

    # make sure we have /var/log soon, some programs fail to start without it
    path.make_directories("/var/log")

    # Create a PID file. The exit handler, installed later, will clean it up.
    pidfile = pid.PidFile(pidname='anaconda', register_term_signal_handler=False)

    try:
        pidfile.create()
    except pid.PidFileError as e:
        log.error("Unable to create %s, exiting", pidfile.filename)

        # If we had a Wayland/X11 display at start and zenity is available, we may
        # be running in a live environment and we can display an error dialog.
        # Otherwise just print an error.
        preexisting_graphics = flags.preexisting_wayland or flags.preexisting_x11
        if preexisting_graphics and os.access("/usr/bin/zenity", os.X_OK):
            # The module-level _() calls are ok here because the language may
            # be set from the live environment in this case, and anaconda's
            # language setup hasn't happened yet.
            # pylint: disable=found-_-in-module-class
            util.execWithRedirect("zenity",
                                  ["--error", "--title", _("Unable to create PID file"), "--text",
                                   _("Anaconda is unable to create %s because the file"
                                     " already exists. Anaconda is already running, or "
                                     "a previous instance of anaconda has crashed.")
                                   % pidfile.filename])
        else:
            print("%s already exists, exiting" % pidfile.filename)

        util.ipmi_report(constants.IPMI_FAILED)
        sys.exit(1)

    # assign the other anaconda variables from options
    anaconda.set_from_opts(opts)

    # check memory, just the text mode for now:
    startup_utils.check_memory(anaconda, opts, display_mode=constants.DisplayModes.TUI)

    # Now that we've got command line/boot options, do some extra processing.
    startup_utils.setup_logging_from_options(opts)

    # Set up proxy environmental variables.
    startup_utils.set_up_proxy_variables(opts.proxy)

    # set flags
    flags.rescue_mode = opts.rescue
    flags.eject = opts.eject
    flags.kexec = opts.kexec

    if opts.liveinst:
        startup_utils.live_startup()

    # Switch to tty1 on exception in case something goes wrong during X start.
    # This way if, for example, window manager doesn't start, we switch back to a
    # text console with a traceback instead of being left looking at a blank
    # screen. python-meh will replace this excepthook with its own handler
    # once it gets going.
    if conf.system.can_switch_tty:
        def _earlyExceptionHandler(ty, value, traceback):
            util.ipmi_report(constants.IPMI_FAILED)
            util.vtActivate(1)
            return sys.__excepthook__(ty, value, traceback)

        sys.excepthook = _earlyExceptionHandler

    if conf.system.can_audit:
        # Turn off audit, if the environment is such that we can do that. Ignore errors, because
        # auditctl is not a dependency and can be missing for other reasons.
        try:
            util.execWithRedirect("auditctl", ["-e", "0"])
        except OSError:
            pass

    log.info("anaconda called with cmdline = %s", sys.argv)
    log.info("Default encoding = %s ", sys.getdefaultencoding())

    # start dbus session (if not already running) and run boss in it
    try:
        anaconda.dbus_launcher.start()
    except Exception as e:    # pylint: disable=broad-except
        stdout_log.error(str(e))
        anaconda.dbus_launcher.stop()
        util.ipmi_report(constants.IPMI_ABORTED)
        time.sleep(10)
        sys.exit(1)

    # Find a kickstart file.
    kspath = startup_utils.find_kickstart(opts)
    log.info("Found a kickstart file: %s", kspath)

    # Run %pre scripts.
    startup_utils.run_pre_scripts(kspath)

    # Parse the kickstart file.
    ksdata = startup_utils.parse_kickstart(kspath, strict_mode=opts.ksstrict)

    # Pick up any changes from interactive-defaults.ks that would
    # otherwise be covered by the dracut KS parser.
    from pyanaconda.modules.common.constants.objects import BOOTLOADER
    from pyanaconda.modules.common.constants.services import RUNTIME, STORAGE

    bootloader_proxy = STORAGE.get_proxy(BOOTLOADER)
    runtime_proxy = RUNTIME.get_proxy()
    rescue_data = RescueData.from_structure(runtime_proxy.Rescue)

    if opts.leavebootorder:
        bootloader_proxy.KeepBootOrder = True

    if opts.nombr:
        bootloader_proxy.KeepMBR = True

    if rescue_data.rescue:
        flags.rescue_mode = True

    reboot_data = RebootData.from_structure(runtime_proxy.Reboot)
    # reboot with kexec
    if reboot_data.kexec:
        flags.kexec = True

    # Change the logging configuration based on the kickstart.
    startup_utils.setup_logging_from_kickstart()

    anaconda.ksdata = ksdata

    # setup keyboard layout from the command line option and let
    # it override from kickstart if/when X is initialized
    startup_utils.activate_keyboard(opts)

    # Users can supply post-install actions as kickstart scripts, independent of actual kickstart.
    # Add those to the ksdata now.
    kickstart.appendPostScripts(ksdata)

    # Set up the UI context.
    from pyanaconda.ui.context import context
    context.payload_type = anaconda.payload.type

    # Set up the payload from the cmdline options.
    anaconda.payload.set_from_opts(opts)

    # Initialize the security configuration.
    startup_utils.initialize_security()

    # Set the language before loading an interface, when it may be too late.
    startup_utils.initialize_locale(opts, text_mode=anaconda.tui_mode)

    # Initialize the network now, in case the display needs it
    from pyanaconda.network import (
        initialize_network,
        wait_for_connected_NM,
        wait_for_connecting_NM_thread,
    )

    initialize_network()
    # If required by user, wait for connection before starting the installation.
    if opts.waitfornet:
        log.info("network: waiting for connectivity requested by inst.waitfornet=%d", opts.waitfornet)
        wait_for_connected_NM(timeout=opts.waitfornet)

    # In any case do some actions only after NM finishes its connecting.
    thread_manager.add_thread(
        name=constants.THREAD_WAIT_FOR_CONNECTING_NM,
        target=wait_for_connecting_NM_thread
    )

    # Start the interface
    display.setup_display(anaconda, opts)

    # Initialize the default systemd target.
    startup_utils.initialize_default_systemd_target(text_mode=anaconda.tui_mode)

    # Set flag to prompt for missing ks data
    if not anaconda.interactive_mode:
        flags.ksprompt = False

    # Set minimal ram size to the storage checker.
    startup_utils.set_storage_checker_minimal_ram_size(anaconda.display_mode)

    # Set the disk images.
    from pyanaconda.argument_parsing import name_path_pairs
    from pyanaconda.modules.common.constants.objects import DISK_SELECTION
    disk_select_proxy = STORAGE.get_proxy(DISK_SELECTION)
    disk_images = {}

    try:
        for (name, path) in name_path_pairs(opts.images):
            log.info("naming disk image '%s' '%s'", path, name)
            disk_images[name] = path
    except ValueError as e:
        stdout_log.error("error specifying image file: %s", e)
        util.ipmi_abort()
        sys.exit(1)

    disk_select_proxy.DiskImages = disk_images

    # Ignore disks labeled OEMDRV
    from pyanaconda.ui.lib.storage import ignore_oemdrv_disks
    ignore_oemdrv_disks()

    if not conf.target.is_directory:
        from pyanaconda.ui.lib.storage import reset_storage

        thread_manager.add_thread(
            name=constants.THREAD_STORAGE,
            target=reset_storage
        )

    # Initialize the system clock.
    startup_utils.initialize_system_clock()

    if flags.rescue_mode:
        rescue.start_rescue_mode_ui(anaconda)
    else:
        startup_utils.clean_pstore()

    # add our own additional signal handlers
    signal.signal(signal.SIGUSR1, lambda signum, frame:
                  exception.test_exception_handling())
    signal.signal(signal.SIGUSR2, lambda signum, frame: anaconda.dumpState())
    atexit.register(exitHandler)

    from pyanaconda import exception
    anaconda.mehConfig = exception.initExceptionHandling(anaconda)

    # Start the subscription handling thread if the Subscription DBus module
    # provides enough authentication data.
    # - as kickstart only supports org + key authentication & nothing
    #   else currently talks to the Subscription DBus module,
    #   we only check if organization id & at least one activation
    #   key are available
    from pyanaconda.modules.common.constants.services import SUBSCRIPTION
    from pyanaconda.modules.common.util import is_module_available

    if is_module_available(SUBSCRIPTION):
        from pyanaconda.ui.lib.subscription import (
            kickstart_error_handler,
            org_keys_sufficient,
            register_and_subscribe,
        )
        if org_keys_sufficient():
            thread_manager.add_thread(
                name=constants.THREAD_SUBSCRIPTION,
                target=register_and_subscribe,
                args=[anaconda.payload],
                kwargs={"error_callback": kickstart_error_handler}
            )

    # Start the setup tasks of the configured payload.
    from pyanaconda.payload.manager import payloadMgr
    payloadMgr.start(anaconda.payload)

    # initialize geolocation and start geolocation lookup if possible and enabled
    geoloc_task_proxy = startup_utils.start_geolocation_conditionally(opts)

    # setup ntp servers and start NTP daemon if not requested otherwise
    startup_utils.start_chronyd()

    # Finish the initialization of the setup on boot action.
    # This should be done sooner and somewhere else once it is possible.
    startup_utils.initialize_first_boot_action()

    # Create pre-install snapshots
    from pykickstart.constants import SNAPSHOT_WHEN_PRE_INSTALL

    from pyanaconda.kickstart import check_kickstart_error
    from pyanaconda.modules.common.constants.objects import SNAPSHOT
    from pyanaconda.modules.common.task import sync_run_task
    snapshot_proxy = STORAGE.get_proxy(SNAPSHOT)

    if snapshot_proxy.IsRequested(SNAPSHOT_WHEN_PRE_INSTALL):
        # What for the storage to load devices.
        # FIXME: Don't block the main thread!
        thread_manager.wait(constants.THREAD_STORAGE)

        # Run the task.
        snapshot_task_path = snapshot_proxy.CreateWithTask(SNAPSHOT_WHEN_PRE_INSTALL)
        snapshot_task_proxy = STORAGE.get_proxy(snapshot_task_path)

        with check_kickstart_error():
            sync_run_task(snapshot_task_proxy)

    # wait for geolocation, if needed
    startup_utils.wait_for_geolocation_and_use(geoloc_task_proxy, anaconda.display_mode)

    anaconda.intf.setup(ksdata)
    anaconda.intf.run()

# vim:tw=78:ts=4:et:sw=4
