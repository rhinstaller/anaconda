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

from pyanaconda import iutil
from pyanaconda import product
from pyanaconda import constants
from pyanaconda.flags import flags

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
