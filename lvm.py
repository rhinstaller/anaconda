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

def vgscan():
    """Runs vgscan."""

    rc = iutil.execWithRedirect("/usr/sbin/vgscan",
                                ["vgscan", "-v"],
                                stdout = "/tmp/lvmout",
                                stderr = "/tmp/lvmout",
                                searchPath = 1)
    if rc:
        raise SystemError, "vgscan failed"

def vgactivate():
    """Activate volume groups by running vgchange -ay."""

    rc = iutil.execWithRedirect("/usr/sbin/vgchange",
                                ["vgchange", "-ay"],
                                stdout = "/tmp/lvmout",
                                stderr = "/tmp/lvmout",
                                searchPath = 1)
    if rc:
        raise SystemError, "vgchange failed"
    
    
