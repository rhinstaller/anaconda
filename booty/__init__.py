#
# bootloader.py - generic boot loader handling backend for up2date and anaconda
#
# Jeremy Katz <katzj@redhat.com>
# Adrian Likins <alikins@redhat.com>
# Peter Jones <pjones@redhat.com>
#
# Copyright 2001-2005 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
"""Module for manipulation and creation of boot loader configurations"""

import rhpl
from bootloaderInfo import *

# return instance of the appropriate bootloader for our arch
def getBootloader():
    """Get the bootloader info object for your architecture"""
    if rhpl.getArch() == 'i386':
        import x86
        return x86.x86BootloaderInfo()
    elif rhpl.getArch() == 'ia64':
        import ia64
        return ia64.ia64BootloaderInfo()
    elif rhpl.getArch() == 's390' or rhpl.getArch() == "s390x":
        import s390
        return s390.s390BootloaderInfo()
    elif rhpl.getArch() == "alpha":
        import alpha
        return alpha.alphaBootloaderInfo()
    elif rhpl.getArch() == "x86_64":
        import x86
        return x86.x86BootloaderInfo()
    elif rhpl.getArch() == "ppc":
        import pcc
        return ppc.ppcBootloaderInfo()
    elif rhpl.getArch() == "sparc":
        import sparc
        return sparc.sparcBootloaderInfo()
    else:
        return bootloaderInfo()
