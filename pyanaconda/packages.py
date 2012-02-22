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

import itertools
import glob
import iutil
import isys
import os
import time
import sys
import string
import language
import shutil
import traceback
from flags import flags
from product import *
from constants import *
from upgrade import bindMountDevDirectory
from storage.errors import *

import logging
log = logging.getLogger("anaconda")

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

def doPostAction(anaconda):
    anaconda.instClass.postAction(anaconda)

def firstbootConfiguration(anaconda):
    if anaconda.firstboot == FIRSTBOOT_RECONFIG:
        f = open(ROOT_PATH + '/etc/reconfigSys', 'w+')
        f.close()
    elif anaconda.firstboot == FIRSTBOOT_SKIP:
        f = open(ROOT_PATH + '/etc/sysconfig/firstboot', 'w+')
        f.write('RUN_FIRSTBOOT=NO')
        f.close()

    return

def writeKSConfiguration(anaconda):
    log.info("Writing autokickstart file")
    fn = ROOT_PATH + "/root/anaconda-ks.cfg"

    anaconda.writeKS(fn)

def turnOnFilesystems(anaconda):
    if anaconda.dir == DISPATCH_BACK:
        rc = anaconda.intf.messageWindow(_("Warning"),
                _("Filesystems have already been activated.  You "
                  "cannot go back past this point.\n\nWould you like to "
                  "continue with the installation?"),
                type="custom", custom_icon=["error","error"],
                custom_buttons=[_("_Exit installer"), _("_Continue")])

        if rc == 0:
            sys.exit(0)
        return DISPATCH_FORWARD

    if not anaconda.upgrade:
        if (flags.livecdInstall and
            not flags.imageInstall and
            not anaconda.storage.fsset.active):
            # turn off any swaps that we didn't turn on
            # needed for live installs
            iutil.execWithRedirect("swapoff", ["-a"],
                                   stdout = "/dev/tty5", stderr="/dev/tty5")
        anaconda.storage.devicetree.teardownAll()

    upgrade_migrate = False
    if anaconda.upgrade:
        for d in anaconda.storage.migratableDevices:
            if d.format.migrate:
                upgrade_migrate = True

    title = None
    message = None
    details = None

    try:
        anaconda.storage.doIt()
    except FSResizeError as (msg, device):
        title = _("Resizing Failed")
        message = _("There was an error encountered while "
                    "resizing the device %s.") % (device,)

        if os.path.exists("/tmp/resize.out"):
            details = open("/tmp/resize.out", "r").read()
        else:
            details = "%s" %(msg,)
    except FSMigrateError as (msg, device):
        title = _("Migration Failed")
        message = _("An error was encountered while "
                    "migrating filesystem on device %s.") % (device,)
        details = msg
    except Exception as e:
        raise

    if title:
        rc = anaconda.intf.detailedMessageWindow(title, message, details,
                        type = "custom",
                        custom_buttons = [_("_File Bug"), _("_Exit installer")])

        if rc == 0:
            raise
        elif rc == 1:
            sys.exit(1)

    if not anaconda.upgrade:
        anaconda.storage.turnOnSwap()
        anaconda.storage.mountFilesystems(raiseErrors=False,
                                          readOnly=False,
                                          skipRoot=anaconda.backend.skipFormatRoot)
    else:
        if upgrade_migrate:
            # we should write out a new fstab with the migrated fstype
            shutil.copyfile("%s/etc/fstab" % ROOT_PATH,
                            "%s/etc/fstab.anaconda" % ROOT_PATH)
            anaconda.storage.fsset.write()

        # and make sure /dev is mounted so we can read the bootloader
        bindMountDevDirectory(ROOT_PATH)


def setupTimezone(anaconda):
    # we don't need this on an upgrade or going backwards
    if anaconda.upgrade or flags.imageInstall or anaconda.dir == DISPATCH_BACK:
        return

    os.environ["TZ"] = anaconda.timezone.tz
    tzfile = "/usr/share/zoneinfo/" + anaconda.timezone.tz
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
    if anaconda.timezone.utc:
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

def betaNagScreen(anaconda):
    publicBetas = { "Red Hat Linux": "Red Hat Linux Public Beta",
                    "Red Hat Enterprise Linux": "Red Hat Enterprise Linux Public Beta",
                    "Fedora Core": "Fedora Core",
                    "Fedora": "Fedora" }


    if anaconda.dir == DISPATCH_BACK:
	return DISPATCH_DEFAULT

    fileagainst = None
    for (key, val) in publicBetas.items():
        if productName.startswith(key):
            fileagainst = val
    if fileagainst is None:
        fileagainst = "%s Beta" %(productName,)
    
    while 1:
	rc = anaconda.intf.messageWindow(_("Warning"),
				 _("Warning!  This is pre-release software!\n\n"
                                   "Thank you for downloading this "
				   "pre-release of %(productName)s.\n\n"
				   "This is not a final "
				   "release and is not intended for use "
				   "on production systems.  The purpose of "
				   "this release is to collect feedback "
				   "from testers, and it is not suitable "
				   "for day to day usage.\n\n"
				   "To report feedback, please visit:\n\n"
				   "   %(bugzillaUrl)s\n\n"
				   "and file a report against '%(fileagainst)s'.\n")
				 % {'productName': productName,
				    'bugzillaUrl': bugzillaUrl,
				    'fileagainst': fileagainst},
				   type="custom", custom_icon="warning",
				   custom_buttons=[_("_Exit"), _("_Install Anyway")])

	if not rc:
            msg =  _("Your system will now be rebooted...")
            buttons = [_("_Back"), _("_Reboot")]
	    rc = anaconda.intf.messageWindow( _("Warning! This is pre-release software!"),
                                     msg,
                                     type="custom", custom_icon="warning",
                                     custom_buttons=buttons)
	    if rc:
		sys.exit(0)
	else:
	    break

def doReIPL(anaconda):
    if not iutil.isS390() or anaconda.dir == DISPATCH_BACK:
        return DISPATCH_DEFAULT

    anaconda.reIPLMessage = iutil.reIPL(anaconda, os.getppid())

    return DISPATCH_FORWARD
