# User interface library functions for the completeness of modules
#
# Copyright (C) 2026  Red Hat, Inc.
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
from pyanaconda.modules.common.constants.completeness import IncompletenessKind
from pyanaconda.modules.common.structures.completeness import IncompletenessReason

__all__ = [
    "get_incompleteness",
    "get_incompleteness_message",
    "is_module_busy",
]


def get_incompleteness(module_proxy):
    """Get the reasons why a module is not ready to install.

    :param module_proxy: a DBus proxy of a kickstart module
    :return: a list of IncompletenessReason
    """
    return IncompletenessReason.from_structure_list(module_proxy.Incompleteness)


def is_module_busy(module_proxy):
    """Is the module incomplete only because it is still working?

    Lets a client show that waiting will resolve the situation, instead
    of telling a user to go and fix something that is about to fix
    itself.

    :param module_proxy: a DBus proxy of a kickstart module
    :return: True if the module is incomplete and all its reasons are transient
    """
    reasons = get_incompleteness(module_proxy)
    return bool(reasons) and all(r.kind == IncompletenessKind.BUSY for r in reasons)


def get_incompleteness_message(module_proxy):
    """Get a message explaining why a module is not ready to install.

    :param module_proxy: a DBus proxy of a kickstart module
    :return: a translated message, or an empty string if the module is complete
    """
    reasons = get_incompleteness(module_proxy)

    if not reasons:
        return ""

    return reasons[0].message
