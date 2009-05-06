#
# partitioning.py: partitioning and other disk management
#
# Matt Wilson <msw@redhat.com>
# Jeremy Katz <katzj@redhat.com>
# Mike Fulbright <msf@redhat.com>
# Harald Hoyer <harald@redhat.de>
#
# Copyright 2001-2003 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import isys
import sys
import iutil
from constants import *
from flags import flags
from partErrors import *

from rhpl.translate import _

import logging
log = logging.getLogger("anaconda")

def partitionObjectsInitialize(anaconda):
    # shut down all dm devices
    anaconda.id.diskset.closeDevices()
    anaconda.id.diskset.stopMdRaid()
    anaconda.id.zfcp.shutdown()

    # clean slate about drives
    isys.flushDriveDict()

    if anaconda.dir == DISPATCH_BACK:
        return

    # ensure iscsi devs are up
    anaconda.id.iscsi.startup(anaconda.intf)

    # ensure zfcp devs are up
    anaconda.id.zfcp.startup()

    # pull in the new iscsi drive
    isys.flushDriveDict()

    # read in drive info
    anaconda.id.diskset.refreshDevices()

    anaconda.id.partitions.setFromDisk(anaconda.id.diskset)
    anaconda.id.partitions.setProtected(anaconda.dispatch)

    # make sure we have all the device nodes we'll want
    iutil.makeDriveDeviceNodes()

def partitioningComplete(anaconda):
    if anaconda.dir == DISPATCH_BACK and anaconda.id.fsset.isActive():
        rc = anaconda.intf.messageWindow(_("Installation cannot continue."),
                                _("The partitioning options you have chosen "
                                  "have already been activated. You can "
                                  "no longer return to the disk editing "
                                  "screen. Would you like to continue "
                                  "with the installation process?"),
                                type = "yesno")
        if rc == 0:
            sys.exit(0)
        return DISPATCH_FORWARD

    anaconda.id.partitions.sortRequests()
    anaconda.id.fsset.reset()
    undoEncryption = False
    partitions = anaconda.id.partitions
    preexist = partitions.hasPreexistingCryptoDev()
    for request in anaconda.id.partitions.requests:
        # XXX improve sanity checking
	if (not request.fstype or (request.fstype.isMountable()
	    and not request.mountpoint)):
	    continue

        # ensure that all newly encrypted devices have a passphrase
        if request.encryption and request.encryption.format:
            if anaconda.isKickstart and request.encryption.passphrase:
                # they set a passphrase for this device explicitly
                pass
            elif partitions.encryptionPassphrase:
                request.encryption.setPassphrase(partitions.encryptionPassphrase)
            elif undoEncryption:
                request.encryption = None
                if request.dev:
                    request.dev.crypto = None
            else:
                while True:
                    (passphrase, retrofit) = anaconda.intf.getLuksPassphrase(preexist=preexist)
                    if passphrase:
                        request.encryption.setPassphrase(passphrase)
                        partitions.encryptionPassphrase = passphrase
                        partitions.retrofitPassphrase = retrofit
                        break
                    else:
                        rc = anaconda.intf.messageWindow(_("Encrypt device?"),
                                    _("You specified block device encryption "
                                      "should be enabled, but you have not "
                                      "supplied a passphrase. If you do not "
                                      "go back and provide a passphrase, "
                                      "block device encryption will be "
                                      "disabled."),
                                      type="custom",
                                      custom_buttons=[_("Back"), _("Continue")],
                                      default=0)
                        if rc == 1:
                            log.info("user elected to not encrypt any devices.")
                            request.encryption = None
                            if request.dev:
                                request.dev.encryption = None
                            undoEncryption = True
                            partitions.autoEncrypt = False
                            break
	    
        entry = request.toEntry(anaconda.id.partitions)
        if entry:
            anaconda.id.fsset.add (entry)
        else:
            raise RuntimeError, ("Managed to not get an entry back from "
                                 "request.toEntry")

    if (not flags.setupFilesystems
        or iutil.memAvailable() > isys.EARLY_SWAP_RAM):
        return
    
    if not anaconda.isKickstart:
        rc = anaconda.intf.messageWindow(_("Low Memory"),
                            _("As you don't have much memory in this "
                              "machine, we need to turn on swap space "
                              "immediately. To do this we'll have to "
                              "write your new partition table to the disk "
                              "immediately. Is that OK?"), "yesno")
    else:
        rc = 1
        
    if rc:
        anaconda.id.partitions.doMetaDeletes(anaconda.id.diskset)        
        anaconda.id.fsset.setActive(anaconda.id.diskset)
        anaconda.id.diskset.savePartitions ()
        anaconda.id.fsset.createLogicalVolumes(anaconda.rootPath)        
        anaconda.id.fsset.formatSwap(anaconda.rootPath)
        anaconda.id.fsset.turnOnSwap(anaconda.rootPath)

    return
