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

from pyanaconda.constants import ROOT_PATH
from blivet import turnOnFilesystems
from pyanaconda.bootloader import writeBootLoader
from pyanaconda.progress import progress_report, progressQ
from pyanaconda.users import createLuserConf, getPassAlgo, Users
from pyanaconda import flags
from pyanaconda import timezone
from pyanaconda.i18n import _
from pyanaconda.threads import threadMgr
import logging
log = logging.getLogger("anaconda")

def _writeKS(ksdata):
    import os

    path = ROOT_PATH + "/root/anaconda-ks.cfg"

    # Clear out certain sensitive information that kickstart doesn't have a
    # way of representing encrypted.
    for obj in [ksdata.autopart] + ksdata.logvol.dataList() + \
               ksdata.partition.dataList() + ksdata.raid.dataList():
        obj.passphrase = ""

    with open(path, "w") as f:
        f.write(str(ksdata))

    # Make it so only root can read - could have passwords
    os.chmod(path, 0600)

def doConfiguration(storage, payload, ksdata, instClass):
    from pyanaconda.kickstart import runPostScripts

    step_count = 6
    # if a realm was discovered,
    # increment the counter as the
    # real joining step will be executed
    if ksdata.realm.discovered:
        step_count += 1
    progressQ.send_init(step_count)

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

    if not flags.flags.imageInstall and not flags.flags.dirInstall:
        with progress_report(_("Writing network configuration")):
            ksdata.network.execute(storage, ksdata, instClass)

    # Creating users and groups requires some pre-configuration.
    with progress_report(_("Creating users")):
        createLuserConf(ROOT_PATH, algoname=getPassAlgo(ksdata.authconfig.authconfig))
        u = Users()
        ksdata.rootpw.execute(storage, ksdata, instClass, u)
        ksdata.group.execute(storage, ksdata, instClass, u)
        ksdata.user.execute(storage, ksdata, instClass, u)

    with progress_report(_("Configuring addons")):
        ksdata.addons.execute(storage, ksdata, instClass, u)
        ksdata.configured_spokes.execute(storage, ksdata, instClass, u)

    with progress_report(_("Generating initramfs")):
        payload.recreateInitrds(force=True)

    if ksdata.realm.discovered:
        with progress_report(_("Joining realm: %s") % ksdata.realm.discovered):
            ksdata.realm.execute(storage, ksdata, instClass)

    with progress_report(_("Running post-installation scripts")):
        runPostScripts(ksdata.scripts)

    # Write the kickstart file to the installed system (or, copy the input
    # kickstart file over if one exists).
    _writeKS(ksdata)

    progressQ.send_complete()

def doInstall(storage, payload, ksdata, instClass):
    """Perform an installation.  This method takes the ksdata as prepared by
       the UI (the first hub, in graphical mode) and applies it to the disk.
       The two main tasks for this are putting filesystems onto disks and
       installing packages onto those filesystems.
    """
    # First save system time to HW clock.
    if flags.can_touch_runtime_system("save system time to HW clock"):
        timezone.save_hw_clock(ksdata.timezone)

    # We really only care about actions that affect filesystems, since
    # those are the ones that take the most time.
    steps = len(storage.devicetree.findActions(type="create", object="format")) + \
            len(storage.devicetree.findActions(type="resize", object="format"))
    steps += 6
    # pre setup phase, packages setup, packages, bootloader, realmd,
    # post install
    progressQ.send_init(steps)

    # This should be the only thread running, wait for the others to finish if not.
    if threadMgr.running > 1:
        with progress_report(_("Waiting for %s threads to finish") % (threadMgr.running-1)):
            map(log.debug, ("Thread %s is running" % n for n in threadMgr.names))
            threadMgr.wait_all()

    with progress_report(_("Setting up the installation environment")):
        ksdata.firstboot.setup(storage, ksdata, instClass)
        ksdata.addons.setup(storage, ksdata, instClass)

    storage.updateKSData()  # this puts custom storage info into ksdata

    # Do partitioning.
    payload.preStorage()

    turnOnFilesystems(storage, mountOnly=flags.flags.dirInstall)
    if not flags.flags.livecdInstall and not flags.flags.dirInstall:
        storage.write()

    # Do packaging.

    # Discover information about realms to join,
    # to determine additional packages
    if ksdata.realm.join_realm:
        with progress_report(_("Discovering realm to join")):
            ksdata.realm.setup()

    # anaconda requires storage packages in order to make sure the target
    # system is bootable and configurable, and some other packages in order
    # to finish setting up the system.
    packages = storage.packages + ["authconfig", "firewalld"] + ksdata.realm.packages

    # don't try to install packages from the install class' ignored list
    packages = [p for p in packages if p not in instClass.ignoredPackages]
    payload.preInstall(packages=packages, groups=payload.languageGroups())
    payload.install()

    if flags.flags.livecdInstall:
        storage.write()

    with progress_report(_("Performing post-installation setup tasks")):
        payload.postInstall()

    # Do bootloader.
    if not flags.flags.dirInstall:
        with progress_report(_("Installing bootloader")):
            writeBootLoader(storage, payload, instClass, ksdata)

    progressQ.send_complete()
