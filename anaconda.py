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

import os
import site


coverage = None

# setup code coverage monitoring
proc_cmdline = open("/proc/cmdline", "r").read()
proc_cmdline = proc_cmdline.split()
if ("inst.debug=1" in proc_cmdline) or ("inst.debug" in proc_cmdline):
    import coverage
    pyanaconda_dir = "pyanaconda"
    for sitepkg in site.getsitepackages():
        possible_dir = os.path.join(sitepkg, "pyanaconda")
        if os.path.isdir(possible_dir):
            pyanaconda_dir = possible_dir
            break
    cov = coverage.coverage(data_file="/mnt/sysimage/root/anaconda.coverage",
                            branch=True,
                            source=["/usr/sbin/anaconda", pyanaconda_dir]
                            )
    cov.start()


import atexit, sys, time, signal
import pid

def exitHandler(rebootData, storage):
    # Clear the list of watched PIDs.
    from pyanaconda.core.process_watchers import WatchProcesses
    WatchProcesses.unwatch_all_processes()

    # stop and save coverage here b/c later the file system may be unavailable
    if coverage is not None:
        cov.stop()
        if os.path.isdir('/mnt/sysimage/root'):
            cov.save()

    if flags.usevnc:
        vnc.shutdownServer()

    if "nokill" in flags.cmdline:
        util.vtActivate(1)
        print("anaconda halting due to nokill flag.")
        print("The system will be rebooted when you press Ctrl-Alt-Delete.")
        while True:
            time.sleep(10000)

    if anaconda.dbus_inhibit_id:
        from pyanaconda.screensaver import uninhibit_screensaver
        uninhibit_screensaver(anaconda.dbus_session_connection, anaconda.dbus_inhibit_id)
        anaconda.dbus_inhibit_id = None

    # Unsetup the payload, which most usefully unmounts live images
    if anaconda.payload:
        anaconda.payload.unsetup()

    if image_count or flags.dirInstall:
        anaconda.storage.umount_filesystems(swapoff=False)
        devicetree = anaconda.storage.devicetree
        devicetree.teardown_all()
        for imageName in devicetree.disk_images:
            dev = devicetree.get_device_by_name(imageName)
            for loop in dev.parents:
                loop.controllable = True
            dev.deactivate(recursive=True)

    # Clean up the PID file
    if pidfile:
        pidfile.close()

    anaconda.cleanup_dbus_session()

    if not flags.imageInstall and not flags.livecdInstall \
       and not flags.dirInstall:
        from pykickstart.constants import KS_SHUTDOWN, KS_WAIT

        if flags.eject or rebootData.eject:
            for cdrom in (d for d in storage.devices if d.type == "cdrom"):
                if util.get_mount_paths(cdrom.path):
                    util.dracut_eject(cdrom.path)

        if flags.kexec:
            util.execWithRedirect("systemctl", ["--no-wall", "kexec"])
            while True:
                time.sleep(10000)
        elif rebootData.action == KS_SHUTDOWN:
            util.execWithRedirect("systemctl", ["--no-wall", "poweroff"])
        elif rebootData.action == KS_WAIT:
            util.execWithRedirect("systemctl", ["--no-wall", "halt"])
        else:  # reboot action is KS_REBOOT or None
            util.execWithRedirect("systemctl", ["--no-wall", "reboot"])

