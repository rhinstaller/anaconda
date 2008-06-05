#
# partmethod_text.py: allows the user to choose how to partition their disks
# in text mode
#
# Copyright (C) 2001, 2002  Red Hat, Inc.  All rights reserved.
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
# Author(s): Jeremy Katz <katzj@redhat.com>
#

from snack import *
from constants_text import *
from autopart import PARTMETHOD_TYPE_DESCR_TEXT

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

class PartitionMethod:
    def __call__(self, screen, partitions, instclass):
        rc = ButtonChoiceWindow(screen, _("Disk Partitioning Setup"),
                               _(PARTMETHOD_TYPE_DESCR_TEXT),
                                [ (_("Autopartition"), "auto"),
                                  (_("Disk Druid"), "ds"),
                                  TEXT_BACK_BUTTON ],
                                width = 50, help = "parttool")

        if rc == TEXT_BACK_CHECK:
            return INSTALL_BACK
	elif rc == "ds":
	    partitions.useAutopartitioning = 0
        else:
            partitions.useAutopartitioning = 1

        return INSTALL_OK
