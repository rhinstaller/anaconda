# install.py
# Do the hard work of performing an installation.
#
# Copyright (C) 2012  Red Hat, Inc.
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
# Red Hat Author(s): Chris Lumens <clumens@redhat.com>
#

from pyanaconda.errors import errorHandler
from pyanaconda.storage import turnOnFilesystems

def doInstall(storage, payload, ksdata, instClass):
    """Perform an installation.  This method takes the ksdata as prepared by
       the UI (the first hub, in graphical mode) and applies it to the disk.
       The two main tasks for this are putting filesystems onto disks and
       installing packages onto those filesystems.
    """
    from pyanaconda import progress

    # First, run all the execute methods of the ksdata.
    ksdata.bootloader.execute(storage, ksdata, instClass)
    ksdata.autopart.execute(storage, ksdata, instClass)

    # We really only care about actions that affect filesystems, since
    # those are the ones that take the most time.
    steps = len(storage.devicetree.findActions(type="create", object="format")) + \
            len(storage.devicetree.findActions(type="resize", object="format")) + \
            len(storage.devicetree.findActions(type="migrate", object="format"))
    progress.send_init(steps)

    # Do partitioning.
    turnOnFilesystems(storage, errorHandler)

    # Do packaging.
    payload.preInstall()
    payload.install()
    payload.postInstall()

    progress.send_complete()