def setup_python_updates():
    """Setup updates to Anaconda Python files."""
    from distutils.sysconfig import get_python_lib
    import gi.overrides

    if "ANACONDA_WIDGETS_OVERRIDES" in os.environ:
        for p in os.environ["ANACONDA_WIDGETS_OVERRIDES"].split(":"):
            gi.overrides.__path__.insert(0, os.path.abspath(p))

    # Temporary hack for F18 alpha to symlink updates and product directories
    # into tmpfs.  To be removed after beta in order to directly use content
    # from /run/install/ -- JLK
    for dirname in ("updates", "product"):
        if os.path.exists("/run/install/%s" % dirname):
            if os.path.islink("/tmp/%s" % dirname):
                # Assume updates have already been setup
                return
            os.symlink("/run/install/%s" % dirname,
                       "/tmp/%s" % dirname)

    if not os.path.exists("/tmp/updates"):
        return

    for pkg in os.listdir("/tmp/updates"):
        d = "/tmp/updates/%s" % pkg

        if not os.path.isdir(d):
            continue

        # See if the package exists in /usr/lib{64,}/python/?.?/site-packages.
        # If it does, we can set it up as an update.  If not, the pkg is
        # likely a completely new directory and should not be looked at.
        dest = "%s/%s" % (get_python_lib(), pkg)
        if not os.access(dest, os.R_OK):
            dest = "%s/%s" % (get_python_lib(1), pkg)
            if not os.access(dest, os.R_OK):
                continue
        # Symlink over everything that's in the python libdir but not in
        # the updates directory.
        symlink_updates(dest, d)

    gi.overrides.__path__.insert(0, "/run/install/updates")

    import glob
    import shutil
    for rule in glob.glob("/tmp/updates/*.rules"):
        target = "/etc/udev/rules.d/" + rule.split('/')[-1]
        shutil.copyfile(rule, target)

def symlink_updates(dest_dir, update_dir):
    """Setup symlinks for the updates from the updates image.

    :param str dest_dir: symlink target
    :param str update_dir: symlink source (updates image content)
    """
    contents = os.listdir(update_dir)

    for f in os.listdir(dest_dir):
        dest_path = os.path.join(dest_dir, f)
        update_path = os.path.join(update_dir, f)
        if f in contents:
            # recurse into directories, there might be files missing in updates
            if os.path.isdir(dest_path) and os.path.isdir(update_path):
                symlink_updates(dest_path, update_path)
        else:
            if f.endswith(".pyc") or f.endswith(".pyo"):
                continue
            os.symlink(dest_path, update_path)

def parse_arguments(argv=None, boot_cmdline=None):
    """Parse command line/boot options and arguments.

    :param argv: command like arguments
    :param boot_cmdline: boot options
    :returns: namespace of parsed options and a list of deprecated
              anaconda options that have been found
    """
    from pyanaconda.argument_parsing import getArgumentParser
    from pyanaconda.startup_utils import get_anaconda_version_string

    ap = getArgumentParser(get_anaconda_version_string(), boot_cmdline)

    namespace = ap.parse_args(argv, boot_cmdline=boot_cmdline)
    return (namespace, ap.deprecated_bootargs)

def setup_python_path():
    """Add items Anaconda needs to sys.path."""
    # First add our updates path
    sys.path.insert(0, '/tmp/updates/')

    from pyanaconda.core.constants import ADDON_PATHS
    # append ADDON_PATHS dirs at the end
    sys.path.extend(ADDON_PATHS)

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

    # Go ahead and set $DISPLAY whether we're going to use X or not
    if "DISPLAY" in os.environ:
        flags.preexisting_x11 = True
    else:
        os.environ["DISPLAY"] = ":%s" % constants.X_DISPLAY_NUMBER

