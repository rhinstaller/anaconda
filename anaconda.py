#!/usr/libexec/system-python
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
    iutil.unwatchAllProcesses()

    # stop and save coverage here b/c later the file system may be unavailable
    if coverage is not None:
        cov.stop()
        if os.path.isdir('/mnt/sysimage/root'):
            cov.save()

    if flags.usevnc:
        vnc.shutdownServer()

    if "nokill" in flags.cmdline:
        iutil.vtActivate(1)
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

    if not flags.imageInstall and not flags.livecdInstall \
       and not flags.dirInstall:
        from pykickstart.constants import KS_SHUTDOWN, KS_WAIT

        if flags.eject or rebootData.eject:
            for cdrom in (d for d in storage.devices if d.type == "cdrom"):
                if iutil.get_mount_paths(cdrom.path):
                    iutil.dracut_eject(cdrom.path)

        if flags.kexec:
            iutil.execWithRedirect("systemctl", ["--no-wall", "kexec"])
            while True:
                time.sleep(10000)
        elif rebootData.action == KS_SHUTDOWN:
            iutil.execWithRedirect("systemctl", ["--no-wall", "poweroff"])
        elif rebootData.action == KS_WAIT:
            iutil.execWithRedirect("systemctl", ["--no-wall", "halt"])
        else:  # reboot action is KS_REBOOT or None
            iutil.execWithRedirect("systemctl", ["--no-wall", "reboot"])

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
    from pyanaconda.anaconda_argparse import getArgumentParser
    ap = getArgumentParser(startup_utils.get_anaconda_version_string(),
                           boot_cmdline)

    namespace = ap.parse_args(argv, boot_cmdline=boot_cmdline)
    return (namespace, ap.deprecated_bootargs)

def setup_python_path():
    """Add items Anaconda needs to sys.path."""
    # First add our updates path
    sys.path.insert(0, '/tmp/updates/')

    from pyanaconda.constants import ADDON_PATHS
    # append ADDON_PATHS dirs at the end
    sys.path.extend(ADDON_PATHS)

