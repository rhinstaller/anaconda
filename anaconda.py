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
# Author(s): Brent Fox <bfox@redhat.com>
#            Mike Fulbright <msf@redhat.com>
#            Jakub Jelinek <jakub@redhat.com>
#            Jeremy Katz <katzj@redhat.com>
#            Chris Lumens <clumens@redhat.com>
#            Paul Nasrat <pnasrat@redhat.com>
#            Erik Troan <ewt@rpath.com>
#            Matt Wilson <msw@rpath.com>
#

# This toplevel file is a little messy at the moment... (2001-06-22)
# ...still messy (2013-07-12)

import os
import site

coverage = None

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
        anaconda.storage.umountFilesystems(swapoff=False)
        devicetree = anaconda.storage.devicetree
        devicetree.teardownAll()
        for imageName in devicetree.diskImages:
            dev = devicetree.getDeviceByName(imageName)
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
            for cdrom in storage.devicetree.getDevicesByType("cdrom"):
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

def startSpiceVDAgent():
    status = iutil.execWithRedirect("spice-vdagent", [])

    if status:
        log.info("spice-vdagent exited with status %d", status)
    else:
        log.info("Started spice-vdagent.")

def startX11():
    import subprocess

    # Start Xorg and wait for it become ready
    iutil.startX(["Xorg", "-br", "-logfile", "/tmp/X.log",
                  ":%s" % constants.X_DISPLAY_NUMBER, "vt6", "-s", "1440", "-ac",
                  "-nolisten", "tcp", "-dpi", "96",
                  "-noreset"], output_redirect=subprocess.DEVNULL)

# function to handle X startup special issues for anaconda
def doStartupX11Actions():
    """Start window manager"""
    # When metacity actually connects to the X server is unknowable, but
    # fortunately it doesn't matter. metacity does not need to be the first
    # connection to Xorg, and if anaconda starts up before metacity, metacity
    # will just take over and maximize the window and make everything right,
    # fingers crossed.
    # Add XDG_DATA_DIRS to the environment to pull in our overridden schema
    # files.
    if 'XDG_DATA_DIRS' in os.environ:
        xdg_data_dirs = '/usr/share/anaconda/window-manager:' + os.environ['XDG_DATA_DIRS']
    else:
        xdg_data_dirs = '/usr/share/anaconda/window-manager:/usr/share'

    childproc = iutil.startProgram(["metacity", "--display", ":1", "--sm-disable"],
            env_add={'XDG_DATA_DIRS': xdg_data_dirs})
    iutil.watchProcess(childproc, "metacity")

def set_x_resolution(runres):
    if runres and opts.display_mode == 'g' and not flags.usevnc:
        try:
            log.info("Setting the screen resolution to: %s.", runres)
            iutil.execWithRedirect("xrandr",
                                   ["-d", ":1", "-s", runres])
        except RuntimeError:
            log.error("The X resolution not set")
            iutil.execWithRedirect("xrandr",
                                   ["-d", ":1", "-q"])

def doExtraX11Actions(runres):
    """Perform X11 actions not related to startup"""

    set_x_resolution(runres)

    startSpiceVDAgent()

def setupPythonUpdates():
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

def getAnacondaVersionString():
    # we are importing the startup module directly so that it can be replaced
    # by updates image, if it was replaced before the updates image can be
    # loaded, it could not be easily replaced
    from pyanaconda import startup_utils
    return startup_utils.get_anaconda_version_string()


def parseArguments(argv=None, boot_cmdline=None):
    from pyanaconda.anaconda_argparse import getArgumentParser
    ap = getArgumentParser(getAnacondaVersionString(), boot_cmdline)

    namespace = ap.parse_args(argv, boot_cmdline=boot_cmdline)
    return (namespace, ap.deprecated_bootargs)

def setupPythonPath():
    # First add our updates path
    sys.path.insert(0, '/tmp/updates/')

    from pyanaconda.constants import ADDON_PATHS
    # append ADDON_PATHS dirs at the end
    sys.path.extend(ADDON_PATHS)

def setupEnvironment():
    # This method is run before any threads are started, so this is the one
    # point where it's ok to modify the environment.
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

