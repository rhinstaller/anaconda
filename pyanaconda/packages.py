#
# packages.py: package management - mainly package installation
#
# Copyright (C) 2001, 2002, 2003, 2004, 2005, 2006  Red Hat, Inc.
# All rights reserved.
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
# Author(s): Erik Troan <ewt@redhat.com>
#            Matt Wilson <msw@redhat.com>
#            Michael Fulbright <msf@redhat.com>
#            Jeremy Katz <katzj@redhat.com>
#

import iutil
import os
import sys
import shutil
from flags import flags
from constants import *

import logging
log = logging.getLogger("anaconda")

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

def doPostAction(anaconda):
    anaconda.instClass.postAction(anaconda)

def setupTimezone(anaconda):
    # we don't need this on an upgrade or going backwards
    if anaconda.upgrade or flags.imageInstall or anaconda.dir == DISPATCH_BACK:
        return

    os.environ["TZ"] = anaconda.ksdata.timezone.timezone
    tzfile = "/usr/share/zoneinfo/" + anaconda.ksdata.timezone.timezone
    tzlocalfile = "/etc/localtime"
    if not os.access(tzfile, os.R_OK):
        log.error("unable to set timezone")
    else:
        try:
            os.remove(tzlocalfile)
        except OSError:
            pass
        try:
            shutil.copyfile(tzfile, tzlocalfile)
        except OSError as e:
            log.error("Error copying timezone (from %s): %s" %(tzfile, e.strerror))

    if iutil.isS390():
        return
    args = [ "--hctosys" ]
    if anaconda.ksdata.timezone.isUtc:
        args.append("-u")

    try:
        iutil.execWithRedirect("/sbin/hwclock", args, stdin = None,
                               stdout = "/dev/tty5", stderr = "/dev/tty5")
    except RuntimeError:
        log.error("Failed to set clock")

# FIXME: using rpm directly here is kind of lame, but in the yum backend
# we don't want to use the metadata as the info we need would require
# the filelists.  and since we only ever call this after an install is
# done, we can be guaranteed this will work.  put here because it's also
# used for livecd installs
def rpmKernelVersionList():
    import rpm

    def get_version(header):
        for f in header['filenames']:
            if f.startswith('/boot/vmlinuz-'):
                return f[14:]
            elif f.startswith('/boot/efi/EFI/redhat/vmlinuz-'):
                return f[29:]
        return ""

    def get_tag(header):
        if header['name'] == "kernel":
            return "base"
        elif header['name'].startswith("kernel-"):
            return header['name'][7:]
        return ""

    versions = []

    iutil.resetRpmDb()
    ts = rpm.TransactionSet(ROOT_PATH)

    mi = ts.dbMatch('provides', 'kernel')
    for h in mi:
        v = get_version(h)
        tag = get_tag(h)
        if v == "" or tag == "":
            log.warning("Unable to determine kernel type/version for %s-%s-%s.%s" %(h['name'], h['version'], h['release'], h['arch'])) 
            continue
        # rpm really shouldn't return the same kernel more than once... but
        # sometimes it does (#467822)
        if (v, h['arch'], tag) in versions:
            continue
        versions.append( (v, h['arch'], tag) )

    return versions

def rpmSetupGraphicalSystem(anaconda):
    import rpm

    iutil.resetRpmDb()
    ts = rpm.TransactionSet(ROOT_PATH)

    # Only add "rhgb quiet" on non-s390, non-serial installs
    if iutil.isConsoleOnVirtualTerminal() and \
       (ts.dbMatch('provides', 'rhgb').count() or \
        ts.dbMatch('provides', 'plymouth').count()):
        anaconda.bootloader.boot_args.update(["rhgb", "quiet"])

    if ts.dbMatch('provides', 'service(graphical-login)').count() and \
       ts.dbMatch('provides', 'xorg-x11-server-Xorg').count() and \
       anaconda.displayMode == 'g' and not flags.usevnc:
        anaconda.desktop.setDefaultRunLevel(5)

#Recreate initrd for use when driver disks add modules
def recreateInitrd (kernelTag, instRoot):
    log.info("recreating initrd for %s" % (kernelTag,))
    iutil.execWithRedirect("/sbin/new-kernel-pkg",
                           [ "--mkinitrd", "--dracut", "--depmod", "--install", kernelTag ],
                           stdout = "/dev/null", stderr = "/dev/null",
                           root = instRoot)

def doReIPL(anaconda):
    if not iutil.isS390() or anaconda.dir == DISPATCH_BACK:
        return DISPATCH_DEFAULT

    anaconda.reIPLMessage = iutil.reIPL(anaconda, os.getppid())

    return DISPATCH_FORWARD
