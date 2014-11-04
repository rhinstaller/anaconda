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

from blivet import turnOnFilesystems, callbacks
from pyanaconda.bootloader import writeBootLoader
from pyanaconda.progress import progress_report, progress_message, progress_step, progress_complete, progress_init
from pyanaconda.users import createLuserConf, getPassAlgo, Users
from pyanaconda import flags
from pyanaconda import iutil
from pyanaconda import timezone
from pyanaconda.i18n import _
from pyanaconda.threads import threadMgr
from pyanaconda.ui.lib.entropy import wait_for_entropy
import logging
import blivet
log = logging.getLogger("anaconda")

def _writeKS(ksdata):
    import os

    path = iutil.getSysroot() + "/root/anaconda-ks.cfg"

    # Clear out certain sensitive information that kickstart doesn't have a
    # way of representing encrypted.
    for obj in [ksdata.autopart] + ksdata.logvol.dataList() + \
               ksdata.partition.dataList() + ksdata.raid.dataList():
        obj.passphrase = ""

    with open(path, "w") as f:
        f.write(str(ksdata))

    # Make it so only root can read - could have passwords
    iutil.eintr_retry_call(os.chmod, path, 0o600)

def doConfiguration(storage, payload, ksdata, instClass):
    from pyanaconda.kickstart import runPostScripts

    willWriteNetwork = not flags.flags.imageInstall and not flags.flags.dirInstall
    willRunRealmd = ksdata.realm.discovered

    # configure base, create users, configure addons, initramfs, post-install
    step_count = 5

    # network, maybe
    if willWriteNetwork:
        step_count += 1

    # if a realm was discovered,
    # increment the counter as the
    # real joining step will be executed
    if willRunRealmd:
        step_count += 1

    progress_init(step_count)

    # Now run the execute methods of ksdata that require an installed system
    # to be present first.
    with progress_report(_("Configuring installed system")):
        ksdata.authconfig.execute(storage, ksdata, instClass)
        ksdata.selinux.execute(storage, ksdata, instClass)
        ksdata.firstboot.execute(storage, ksdata, instClass)
        ksdata.services.execute(storage, ksdata, instClass)
        ksdata.keyboard.execute(storage, ksdata, instClass)
        ksdata.timezone.execute(storage, ksdata, instClass)
        ksdata.lang.execute(storage, ksdata, instClass)
        ksdata.firewall.execute(storage, ksdata, instClass)
        ksdata.xconfig.execute(storage, ksdata, instClass)
        ksdata.skipx.execute(storage, ksdata, instClass)

    if willWriteNetwork:
        with progress_report(_("Writing network configuration")):
            ksdata.network.execute(storage, ksdata, instClass)

    # Creating users and groups requires some pre-configuration.
    with progress_report(_("Creating users")):
        createLuserConf(iutil.getSysroot(), algoname=getPassAlgo(ksdata.authconfig.authconfig))
        u = Users()
        ksdata.rootpw.execute(storage, ksdata, instClass, u)
        ksdata.group.execute(storage, ksdata, instClass, u)
        ksdata.user.execute(storage, ksdata, instClass, u)

    with progress_report(_("Configuring addons")):
        ksdata.addons.execute(storage, ksdata, instClass, u)

    with progress_report(_("Generating initramfs")):
        payload.recreateInitrds(force=True)

    if willRunRealmd:
        with progress_report(_("Joining realm: %s") % ksdata.realm.discovered):
            ksdata.realm.execute(storage, ksdata, instClass)

    with progress_report(_("Running post-installation scripts")):
        runPostScripts(ksdata.scripts)

    # Write the kickstart file to the installed system (or, copy the input
    # kickstart file over if one exists).
    _writeKS(ksdata)

    progress_complete()

def moveBootMntToPhysical(storage):
    """Move the /boot mount to /mnt/sysimage/boot."""
    if iutil.getSysroot() == iutil.getTargetPhysicalRoot():
        return
    bootmnt = storage.mountpoints.get('/boot')
    if bootmnt is None:
        return
    bootmnt.format.teardown()
    bootmnt.teardown()
    bootmnt.format.setup(options=bootmnt.format.options, chroot=iutil.getTargetPhysicalRoot())