def setupLoggingFromOpts(options):
    if (options.debug or options.updateSrc) and not options.loglevel:
        # debugging means debug logging if an explicit level hasn't been st
        options.loglevel = "debug"

    if options.loglevel and options.loglevel in anaconda_log.logLevelMap:
        log.info("Switching logging level to %s", options.loglevel)
        level = anaconda_log.logLevelMap[options.loglevel]
        anaconda_log.logger.loglevel = level
        anaconda_log.setHandlersLevel(log, level)
        storage_log = logging.getLogger("storage")
        anaconda_log.setHandlersLevel(storage_log, level)
        packaging_log = logging.getLogger("packaging")
        anaconda_log.setHandlersLevel(packaging_log, level)

    if can_touch_runtime_system("syslog setup"):
        if options.syslog:
            anaconda_log.logger.updateRemote(options.syslog)

    if options.remotelog:
        try:
            host, port = options.remotelog.split(":", 1)
            port = int(port)
            anaconda_log.logger.setup_remotelog(host, port)
        except ValueError:
            log.error("Could not setup remotelog with %s", options.remotelog)

def gtk_warning(title, reason):
    import gi
    gi.require_version("Gtk", "3.0")

    from gi.repository import Gtk
    dialog = Gtk.MessageDialog(type=Gtk.MessageType.ERROR,
                               buttons=Gtk.ButtonsType.CLOSE,
                               message_format=reason)
    dialog.set_title(title)
    dialog.run()
    dialog.destroy()

# pylint: disable=redefined-outer-name
def check_memory(anaconda, options, display_mode=None):
    from pyanaconda import isys

    reason_strict = _("%(product_name)s requires %(needed_ram)s MB of memory to "
                      "install, but you only have %(total_ram)s MB on this machine.\n")
    reason_graphical = _("The %(product_name)s graphical installer requires %(needed_ram)s "
                         "MB of memory, but you only have %(total_ram)s MB\n.")

    reboot_extra = _('\n'
                     'Press <Enter> to reboot your system.\n')
    livecd_title = _("Not enough RAM")
    livecd_extra = _(" Try the text mode installer by running:\n\n"
                     "'/usr/bin/liveinst -T'\n\n from a root "
                     "terminal.")
    nolivecd_extra = _(" Starting text mode.")

    if options.rescue:
        return

    if not display_mode:
        display_mode = anaconda.displayMode

    reason = reason_strict
    total_ram = int(isys.total_memory() / 1024)
    needed_ram = int(isys.MIN_RAM)
    graphical_ram = int(isys.MIN_GUI_RAM)

    # count the squashfs.img in if it is kept in RAM
    if not iutil.persistent_root_image():
        needed_ram += isys.SQUASHFS_EXTRA_RAM
        graphical_ram += isys.SQUASHFS_EXTRA_RAM

    log.info("check_memory(): total:%s, needed:%s, graphical:%s",
             total_ram, needed_ram, graphical_ram)

    if not options.memcheck:
        log.warning("CHECK_MEMORY DISABLED")
        return

    reason_args = {"product_name": product.productName,
                   "needed_ram": needed_ram,
                   "total_ram": total_ram}
    if needed_ram > total_ram:
        if options.liveinst:
            # pylint: disable=logging-not-lazy
            stdoutLog.warning(reason % reason_args)
            gtk_warning(livecd_title, reason % reason_args)
        else:
            reason += reboot_extra
            print(reason % reason_args)
            print(_("The installation cannot continue and the system will be rebooted"))
            print(_("Press ENTER to continue"))
            input()

        iutil.ipmi_report(constants.IPMI_ABORTED)
        sys.exit(1)

    # override display mode if machine cannot nicely run X
    if display_mode not in ('t', 'c', 's') and not flags.usevnc:
        needed_ram = graphical_ram
        reason_args["needed_ram"] = graphical_ram
        reason = reason_graphical

        if needed_ram > total_ram:
            if options.liveinst:
                reason += livecd_extra
                # pylint: disable=logging-not-lazy
                stdoutLog.warning(reason % reason_args)
                title = livecd_title
                gtk_warning(title, reason % reason_args)
                iutil.ipmi_report(constants.IPMI_ABORTED)
                sys.exit(1)
            else:
                reason += nolivecd_extra
                # pylint: disable=logging-not-lazy
                stdoutLog.warning(reason % reason_args)
                anaconda.displayMode = 't'
                time.sleep(2)

def startDebugger(signum, frame):
    # pylint: disable=import-error
    import epdb
    epdb.serve(skip=1)