def setup_environment():
    """Setup contents of os.environ according to Anaconda needs.

    This method is run before any threads are started, so this is the one
    point where it's ok to modify the environment.
    """
    # pylint: disable=environment-modify

    # Silly GNOME stuff
    if 'HOME' in os.environ and not "XAUTHORITY" in os.environ:
        os.environ['XAUTHORITY'] = os.environ['HOME'] + '/.Xauthority'
    os.environ['HOME'] = '/tmp'
    os.environ['LC_NUMERIC'] = 'C'
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
    if 'DISPLAY' in os.environ:
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
        log = logging.getLogger("anaconda")
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
    from pyanaconda.threads import initThreading, AnacondaThread
    initThreading()
    from pyanaconda.threads import threadMgr

    from pyanaconda.i18n import _

    from pyanaconda import constants
    from pyanaconda.addons import collect_addon_paths
    from pyanaconda import iutil
    from pyanaconda import startup_utils

    # do this early so we can set flags before initializing logging
    from pyanaconda.flags import flags, can_touch_runtime_system
    (opts, depr) = parse_arguments(boot_cmdline=flags.cmdline)

    if opts.images:
        flags.imageInstall = True
    elif opts.dirinstall:
        flags.dirInstall = True

    # Set up logging as early as possible.
    import logging
    from pyanaconda import anaconda_log
    anaconda_log.init()
    anaconda_log.logger.setupVirtio()

    from pyanaconda import network
    network.setup_ifcfg_log()

    log = logging.getLogger("anaconda")
    stdout_log = logging.getLogger("anaconda.stdout")

    if os.geteuid() != 0:
        stdout_log.error("anaconda must be run as root.")
        sys.exit(1)

    # check if input kickstart should be saved
    if flags.nosave_input_ks:
        log.warning("Input kickstart will not be saved to the installed system due to the nosave option.")
        iutil.touch('/tmp/NOSAVE_INPUT_KS')

    # check if logs should be saved
    if flags.nosave_logs:
        log.warning("Installation logs will not be saved to the installed system due to the nosave option.")
        iutil.touch('/tmp/NOSAVE_LOGS')

    # see if we're on s390x and if we've got an ssh connection
    uname = os.uname()
    if uname[4] == 's390x':
        if 'TMUX' not in os.environ and 'ks' not in flags.cmdline and not flags.imageInstall:
            startup_utils.prompt_for_ssh()
            sys.exit(0)

    log.info("%s %s", sys.argv[0], startup_utils.get_anaconda_version_string())
    if os.path.exists("/tmp/updates"):
        log.info("Using updates in /tmp/updates/ from %s", opts.updateSrc)

    # TODO: uncomment this when we're sure that we're doing the right thing
    # with flags.cmdline *everywhere* it appears...
    #for arg in depr:
    #    stdout_log.warn("Boot argument '%s' is deprecated. "
    #                   "In the future, use 'inst.%s'.", arg, arg)

    from pyanaconda import isys

    iutil.ipmi_report(constants.IPMI_STARTED)

    if (opts.images or opts.dirinstall) and opts.liveinst:
        stdout_log.error("--liveinst cannot be used with --images or --dirinstall")
        iutil.ipmi_report(constants.IPMI_ABORTED)
        sys.exit(1)

    if opts.images and opts.dirinstall:
        stdout_log.error("--images and --dirinstall cannot be used at the same time")
        iutil.ipmi_report(constants.IPMI_ABORTED)
        sys.exit(1)
    elif opts.dirinstall:
        root_path = opts.dirinstall
        iutil.setTargetPhysicalRoot(root_path)
        iutil.setSysroot(root_path)

    from pyanaconda import vnc
    from pyanaconda import kickstart
    from pyanaconda import ntp
    from pyanaconda import keyboard
    # we are past the --version and --help shortcut so we can import display &
    # startup_utils, which import Blivet, without slowing down anything critical
    from pyanaconda import display
    from pyanaconda import startup_utils
    from pyanaconda import rescue
    from pyanaconda.iutil import ProxyString, ProxyStringError

    # Print the usual "startup note" that contains Anaconda version
    # and short usage & bug reporting instructions.
    # The note should in most cases end on TTY1.
    startup_utils.print_startup_note(options=opts)

    from pyanaconda.anaconda import Anaconda
    anaconda = Anaconda()
    iutil.setup_translations()

    # reset python's default SIGINT handler
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, lambda num, frame: sys.exit(1))

    # synchronously-delivered signals such as SIGSEGV and SIGILL cannot be
    # handled properly from python, so install signal handlers from the C
    # function in isys.
    isys.installSyncSignalHandlers()

    setup_environment()

    # make sure we have /var/log soon, some programs fail to start without it
    iutil.mkdirChain("/var/log")

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
            iutil.execWithRedirect("zenity",
                                   ["--error", "--title", _("Unable to create PID file"), "--text",
                                   _("Anaconda is unable to create %s because the file" +
                                   " already exists. Anaconda is already running, or a previous instance" +
                                   " of anaconda has crashed.") % pidfile.filename])
        else:
            print("%s already exists, exiting" % pidfile.filename)

        iutil.ipmi_report(constants.IPMI_FAILED)
        sys.exit(1)

    # add our own additional signal handlers
    signal.signal(signal.SIGHUP, start_debugger)

    anaconda.opts = opts

    # check memory, just the text mode for now:
    startup_utils.check_memory(anaconda, opts, display_mode=constants.DisplayModes.TUI)

    # Now that we've got command line/boot options, do some extra processing.
    startup_utils.setup_logging_from_options(opts)

    # Default is to prompt to mount the installed system.
    anaconda.rescue_mount = not opts.rescue_nomount

    # assign the other anaconda variables from options
    anaconda.proxy = opts.proxy
    anaconda.updateSrc = opts.updateSrc
    anaconda.methodstr = opts.method
    anaconda.stage2 = opts.stage2
    flags.rescue_mode = opts.rescue

    if opts.liveinst:
        startup_utils.live_startup(anaconda, opts)
    elif "LIVECMD" in os.environ:
        log.warning("Running via liveinst, but not setting flags.livecdInstall - this is for testing only")

    # set flags
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
    flags.selinux = opts.selinux
    flags.eject = opts.eject
    flags.kexec = opts.kexec
    flags.singlelang = opts.singlelang

    # Switch to tty1 on exception in case something goes wrong during X start.
    # This way if, for example, metacity doesn't start, we switch back to a
    # text console with a traceback instead of being left looking at a blank
    # screen. python-meh will replace this excepthook with its own handler
    # once it gets going.
    if can_touch_runtime_system("early exception handler"):
        def _earlyExceptionHandler(ty, value, traceback):
            iutil.ipmi_report(constants.IPMI_FAILED)
            iutil.vtActivate(1)
            return sys.__excepthook__(ty, value, traceback)

        sys.excepthook = _earlyExceptionHandler

    if can_touch_runtime_system("start audit daemon"):
        # auditd will turn into a daemon and exit. Ignore startup errors
        try:
            iutil.execWithRedirect("/sbin/auditd", [])
        except OSError:
            pass

    log.info("anaconda called with cmdline = %s", sys.argv)
    log.info("Default encoding = %s ", sys.getdefaultencoding())

    # Collect all addon paths
    addon_paths = collect_addon_paths(constants.ADDON_PATHS)

    # If we were given a kickstart file on the command line, parse (but do not
    # execute) that now.  Otherwise, load in defaults from kickstart files
    # shipped with the installation media.
    ksdata = startup_utils.parse_kickstart(opts, addon_paths)

    # Pick up any changes from interactive-defaults.ks that would
    # otherwise be covered by the dracut KS parser.
    if ksdata.bootloader.extlinux:
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

    # setup keyboard layout from the command line option and let
    # it override from kickstart if/when X is initialized
    if opts.keymap:
        if not ksdata.keyboard.keyboard:
            ksdata.keyboard.keyboard = opts.keymap

    if ksdata.keyboard.keyboard:
        if can_touch_runtime_system("activate keyboard"):
            keyboard.activate_keyboard(ksdata.keyboard)
        else:
            # at least make sure we have all the values
            keyboard.populate_missing_items(ksdata.keyboard)

    # Some post-install parts of anaconda are implemented as kickstart
    # scripts.  Add those to the ksdata now.
    kickstart.appendPostScripts(ksdata)

    # cmdline flags override kickstart settings
    if anaconda.proxy:
        ksdata.method.proxy = anaconda.proxy

        # Setup proxy environmental variables so that pre/post scripts use it
        # as well as libreport
        try:
            proxy = ProxyString(anaconda.proxy)
        except ProxyStringError as e:
            log.info("Failed to parse proxy \"%s\": %s", anaconda.proxy, e)
        else:
            # Set environmental variables to be used by pre/post scripts
            iutil.setenv("PROXY", proxy.noauth_url)
            iutil.setenv("PROXY_USER", proxy.username or "")
            iutil.setenv("PROXY_PASSWORD", proxy.password or "")

            # Variables used by curl, libreport, etc.
            iutil.setenv("http_proxy", proxy.url)
            iutil.setenv("ftp_proxy", proxy.url)
            iutil.setenv("HTTPS_PROXY", proxy.url)

    if flags.noverifyssl:
        ksdata.method.noverifyssl = flags.noverifyssl
    if opts.multiLib:
        # sets dnf's multilib_policy to "all" (as opposed to "best")
        ksdata.packages.multiLib = opts.multiLib

    # set ksdata.method based on anaconda.method if it isn't already set
    # - anaconda.method is currently set by command line/boot options
    if anaconda.methodstr and not ksdata.method.seen:
        startup_utils.set_installation_method_from_anaconda_options(anaconda, ksdata)

    # Override the selinux state from kickstart if set on the command line
    if flags.selinux != constants.SELINUX_DEFAULT:
        ksdata.selinux.selinux = flags.selinux

    from pyanaconda import localization
    # Set the language before loading an interface, when it may be too late.

    # If the language was set on the command line, copy that to kickstart
    if opts.lang:
        ksdata.lang.lang = opts.lang
        ksdata.lang.seen = True

    # Setup the locale environment
    if ksdata.lang.seen:
        locale_option = ksdata.lang.lang
    else:
        locale_option = None
    localization.setup_locale_environment(locale_option, text_mode=anaconda.tui_mode)

    # Now that LANG is set, do something with it
    localization.setup_locale(os.environ["LANG"], ksdata.lang, text_mode=anaconda.tui_mode)

    import blivet
    blivet.enable_installer_mode()

    # Initialize the network now, in case the display needs it
    from pyanaconda.network import networkInitialize, wait_for_connecting_NM_thread

    networkInitialize(ksdata)
    threadMgr.add(AnacondaThread(name=constants.THREAD_WAIT_FOR_CONNECTING_NM, target=wait_for_connecting_NM_thread, args=(ksdata,)))

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
        localization.setup_locale(os.environ["LANG"], ksdata.lang, text_mode=anaconda.tui_mode)

    # we now know in which mode we are going to run so store the information
    from pykickstart import constants as pykickstart_constants
    display_mode_coversion_table = {
        constants.DisplayModes.GUI: pykickstart_constants.DISPLAY_MODE_GRAPHICAL,
        constants.DisplayModes.TUI: pykickstart_constants.DISPLAY_MODE_TEXT,
        constants.DisplayModes.NUI: pykickstart_constants.DISPLAY_MODE_TEXT
    }
    ksdata.displaymode.displayMode = display_mode_coversion_table[anaconda.display_mode]
    ksdata.displaymode.nonInteractive = not anaconda.interactive_mode

    # if we're in text mode, the resulting system should be too
    # ...unless the kickstart specified otherwise
    if anaconda.tui_mode and not anaconda.ksdata.xconfig.startX:
        anaconda.ksdata.skipx.skipx = True

    # Set flag to prompt for missing ks data
    if not anaconda.interactive_mode:
        flags.ksprompt = False

    # Set minimal ram size to the storage checker.
    if anaconda.display_mode == constants.DisplayModes.GUI:
        min_ram = isys.MIN_GUI_RAM
    else:
        min_ram = isys.MIN_RAM

    from pyanaconda.storage_utils import storage_checker
    storage_checker.add_constraint("min_ram", min_ram)
    anaconda.instClass.setStorageChecker(storage_checker)

    from pyanaconda.anaconda_argparse import name_path_pairs

    image_count = 0
    try:
        for (name, path) in name_path_pairs(opts.images):
            log.info("naming disk image '%s' '%s'", path, name)
            anaconda.storage.config.disk_images[name] = path
            image_count += 1
            flags.imageInstall = True
    except ValueError as e:
        stdout_log.error("error specifying image file: %s", e)
        iutil.ipmi_abort(scripts=ksdata.scripts)
        sys.exit(1)

    if image_count:
        anaconda.storage.setup_disk_images()

    from blivet.osinstall import storage_initialize
    from pyanaconda.payload import payloadMgr
    from pyanaconda.timezone import time_initialize

    if not flags.dirInstall:
        threadMgr.add(AnacondaThread(name=constants.THREAD_STORAGE, target=storage_initialize,
                                     args=(anaconda.storage, ksdata, anaconda.protected)))

    if can_touch_runtime_system("initialize time", touch_live=True):
        threadMgr.add(AnacondaThread(name=constants.THREAD_TIME_INIT, target=time_initialize,
                                     args=(ksdata.timezone, anaconda.storage, anaconda.bootloader)))

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

    # Fallback to default for interactive or for a kickstart with no installation method.
    fallback = not (flags.automatedInstall and ksdata.method.method)
    payloadMgr.restartThread(anaconda.storage, ksdata, anaconda.payload, anaconda.instClass, fallback=fallback)

    # check if geolocation should be enabled for this type of installation
    use_geolocation = True
    if flags.imageInstall or flags.dirInstall or flags.automatedInstall:
        use_geolocation = False
    # and also check if it was not disabled by boot option
    else:
        # flags.cmdline.getbool is used as it handles values such as
        # 0, no, off and also nogeoloc as False
        # and other values or geoloc not being present as True
        use_geolocation = flags.cmdline.getbool('geoloc', True)

    if use_geolocation:
        startup_utils.start_geolocation(provider_id=opts.geoloc)

    # setup ntp servers and start NTP daemon if not requested otherwise
    if can_touch_runtime_system("start chronyd"):
        if anaconda.ksdata.timezone.ntpservers:
            pools, servers = ntp.internal_to_pools_and_servers(anaconda.ksdata.timezone.ntpservers)
            ntp.save_servers_to_config(pools, servers)

        if not anaconda.ksdata.timezone.nontp:
            iutil.start_service("chronyd")

    anaconda._intf.setup(ksdata)
    anaconda._intf.run()

# vim:tw=78:ts=4:et:sw=4