def doInstall(storage, payload, ksdata, instClass):
    """Perform an installation.  This method takes the ksdata as prepared by
       the UI (the first hub, in graphical mode) and applies it to the disk.
       The two main tasks for this are putting filesystems onto disks and
       installing packages onto those filesystems.
    """
    willRunRealmd = ksdata.realm.join_realm
    willInstallBootloader = not flags.flags.dirInstall and (not ksdata.bootloader.disabled
                                                            and ksdata.bootloader != "none")

    # First save system time to HW clock.
    if flags.can_touch_runtime_system("save system time to HW clock"):
        timezone.save_hw_clock(ksdata.timezone)

    # We really only care about actions that affect filesystems, since
    # those are the ones that take the most time.
    steps = len(storage.devicetree.findActions(action_type="create", object_type="format")) + \
            len(storage.devicetree.findActions(action_type="resize", object_type="format"))

    # pre setup phase, post install
    steps += 2

    # realmd, maybe
    if willRunRealmd:
        steps += 1

    # bootloader, maybe
    if willInstallBootloader:
        steps += 1

    # This should be the only thread running, wait for the others to finish if not.
    if threadMgr.running > 1:
        progress_init(steps+1)

        with progress_report(_("Waiting for %s threads to finish") % (threadMgr.running-1)):
            map(log.debug, ("Thread %s is running" % n for n in threadMgr.names))
            threadMgr.wait_all()
    else:
        progress_init(steps)

    with progress_report(_("Setting up the installation environment")):
        ksdata.firstboot.setup(storage, ksdata, instClass)
        ksdata.addons.setup(storage, ksdata, instClass)

    storage.updateKSData()  # this puts custom storage info into ksdata

    # Do partitioning.
    payload.preStorage()

    # callbacks for blivet
    message_clbk = lambda clbk_data: progress_message(clbk_data.msg)
    step_clbk = lambda clbk_data: progress_step(clbk_data.msg)
    entropy_wait_clbk = lambda clbk_data: wait_for_entropy(clbk_data.msg,
                                                           clbk_data.min_entropy, ksdata)
    callbacks_reg = callbacks.create_new_callbacks_register(create_format_pre=message_clbk,
                                                            create_format_post=step_clbk,
                                                            resize_format_pre=message_clbk,
                                                            resize_format_post=step_clbk,
                                                            wait_for_entropy=entropy_wait_clbk)

    turnOnFilesystems(storage, mountOnly=flags.flags.dirInstall, callbacks=callbacks_reg)
    write_storage_late = (flags.flags.livecdInstall or ksdata.ostreesetup.seen
                          or ksdata.method.method == "liveimg"
                          and not flags.flags.dirInstall)
    if not write_storage_late:
        storage.write()

    # Do packaging.

    # Discover information about realms to join,
    # to determine additional packages
    if willRunRealmd:
        with progress_report(_("Discovering realm to join")):
            ksdata.realm.setup()

    # Check for additional packages
    ksdata.authconfig.setup()
    ksdata.firewall.setup()

    # anaconda requires storage packages in order to make sure the target
    # system is bootable and configurable, and some other packages in order
    # to finish setting up the system.
    packages = storage.packages + ksdata.realm.packages
    packages += ksdata.authconfig.packages + ksdata.firewall.packages

    if willInstallBootloader:
        packages += storage.bootloader.packages

    # don't try to install packages from the install class' ignored list and the
    # explicitly excluded ones (user takes the responsibility)
    packages = [p for p in packages
                if p not in instClass.ignoredPackages and p not in ksdata.packages.excludedList]
    payload.preInstall(packages=packages, groups=payload.languageGroups())
    payload.install()

    if write_storage_late:
        if iutil.getSysroot() != iutil.getTargetPhysicalRoot():
            blivet.setSysroot(iutil.getTargetPhysicalRoot(),
                              iutil.getSysroot())
            storage.write()

            # Now that we have the FS layout in the target, umount
            # things that were in the legacy sysroot, and put them in
            # the target root, except for the physical /.  First,
            # unmount all target filesystems.
            storage.umountFilesystems()

            # Explicitly mount the root on the physical sysroot
            rootmnt = storage.mountpoints.get('/')
            rootmnt.setup()
            rootmnt.format.setup(options=rootmnt.format.options, chroot=iutil.getTargetPhysicalRoot())

            payload.prepareMountTargets(storage)

            # Everything else goes in the target root, including /boot
            # since the bootloader code will expect to find /boot
            # inside the chroot.
            storage.mountFilesystems(skipRoot=True)
        else:
            storage.write()

    # Do bootloader.
    if willInstallBootloader:
        with progress_report(_("Installing bootloader")):
            writeBootLoader(storage, payload, instClass, ksdata)

    with progress_report(_("Performing post-installation setup tasks")):
        # Now, let's reset the state here so that the payload has
        # /boot in the system root.
        moveBootMntToPhysical(storage)
        payload.postInstall()

    progress_complete()