# pylint: disable=redefined-outer-name
def setupDisplay(anaconda, options, addons=None):
    from pyanaconda.ui.tui.simpleline import App
    from pyanaconda.ui.tui.spokes.askvnc import AskVNCSpoke
    from pykickstart.constants import DISPLAY_MODE_TEXT
    from pyanaconda.nm import nm_is_connected, nm_is_connecting
    from blivet import arch

    graphical_failed = 0
    vncS = vnc.VncServer()          # The vnc Server object.
    vncS.anaconda = anaconda

    anaconda.displayMode = options.display_mode
    anaconda.isHeadless = arch.isS390()

    if options.vnc:
        flags.usevnc = True
        anaconda.displayMode = 'g'
        vncS.password = options.vncpassword

        # Only consider vncconnect when vnc is a param
        if options.vncconnect:
            cargs = options.vncconnect.split(":")
            vncS.vncconnecthost = cargs[0]
            if len(cargs) > 1 and len(cargs[1]) > 0:
                if len(cargs[1]) > 0:
                    vncS.vncconnectport = cargs[1]

    if options.xdriver:
        anaconda.xdriver = options.xdriver
        anaconda.writeXdriver(root="/")

    if flags.rescue_mode:
        return

    if anaconda.ksdata.vnc.enabled:
        flags.usevnc = True
        anaconda.displayMode = 'g'

        if vncS.password == "":
            vncS.password = anaconda.ksdata.vnc.password

        if vncS.vncconnecthost == "":
            vncS.vncconnecthost = anaconda.ksdata.vnc.host

        if vncS.vncconnectport == "":
            vncS.vncconnectport = anaconda.ksdata.vnc.port

    if anaconda.displayMode == "g":
        import pkgutil
        import pyanaconda.ui

        mods = (tup[1] for tup in pkgutil.iter_modules(pyanaconda.ui.__path__, "pyanaconda.ui."))
        if "pyanaconda.ui.gui" not in mods:
            stdoutLog.warning("Graphical user interface not available, falling back to text mode")
            anaconda.displayMode = "t"
            flags.usevnc = False
            flags.vncquestion = False

    # disable VNC over text question when not enough memory is available
    if blivet.util.total_memory() < isys.MIN_GUI_RAM:
        stdoutLog.warning("Not asking for VNC because current memory (%d) < MIN_GUI_RAM (%d)", blivet.util.total_memory(), isys.MIN_GUI_RAM)
        flags.vncquestion = False

    # disable VNC question if text mode is requested and this is a ks install
    if anaconda.displayMode == 't' and flags.automatedInstall:
        stdoutLog.warning("Not asking for VNC because of an automated install")
        flags.vncquestion = False

    # disable VNC question if we were explicitly asked for text in kickstart
    if anaconda.ksdata.displaymode.displayMode == DISPLAY_MODE_TEXT:
        stdoutLog.warning("Not asking for VNC because text mode was explicitly asked for in kickstart")
        flags.vncquestion = False

    # disable VNC question if we don't have network
    if not nm_is_connecting() and not nm_is_connected():
        stdoutLog.warning("Not asking for VNC because we don't have a network")
        flags.vncquestion = False

    # disable VNC question if we don't have Xvnc
    if not os.access('/usr/bin/Xvnc', os.X_OK):
        stdoutLog.warning("Not asking for VNC because we don't have Xvnc")
        flags.vncquestion = False

    # Should we try to start Xorg?
    want_x = anaconda.displayMode == 'g' and \
             not (flags.preexisting_x11 or flags.usevnc)

    # X on a headless (e.g. s390) system? Nonsense!
    if want_x and anaconda.isHeadless:
        stdoutLog.warning(_("DISPLAY variable not set. Starting text mode."))
        anaconda.displayMode = 't'
        graphical_failed = 1
        time.sleep(2)
        want_x = False

    # Is Xorg is actually available?
    if want_x and not os.access("/usr/bin/Xorg", os.X_OK):
        stdoutLog.warning(_("Graphical installation is not available. "
                            "Starting text mode."))
        time.sleep(2)
        anaconda.displayMode = 't'
        want_x = False

    if anaconda.displayMode == 't' and flags.vncquestion:
        #we prefer vnc over text mode, so ask about that
        message = _("Text mode provides a limited set of installation "
                    "options. It does not offer custom partitioning for "
                    "full control over the disk layout. Would you like "
                    "to use VNC mode instead?")

        app = App("VNC Question")
        spoke = AskVNCSpoke(app, anaconda.ksdata, message=message)
        app.schedule_screen(spoke)
        app.run()

        if anaconda.ksdata.vnc.enabled:
            anaconda.displayMode = 'g'
            flags.usevnc = True
            vncS.password = anaconda.ksdata.vnc.password
        else:
            # user has explicitly specified text mode
            flags.vncquestion = False

    log.info("Display mode = %s", anaconda.displayMode)
    check_memory(anaconda, options)

    # check_memory may have changed the display mode
    want_x = want_x and (anaconda.displayMode == "g")
    if want_x:
        try:
            startX11()
            doStartupX11Actions()
        except (OSError, RuntimeError) as e:
            log.warning("X startup failed: %s", e)
            stdoutLog.warning("X startup failed, falling back to text mode")
            anaconda.displayMode = 't'
            graphical_failed = 1
            time.sleep(2)

        if not graphical_failed:
            doExtraX11Actions(options.runres)

    if anaconda.displayMode == 't' and graphical_failed and \
         flags.vncquestion and not anaconda.ksdata.vnc.enabled:
        app = App("VNC Question")
        spoke = AskVNCSpoke(app, anaconda.ksdata)
        app.schedule_screen(spoke)
        app.run()

        if anaconda.ksdata.vnc.enabled:
            anaconda.displayMode = 'g'
            flags.usevnc = True
            vncS.password = anaconda.ksdata.vnc.password

    # if they want us to use VNC do that now
    if anaconda.displayMode == 'g' and flags.usevnc:
        vncS.startServer()
        doStartupX11Actions()

    # with X running we can initialize the UI interface
    anaconda.initInterface(addons)

    anaconda.instClass.configure(anaconda)

    # report if starting the GUI failed
    anaconda.gui_startup_failed = bool(graphical_failed)

