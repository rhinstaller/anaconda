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

import iutil
from bootloaderInfo import *
from bootloader import *

class BootyNoKernelWarning(Exception):
    def __init__ (self, value=""):
        self.value = value

    def __str__ (self):
        return self.value

# return instance of the appropriate bootloader for our arch
def getBootloader(anaconda):
    """Get the bootloader info object for your architecture"""
    if iutil.isX86():
        import x86
        return x86.x86BootloaderInfo(anaconda)
    elif iutil.isIA64():
        import ia64
        return ia64.ia64BootloaderInfo(anaconda)
    elif iutil.isS390():
        import s390
        return s390.s390BootloaderInfo(anaconda)
    elif iutil.isAlpha():
        import alpha
        return alpha.alphaBootloaderInfo(anaconda)
    elif iutil.isPPC():
        import ppc
        return ppc.ppcBootloaderInfo(anaconda)
    elif iutil.isSparc():
        import sparc
        return sparc.sparcBootloaderInfo(anaconda)
    else:
        return bootloaderInfo(anaconda)
