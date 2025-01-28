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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import os
import pkgutil
import sys
import time

from blivet.arch import is_s390
from blivet.util import total_memory
from dasbus.typing import Int, get_variant

from pyanaconda import anaconda_logging, kickstart, network, ntp
from pyanaconda.anaconda_loggers import get_module_logger, get_stdout_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import (
    DRACUT_ERRORS_PATH,
    GEOLOC_CONNECTION_TIMEOUT,
    IPMI_ABORTED,
    SELINUX_DEFAULT,
    SETUP_ON_BOOT_DEFAULT,
    SETUP_ON_BOOT_ENABLED,
    STORAGE_MIN_RAM,
    TEXT_ONLY_TARGET,
    THREAD_TIME_INIT,
    TIMEZONE_PRIORITY_GEOLOCATION,
    DisplayModes,
)
from pyanaconda.core.hw import minimal_memory_needed
from pyanaconda.core.i18n import _
from pyanaconda.core.payload import ProxyString, ProxyStringError
from pyanaconda.core.product import (
    get_product_is_final_release,
    get_product_name,
    get_product_version,
)
from pyanaconda.core.service import start_service
from pyanaconda.core.threads import thread_manager
from pyanaconda.core.util import (
    get_anaconda_version_string,
    ipmi_report,
    persistent_root_image,
    setenv,
)
from pyanaconda.flags import flags
from pyanaconda.localization import (
    get_territory_locales,
    locale_has_translation,
    setup_locale,
)
from pyanaconda.modules.common.constants.objects import (
    CERTIFICATES,
    STORAGE_CHECKER,
)
from pyanaconda.modules.common.constants.services import (
    LOCALIZATION,
    RUNTIME,
    SECURITY,
    SERVICES,
    STORAGE,
    TIMEZONE,
)
from pyanaconda.modules.common.errors.installation import SecurityInstallationError
from pyanaconda.modules.common.structures.logging import LoggingData
from pyanaconda.modules.common.structures.timezone import (
    GeolocationData,
    TimeSourceData,
)
from pyanaconda.modules.common.task import sync_run_task, wait_for_task
from pyanaconda.modules.common.util import is_module_available
from pyanaconda.screensaver import inhibit_screensaver

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
    """Check if the system has enough RAM for installation.

    :param anaconda: instance of the Anaconda class
    :param options: command line/boot options
    :param display_mode: a display mode to use for the check
                         (graphical mode usually needs more RAM, etc.)
    """

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
    total_ram = int(total_memory().convert_to("MiB"))

    # count the squashfs.img in if it is kept in RAM
    with_squashfs = not persistent_root_image()
    needed_ram = minimal_memory_needed(with_gui=False, with_squashfs=with_squashfs)
    log.info("check_memory(): total:%s, needed:%s", total_ram, needed_ram)

    if not options.memcheck:
        log.warning("CHECK_MEMORY DISABLED")
        return

    reason_args = {"product_name": get_product_name(),
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

        ipmi_report(IPMI_ABORTED)
        sys.exit(1)

    # override display mode if machine cannot nicely run X
    if display_mode != DisplayModes.TUI and not flags.use_rd:
        needed_ram = minimal_memory_needed(with_gui=True, with_squashfs=with_squashfs)
        log.info("check_memory(): total:%s, graphical:%s", total_ram, needed_ram)
        reason_args["needed_ram"] = needed_ram
        reason = reason_graphical

        if needed_ram > total_ram:
            if options.liveinst:
                reason += livecd_extra
                # pylint: disable=logging-not-lazy
                stdout_log.warning(reason % reason_args)
                title = livecd_title
                gtk_warning(title, reason % reason_args)
                ipmi_report(IPMI_ABORTED)
                sys.exit(1)
            else:
                reason += nolivecd_extra
                # pylint: disable=logging-not-lazy
                stdout_log.warning(reason % reason_args)
                anaconda.display_mode = DisplayModes.TUI
                time.sleep(2)


def set_storage_checker_minimal_ram_size(display_mode):
    """Set minimal ram size to the storage checker.

    :param display_mode: display mode
    :type display_mode: constants.DisplayModes.[TUI|GUI]
    """
    min_ram = minimal_memory_needed(with_gui=display_mode == DisplayModes.GUI)

    storage_checker = STORAGE.get_proxy(STORAGE_CHECKER)
    storage_checker.SetConstraint(
        STORAGE_MIN_RAM,
        get_variant(Int, min_ram * 1024 * 1024)
    )


def fallback_to_tui_if_gtk_ui_is_not_available(anaconda):
    """Check if GTK UI is available in this environment and fallback to TUI if not.

    Also take into account Web UI.
    """
    if anaconda.gui_mode and not anaconda.is_webui_supported:
        import pyanaconda.ui

        mods = (tup[1] for tup in pkgutil.iter_modules(pyanaconda.ui.__path__, "pyanaconda.ui."))
        if "pyanaconda.ui.gui" not in mods:
            stdout_log.warning("Graphical user interface not available, falling back to text mode")
            anaconda.display_mode = DisplayModes.TUI
            flags.use_rd = False
            flags.rd_question = False


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


def setup_logging_from_kickstart():
    """Configure logging according to the kickstart.
    """
    runtime_proxy = RUNTIME.get_proxy()
    logging_data = LoggingData.from_structure(runtime_proxy.Logging)
    host = logging_data.host
    port = logging_data.port

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
        setenv("PROXY", proxy.noauth_url)
        setenv("PROXY_USER", proxy.username or "")
        setenv("PROXY_PASSWORD", proxy.password or "")

        # Variables used by curl, libreport, etc.
        setenv("http_proxy", proxy.url)
        setenv("ftp_proxy", proxy.url)
        setenv("HTTPS_PROXY", proxy.url)


def prompt_for_ssh(options):
    """Prompt the user to ssh to the installation environment on the s390.

    :param options: Anaconda command line/boot options
    :return: True if the prompt is printed, otherwise False
    """
    if not is_s390():
        return False

    if not conf.target.is_hardware:
        return False

    if 'TMUX' in os.environ:
        return False

    if options.ksfile:
        return False

    if options.rdp_enabled:
        return False

    # Do some work here to get the ip addr / hostname to pass
    # to the user.
    import socket

    ip = network.get_first_ip_address()

    if not ip:
        stdout_log.error("No IP addresses found, cannot continue installation.")
        ipmi_report(IPMI_ABORTED)
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
    verdesc = "%s for %s %s" % (get_anaconda_version_string(build_time_version=True),
                                get_product_name(), get_product_version())
    logs_note = " * installation log files are stored in /tmp during the installation"
    shell_and_tmux_note = " * shell is available on TTY2"
    shell_only_note = " * shell is available on TTY2 and in second TMUX pane (ctrl+b, then press 2)"
    tmux_only_note = " * shell is available in second TMUX pane (ctrl+b, then press 2)"
    text_mode_note = " * if the graphical installation interface fails to start, try again with the\n"\
                     "   inst.text boot option to start text installation"
    separate_attachements_note = " * when reporting a bug add logs from /tmp as separate text/plain attachments"

    if get_product_is_final_release():
        print("anaconda %s started." % verdesc)
    else:
        print("anaconda %s (pre-release) started." % verdesc)

    if not options.images and not options.dirinstall:
        print(logs_note)
        # no fancy stuff like TTYs on a s390...
        if not is_s390():
            if "TMUX" in os.environ and os.environ.get("TERM") == "screen":
                print(shell_and_tmux_note)
            else:
                print(shell_only_note)  # TMUX is not running
        # ...but there is apparently TMUX during the manual installation on s390!
        elif not options.ksfile:
            print(tmux_only_note)  # but not during kickstart installation
        # no need to tell users how to switch to text mode
        # if already in text mode
        if options.display_mode == DisplayModes.TUI:
            print(text_mode_note)
        print(separate_attachements_note)


def live_startup():
    """Live environment startup tasks."""
    inhibit_screensaver()


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
            ipmi_report(IPMI_ABORTED)
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


def run_pre_scripts(ks_path):
    """Run %pre scripts.

    :param ks_path: a path to a kickstart file or None
    """
    if ks_path is not None:
        kickstart.preScriptPass(ks_path)


def parse_kickstart(ks_path, strict_mode=False):
    """Parse the given kickstart file.

    :param ks_path: a path to a kickstart file or None
    :param strict_mode: process warnings as errors if True
    :returns: kickstart parsed to a data model
    """
    ksdata = kickstart.AnacondaKSHandler()

    if ks_path is not None:
        log.info("Parsing kickstart: %s", ks_path)
        kickstart.parseKickstart(ksdata, ks_path, strict_mode=strict_mode)

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

    thread_manager.add_thread(
        name=THREAD_TIME_INIT,
        target=time_initialize,
        args=(timezone_proxy,)
    )


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
        localization_proxy.KeyboardKickstarted = True

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
            localization_proxy.Language = opts.lang
            localization_proxy.LanguageKickstarted = True

        # Setup the locale environment
        if localization_proxy.LanguageKickstarted:
            locale_option = localization_proxy.Language

    localization.setup_locale_environment(locale_option, text_mode=text_mode)

    # Now that LANG is set, do something with it
    localization.setup_locale(os.environ["LANG"], localization_proxy, text_mode=text_mode)


def reinitialize_locale(text_mode):
    """Reinitialize locale.

    We need to reinitialize the locale if GUI startup failed.
    The text mode might not be able to display the characters
    from our current locale.

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

        Installation controlled via RDP is considered to be
        a text mode installation, as the installation run itself
        is effectively headless.

    :param text_mode: does the installer run in the text mode?
    """
    if not is_module_available(SERVICES):
        return

    services_proxy = SERVICES.get_proxy()

    if not services_proxy.DefaultTarget and (text_mode or flags.use_rd):
        log.debug("no default systemd target set & in text/remote desktop mode - "
                  "setting multi-user.target.")
        services_proxy.DefaultTarget = TEXT_ONLY_TARGET


def initialize_first_boot_action():
    """Initialize the setup on boot action."""
    if not is_module_available(SERVICES):
        return

    services_proxy = SERVICES.get_proxy()

    if services_proxy.SetupOnBoot == SETUP_ON_BOOT_DEFAULT:
        if not flags.automatedInstall:
            # Enable by default for interactive installations.
            services_proxy.SetupOnBoot = SETUP_ON_BOOT_ENABLED


def initialize_security():
    """Initialize the security configuration."""
    if not is_module_available(SECURITY):
        return

    security_proxy = SECURITY.get_proxy()

    # Override the selinux state from kickstart if set on the command line
    if conf.security.selinux != SELINUX_DEFAULT:
        security_proxy.SELinux = conf.security.selinux

    # Enable fingerprint option by default (#481273).
    if not flags.automatedInstall:
        security_proxy.FingerprintAuthEnabled = True

    # Import certificates from kickstart
    # In most cases they have already been imported from kickstart
    # during the initramfs stage kickstart processing and passed to the
    # installer enviroment either from initramfs or early after
    # switch root by a dedicated systemd service.
    # However they would not be already imported for example in case the
    # certificate is included by a snippet created in kickstart %pre
    # section.
    certificates_proxy = SECURITY.get_proxy(CERTIFICATES)
    import_task_path = certificates_proxy.ImportWithTask()
    task_proxy = SECURITY.get_proxy(import_task_path)
    try:
        sync_run_task(task_proxy)
    except SecurityInstallationError as e:
        log.error(e)
        print(_("\nAn error occurred during certificate import from kickstart:"
                "\n%s\n") % str(e).strip())

        print(_("The installation cannot continue"))
        ipmi_report(IPMI_ABORTED)
        sys.exit(1)


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


def check_if_geolocation_should_be_used(opts):
    """Check if geolocation can be used during this installation run.

    The result is based on current installation type - fully interactive vs
    fully or partially automated kickstart installation and on the state of the
    "geoloc*" boot/CLI options.

    By default geolocation is not enabled during a kickstart based installation,
    unless the geoloc_use_with_ks boot/CLI option is used.

    Also the geoloc boot/CLI option can be used to make sure geolocation
    will not be used during an installation, like this:

    inst.geoloc=0

    :param opts: the command line/boot options
    """
    # don't use geolocation during image and directory installation
    if not conf.target.is_hardware:
        log.info("Geolocation is disabled for image or directory installation.")
        return False

    # check if geolocation was not disabled by boot or command line option
    # our documentation mentions only "0" as the way to disable it
    if str(opts.geoloc).strip() == "0":
        log.info("Geolocation is disabled by the geoloc option.")
        return False

    # don't use geolocation during kickstart installation unless explicitly
    # requested by the user
    if flags.automatedInstall:
        if opts.geoloc_use_with_ks:
            # check for use-with-kickstart overrides
            log.info("Geolocation is enabled during kickstart installation due to use of "
                     "the geoloc-use-with-ks option.")
            return True
        else:
            # otherwise disable geolocation during a kickstart installation
            log.info("Geolocation is disabled due to automated kickstart based installation.")
            return False

    log.info("Geolocation is enabled.")
    return True


def start_geolocation_conditionally(opts):
    """Start geolocation conditionally, according to the command line or boot options.

    :param opts: the command line/boot options
    :return: D-Bus proxy for the geolocation task
    """
    use_geoloc = check_if_geolocation_should_be_used(opts)
    if not use_geoloc:
        return None

    if not is_module_available(TIMEZONE):
        log.warning("Geoloc: not starting due to missing Timezone module")
        return None

    if not is_module_available(LOCALIZATION):
        log.warning("Geoloc: not starting due to missing Localization module")
        return None

    timezone_proxy = TIMEZONE.get_proxy()
    geoloc_task_path = timezone_proxy.StartGeolocationWithTask()
    geoloc_task_proxy = TIMEZONE.get_proxy(geoloc_task_path)
    geoloc_task_proxy.Start()
    return geoloc_task_proxy


def wait_for_geolocation_and_use(geoloc_task_proxy, display_mode):
    """Wait for geolocation and use the result, if started.

    :param geoloc_task_proxy: D-Bus proxy for a GeolocationTask instance
    :param display_mode: a display mode to use for the check
    """
    if not geoloc_task_proxy:
        return

    try:
        wait_for_task(geoloc_task_proxy, timeout=GEOLOC_CONNECTION_TIMEOUT)
    except TimeoutError:
        log.debug("Geolocation timed out. Exceptions will not be logged.")
        return
    else:
        apply_geolocation_result(display_mode)


def apply_geolocation_result(display_mode):
    """Apply geolocation result.

    This does not check for kickstart installations, because in that case geolocation is not even
    started.

    :param display_mode: a display mode to use for the check
    """
    timezone_module = TIMEZONE.get_proxy()
    localization_module = LOCALIZATION.get_proxy()

    geoloc_result = GeolocationData.from_structure(timezone_module.GeolocationResult)

    # Nothing to do with no inputs.
    if geoloc_result.is_empty():
        return

    if geoloc_result.timezone:
        # (the geolocation module makes sure that the returned timezone is
        # either a valid timezone or empty string)
        log.info("Geoloc: using timezone determined by geolocation")
        timezone_module.SetTimezoneWithPriority(
            geoloc_result.timezone,
            TIMEZONE_PRIORITY_GEOLOCATION
        )
        # Either this is an interactive install and timezone.seen propagates
        # from the interactive default kickstart, or this is a kickstart
        # install where the user explicitly requested geolocation to be used.
        # So set timezone.seen to True, so that the user isn't forced to
        # enter the Date & Time spoke to acknowledge the timezone detected
        # by geolocation before continuing the installation.
        timezone_module.Kickstarted = True

    if not conf.localization.use_geolocation:
        log.info("Geoloc: skipping locale because of use_geolocation configuration")
        return

    # skip language setup if already set by boot options or kickstart
    language = localization_module.Language
    if language and localization_module.LanguageKickstarted:
        log.info("Geoloc: skipping locale because already set")
        return

    territory = geoloc_result.territory
    locales = get_territory_locales(territory)
    try:
        locale = next(loc for loc in locales if locale_has_translation(loc))
    except StopIteration:
        log.info("Geoloc: detected languages are not translated, skipping locale")
        return

    is_console = display_mode == DisplayModes.TUI
    locale = setup_locale(locale, localization_module, text_mode=is_console)
    # pylint: disable=environment-modify
    os.environ["LANG"] = locale