# pylint: disable=redefined-outer-name
def start_debugger(signum, frame):
    # pylint: disable=import-error
    import epdb
    epdb.serve(skip=1)

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

    print("Starting installer, one moment...")

    # Allow a file to be loaded as early as possible
    try:
        # pylint: disable=import-error,unused-import
        import updates_disk_hook
    except ImportError:
        pass

    # this handles setting up updates for pypackages to minimize the set needed
    setup_python_updates()
    setup_python_path()

    # init threading before Gtk can do anything and before we start using threads
    # initThreading initializes the threadMgr instance, import it afterwards
    from pyanaconda.threading import initThreading, AnacondaThread, threadMgr
    initThreading()

    from pyanaconda.core.i18n import _

    from pyanaconda.addons import collect_addon_paths
    from pyanaconda.core import util, constants
    from pyanaconda import startup_utils

    # do this early so we can set flags before initializing logging
    from pyanaconda.flags import flags, can_touch_runtime_system
    (opts, depr) = parse_arguments(boot_cmdline=flags.cmdline)

    if opts.images:
        flags.imageInstall = True
    elif opts.dirinstall:
        flags.dirInstall = True

    # Set up logging as early as possible.
    from pyanaconda import anaconda_logging
    from pyanaconda import anaconda_loggers
    anaconda_logging.init()
    anaconda_logging.logger.setupVirtio()

    from pyanaconda import network
    network.setup_ifcfg_log()

    log = anaconda_loggers.get_main_logger()
    stdout_log = anaconda_loggers.get_stdout_logger()

    if os.geteuid() != 0:
        stdout_log.error("anaconda must be run as root.")
        sys.exit(1)

    # check if input kickstart should be saved
    if flags.nosave_input_ks:
        log.warning("Input kickstart will not be saved to the installed system due to the nosave option.")
        util.touch('/tmp/NOSAVE_INPUT_KS')

    # check if logs should be saved
    if flags.nosave_logs:
        log.warning("Installation logs will not be saved to the installed system due to the nosave option.")
        util.touch('/tmp/NOSAVE_LOGS')

    # see if we're on s390x and if we've got an ssh connection
    uname = os.uname()
    if uname[4] == 's390x':
        if 'TMUX' not in os.environ and 'ks' not in flags.cmdline and not flags.imageInstall:
            startup_utils.prompt_for_ssh()
            sys.exit(0)

    log.info("%s %s", sys.argv[0], startup_utils.get_anaconda_version_string(build_time_version=True))
    if os.path.exists("/tmp/updates"):
        log.info("Using updates in /tmp/updates/ from %s", opts.updateSrc)

    # TODO: uncomment this when we're sure that we're doing the right thing
    # with flags.cmdline *everywhere* it appears...
    #for arg in depr:
    #    stdout_log.warn("Boot argument '%s' is deprecated. "
    #                   "In the future, use 'inst.%s'.", arg, arg)

    from pyanaconda import isys

    util.ipmi_report(constants.IPMI_STARTED)

    if (opts.images or opts.dirinstall) and opts.liveinst:
        stdout_log.error("--liveinst cannot be used with --images or --dirinstall")
        util.ipmi_report(constants.IPMI_ABORTED)
        sys.exit(1)

    if opts.images and opts.dirinstall:
        stdout_log.error("--images and --dirinstall cannot be used at the same time")
        util.ipmi_report(constants.IPMI_ABORTED)
        sys.exit(1)
    elif opts.dirinstall:
        root_path = opts.dirinstall
        util.setTargetPhysicalRoot(root_path)
        util.setSysroot(root_path)

    from pyanaconda import vnc
    from pyanaconda import kickstart
    from pyanaconda import ntp
    from pyanaconda import keyboard
    # we are past the --version and --help shortcut so we can import display &
    # startup_utils, which import Blivet, without slowing down anything critical
    from pyanaconda import display
    from pyanaconda import startup_utils
    from pyanaconda import rescue
    from pyanaconda import geoloc
    from pyanaconda.core.util import ProxyString, ProxyStringError

    # Print the usual "startup note" that contains Anaconda version
    # and short usage & bug reporting instructions.
    # The note should in most cases end on TTY1.
    startup_utils.print_startup_note(options=opts)

    from pyanaconda.anaconda import Anaconda
    anaconda = Anaconda()
    util.setup_translations()

    # reset python's default SIGINT handler
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, lambda num, frame: sys.exit(1))

    # synchronously-delivered signals such as SIGSEGV and SIGILL cannot be
    # handled properly from python, so install signal handlers from the C
    # function in isys.
    isys.installSyncSignalHandlers()

    setup_environment()

    # make sure we have /var/log soon, some programs fail to start without it
    util.mkdirChain("/var/log")

    # Create a PID file. The exit handler, installed later, will clean it up.
    pidfile = pid.PidFile(pidname='anaconda', register_term_signal_handler=False)

    try:
        pidfile.create()
    except pid.PidFileError as e:
        log.error("Unable to create %s, exiting", pidfile.filename)

        # If we had a $DISPLAY at start and zenity is available, we may be
        # running in a live environment and we can display an error dialog.
        # Otherwise just print an error.
        if flags.preexisting_x11 and os.access("/usr/bin/zenity", os.X_OK):
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

    # add our own additional signal handlers
    signal.signal(signal.SIGHUP, start_debugger)

    # assign the other anaconda variables from options
    anaconda.set_from_opts(opts)

    # check memory, just the text mode for now:
    startup_utils.check_memory(anaconda, opts, display_mode=constants.DisplayModes.TUI)

    # Now that we've got command line/boot options, do some extra processing.
    startup_utils.setup_logging_from_options(opts)

    # set flags
    flags.rescue_mode = opts.rescue
    flags.noverifyssl = opts.noverifyssl
    flags.armPlatform = opts.armPlatform
    flags.extlinux = opts.extlinux
    flags.nombr = opts.nombr
    flags.mpathFriendlyNames = opts.mpathfriendlynames
    flags.debug = opts.debug
    flags.askmethod = opts.askmethod
    flags.dmraid = opts.dmraid
    flags.mpath = opts.mpath
    flags.ibft = opts.ibft
    flags.nonibftiscsiboot = opts.nonibftiscsiboot
    flags.selinux = opts.selinux
    flags.eject = opts.eject
    flags.kexec = opts.kexec
    flags.singlelang = opts.singlelang

    if opts.liveinst:
        startup_utils.live_startup(anaconda)
    elif "LIVECMD" in os.environ:
        log.warning("Running via liveinst, but not setting flags.livecdInstall - this is for testing only")

    # Switch to tty1 on exception in case something goes wrong during X start.
    # This way if, for example, metacity doesn't start, we switch back to a
    # text console with a traceback instead of being left looking at a blank
    # screen. python-meh will replace this excepthook with its own handler
    # once it gets going.
    if can_touch_runtime_system("early exception handler"):
        def _earlyExceptionHandler(ty, value, traceback):
            util.ipmi_report(constants.IPMI_FAILED)
            util.vtActivate(1)
            return sys.__excepthook__(ty, value, traceback)

        sys.excepthook = _earlyExceptionHandler

    if can_touch_runtime_system("start audit daemon"):
        # auditd will turn into a daemon and exit. Ignore startup errors
        try:
            util.execWithRedirect("/sbin/auditd", [])
        except OSError:
            pass

    log.info("anaconda called with cmdline = %s", sys.argv)
    log.info("Default encoding = %s ", sys.getdefaultencoding())

    # start dbus session (if not already running) and run boss in it
    anaconda.run_boss_with_dbus()

    # Collect all addon paths
    addon_paths = collect_addon_paths(constants.ADDON_PATHS)

    # Make sure that all DBus modules are ready.
    if not startup_utils.wait_for_modules():
        stdout_log.error("Anaconda DBus modules failed to start on time.")
        util.ipmi_report(constants.IPMI_ABORTED)
        time.sleep(10)
        sys.exit(1)

    # If we were given a kickstart file on the command line, parse (but do not
    # execute) that now.  Otherwise, load in defaults from kickstart files
    # shipped with the installation media.
    ksdata = startup_utils.parse_kickstart(opts, addon_paths, pass_to_boss=True)

    # Pick up any changes from interactive-defaults.ks that would
    # otherwise be covered by the dracut KS parser.
    from pyanaconda.modules.common.constants.services import STORAGE
    from pyanaconda.modules.common.constants.objects import BOOTLOADER
    bootloader_proxy = STORAGE.get_proxy(BOOTLOADER)

    if bootloader_proxy.BootloaderType == constants.BOOTLOADER_TYPE_EXTLINUX:
        flags.extlinux = True

    if ksdata.rescue.rescue:
        flags.rescue_mode = True

    # reboot with kexec
    if ksdata.reboot.kexec:
        flags.kexec = True

    # Some kickstart commands must be executed immediately, as they affect
    # how anaconda operates.
    ksdata.logging.execute()

    anaconda.ksdata = ksdata

    # setup network module mode depending on anaconda runtime environment
    if not can_touch_runtime_system("setup network module mode"):
        from pyanaconda.modules.common.constants.services import NETWORK
        network_proxy = NETWORK.get_proxy()
        network_proxy.DontTouchRuntimeSystem()
        log.debug("Network module set up to not touch runtime system")

    # setup keyboard layout from the command line option and let
    # it override from kickstart if/when X is initialized

    from pyanaconda.modules.common.constants.services import LOCALIZATION
    localization_proxy = LOCALIZATION.get_proxy()

    configured = any((localization_proxy.Keyboard,
                      localization_proxy.VirtualConsoleKeymap,
                      localization_proxy.XLayouts))

    if opts.keymap and not configured:
        localization_proxy.SetKeyboard(opts.keymap)
        configured = True

    if configured:
        if can_touch_runtime_system("activate keyboard"):
            keyboard.activate_keyboard(localization_proxy)
        else:
            # at least make sure we have all the values
            keyboard.populate_missing_items(localization_proxy)

    # Some post-install parts of anaconda are implemented as kickstart
    # scripts.  Add those to the ksdata now.
    kickstart.appendPostScripts(ksdata)

    # cmdline flags override kickstart settings
    if anaconda.proxy:

        if hasattr(ksdata.method, "proxy"):
            ksdata.method.proxy = anaconda.proxy

        # Setup proxy environmental variables so that pre/post scripts use it
        # as well as libreport
        try:
            proxy = ProxyString(anaconda.proxy)
        except ProxyStringError as e:
            log.info("Failed to parse proxy \"%s\": %s", anaconda.proxy, e)
        else:
            # Set environmental variables to be used by pre/post scripts
            util.setenv("PROXY", proxy.noauth_url)
            util.setenv("PROXY_USER", proxy.username or "")
            util.setenv("PROXY_PASSWORD", proxy.password or "")

            # Variables used by curl, libreport, etc.
            util.setenv("http_proxy", proxy.url)
            util.setenv("ftp_proxy", proxy.url)
            util.setenv("HTTPS_PROXY", proxy.url)

    if flags.noverifyssl and hasattr(ksdata.method, "noverifyssl"):
        ksdata.method.noverifyssl = flags.noverifyssl
    if opts.multiLib:
        # sets dnf's multilib_policy to "all" (as opposed to "best")
        ksdata.packages.multiLib = opts.multiLib

    # set ksdata.method based on anaconda.method if it isn't already set
    # - anaconda.method is currently set by command line/boot options
    if anaconda.methodstr and not ksdata.method.seen:
        startup_utils.set_installation_method_from_anaconda_options(anaconda, ksdata)

    # Enable SE/HMC if it was selected as an installation source.
    if ksdata.method.method == "hmc":
        flags.hmc = True

    # Override the selinux state from kickstart if set on the command line
    from pyanaconda.modules.common.constants.services import SECURITY
    if flags.selinux != constants.SELINUX_DEFAULT:
        security_proxy = SECURITY.get_proxy()
        security_proxy.SetSELinux(flags.selinux)

    from pyanaconda import localization
    # Set the language before loading an interface, when it may be too late.

    from pyanaconda.modules.common.constants.services import LOCALIZATION
    localization_proxy = LOCALIZATION.get_proxy()

    # If the language was set on the command line, copy that to kickstart
    if opts.lang:
        localization_proxy.SetLanguage(opts.lang)
        localization_proxy.SetLanguageKickstarted(True)

    # Setup the locale environment
    if localization_proxy.LanguageKickstarted:
        locale_option = localization_proxy.Language
    else:
        locale_option = None
    localization.setup_locale_environment(locale_option, text_mode=anaconda.tui_mode)

    # Now that LANG is set, do something with it
    localization.setup_locale(os.environ["LANG"], localization_proxy, text_mode=anaconda.tui_mode)

    from pyanaconda.storage.osinstall import storage_initialize, enable_installer_mode
    enable_installer_mode()

    # Initialize the network now, in case the display needs it
    from pyanaconda.network import networkInitialize, wait_for_connecting_NM_thread, wait_for_connected_NM

    networkInitialize(ksdata)
    # If required by user, wait for connection before starting the installation.
    if opts.waitfornet:
        log.info("network: waiting for connectivity requested by inst.waitfornet=%d", opts.waitfornet)
        wait_for_connected_NM(timeout=opts.waitfornet)

    # In any case do some actions only after NM finishes its connecting.
    threadMgr.add(AnacondaThread(name=constants.THREAD_WAIT_FOR_CONNECTING_NM,
                                 target=wait_for_connecting_NM_thread))

    # initialize the screen access manager before launching the UI
    from pyanaconda import screen_access
    screen_access.initSAM()
    # try to open any existing config file
    # (might be created by pre-anaconda helper tools, injected during image
    # generation, etc.)
    screen_access.sam.open_config_file()

    # now start the interface
    display.setup_display(anaconda, opts, addon_paths=addon_paths)
    if anaconda.gui_startup_failed:
        # we need to reinitialize the locale if GUI startup failed,
        # as we might now be in text mode, which might not be able to display
        # the characters from our current locale
        log.warning("reinitializing locale due to failed attempt to start the GUI")
        localization.setup_locale(os.environ["LANG"], localization_proxy, text_mode=anaconda.tui_mode)

    # we now know in which mode we are going to run so store the information
    from pykickstart import constants as pykickstart_constants
    display_mode_coversion_table = {
        constants.DisplayModes.GUI: pykickstart_constants.DISPLAY_MODE_GRAPHICAL,
        constants.DisplayModes.TUI: pykickstart_constants.DISPLAY_MODE_TEXT
    }
    ksdata.displaymode.displayMode = display_mode_coversion_table[anaconda.display_mode]
    ksdata.displaymode.nonInteractive = not anaconda.interactive_mode

    # if we're in text mode, the resulting system should be too
    # ...unless the kickstart specified otherwise
    from pyanaconda.modules.common.constants.services import SERVICES
    from pyanaconda.core.constants import TEXT_ONLY_TARGET
    services_proxy = SERVICES.get_proxy()

    if not services_proxy.DefaultTarget and anaconda.tui_mode:
        services_proxy.SetDefaultTarget(TEXT_ONLY_TARGET)

    # Set flag to prompt for missing ks data
    if not anaconda.interactive_mode:
        flags.ksprompt = False

    # Set minimal ram size to the storage checker.
    if anaconda.display_mode == constants.DisplayModes.GUI:
        min_ram = isys.MIN_GUI_RAM
    else:
        min_ram = isys.MIN_RAM

    from pyanaconda.storage_utils import storage_checker
    storage_checker.add_constraint(constants.STORAGE_MIN_RAM, min_ram)
    anaconda.instClass.setStorageChecker(storage_checker)

    from pyanaconda.argument_parsing import name_path_pairs

    image_count = 0
    try:
        for (name, path) in name_path_pairs(opts.images):
            log.info("naming disk image '%s' '%s'", path, name)
            anaconda.storage.disk_images[name] = path
            image_count += 1
            flags.imageInstall = True
    except ValueError as e:
        stdout_log.error("error specifying image file: %s", e)
        util.ipmi_abort(scripts=ksdata.scripts)
        sys.exit(1)

    if image_count:
        anaconda.storage.setup_disk_images()

    # Ignore disks labeled OEMDRV
    from pyanaconda.modules.common.constants.services import STORAGE
    from pyanaconda.modules.common.constants.objects import DISK_SELECTION
    from pyanaconda.storage_utils import device_matches
    matched = device_matches("LABEL=OEMDRV", disks_only=True)
    for oemdrv_disk in matched:
        disk_select_proxy = STORAGE.get_proxy(DISK_SELECTION)
        ignored_disks = disk_select_proxy.IgnoredDisks

        if oemdrv_disk not in ignored_disks:
            log.info("Adding disk %s labeled OEMDRV to ignored disks", oemdrv_disk)
            ignored_disks.append(oemdrv_disk)
            disk_select_proxy.SetIgnoredDisks(ignored_disks)

    from pyanaconda.payload import payloadMgr
    from pyanaconda.timezone import time_initialize

    if not flags.dirInstall:
        threadMgr.add(AnacondaThread(name=constants.THREAD_STORAGE, target=storage_initialize,
                                     args=(anaconda.storage, ksdata, anaconda.protected)))

    from pyanaconda.modules.common.constants.services import TIMEZONE
    timezone_proxy = TIMEZONE.get_proxy()

    if can_touch_runtime_system("initialize time", touch_live=True):
        threadMgr.add(AnacondaThread(name=constants.THREAD_TIME_INIT,
                                     target=time_initialize,
                                     args=(timezone_proxy,
                                           anaconda.storage,
                                           anaconda.bootloader)))

    if flags.rescue_mode:
        rescue.start_rescue_mode_ui(anaconda)
    else:
        startup_utils.clean_pstore()

    # only install interactive exception handler in interactive modes
    if ksdata.displaymode.displayMode != pykickstart_constants.DISPLAY_MODE_CMDLINE or flags.debug:
        from pyanaconda import exception
        anaconda.mehConfig = exception.initExceptionHandling(anaconda)

    # add our own additional signal handlers
    signal.signal(signal.SIGUSR1, lambda signum, frame:
                  exception.test_exception_handling())
    signal.signal(signal.SIGUSR2, lambda signum, frame: anaconda.dumpState())
    atexit.register(exitHandler, ksdata.reboot, anaconda.storage)

    from pyanaconda import exception
    anaconda.mehConfig = exception.initExceptionHandling(anaconda)

    anaconda.postConfigureInstallClass()

    # add additional repositories from the cmdline to kickstart data
    anaconda.add_additional_repositories_to_ksdata()

    # Fallback to default for interactive or for a kickstart with no installation method.
    fallback = not (flags.automatedInstall and ksdata.method.method)
    payloadMgr.restartThread(anaconda.storage, ksdata, anaconda.payload, anaconda.instClass, fallback=fallback)

    # initialize the geolocation singleton
    geoloc.init_geolocation(geoloc_option=opts.geoloc,
                            options_override=opts.geoloc_use_with_ks,
                            install_class_override=anaconda.instClass.use_geolocation_with_kickstart)

    # start geolocation lookup if enabled
    if geoloc.geoloc.enabled:
        geoloc.geoloc.refresh()

    # setup ntp servers and start NTP daemon if not requested otherwise
    if can_touch_runtime_system("start chronyd"):
        kickstart_ntpservers = timezone_proxy.NTPServers

        if kickstart_ntpservers:
            pools, servers = ntp.internal_to_pools_and_servers(kickstart_ntpservers)
            ntp.save_servers_to_config(pools, servers)

        if timezone_proxy.NTPEnabled:
            util.start_service("chronyd")

    # Finish the initialization of the setup on boot action.
    # This should be done sooner and somewhere else once it is possible.
    from pyanaconda.core.constants import SETUP_ON_BOOT_DEFAULT, SETUP_ON_BOOT_DISABLED
    from pyanaconda.modules.common.constants.services import SERVICES
    services_proxy = SERVICES.get_proxy()

    if services_proxy.SetupOnBoot == SETUP_ON_BOOT_DEFAULT:
        if flags.automatedInstall:
            # Disable by default after kickstart installations.
            services_proxy.SetSetupOnBoot(SETUP_ON_BOOT_DISABLED)
        else:
            # Otherwise use the install class's default value.
            services_proxy.SetSetupOnBoot(anaconda.instClass.setup_on_boot)

    # Create pre-install snapshots
    from pykickstart.constants import SNAPSHOT_WHEN_PRE_INSTALL
    from pyanaconda.kickstart import check_kickstart_error
    if ksdata.snapshot.has_snapshot(SNAPSHOT_WHEN_PRE_INSTALL):
        with check_kickstart_error():
            ksdata.snapshot.pre_setup(anaconda.storage, ksdata, anaconda.instClass)
            ksdata.snapshot.pre_execute(anaconda.storage, ksdata, anaconda.instClass)

    anaconda._intf.setup(ksdata)
    anaconda._intf.run()

# vim:tw=78:ts=4:et:sw=4
