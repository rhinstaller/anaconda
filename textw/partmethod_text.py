#
# partmethod_text.py: allows the user to choose how to partition their disks
# in text mode
#
# Jeremy Katz <katzj@redhat.com>
#
# Copyright 2001 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

from snack import *
from translate import _, cat, N_
from constants_text import *
from autopart import PARTMETHOD_TYPE_DESCR_TEXT

class PartitionMethod:
    def __call__(self, screen, partitions):
        rc = ButtonChoiceWindow(screen, _("Disk Partitioning Setup"),
                                PARTMETHOD_TYPE_DESCR_TEXT,
             [ (_("Autopartitioning"), "auto"), (_("Disk Druid"), "ds"),
                (_("fdisk"), "fd"), TEXT_BACK_BUTTON ],
               width = 50, help = "parttool")

        if rc == TEXT_BACK_CHECK:
            return INSTALL_BACK
        elif rc == "fd":
            partitions.useAutopartitioning = 0
            partitions.useFdisk = 1
        elif rc == "ds":
            partitions.useAutopartitioning = 0
            partitions.useFdisk = 0
        else:
            partitions.useAutopartitioning = 1
            partitions.useFdisk = 0

        return INSTALL_OK
