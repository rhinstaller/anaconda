#
# startup_utils.py - code used during early startup with minimal dependencies
#
# Copyright (C) 2014  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import sys
import time
import os
import blivet

from pyanaconda import product, ntp
from pyanaconda import anaconda_logging
from pyanaconda import network
from pyanaconda import safe_dbus
from pyanaconda import kickstart
from pyanaconda.anaconda_loggers import get_stdout_logger, get_module_logger
from pyanaconda.core import util, constants
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import TEXT_ONLY_TARGET, SETUP_ON_BOOT_DEFAULT, \
    SETUP_ON_BOOT_ENABLED, DRACUT_ERRORS_PATH
from pyanaconda.core.i18n import _
from pyanaconda.core.payload import ProxyString, ProxyStringError
from pyanaconda.core.service import start_service
from pyanaconda.flags import flags
from pyanaconda.screensaver import inhibit_screensaver
from pyanaconda.modules.common.structures.timezone import TimeSourceData
from pyanaconda.modules.common.constants.services import TIMEZONE, LOCALIZATION, SERVICES, \
    SECURITY
from pyanaconda.modules.common.util import is_module_available
from pyanaconda.threading import AnacondaThread, threadMgr

stdout_log = get_stdout_logger()
log = get_module_logger(__name__)


def gtk_warning(title, reason):
    """A simple warning dialog for use during early startup of the Anaconda GUI.

    :param str title: title of the warning dialog
    :param str reason: warning message

    TODO: this should be abstracted out to some kind of a "warning API" + UI code
          that shows the actual warning
    """
    import gi
    gi.require_version("Gtk", "3.0")

    from gi.repository import Gtk
    dialog = Gtk.MessageDialog(type=Gtk.MessageType.ERROR,
                               buttons=Gtk.ButtonsType.CLOSE,
                               message_format=reason)
    dialog.set_title(title)
    dialog.run()
    dialog.destroy()


def check_memory(anaconda, options, display_mode=None):
    """Check is the system has enough RAM for installation.

    :param anaconda: instance of the Anaconda class
    :param options: command line/boot options
    :param display_mode: a display mode to use for the check
                         (graphical mode usually needs more RAM, etc.)
    """

    from pyanaconda import isys

    reason_strict = _("%(product_name)s requires %(needed_ram)s MB of memory to "
                      "install, but you only have %(total_ram)s MB on this machine.\n")
    reason_graphical = _("The %(product_name)s graphical installer requires %(needed_ram)s "
                         "MB of memory, but you only have %(total_ram)s MB.\n")

    reboot_extra = _('\n'
                     'Press [Enter] to reboot your system.\n')
    livecd_title = _("Not enough RAM")
    livecd_extra = _(" Try the text mode installer by running:\n\n"
                     "'/usr/bin/liveinst -T'\n\n from a root terminal.")
    nolivecd_extra = _(" Starting text mode.")

    # skip the memory check in rescue mode
    if options.rescue:
        return

    if not display_mode:
        display_mode = anaconda.display_mode

    reason = reason_strict
    total_ram = int(isys.total_memory() / 1024)
    needed_ram = int(isys.MIN_RAM)
    graphical_ram = int(isys.MIN_GUI_RAM)

    # count the squashfs.img in if it is kept in RAM
    if not util.persistent_root_image():
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
            stdout_log.warning(reason % reason_args)
            gtk_warning(livecd_title, reason % reason_args)
        else:
            reason += reboot_extra
            print(reason % reason_args)
            print(_("The installation cannot continue and the system will be rebooted"))
            print(_("Press ENTER to continue"))
            input()

        util.ipmi_report(constants.IPMI_ABORTED)
        sys.exit(1)

    # override display mode if machine cannot nicely run X
    if display_mode != constants.DisplayModes.TUI and not flags.usevnc:
        needed_ram = graphical_ram
        reason_args["needed_ram"] = graphical_ram
        reason = reason_graphical

        if needed_ram > total_ram:
            if options.liveinst:
                reason += livecd_extra
                # pylint: disable=logging-not-lazy
                stdout_log.warning(reason % reason_args)
                title = livecd_title
                gtk_warning(title, reason % reason_args)
                util.ipmi_report(constants.IPMI_ABORTED)
                sys.exit(1)
            else:
                reason += nolivecd_extra
                # pylint: disable=logging-not-lazy
                stdout_log.warning(reason % reason_args)
                anaconda.display_mode = constants.DisplayModes.TUI
                time.sleep(2)


