# lvm.py - lvm probing control
#
# Jeremy Katz <katzj@redhat.com>
#
# Copyright 2002 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# general public license.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import iutil
import os,sys
import string

output = "/tmp/lvmout"

def vgscan():
    """Runs vgscan."""

    rc = iutil.execWithRedirect("/usr/sbin/vgscan",
                                ["vgscan", "-v"],
                                stdout = output,
                                stderr = output,
                                searchPath = 1)
    if rc:
        raise SystemError, "vgscan failed"

def vgactivate(volgroup = None):
    """Activate volume groups by running vgchange -ay.

    volgroup - optional single volume group to activate
    """

    args = ["/usr/sbin/vgchange", "-ay"]
    if volgroup:
        args.append(volgroup)
    rc = iutil.execWithRedirect(args[0], args,
                                stdout = output,
                                stderr = output,
                                searchPath = 1)
    if rc:
        raise SystemError, "vgchange failed"

def vgdeactivate(volgroup = None):
    """Deactivate volume groups by running vgchange -an.

    volgroup - optional single volume group to deactivate
    """

    args = ["/usr/sbin/vgchange", "-an"]
    if volgroup:
        args.append(volgroup)
    rc = iutil.execWithRedirect(args[0], args,
                                stdout = output,
                                stderr = output,
                                searchPath = 1)
    if rc:
        raise SystemError, "vgchange failed"
    
    
def lvremove(lvname, vgname):
    """Removes a logical volume.

    lvname - name of logical volume to remove.
    vgname - name of volume group lv is in.
    """

    args = ["/usr/sbin/lvremove", "-f"]
    dev = "/dev/%s/%s" %(vgname, lvname)
    args.append(dev)

    rc = iutil.execWithRedirect(args[0], args,
                                stdout = output,
                                stderr = output,
                                searchPath = 1)
    if rc:
        raise SystemError, "lvremove failed"


def vgremove(vgname):
    """Removes a volume group.  Deactivates the volume group first

    vgname - name of volume group.
    """

    # we'll try to deactivate... if it fails, we'll probably fail on
    # the removal too... but it's worth a shot
    try:
        vgdeactivate(vgname)
    except:
        pass

    args = ["/usr/sbin/vgremove", vgname]

    rc = iutil.execWithRedirect(args[0], args,
                                stdout = output,
                                stderr = output,
                                searchPath = 1)
    if rc:
        raise SystemError, "vgremove failed"
