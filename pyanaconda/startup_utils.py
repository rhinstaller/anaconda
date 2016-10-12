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
from pyanaconda.i18n import _

import logging
log = logging.getLogger("anaconda")
stdout_log = logging.getLogger("anaconda.stdout")

import sys
import time
import imp
import os

from pyanaconda import iutil
from pyanaconda import product
from pyanaconda import constants
from pyanaconda import geoloc
from pyanaconda import anaconda_log
from pyanaconda import network
from pyanaconda.flags import flags
from pyanaconda.flags import can_touch_runtime_system

import blivet

def module_exists(module_path):
    """Report is a given module exists in the current module import pth or not.
    Supports checking bot modules ("foo") os submodules ("foo.bar.baz")

    :param str module_path: (sub)module identifier

    :returns: True if (sub)module exists in path, False if not
    :rtype: bool
    """

    module_path_components = module_path.split(".")
    module_name = module_path_components.pop()
    parent_module_path = None
    if module_path_components:
        # the path specifies a submodule ("bar.foo")
        # we need to chain-import all the modules in the submodule path before
        # we can check if the submodule itself exists
        for name in module_path_components:
            module_info = imp.find_module(name, parent_module_path)
            module = imp.load_module(name, *module_info)
            if module:
                parent_module_path = module.__path__
            else:
                # one of the parents was not found, abort search
                return False
    # if we got this far we should have either some path or the module is
    # not a submodule and the default set of paths will be used (path=None)
    try:
        # if the module is not found imp raises an ImportError
        imp.find_module(module_name, parent_module_path)
        return True
    except ImportError:
        return False

def get_anaconda_version_string():
    """Return a string describing current Anaconda version.
    If the current version can't be determined the string
    "unknown" will be returned.

    :returns: string describing Anaconda version
    :rtype: str
    """

    # we are importing the version module directly so that we don't drag in any
    # non-necessary stuff; we also need to handle the possibility of the
    # import itself failing
    if module_exists("pyanaconda.version"):
        # Ignore pylint not finding the version module, since thanks to automake
        # there's a good chance that version.py is not in the same directory as
        # the rest of pyanaconda.
        from pyanaconda import version  # pylint: disable=no-name-in-module
        return version.__version__
    else:
        return "unknown"

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
                         "MB of memory, but you only have %(total_ram)s MB\n.")

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
            stdout_log.warning(reason % reason_args)
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
    if display_mode not in constants.TEXT_DISPLAY_MODES and not flags.usevnc:
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
                iutil.ipmi_report(constants.IPMI_ABORTED)
                sys.exit(1)
            else:
                reason += nolivecd_extra
                # pylint: disable=logging-not-lazy
                stdout_log.warning(reason % reason_args)
                anaconda.display_mode = constants.DISPLAY_MODE_TUI
                time.sleep(2)

def start_geolocation(provider_id=constants.GEOLOC_DEFAULT_PROVIDER):
    """Start an asynchronous geolocation attempt.

    The data from geolocation is used to pre-select installation language and timezone.

    :param str provider_id: geolocation provider id
    """
    # check if the provider id is valid
    parsed_id = geoloc.get_provider_id_from_option(provider_id)
    if parsed_id is None:
        log.error('geoloc: wrong provider id specified: %s', provider_id)
    else:
        provider_id = parsed_id
    # instantiate the geolocation module and start location data refresh
    geoloc.init_geolocation(provider_id=provider_id)
    geoloc.refresh()

def setup_logging_from_options(options):
    """Configure logging according to Anaconda command line/boot options.

    :param options: Anaconda command line/boot options
    """
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

def prompt_for_ssh():
    """Prompt the user to ssh to the installation environment on the s390."""

    # Do some work here to get the ip addr / hostname to pass
    # to the user.
    import socket

    ip = network.getFirstRealIP()

    if not ip:
        stdout_log.error("No IP addresses found, cannot continue installation.")
        iutil.ipmi_report(constants.IPMI_ABORTED)
        sys.exit(1)

    ipstr = ip

    try:
        hinfo = socket.gethostbyaddr(ipstr)
    except socket.herror as e:
        stdout_log.debug("Exception caught trying to get host name of %s: %s", ipstr, e)
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
        stdout_log.info(_("Please ssh install@%s to begin the install."), connxinfo)
    else:
        stdout_log.info(_("Please ssh install@HOSTNAME to continue installation."))

def clean_pstore():
    """Remove files stored in nonvolatile ram created by the pstore subsystem.

    Files in pstore are Linux (not distribution) specific, but we want to
    make sure the entirety of them are removed so as to ensure that there
    is sufficient free space on the flash part.  On some machines this will
    take effect immediately, which is the best case.  Unfortunately on some,
    an intervening reboot is needed.
    """
    iutil.dir_tree_map("/sys/fs/pstore", os.unlink, files=True, dirs=False)

def print_startup_note(options):
    """Print Anaconda version and short usage instructions.

    Print Anaconda version and short usage instruction to the TTY where Anaconda is running.

    :param options: command line/boot options
    """
    verdesc = "%s for %s %s" % (get_anaconda_version_string(),
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
        if options.display_mode == constants.DISPLAY_MODE_TUI:
            print(text_mode_note)
        print(separate_attachements_note)