def setup_logging_from_options(options):
    """Configure logging according to Anaconda command line/boot options.

    :param options: Anaconda command line/boot options
    """
    if conf.system.can_modify_syslog:
        if options.syslog:
            anaconda_logging.logger.updateRemote(options.syslog)

    if options.remotelog:
        try:
            host, port = options.remotelog.split(":", 1)
            port = int(port)
            anaconda_logging.logger.setup_remotelog(host, port)
        except ValueError:
            log.error("Could not setup remotelog with %s", options.remotelog)


def setup_logging_from_kickstart(data):
    """Configure logging according to the kickstart.

    :param data: kickstart data
    """
    host = data.logging.host
    port = data.logging.port

    if anaconda_logging.logger.remote_syslog is None and len(host) > 0:
        # not set from the command line, ok to use kickstart
        remote_server = host
        if port:
            remote_server = "%s:%s" % (host, port)
        anaconda_logging.logger.updateRemote(remote_server)


def set_up_proxy_variables(proxy):
    """Set up proxy environmental variables.

    Set up proxy environmental variables so that %pre and %post
    scripts can use it as well as curl, libreport, etc.

    :param proxy: a string with the proxy URL
    """
    if not proxy:
        log.debug("Don't set up proxy variables.")
        return

    try:
        proxy = ProxyString(proxy)
    except ProxyStringError as e:
        log.info("Failed to parse proxy \"%s\": %s", proxy, e)
    else:
        # Set environmental variables to be used by pre/post scripts
        util.setenv("PROXY", proxy.noauth_url)
        util.setenv("PROXY_USER", proxy.username or "")
        util.setenv("PROXY_PASSWORD", proxy.password or "")

        # Variables used by curl, libreport, etc.
        util.setenv("http_proxy", proxy.url)
        util.setenv("ftp_proxy", proxy.url)
        util.setenv("HTTPS_PROXY", proxy.url)


def prompt_for_ssh(options):
    """Prompt the user to ssh to the installation environment on the s390.

    :param options: Anaconda command line/boot options
    :return: True if the prompt is printed, otherwise False
    """
    if not blivet.arch.is_s390():
        return False

    if not conf.target.is_hardware:
        return False

    if 'TMUX' in os.environ:
        return False

    if options.ksfile:
        return False

    if options.vnc:
        return False

    # Do some work here to get the ip addr / hostname to pass
    # to the user.
    import socket

    ip = network.get_first_ip_address()

    if not ip:
        stdout_log.error("No IP addresses found, cannot continue installation.")
        util.ipmi_report(constants.IPMI_ABORTED)
        sys.exit(1)

    ipstr = ip

    name = None
    try:
        hinfo = socket.gethostbyaddr(ipstr)
    except socket.herror as e:
        stdout_log.debug("Exception caught trying to get host name of %s: %s", ipstr, e)
        name = socket.gethostname()
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
        stdout_log.info(_("Please ssh install@%s to begin the install."), connxinfo)
    else:
        stdout_log.info(_("Please ssh install@HOSTNAME to continue installation."))

    return True


def clean_pstore():
    """Remove files stored in nonvolatile ram created by the pstore subsystem.

    Files in pstore are Linux (not distribution) specific, but we want to
    make sure the entirety of them are removed so as to ensure that there
    is sufficient free space on the flash part.  On some machines this will
    take effect immediately, which is the best case.  Unfortunately on some,
    an intervening reboot is needed.
    """
    for (base, dirs, files) in os.walk("/sys/fs/pstore"):  # pylint: disable=unused-variable
        for file in files:
            try:
                os.unlink(os.path.join(base, file))
            except OSError:
                pass

