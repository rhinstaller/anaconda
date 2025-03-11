#
# Copyright (C) 2020  Red Hat, Inc.
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
from pyanaconda.core.i18n import P_, _


def check_disk_selection(storage, selected_disks):
    """Return a list of errors related to a proposed disk selection.

    :param storage: blivet.Blivet instance
    :param selected_disks: names of selected disks
    :type selected_disks: list of str
    :returns: a list of error messages
    :rtype: list of str
    """
    errors = []

    for disk_id in selected_disks:
        selected = storage.devicetree.get_device_by_device_id(disk_id, hidden=True)

        if not selected:
            errors.append(_("The selected disk {} is not recognized.").format(disk_id))
            continue

        related = sorted(storage.devicetree.get_related_disks(selected), key=lambda d: d.device_id)
        missing = [r for r in related if r.device_id not in selected_disks]

        if not missing:
            continue

        errors.append(P_(
            "You selected disk %(selected)s, which contains "
            "devices that also use unselected disk "
            "%(unselected)s. You must select or de-select "
            "these disks as a set.",
            "You selected disk %(selected)s, which contains "
            "devices that also use unselected disks "
            "%(unselected)s. You must select or de-select "
            "these disks as a set.",
            len(missing)) % {
            "selected": selected.name,
            "unselected": ", ".join([m.name for m in missing])
        })

    return errors
