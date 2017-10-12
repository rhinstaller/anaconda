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
from pyanaconda.progress import progress_message, progress_step, progress_complete, progress_init
from pyanaconda.users import Users
from pyanaconda import flags
from pyanaconda import iutil
from pyanaconda import timezone
from pyanaconda import network
from pyanaconda import screen_access
from pyanaconda.i18n import N_
from pyanaconda.threading import threadMgr
from pyanaconda.ui.lib.entropy import wait_for_entropy
from pyanaconda.kickstart import runPostScripts, runPreInstallScripts
from pyanaconda.kexec import setup_kexec
from pyanaconda.installation_tasks import Task, TaskQueue
from pykickstart.constants import SNAPSHOT_WHEN_POST_INSTALL

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

class WriteResolvConfTask(Task):
    """Custom task subclass for handling the resolv.conf copy task.

    The main reason is to resolve the sysroot path right before the
    copy operation, not at task & task queue creation time.

    Secondary reason is to demonstrate how a lightweight Task subclass can be used.
    """

    def do_run(self):
        """Resolve the sysroot path only right before doing the copy operatio.

        If we just added the sysroot path as an argument, it would be resolved when the
        task queue was created, not when the task is actually executed, which could
        theoretically result in an incorrect path.
        """
        network.copyFileToPath("/etc/resolv.conf", iutil.getSysroot())


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
    """Configure the installed system."""

    configuration_queue = TaskQueue("Configuration queue")
    # connect progress reporting
    configuration_queue.queue_started.connect(lambda x: progress_message(x.status_message))
    configuration_queue.queue_completed.connect(lambda x: progress_step("%s -- DONE" % x.status_message))

    # schedule the execute methods of ksdata that require an installed system to be present
    os_config = TaskQueue("Installed system configuration", N_("Configuring installed system"))
    os_config.append(Task("Configure authconfig", ksdata.authconfig.execute, (storage, ksdata, instClass)))
    os_config.append(Task("Configure SELinux", ksdata.selinux.execute, (storage, ksdata, instClass)))
    os_config.append(Task("Configure first boot tasks", ksdata.firstboot.execute, (storage, ksdata, instClass)))
    os_config.append(Task("Configure services", ksdata.services.execute, (storage, ksdata, instClass)))
    os_config.append(Task("Configure keyboard", ksdata.keyboard.execute, (storage, ksdata, instClass)))
    os_config.append(Task("Configure timezone", ksdata.timezone.execute, (storage, ksdata, instClass)))
    os_config.append(Task("Configure language", ksdata.lang.execute, (storage, ksdata, instClass)))
    os_config.append(Task("Configure firewall", ksdata.firewall.execute, (storage, ksdata, instClass)))
    os_config.append(Task("Configure X", ksdata.xconfig.execute, (storage, ksdata, instClass)))
    os_config.append(Task("Configure skip-X", ksdata.skipx.execute, (storage, ksdata, instClass)))
    configuration_queue.append(os_config)

    # schedule network configuration (if required)
    will_write_network = not flags.flags.imageInstall and not flags.flags.dirInstall
    if will_write_network:
        network_config = TaskQueue("Network configuration", N_("Writing network configuration"))
        network_config.append(Task("Network configuration",
                                   ksdata.network.execute, (storage, ksdata, instClass)))
        configuration_queue.append(network_config)

    # creating users and groups requires some pre-configuration.
    u = Users()
    user_config = TaskQueue("User creation", N_("Creating users"))
    user_config.append(Task("Configure root", ksdata.rootpw.execute, (storage, ksdata, instClass, u)))
    user_config.append(Task("Configure user groups", ksdata.group.execute, (storage, ksdata, instClass, u)))
    user_config.append(Task("Configure user", ksdata.user.execute, (storage, ksdata, instClass, u)))
    user_config.append(Task("Configure SSH key", ksdata.sshkey.execute, (storage, ksdata, instClass, u)))
    configuration_queue.append(user_config)

    # Anaconda addon configuration
    addon_config = TaskQueue("Anaconda addon configuration", N_("Configuring addons"))
    addon_config.append(Task("Configure Anaconda addons", ksdata.addons.execute, (storage, ksdata, instClass, u, payload)))
    configuration_queue.append(addon_config)

    # Initramfs generation
    generate_initramfs = TaskQueue("Initramfs generation", N_("Generating initramfs"))
    generate_initramfs.append(Task("Generate initramfs", payload.recreateInitrds))

    # This works around 2 problems, /boot on BTRFS and BTRFS installations where the initrd is
    # recreated after the first writeBootLoader call. This reruns it after the new initrd has
    # been created, fixing the kernel root and subvol args and adding the missing initrd entry.
    boot_on_btrfs = isinstance(storage.mountpoints.get("/"), BTRFSDevice)
    bootloader_enabled = not ksdata.bootloader.disabled and ksdata.bootloader != "none"
    if flags.flags.livecdInstall and boot_on_btrfs and bootloader_enabled:
        generate_initramfs.append(Task("Write BTRFS bootloader fix", writeBootLoader, (storage, payload, instClass, ksdata)))
    configuration_queue.append(generate_initramfs)

    # join a realm (if required)
    if ksdata.realm.discovered:
        join_realm = TaskQueue("Realm join", N_("Joining realm: %s") % ksdata.realm.discovered)
        join_realm.append(Task("Join a realm", ksdata.realm.execute, (storage, ksdata, instClass)))
        configuration_queue.append(join_realm)

    post_scripts = TaskQueue("Post installation scripts", N_("Running post-installation scripts"))
    post_scripts.append(Task("Run post installation scripts", runPostScripts, (ksdata.scripts,)))
    configuration_queue.append(post_scripts)

    # setup kexec reboot if requested
    if flags.flags.kexec:
        kexec_setup = TaskQueue("Kexec setup", N_("Setting up kexec"))
        kexec_setup.append(Task("Setup kexec", setup_kexec))
        configuration_queue.append(kexec_setup)

    # write anaconda related configs & kickstarts
    write_configs = TaskQueue("Write configs and kickstarts", N_("Storing configuration files and kickstarts"))

    # Write the kickstart file to the installed system (or, copy the input
    # kickstart file over if one exists).
    if flags.flags.nosave_output_ks:
        # don't write the kickstart file to the installed system if this has
        # been disabled by the nosave option
        log.warning("Writing of the output kickstart to installed system has been disabled"
                    " by the nosave option.")
    else:
       # write anaconda related configs & kickstarts
        write_configs.append(Task("Store kickstarts", _writeKS, (ksdata,)))

    # Write out the user interaction config file.
    #
    # But make sure it's not written out in the image and directory installation mode,
    # as that might result in spokes being inadvertently hidden when the actual installation
    # starts from the generate image or directory contents.
    if flags.flags.imageInstall:
        log.info("Not writing out user interaction config file due to image install mode.")
    elif flags.flags.dirInstall:
        log.info("Not writing out user interaction config file due to directory install mode.")
    else:
        write_configs.append(Task("Store user interaction config", screen_access.sam.write_out_config_file))

    # only add write_configs to the main queue if we actually store some kickstarts/configs
    if write_configs.task_count:
        configuration_queue.append(write_configs)

    # notify progress tracking about the number of steps
    progress_init(len(configuration_queue))
    # log contents of the main task queue
    log.info(configuration_queue.summary)

    # log tasks and queues when they are started
    # - note that we are using generators to add the counter
    queue_counter = iutil.item_counter(configuration_queue.queue_count)
    task_started_counter = iutil.item_counter(configuration_queue.task_count)
    task_completed_counter = iutil.item_counter(configuration_queue.task_count)
    configuration_queue.queue_started.connect(lambda x: log.info("Queue started: %s (%s)", x.name, next(queue_counter)))
    configuration_queue.task_started.connect(lambda x: log.info("Task started: %s (%s)", x.name, next(task_started_counter)))
    configuration_queue.task_completed.connect(lambda x: log.debug("Task completed: %s (%s) (%1.1f s)",
                                                                   x.name, next(task_completed_counter),
                                                                   x.elapsed_time))
    # start the task queue
    configuration_queue.start()
    # done
    progress_complete()