def print_startup_note(options):
    """Print Anaconda version and short usage instructions.

    Print Anaconda version and short usage instruction to the TTY where Anaconda is running.

    :param options: command line/boot options
    """
    verdesc = "%s for %s %s" % (util.get_anaconda_version_string(build_time_version=True),
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

    if not options.images and not options.dirinstall:
        print(logs_note)
        # no fancy stuff like TTYs on a s390...
        if not blivet.arch.is_s390():
            if "TMUX" in os.environ and os.environ.get("TERM") == "screen":
                print(shell_and_tmux_note)
            else:
                print(shell_only_note)  # TMUX is not running
        # ...but there is apparently TMUX during the manual installation on s390!
        elif not options.ksfile:
            print(tmux_only_note)  # but not during kickstart installation
        # no need to tell users how to switch to text mode
        # if already in text mode
        if options.display_mode == constants.DisplayModes.TUI:
            print(text_mode_note)
        print(separate_attachements_note)


def live_startup(anaconda):
    """Live environment startup tasks.

    :param anaconda: instance of the Anaconda class
    """
    try:
        anaconda.dbus_session_connection = safe_dbus.get_new_session_connection()
    except safe_dbus.DBusCallError as e:
        log.info("Unable to connect to DBus session bus: %s", e)
    else:
        anaconda.dbus_inhibit_id = inhibit_screensaver(anaconda.dbus_session_connection)


def find_kickstart(options):
    """Find a kickstart to parse.

    If we were given a kickstart file, return that one. Otherwise, return
    a default kickstart file shipped with the installation media.

    Pick up any changes from interactive-defaults.ks that would otherwise
    be covered by the dracut kickstart parser.

    :param options: command line/boot options
    :returns: a path to a kickstart file or None
    """
    if options.ksfile and not options.liveinst:
        if not os.path.exists(options.ksfile):
            stdout_log.error("Kickstart file %s is missing.", options.ksfile)
            util.ipmi_report(constants.IPMI_ABORTED)
            sys.exit(1)

        flags.automatedInstall = True
        flags.eject = False
        ks_files = [options.ksfile]
    elif os.path.exists("/run/install/ks.cfg") and not options.liveinst:
        # this is to handle such cases where a user has pre-loaded a
        # ks.cfg onto an OEMDRV labeled device
        flags.automatedInstall = True
        flags.eject = False
        ks_files = ["/run/install/ks.cfg"]
    else:
        ks_files = ["/usr/share/anaconda/interactive-defaults.ks"]

    for ks in ks_files:
        if not os.path.exists(ks):
            continue

        return ks

    return None


def run_pre_scripts(ks):
    """Run %pre scripts.

    :param ks: a path to a kickstart file or None
    """
    if ks is not None:
        kickstart.preScriptPass(ks)


def parse_kickstart(ks, strict_mode=False):
    """Parse the given kickstart file.

    :param ks: a path to a kickstart file or None
    :param strict_mode: process warnings as errors if True
    :returns: kickstart parsed to a data model
    """
    ksdata = kickstart.AnacondaKSHandler()

    if ks is not None:
        log.info("Parsing kickstart: %s", ks)
        kickstart.parseKickstart(ksdata, ks, strict_mode=strict_mode, pass_to_boss=True)

    return ksdata


def initialize_system_clock():
    """Initialize the system clock."""
    if not conf.system.can_initialize_system_clock:
        log.debug("Skip the clock initialization.")
        return

    if not is_module_available(TIMEZONE):
        return

    from pyanaconda.timezone import time_initialize
    timezone_proxy = TIMEZONE.get_proxy()

    threadMgr.add(AnacondaThread(
        name=constants.THREAD_TIME_INIT,
        target=time_initialize,
        args=(timezone_proxy,)
    ))


def start_chronyd():
    """Start the NTP daemon chronyd.

    Set up NTP servers and start NTP daemon if not requested otherwise.
    """
    if not conf.system.can_set_time_synchronization:
        log.debug("Skip the time synchronization.")
        return

    if not is_module_available(TIMEZONE):
        log.debug("Skip the time synchronization due to disabled module.")
        return

    timezone_proxy = TIMEZONE.get_proxy()
    enabled = timezone_proxy.NTPEnabled
    servers = TimeSourceData.from_structure_list(
        timezone_proxy.TimeSources
    )

    if servers:
        ntp.save_servers_to_config(servers)

    if enabled:
        start_service("chronyd")


def activate_keyboard(opts):
    """Activate keyboard.

    Set up keyboard layout from the command line option and
    let it override from kickstart if/when X is initialized.

    :param opts: the command line/boot options
    """
    if not is_module_available(LOCALIZATION):
        return

    from pyanaconda import keyboard
    localization_proxy = LOCALIZATION.get_proxy()

    if opts.keymap and not localization_proxy.KeyboardKickstarted:
        localization_proxy.SetKeyboard(opts.keymap)
        localization_proxy.SetKeyboardKickstarted(True)

    if localization_proxy.KeyboardKickstarted:
        if conf.system.can_activate_keyboard:
            keyboard.activate_keyboard(localization_proxy)
        else:
            # at least make sure we have all the values
            keyboard.populate_missing_items(localization_proxy)


def initialize_locale(opts, text_mode):
    """Initialize locale.

    :param opts: the command line/boot options
    :param text_mode: is the locale being set up for the text mode?
    """
    from pyanaconda import localization

    locale_option = None
    localization_proxy = None

    if is_module_available(LOCALIZATION):
        localization_proxy = LOCALIZATION.get_proxy()

        # If the language was set on the command line, copy that to kickstart
        if opts.lang:
            localization_proxy.SetLanguage(opts.lang)
            localization_proxy.SetLanguageKickstarted(True)

        # Setup the locale environment
        if localization_proxy.LanguageKickstarted:
            locale_option = localization_proxy.Language

    localization.setup_locale_environment(locale_option, text_mode=text_mode)

    # Now that LANG is set, do something with it
    localization.setup_locale(os.environ["LANG"], localization_proxy, text_mode=text_mode)


def reinitialize_locale(opts, text_mode):
    """Reinitialize locale.

    We need to reinitialize the locale if GUI startup failed.
    The text mode might not be able to display the characters
    from our current locale.

    :param opts: the command line/boot options
    :param text_mode: is the locale being set up for the text mode?
    """
    from pyanaconda import localization
    localization_proxy = None

    if is_module_available(LOCALIZATION):
        localization_proxy = LOCALIZATION.get_proxy()

    log.warning("reinitializing locale due to failed attempt to start the GUI")
    localization.setup_locale(os.environ["LANG"], localization_proxy, text_mode=text_mode)


def initialize_default_systemd_target(text_mode):
    """Initialize the default systemd target.

    If we're in text mode, the resulting system should be too
    unless the kickstart specified otherwise.

    NOTE:

        Installation controlled via VNC is considered to be
        a text mode installation, as the installation run itself
        is effectively headless.

    :param text_mode: does the installer run in the text mode?
    """
    if not is_module_available(SERVICES):
        return

    services_proxy = SERVICES.get_proxy()

    if not services_proxy.DefaultTarget and (text_mode or flags.usevnc):
        log.debug("no default systemd target set & in text/vnc mode - setting multi-user.target.")
        services_proxy.SetDefaultTarget(TEXT_ONLY_TARGET)


def initialize_first_boot_action():
    """Initialize the setup on boot action."""
    if not is_module_available(SERVICES):
        return

    services_proxy = SERVICES.get_proxy()

    if services_proxy.SetupOnBoot == SETUP_ON_BOOT_DEFAULT:
        if not flags.automatedInstall:
            # Enable by default for interactive installations.
            services_proxy.SetSetupOnBoot(SETUP_ON_BOOT_ENABLED)


def initialize_security():
    """Initialize the security configuration."""
    if not is_module_available(SECURITY):
        return

    security_proxy = SECURITY.get_proxy()

    # Override the selinux state from kickstart if set on the command line
    if conf.security.selinux != constants.SELINUX_DEFAULT:
        security_proxy.SetSELinux(conf.security.selinux)

    # Enable fingerprint option by default (#481273).
    if not flags.automatedInstall:
        security_proxy.SetFingerprintAuthEnabled(True)


def print_dracut_errors(stdout_logger):
    """Print Anaconda critical warnings from Dracut to user before starting Anaconda.

    :param stdout_logger: python logger to stdout
    """
    try:
        with open(DRACUT_ERRORS_PATH, "rt") as fd:
            section_name = "Installer errors encountered during boot"
            msg = "\n{:#^70}\n{}\n{:#^70}".format(  # add starting \n because timestamp
                " " + section_name + " ",           # start of the section
                "".join(fd.readlines()),            # errors from Dracut
                " " + section_name + " end ")       # end of the section
            stdout_logger.warning(msg)
    except OSError:
        pass
