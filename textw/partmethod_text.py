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

class PartitionMethod:
    def __call__(self, screen, id):
        rc = ButtonChoiceWindow(screen, _("Disk Setup"),
             _("Autopartitioning sets up your partitioning in a reasonable "
               "way depending on your installation type and then gives you a "
               "chance to customize this setup.\n"
               "\n"
               "Disk Shaman is a tool designed for partitioning and setting "
               "up mount points.  It is designed to be easier to use than "
               "Linux's traditional disk partitioning software, fdisk, as "
               "well as more powerful.  However, there are some cases where "
               "fdisk may be preferred.\n"
               "\n"
               "Which tool would you like to use?"),
             [ (_("Autopartitioning"), "auto"), (_("Disk Shaman"), "ds"),
                (_("fdisk"), "fd"), TEXT_BACK_BUTTON ],
               width = 50, help = "parttool")

        if rc == TEXT_BACK_CHECK:
            return INSTALL_BACK
        elif rc == "fd":
            id.useAutopartitioning = 0
            id.useFdisk = 1
        elif rc == "ds":
            id.useAutopartitioning = 0
            id.useFdisk = 0
        else:
            id.useAutopartitioning = 1
            id.useFdisk = 0

        return INSTALL_OK