def doInstall(storage, payload, ksdata, instClass):
    """Perform an installation.  This method takes the ksdata as prepared by
       the UI (the first hub, in graphical mode) and applies it to the disk.
       The two main tasks for this are putting filesystems onto disks and
       installing packages onto those filesystems.
    """
    willInstallBootloader = not flags.flags.dirInstall and (not ksdata.bootloader.disabled
                                                            and ksdata.bootloader != "none")

    installation_queue = TaskQueue("Installation queue")
    # connect progress reporting
    installation_queue.queue_started.connect(lambda x: progress_message(x.status_message))
    installation_queue.queue_completed.connect(lambda x: progress_step("%s -- DONE" % x.status_message))

    # This should be the only thread running, wait for the others to finish if not.
    if threadMgr.running > 1:
        # it could be that the threads finish execution before the task is executed,
        # but that should not cause any issues

        def wait_for_all_treads():
            for message in ("Thread %s is running" % n for n in threadMgr.names):
                log.debug(message)
            threadMgr.wait_all()

        # Use a queue with a single task as only TaskQueues have the status_message
        # property used for setting the progress status in the UI.
        wait_for_threads = TaskQueue("Wait for threads to finish",
                                     N_("Waiting for %s threads to finish") % (threadMgr.running - 1))

        wait_for_threads.append(Task("Wait for all threads to finish", wait_for_all_treads))
        installation_queue.append(wait_for_threads)

    # Save system time to HW clock.
    # - this used to be before waiting on threads, but I don't think that's needed
    if flags.can_touch_runtime_system("save system time to HW clock"):
        # lets just do this as a top-level task - no
        save_hwclock = Task("Save system time to HW clock", timezone.save_hw_clock, (ksdata.timezone,))
        installation_queue.append(save_hwclock)

    # setup the installation environment
    setup_environment = TaskQueue("Installation environment setup", N_("Setting up the installation environment"))
    setup_environment.append(Task("Setup firstboot", ksdata.firstboot.setup, (ksdata, instClass)))
    setup_environment.append(Task("Setup addons", ksdata.addons.setup, (storage, ksdata, instClass, payload)))
    installation_queue.append(setup_environment)

    # Do partitioning.
    # Depending on current payload the storage might be apparently configured
    # either before or after package/payload installation.
    # So let's have two task queues - early storage & late storage.
    early_storage = TaskQueue("Early storage configuration", N_("Configuring storage"))

    # put custom storage info into ksdata, but not if just assigning mount points
    if not ksdata.mount.dataList():
        early_storage.append(Task("Insert custom storage to ksdata", storage.update_ksdata))

    # pre-storage tasks
    # - Is this actually needed ? It does not appear to do anything right now.
    early_storage.append(Task("Run pre-storage tasks", payload.preStorage))

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

    early_storage.append(Task("Activate filesystems",
                              task=turn_on_filesystems,
                              task_args=(storage,),
                              task_kwargs={"mount_only": flags.flags.dirInstall, "callbacks": callbacks_reg}))

    early_storage.append(Task("Write early storage", payload.writeStorageEarly))
    installation_queue.append(early_storage)

    # Run %pre-install scripts with the filesystem mounted and no packages
    pre_install_scripts = TaskQueue("Pre-install scripts", N_("Running pre-installation scripts"))
    pre_install_scripts.append(Task("Run %pre-install scripts", runPreInstallScripts, (ksdata.scripts,)))
    installation_queue.append(pre_install_scripts)

    # Do packaging.

    # Discover information about realms to join to determine the need for additional packages.
    if ksdata.realm.join_realm:
        realm_discover = TaskQueue("Realm discover", N_("Discovering realm to join"))
        realm_discover.append(Task("Discover realm to join", ksdata.realm.setup))
        installation_queue.append(realm_discover)

    # Check for other possibly needed additional packages.
    pre_install = TaskQueue("Pre install tasks", N_("Running pre-installation tasks"))
    pre_install.append(Task("Setup authconfig", ksdata.authconfig.setup))
    pre_install.append(Task("Setup firewall", ksdata.firewall.setup))
    pre_install.append(Task("Setup network", ksdata.network.setup))
    # Setup timezone and add chrony as package if timezone was set in KS
    # and "-chrony" wasn't in packages section and/or --nontp wasn't set.
    pre_install.append(Task("Setup timezone", ksdata.timezone.setup, (ksdata,)))

    # make name resolution work for rpm scripts in chroot
    if flags.can_touch_runtime_system("copy /etc/resolv.conf to sysroot"):
        # we use a custom Task subclass as the sysroot path has to be resolved
        # only when the task is actually started, not at task creation time
        pre_install.append(WriteResolvConfTask("Copy /resolv.conf to sysroot"))

    def run_pre_install():
        """This means to gather what additional packages (if any) are needed & executing payload.preInstall()."""
        # anaconda requires storage packages in order to make sure the target
        # system is bootable and configurable, and some other packages in order
        # to finish setting up the system.
        payload.requirements.add_packages(storage.packages, reason="storage")
        payload.requirements.add_packages(ksdata.realm.packages, reason="realm")
        payload.requirements.add_packages(ksdata.authconfig.packages, reason="authconfig")
        payload.requirements.add_packages(ksdata.firewall.packages, reason="firewall")
        payload.requirements.add_packages(ksdata.network.packages, reason="network")
        payload.requirements.add_packages(ksdata.timezone.packages, reason="ntp", strong=False)

        if willInstallBootloader:
            payload.requirements.add_packages(storage.bootloader.packages, reason="bootloader")
        payload.requirements.add_groups(payload.languageGroups(), reason="language groups")
        payload.requirements.add_packages(payload.langpacks(), reason="langpacks", strong=False)
        payload.preInstall()

    pre_install.append(Task("Find additional packages & run preInstall()", run_pre_install))
    installation_queue.append(pre_install)

    payload_install = TaskQueue("Payload installation", N_("Installing."))
    payload_install.append(Task("Install the payload", payload.install))
    installation_queue.append(payload_install)

    # for some payloads storage is configured after the payload is installed
    late_storage = TaskQueue("Late storage configuration", N_("Configuring storage"))
    late_storage.append(Task("Write late storage", payload.writeStorageLate))
    installation_queue.append(late_storage)

    # Do bootloader.
    if willInstallBootloader:
        bootloader_install = TaskQueue("Bootloader installation", N_("Installing boot loader"))
        bootloader_install.append(Task("Install bootloader", writeBootLoader, (storage, payload, instClass, ksdata)))
        installation_queue.append(bootloader_install)

    post_install = TaskQueue("Post-installation setup tasks", (N_("Performing post-installation setup tasks")))
    post_install.append(Task("Run post-installation setup tasks", payload.postInstall))
    installation_queue.append(post_install)

    # Create snapshot
    if ksdata.snapshot and ksdata.snapshot.has_snapshot(SNAPSHOT_WHEN_POST_INSTALL):
        snapshot_creation = TaskQueue("Creating post installation snapshots", N_("Creating snapshots"))
        snapshot_creation.append(Task("Create post-install snapshots", ksdata.snapshot.execute, (storage, ksdata, instClass)))
        installation_queue.append(snapshot_creation)

    # notify progress tracking about the number of steps
    progress_init(len(installation_queue))
    # log contents of the main task queue
    log.info(installation_queue.summary)

    # log tasks and queues when they are started
    # - note that we are using generators to add the counter
    queue_counter = iutil.item_counter(installation_queue.queue_count)
    task_started_counter = iutil.item_counter(installation_queue.task_count)
    task_completed_counter = iutil.item_counter(installation_queue.task_count)
    installation_queue.queue_started.connect(lambda x: log.info("Queue started: %s (%s)", x.name, next(queue_counter)))
    installation_queue.task_started.connect(lambda x: log.info("Task started: %s (%s)", x.name, next(task_started_counter)))
    installation_queue.task_completed.connect(lambda x: log.debug("Task completed: %s (%s) (%1.1f s)",
                                                                  x.name, next(task_completed_counter),
                                                                  x.elapsed_time))
    # start the task queue
    installation_queue.start()
    # done
    progress_complete()
