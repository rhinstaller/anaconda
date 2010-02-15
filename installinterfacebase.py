#
# installinterfacebase.py: a baseclass for anaconda interface classes
#
# Copyright (C) 2010  Red Hat, Inc.  All rights reserved.
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
# Author(s): Hans de Goede <hdegoede@redhat.com>

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)
P_ = lambda x, y, z: gettext.ldngettext("anaconda", x, y, z)

class InstallInterfaceBase(object):
    def __init__(self):
        self._warnedUnusedRaidMembers = []

    def messageWindow(self, title, text, type="ok", default = None,
             custom_buttons=None,  custom_icon=None):
        raise NotImplementedError

    def unusedRaidMembersWarning(self, unusedRaidMembers):
        """Warn about unused BIOS RAID members"""
        unusedRaidMembers = \
            filter(lambda m: m not in self._warnedUnusedRaidMembers,
                   unusedRaidMembers)
        if unusedRaidMembers:
            self._warnedUnusedRaidMembers.extend(unusedRaidMembers)
            unusedRaidMembers.sort()
            self.messageWindow(_("Warning"),
                P_("Disk %s contains BIOS RAID metadata, but is not part of "
                   "any recognized BIOS RAID sets. Ignoring disk %s." %
                   (", ".join(unusedRaidMembers),
                    ", ".join(unusedRaidMembers)),
                   "Disks %s contain BIOS RAID metadata, but are not part of "
                   "any recognized BIOS RAID sets. Ignoring disks %s." %
                   (", ".join(unusedRaidMembers),
                    ", ".join(unusedRaidMembers)),
                   len(unusedRaidMembers)),
                custom_icon="warning")