def prompt_for_ssh():
    # Do some work here to get the ip addr / hostname to pass
    # to the user.
    import socket

    ip = network.getFirstRealIP()

    if not ip:
        stdoutLog.error("No IP addresses found, cannot continue installation.")
        iutil.ipmi_report(constants.IPMI_ABORTED)
        sys.exit(1)

    ipstr = ip

    try:
        hinfo = socket.gethostbyaddr(ipstr)
    except socket.herror as e:
        stdoutLog.debug("Exception caught trying to get host name of %s: %s", ipstr, e)
        name = network.getHostname()
    else:
        if len(hinfo) == 3:
            name = hinfo[0]

    if ip.find(':') != -1:
        ipstr = "[%s]" % (ip,)

    if (name is not None) and (not name.startswith('localhost')) and (ipstr is not None):
        connxinfo = "%s (%s)" % (socket.getfqdn(name=name), ipstr,)
    elif ipstr is not None:
        connxinfo = "%s" % (ipstr,)
    else:
        connxinfo = None

    if connxinfo:
        stdoutLog.info(_("Please ssh install@%s to begin the install."), connxinfo)
    else:
        stdoutLog.info(_("Please ssh install@<host> to continue installation."))

def cleanPStore():
    """remove files stored in nonvolatile ram created by the pstore subsystem"""

    # files in pstore are linux (not distribution) specific, but we want to
    # make sure the entirity of them are removed so as to ensure that there
    # is sufficient free space on the flash part.  On some machines this will
    # take effect immediately, which is the best case.  Unfortunately on some,
    # an intervening reboot is needed."""
    iutil.dir_tree_map("/sys/fs/pstore", os.unlink, files=True, dirs=False)

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
        parseArguments()

    print("Starting installer, one moment...")

    # Allow a file to be loaded as early as possible
    try:
        # pylint: disable=import-error,unused-import
        import updates_disk_hook
    except ImportError:
        pass

    # this handles setting up updates for pypackages to minimize the set needed
    setupPythonUpdates()
    setupPythonPath()

    # init threading before Gtk can do anything and before we start using threads
    # initThreading initializes the threadMgr instance, import it afterwards
    from pyanaconda.threads import initThreading, AnacondaThread
    initThreading()
    from pyanaconda.threads import threadMgr

    from pyanaconda.i18n import _

    from pyanaconda import constants
    from pyanaconda.addons import collect_addon_paths
    from pyanaconda import geoloc
    from pyanaconda import iutil

    # do this early so we can set flags before initializing logging
    from pyanaconda.flags import flags, can_touch_runtime_system
    (opts, depr) = parseArguments(boot_cmdline=flags.cmdline)

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
    stdoutLog = logging.getLogger("anaconda.stdout")

    if os.geteuid() != 0:
        stdoutLog.error("anaconda must be run as root.")
        sys.exit(1)

    # see if we're on s390x and if we've got an ssh connection
    uname = os.uname()
    if uname[4] == 's390x':
        if 'TMUX' not in os.environ and 'ks' not in flags.cmdline and not flags.imageInstall:
            prompt_for_ssh()
            sys.exit(0)

    log.info("%s %s", sys.argv[0], getAnacondaVersionString())
    if os.path.exists("/tmp/updates"):
        log.info("Using updates in /tmp/updates/ from %s", opts.updateSrc)

    # TODO: uncomment this when we're sure that we're doing the right thing
    # with flags.cmdline *everywhere* it appears...
    #for arg in depr:
    #    stdoutLog.warn("Boot argument '%s' is deprecated. "
    #                   "In the future, use 'inst.%s'.", arg, arg)

    # pull this in to get product name and versioning
    from pyanaconda import product

    from pyanaconda import isys

    iutil.ipmi_report(constants.IPMI_STARTED)

    if opts.images and opts.dirinstall:
        stdoutLog.error("--images and --dirinstall cannot be used at the same time")
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
    from pyanaconda.iutil import ProxyString, ProxyStringError

    verdesc = "%s for %s %s" % (getAnacondaVersionString(),
                                product.productName, product.productVersion)

    logs_note = " * installation log files are stored in /tmp during the installation"
    shell_and_tmux_note = " * shell is available on TTY2"
    shell_only_note = " * shell is available on TTY2 and in second TMUX pane (ctrl+b, then press 2)"
    tmux_only_note = " * shell is available in second TMUX pane (ctrl+b, then press 2)"
    text_mode_note = " * if the graphical installation interface fails to start, try again with the\n"\
                     "   inst.text bootoption to start text installation"
    separate_attachements_note = " * when reporting a bug add logs from /tmp as separate text/plain attachments"

    if product.isFinal:
        print("anaconda %s started." % verdesc)
    else:
        print("anaconda %s (pre-release) started." % verdesc)

    # we are past the --version and --help shortcut so we can import Blivet
    # now without slowing down anything critical

    # pylint: disable=import-error
    from blivet import arch

    if not opts.images and not opts.dirinstall:
        print(logs_note)
        # no fancy stuff like TTYs on a s390...
        if not arch.isS390():
            if "TMUX" in os.environ and os.environ.get("TERM") == "screen":
                print(shell_and_tmux_note)
            else:
                print(shell_only_note)  # TMUX is not running
        # ...but there is apparently TMUX during the manual installation on s390!
        elif not opts.ksfile:
            print(tmux_only_note)  # but not during kickstart installation
        # no need to tell users how to switch to text mode
        # if already in text mode
        if opts.display_mode == 'g':
            print(text_mode_note)
        print(separate_attachements_note)

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

    setupEnvironment()

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
    signal.signal(signal.SIGHUP, startDebugger)

    anaconda.opts = opts

    # check memory, just the text mode for now:
    check_memory(anaconda, opts, 't')

    # Now that we've got arguments, do some extra processing.
    setupLoggingFromOpts(opts)

    # Default is to prompt to mount the installed system.
    anaconda.rescue_mount = not opts.rescue_nomount

    # assign the other anaconda variables from options
    anaconda.proxy = opts.proxy
    anaconda.updateSrc = opts.updateSrc
    anaconda.methodstr = opts.method
    anaconda.stage2 = opts.stage2
    flags.rescue_mode = opts.rescue

    if opts.liveinst:
        from pyanaconda.screensaver import inhibit_screensaver
        from pyanaconda import safe_dbus

        flags.livecdInstall = True

        try:
            anaconda.dbus_session_connection = safe_dbus.get_new_session_connection()
        except safe_dbus.DBusCallError as e:
            log.info("Unable to connect to DBus session bus: %s", e)
        else:
            anaconda.dbus_inhibit_id = inhibit_screensaver(anaconda.dbus_session_connection)
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

    # setup links required for all install types
    for i in ("services", "protocols", "nsswitch.conf", "joe", "selinux",
              "mke2fs.conf"):
        try:
            if os.path.exists("/mnt/runtime/etc/" + i):
                os.symlink("../mnt/runtime/etc/" + i, "/etc/" + i)
        except OSError:
            pass

    log.info("anaconda called with cmdline = %s", sys.argv)
    log.info("Default encoding = %s ", sys.getdefaultencoding())

    iutil.execWithRedirect("udevadm", ["control", "--env=ANACONDA=1"])

    # Collect all addon paths
    addon_paths = collect_addon_paths(constants.ADDON_PATHS)

    # If we were given a kickstart file on the command line, parse (but do not
    # execute) that now.  Otherwise, load in defaults from kickstart files
    # shipped with the installation media.
    ksdata = None
    if opts.ksfile and not opts.liveinst:
        if not os.path.exists(opts.ksfile):
            stdoutLog.error("Kickstart file %s is missing.", opts.ksfile)
            iutil.ipmi_report(constants.IPMI_ABORTED)
            sys.exit(1)

        flags.automatedInstall = True
        flags.eject = False
        ksFiles = [opts.ksfile]
    elif os.path.exists("/run/install/ks.cfg") and not opts.liveinst:
        # this is to handle such cases where a user has pre-loaded a
        # ks.cfg onto an OEMDRV labeled device
        flags.automatedInstall = True
        flags.eject = False
        ksFiles = ["/run/install/ks.cfg"]
    else:
        ksFiles = ["/tmp/updates/interactive-defaults.ks",
                   "/usr/share/anaconda/interactive-defaults.ks"]

    for ks in ksFiles:
        if not os.path.exists(ks):
            continue

        kickstart.preScriptPass(ks)
        log.info("Parsing kickstart: " + ks)
        ksdata = kickstart.parseKickstart(ks)

        # Only load the first defaults file we find.
        break

    if not ksdata:
        ksdata = kickstart.AnacondaKSHandler(addon_paths["ks"])

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
    if anaconda.methodstr and not ksdata.method.seen:
        if anaconda.methodstr.startswith("cdrom"):
            ksdata.method.method = "cdrom"
        elif anaconda.methodstr.startswith("nfs"):
            ksdata.method.method = "nfs"
            (nfsOptions, server, path) = iutil.parseNfsUrl(anaconda.methodstr)
            ksdata.method.server = server
            ksdata.method.dir = path
            ksdata.method.opts = nfsOptions
        elif anaconda.methodstr.startswith("hd:"):
            ksdata.method.method = "harddrive"
            url = anaconda.methodstr.split(":", 1)[1]
            url_parts = url.split(":")
            device = url_parts[0]
            path = ""
            if len(url_parts) == 2:
                path = url_parts[1]
            elif len(url_parts) == 3:
                fstype = url_parts[1]   # XXX not used
                path = url_parts[2]

            ksdata.method.partition = device
            ksdata.method.dir = path
        elif anaconda.methodstr.startswith("http") or \
             anaconda.methodstr.startswith("ftp") or \
             anaconda.methodstr.startswith("file"):
            ksdata.method.method = "url"
            ksdata.method.url = anaconda.methodstr
            # installation source specified by bootoption
            # overrides source set from kickstart;
            # the kickstart might have specified a mirror list,
            # so we need to clear it here if plain url source is provided
            # by a bootoption, because having both url & mirror list
            # set at once is not supported and breaks dnf in
            # unpredictable ways
            # FIXME: Is this still needed for dnf?
            ksdata.method.mirrorlist = None
        elif anaconda.methodstr.startswith("livecd"):
            ksdata.method.method = "harddrive"
            device = anaconda.methodstr.split(":", 1)[1]
            ksdata.method.partition = os.path.normpath(device)
        else:
            log.error("Unknown method: %s", anaconda.methodstr)

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
    localization.setup_locale_environment(locale_option, opts.display_mode != "g")

    # Now that LANG is set, do something with it
    localization.setup_locale(os.environ["LANG"], ksdata.lang, opts.display_mode != "g")

    import blivet
    blivet.enable_installer_mode()

    # Initialize the network now, in case the display needs it
    from pyanaconda.network import networkInitialize, wait_for_connecting_NM_thread

    networkInitialize(ksdata)
    threadMgr.add(AnacondaThread(name=constants.THREAD_WAIT_FOR_CONNECTING_NM, target=wait_for_connecting_NM_thread, args=(ksdata,)))

    # now start the interface
    setupDisplay(anaconda, opts, addon_paths)
    if anaconda.gui_startup_failed:
        # we need to reinitialize the locale if GUI startup failed,
        # as we might now be in text mode, which might not be able to display
        # the characters from our current locale
        log.warning("reinitializing locale due to failed attempt to start the GUI")
        localization.setup_locale(os.environ["LANG"], ksdata.lang, anaconda.displayMode != "g")

    # we now know in which mode we are going to run so store the information
    from pykickstart.constants import DISPLAY_MODE_GRAPHICAL, DISPLAY_MODE_CMDLINE, DISPLAY_MODE_TEXT
    mode_char_to_const = {'g': DISPLAY_MODE_GRAPHICAL, 't': DISPLAY_MODE_TEXT, 'c': DISPLAY_MODE_CMDLINE}
    ksdata.displaymode.displayMode = mode_char_to_const[anaconda.displayMode]

    # if we're in text mode, the resulting system should be too
    # ...unless the kickstart specified otherwise
    if anaconda.displayMode != 'g' and not anaconda.ksdata.xconfig.startX:
        anaconda.ksdata.skipx.skipx = True

    # Set flag to prompt for missing ks data
    if anaconda.displayMode == 'c':
        flags.ksprompt = False

    from pyanaconda.anaconda_argparse import name_path_pairs

    image_count = 0
    try:
        for (name, path) in name_path_pairs(opts.images):
            log.info("naming disk image '%s' '%s'", path, name)
            anaconda.storage.config.diskImages[name] = path
            image_count += 1
            flags.imageInstall = True
    except ValueError as e:
        stdoutLog.error("error specifying image file: %s", e)
        iutil.ipmi_report(constants.IPMI_ABORTED)
        sys.exit(1)

    if image_count:
        anaconda.storage.setupDiskImages()

    from blivet.osinstall import storageInitialize
    from pyanaconda.packaging import payloadMgr
    from pyanaconda.timezone import time_initialize

    if not flags.dirInstall:
        threadMgr.add(AnacondaThread(name=constants.THREAD_STORAGE, target=storageInitialize,
                                     args=(anaconda.storage, ksdata, anaconda.protected)))

    if can_touch_runtime_system("initialize time", touch_live=True):
        threadMgr.add(AnacondaThread(name=constants.THREAD_TIME_INIT, target=time_initialize,
                                     args=(ksdata.timezone, anaconda.storage, anaconda.bootloader)))

    if flags.rescue_mode:
        from pyanaconda.ui.tui.simpleline import App
        from pyanaconda.rescue import RescueMode
        app = App("Rescue Mode")
        spoke = RescueMode(app, anaconda.ksdata, anaconda.storage)
        app.schedule_screen(spoke)
        app.run()
    else:
        cleanPStore()

    # only install interactive exception handler in interactive modes
    if ksdata.displaymode.displayMode != DISPLAY_MODE_CMDLINE or flags.debug:
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
    payloadMgr.restartThread(anaconda.storage, ksdata, anaconda.payload, anaconda.instClass,
            fallback=fallback)

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
        provider_id = constants.GEOLOC_DEFAULT_PROVIDER
        # check if a provider was specified by an option
        if opts.geoloc is not None:
            parsed_id = geoloc.get_provider_id_from_option(opts.geoloc)
            if parsed_id is None:
                log.error('geoloc: wrong provider id specified: %s', opts.geoloc)
            else:
                provider_id = parsed_id
        # instantiate the geolocation module and start location data refresh
        geoloc.init_geolocation(provider_id=provider_id)
        geoloc.refresh()

    # setup ntp servers and start NTP daemon if not requested otherwise
    if can_touch_runtime_system("start chronyd"):
        if anaconda.ksdata.timezone.ntpservers:
            pools, servers = ntp.internal_to_pools_and_servers(anaconda.ksdata.timezone.ntpservers)
            ntp.save_servers_to_config(pools, servers)

        if not anaconda.ksdata.timezone.nontp:
            iutil.start_service("chronyd")

    # FIXME:  This will need to be made cleaner once this file starts to take
    # shape with the new UI code.
    anaconda._intf.setup(ksdata)
    anaconda._intf.run()

# vim:tw=78:ts=4:et:sw=4
