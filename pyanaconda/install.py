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

from blivet import callbacks
from blivet.osinstall import turn_on_filesystems
from blivet.devices import BTRFSDevice
from pyanaconda.bootloader import writeBootLoader
from pyanaconda.progress import progress_report, progress_message, progress_step, progress_complete, progress_init
from pyanaconda.users import Users
from pyanaconda import flags
from pyanaconda import iutil
from pyanaconda import timezone
from pyanaconda import network
from pyanaconda import screen_access
from pyanaconda.i18n import N_
from pyanaconda.threads import threadMgr
from pyanaconda.ui.lib.entropy import wait_for_entropy
from pyanaconda.kickstart import runPostScripts, runPreInstallScripts
from pyanaconda.kexec import setup_kexec
import logging
log = logging.getLogger("anaconda")

def _writeKS(ksdata):
    path = iutil.getSysroot() + "/root/anaconda-ks.cfg"

    # Clear out certain sensitive information that kickstart doesn't have a
    # way of representing encrypted.
    for obj in [ksdata.autopart] + ksdata.logvol.dataList() + \
               ksdata.partition.dataList() + ksdata.raid.dataList():
        obj.passphrase = ""

    # Make it so only root can read - could have passwords
    with iutil.open_with_perm(path, "w", 0o600) as f:
        f.write(str(ksdata))

def doConfiguration(storage, payload, ksdata, instClass):
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
    with progress_report(N_("Configuring installed system")):
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
        with progress_report(N_("Writing network configuration")):
            ksdata.network.execute(storage, ksdata, instClass)

    # Creating users and groups requires some pre-configuration.
    with progress_report(N_("Creating users")):
        u = Users()
        ksdata.rootpw.execute(storage, ksdata, instClass, u)
        ksdata.group.execute(storage, ksdata, instClass, u)
        ksdata.user.execute(storage, ksdata, instClass, u)
        ksdata.sshkey.execute(storage, ksdata, instClass, u)

    with progress_report(N_("Configuring addons")):
        ksdata.addons.execute(storage, ksdata, instClass, u, payload)

    with progress_report(N_("Generating initramfs")):
        payload.recreateInitrds()

    # This works around 2 problems, /boot on BTRFS and BTRFS installations where the initrd is
    # recreated after the first writeBootLoader call. This reruns it after the new initrd has
    # been created, fixing the kernel root and subvol args and adding the missing initrd entry.
    boot_on_btrfs = isinstance(storage.mountpoints.get("/"), BTRFSDevice)
    if flags.flags.livecdInstall and boot_on_btrfs \
                                 and (not ksdata.bootloader.disabled and ksdata.bootloader != "none"):
        writeBootLoader(storage, payload, instClass, ksdata)

    if willRunRealmd:
        with progress_report(N_("Joining realm: %s") % ksdata.realm.discovered):
            ksdata.realm.execute(storage, ksdata, instClass)

    with progress_report(N_("Running post-installation scripts")):
        runPostScripts(ksdata.scripts)

    # setup kexec reboot if requested
    if flags.flags.kexec:
        setup_kexec()

    # Write the kickstart file to the installed system (or, copy the input
    # kickstart file over if one exists).
    if flags.flags.nosave_output_ks:
        # don't write the kickstart file to the installed system if this has
        # been disabled by the nosave option
        log.warning("Writing of the output kickstart to installed system has been disabled"
                    " by the nosave option.")
    else:
        _writeKS(ksdata)

    # Write out the user interaction config file.
    #
    # But make sure it's not written out in the image and directory installation mode,
    # as that might result in spokes being inadvertedly hidden when the actual installation
    # startes from the generate image or directory contents.
    if flags.flags.imageInstall:
        log.info("Not writing out user interaction config file due to image install mode.")
    elif flags.flags.dirInstall:
        log.info("Not writing out user interaction config file due to directory install mode.")
    else:
        screen_access.sam.write_out_config_file()

    progress_complete()

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
    steps = len(storage.devicetree.actions.find(action_type="create", object_type="format")) + \
            len(storage.devicetree.actions.find(action_type="resize", object_type="format"))

    # Update every 10% of packages installed.  We don't know how many packages
    # we are installing until it's too late (see realmd later on) so this is
    # the best we can do.
    steps += 11

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

        with progress_report(N_("Waiting for %s threads to finish") % (threadMgr.running-1)):
            for message in ("Thread %s is running" % n for n in threadMgr.names):
                log.debug(message)
            threadMgr.wait_all()
    else:
        progress_init(steps)

    with progress_report(N_("Setting up the installation environment")):
        ksdata.firstboot.setup(storage, ksdata, instClass)
        ksdata.addons.setup(storage, ksdata, instClass, payload)

    storage.update_ksdata()  # this puts custom storage info into ksdata

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

    turn_on_filesystems(storage, mount_only=flags.flags.dirInstall, callbacks=callbacks_reg)
    payload.writeStorageEarly()

    # Run %pre-install scripts with the filesystem mounted and no packages
    with progress_report(N_("Running pre-installation scripts")):
        runPreInstallScripts(ksdata.scripts)

    # Do packaging.

    # Discover information about realms to join,
    # to determine additional packages
    if willRunRealmd:
        with progress_report(N_("Discovering realm to join")):
            ksdata.realm.setup()

    # Check for additional packages
    ksdata.authconfig.setup()
    ksdata.firewall.setup()
    ksdata.network.setup()
    # Setup timezone and add chrony as package if timezone was set in KS
    # and "-chrony" wasn't in packages section and/or --nontp wasn't set.
    ksdata.timezone.setup(ksdata)

    # make name resolution work for rpm scripts in chroot
    if flags.can_touch_runtime_system("copy /etc/resolv.conf to sysroot"):
        network.copyFileToPath("/etc/resolv.conf", iutil.getSysroot())

    # anaconda requires storage packages in order to make sure the target
    # system is bootable and configurable, and some other packages in order
    # to finish setting up the system.
    packages = storage.packages + ksdata.realm.packages
    packages += ksdata.authconfig.packages + ksdata.firewall.packages + ksdata.network.packages

    if willInstallBootloader:
        packages += storage.bootloader.packages

    # don't try to install packages from the install class' ignored list and the
    # explicitly excluded ones (user takes the responsibility)
    packages = [p for p in packages
                if p not in instClass.ignoredPackages and p not in ksdata.packages.excludedList]
    payload.preInstall(packages=packages, groups=payload.languageGroups())
    payload.install()

    payload.writeStorageLate()

    # Do bootloader.
    if willInstallBootloader:
        with progress_report(N_("Installing boot loader")):
            writeBootLoader(storage, payload, instClass, ksdata)

    with progress_report(N_("Performing post-installation setup tasks")):
        payload.postInstall()

    progress_complete()
