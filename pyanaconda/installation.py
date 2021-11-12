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
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import PAYLOAD_LIVE_TYPES
from pyanaconda.core.kernel import kernel_arguments
from pyanaconda.modules.common.constants.objects import BOOTLOADER, SNAPSHOT, FIREWALL
from pyanaconda.modules.common.constants.services import STORAGE, USERS, SERVICES, NETWORK, SECURITY, \
    LOCALIZATION, TIMEZONE, BOSS, SUBSCRIPTION
from pyanaconda.modules.common.structures.requirement import Requirement
from pyanaconda.modules.common.task import sync_run_task
from pyanaconda.modules.common.util import is_module_available
from pyanaconda.progress import progress_message, progress_step, progress_complete, progress_init
from pyanaconda import flags
from pyanaconda.core import util
from pyanaconda import timezone
from pyanaconda import network
from pyanaconda.core.i18n import N_
from pyanaconda.threading import threadMgr
from pyanaconda.kickstart import runPostScripts, runPreInstallScripts
from pyanaconda.kexec import setup_kexec
from pyanaconda.installation_tasks import Task, TaskQueue
from pyanaconda.progress import progressQ
from pykickstart.constants import SNAPSHOT_WHEN_POST_INSTALL

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

__all__ = ["run_installation"]


class WriteResolvConfTask(Task):
    """Custom task subclass for handling the resolv.conf copy task.

    The main reason is to resolve the sysroot path right before the
    copy operation, not at task & task queue creation time.

    Secondary reason is to demonstrate how a lightweight Task subclass can be used.
    """

    def run_task(self):
        """Resolve the sysroot path only right before doing the copy operation.

        If we just added the sysroot path as an argument, it would be resolved when the
        task queue was created, not when the task is actually executed, which could
        theoretically result in an incorrect path.
        """
        network.copy_resolv_conf_to_root(conf.target.system_root)


def _writeKS(ksdata):
    path = conf.target.system_root + "/root/anaconda-ks.cfg"

    # Make it so only root can read - could have passwords
    with util.open_with_perm(path, "w", 0o600) as f:
        f.write(str(ksdata))


def _prepare_configuration(payload, ksdata):
    """Configure the installed system."""

    configuration_queue = TaskQueue("Configuration queue")
    # connect progress reporting
    configuration_queue.queue_started.connect(lambda x: progress_message(x.status_message))
    configuration_queue.task_completed.connect(lambda x: progress_step(x.name))

    # add installation tasks for the Subscription DBus module
    if is_module_available(SUBSCRIPTION):
        # we only run the tasks if the Subscription module is available
        subscription_config = TaskQueue("Subscription configuration",
                                        N_("Configuring Red Hat subscription"))
        subscription_proxy = SUBSCRIPTION.get_proxy()
        subscription_dbus_tasks = subscription_proxy.InstallWithTasks()
        subscription_config.append_dbus_tasks(SUBSCRIPTION, subscription_dbus_tasks)
        configuration_queue.append(subscription_config)

    # schedule the execute methods of ksdata that require an installed system to be present
    os_config = TaskQueue("Installed system configuration", N_("Configuring installed system"))

    # add installation tasks for the Security DBus module
    if is_module_available(SECURITY):
        security_proxy = SECURITY.get_proxy()
        security_dbus_tasks = security_proxy.InstallWithTasks()
        os_config.append_dbus_tasks(SECURITY, security_dbus_tasks)

    # add installation tasks for the Timezone DBus module
    # run these tasks before tasks of the Services module
    if is_module_available(TIMEZONE):
        timezone_proxy = TIMEZONE.get_proxy()
        timezone_dbus_tasks = timezone_proxy.InstallWithTasks()
        os_config.append_dbus_tasks(TIMEZONE, timezone_dbus_tasks)

    # add installation tasks for the Services DBus module
    if is_module_available(SERVICES):
        services_proxy = SERVICES.get_proxy()
        services_dbus_tasks = services_proxy.InstallWithTasks()
        os_config.append_dbus_tasks(SERVICES, services_dbus_tasks)

    # add installation tasks for the Localization DBus module
    if is_module_available(LOCALIZATION):
        localization_proxy = LOCALIZATION.get_proxy()
        localization_dbus_tasks = localization_proxy.InstallWithTasks()
        os_config.append_dbus_tasks(LOCALIZATION, localization_dbus_tasks)

    # add the Firewall configuration task
    if conf.target.can_configure_network:
        firewall_proxy = NETWORK.get_proxy(FIREWALL)
        firewall_dbus_task = firewall_proxy.InstallWithTask()
        os_config.append_dbus_tasks(NETWORK, [firewall_dbus_task])

    configuration_queue.append(os_config)

    # schedule network configuration (if required)
    if conf.target.can_configure_network and conf.system.provides_network_config:
        overwrite = payload.type in PAYLOAD_LIVE_TYPES
        network_config = TaskQueue("Network configuration", N_("Writing network configuration"))
        network_config.append(Task("Network configuration",
                                   network.write_configuration, (overwrite, )))
        configuration_queue.append(network_config)

    # add installation tasks for the Users DBus module
    if is_module_available(USERS):
        user_config = TaskQueue("User creation", N_("Creating users"))
        users_proxy = USERS.get_proxy()
        users_dbus_tasks = users_proxy.InstallWithTasks()
        os_config.append_dbus_tasks(USERS, users_dbus_tasks)
        configuration_queue.append(user_config)

    # Anaconda addon configuration
    addon_config = TaskQueue("Anaconda addon configuration", N_("Configuring addons"))

    # there is no longer a User class & addons should no longer need it
    # FIXME: drop user class parameter from the API & all known addons
    addon_config.append(Task(
        "Configure Anaconda addons",
        ksdata.addons.execute,
        (None, ksdata, None, payload)
    ))

    boss_proxy = BOSS.get_proxy()
    addon_config.append_dbus_tasks(BOSS, [boss_proxy.InstallSystemWithTask()])

    configuration_queue.append(addon_config)

    # Initramfs generation
    generate_initramfs = TaskQueue("Initramfs generation", N_("Generating initramfs"))
    generate_initramfs.append(Task("Generate initramfs", payload.recreate_initrds))

    # This works around 2 problems, /boot on BTRFS and BTRFS installations where the initrd is
    # recreated after the first writeBootLoader call. This reruns it after the new initrd has
    # been created, fixing the kernel root and subvol args and adding the missing initrd entry.
    bootloader_proxy = STORAGE.get_proxy(BOOTLOADER)

    def fix_btrfs_bootloader():
        btrfs_task = bootloader_proxy.FixBTRFSWithTask(payload.kernel_version_list)
        sync_run_task(STORAGE.get_proxy(btrfs_task))

    if payload.type in PAYLOAD_LIVE_TYPES:
        generate_initramfs.append(Task("Fix bootloader on BTRFS", fix_btrfs_bootloader))

    # Invoking zipl should be the last thing done on a s390x installation (see #1652727).
    zipl_task = bootloader_proxy.FixZIPLWithTask()
    generate_initramfs.append_dbus_tasks(STORAGE, [zipl_task])
    configuration_queue.append(generate_initramfs)

    # realm join
    # - this can run only after network is configured in the target system chroot
    if is_module_available(SECURITY):
        security_proxy = SECURITY.get_proxy()
        configuration_queue.append_dbus_tasks(SECURITY, [security_proxy.JoinRealmWithTask()])

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

    # only add write_configs to the main queue if we actually store some kickstarts/configs
    if write_configs.task_count:
        configuration_queue.append(write_configs)

    post_scripts = TaskQueue(
        "Post installation scripts",
        N_("Running post-installation scripts")
    )
    post_scripts.append(Task(
        "Run post installation scripts",
        runPostScripts,
        (ksdata.scripts,)
    ))
    configuration_queue.append(post_scripts)

    return configuration_queue


def _prepare_installation(payload, ksdata):
    """Perform an installation.  This method takes the ksdata as prepared by
       the UI (the first hub, in graphical mode) and applies it to the disk.
       The two main tasks for this are putting filesystems onto disks and
       installing packages onto those filesystems.
    """
    installation_queue = TaskQueue("Installation queue")
    # connect progress reporting
    installation_queue.queue_started.connect(lambda x: progress_message(x.status_message))
    installation_queue.task_completed.connect(lambda x: progress_step(x.name))

    # This should be the only thread running, wait for the others to finish if not.
    #
    # We need to do this before we start filling the task queue, or else the DBus
    # tasks we create might have stale data due to background processing threads
    # still running at task creation time.
    if threadMgr.running > 1:
        # show a progress message
        progressQ.send_message(N_("Waiting for %s threads to finish") % (threadMgr.running - 1))
        for message in ("Thread %s is running" % n for n in threadMgr.names):
            log.debug(message)
        threadMgr.wait_all()
        log.debug("No more threads are running, assembling installation task queue.")

    # Save system time to HW clock.
    # - this used to be before waiting on threads, but I don't think that's needed
    if conf.system.can_set_hardware_clock:
        # lets just do this as a top-level task - no
        save_hwclock = Task("Save system time to HW clock", timezone.save_hw_clock)
        installation_queue.append(save_hwclock)

    # setup the installation environment
    setup_environment = TaskQueue("Installation environment setup", N_("Setting up the installation environment"))
    setup_environment.append(Task(
        "Setup addons",
        ksdata.addons.setup,
        (None, ksdata, payload)
    ))

    boss_proxy = BOSS.get_proxy()
    setup_environment.append_dbus_tasks(BOSS, [boss_proxy.ConfigureRuntimeWithTask()])

    installation_queue.append(setup_environment)

    # Do partitioning.
    # Depending on current payload the storage might be apparently configured
    # either before or after package/payload installation.
    # So let's have two task queues - early storage & late storage.
    storage_proxy = STORAGE.get_proxy()
    early_storage = TaskQueue("Early storage configuration", N_("Configuring storage"))
    early_storage.append_dbus_tasks(STORAGE, storage_proxy.InstallWithTasks())

    if payload.needs_storage_configuration:
        conf_task = storage_proxy.WriteConfigurationWithTask()
        early_storage.append_dbus_tasks(STORAGE, [conf_task])

    installation_queue.append(early_storage)

    # Run %pre-install scripts with the filesystem mounted and no packages
    pre_install_scripts = TaskQueue("Pre-install scripts", N_("Running pre-installation scripts"))
    pre_install_scripts.append(Task("Run %pre-install scripts", runPreInstallScripts, (ksdata.scripts,)))
    installation_queue.append(pre_install_scripts)

    # Do various pre-installation tasks
    # - try to discover a realm (if any)
    # - check for possibly needed additional packages.
    pre_install = TaskQueue("Pre install tasks", N_("Running pre-installation tasks"))

    # make name resolution work for rpm scripts in chroot
    if conf.system.provides_resolver_config:
        # we use a custom Task subclass as the sysroot path has to be resolved
        # only when the task is actually started, not at task creation time
        pre_install.append(WriteResolvConfTask("Copy resolv.conf to sysroot"))

    # realm discovery
    if is_module_available(SECURITY):
        security_proxy = SECURITY.get_proxy()
        pre_install.append_dbus_tasks(SECURITY, [security_proxy.DiscoverRealmWithTask()])

    def run_pre_install():
        """This means to gather what additional packages (if any) are needed & executing payload.pre_install()."""
        # anaconda requires storage packages in order to make sure the target
        # system is bootable and configurable, and some other packages in order
        # to finish setting up the system.
        if kernel_arguments.is_enabled("fips"):
            payload.requirements.add_packages(['/usr/bin/fips-mode-setup'], reason="compliance")

        payload.requirements.add_groups(payload.language_groups(), reason="language groups")
        payload.requirements.add_packages(payload.langpacks(), reason="langpacks", strong=False)

        # add package requirements from modules
        # - iterate over all modules we know have valid package requirements
        # - add any requirements found to the payload requirement tracking
        modules_with_package_requirements = [SECURITY, NETWORK, TIMEZONE, STORAGE, SUBSCRIPTION]
        for module in modules_with_package_requirements:
            # Skip unavailable modules.
            if not is_module_available(module):
                continue

            module_proxy = module.get_proxy()
            module_requirements = Requirement.from_structure_list(module_proxy.CollectRequirements())
            log.debug("Adding requirements for module %s : %s", module, module_requirements)
            payload.requirements.add_requirements(module_requirements)

        payload.pre_install()

    pre_install.append(Task("Find additional packages & run pre_install()", run_pre_install))
    installation_queue.append(pre_install)

    payload_install = TaskQueue("Payload installation", N_("Installing."))
    payload_install.append(Task("Install the payload", payload.install))
    installation_queue.append(payload_install)

    # for some payloads storage is configured after the payload is installed
    if not payload.needs_storage_configuration:
        late_storage = TaskQueue("Late storage configuration", N_("Configuring storage"))
        conf_task = storage_proxy.WriteConfigurationWithTask()
        late_storage.append_dbus_tasks(STORAGE, [conf_task])
        installation_queue.append(late_storage)

    # Do bootloader.
    bootloader_proxy = STORAGE.get_proxy(BOOTLOADER)
    bootloader_install = TaskQueue("Bootloader installation", N_("Installing boot loader"))

    def configure_bootloader():
        boot_task = bootloader_proxy.ConfigureWithTask(payload.kernel_version_list)
        sync_run_task(STORAGE.get_proxy(boot_task))

    if not payload.handles_bootloader_configuration:
        # FIXME: This is a temporary workaround, run the DBus task directly.
        bootloader_install.append(Task("Configure the bootloader", configure_bootloader))

    bootloader_install.append_dbus_tasks(STORAGE, [bootloader_proxy.InstallWithTask()])
    installation_queue.append(bootloader_install)

    post_install = TaskQueue("Post-installation setup tasks", (N_("Performing post-installation setup tasks")))
    post_install.append(Task("Run post-installation setup tasks", payload.post_install))
    installation_queue.append(post_install)

    # Create snapshot
    snapshot_proxy = STORAGE.get_proxy(SNAPSHOT)

    if snapshot_proxy.IsRequested(SNAPSHOT_WHEN_POST_INSTALL):
        snapshot_creation = TaskQueue("Creating post installation snapshots", N_("Creating snapshots"))
        snapshot_task = snapshot_proxy.CreateWithTask(SNAPSHOT_WHEN_POST_INSTALL)
        snapshot_creation.append_dbus_tasks(STORAGE, [snapshot_task])
        installation_queue.append(snapshot_creation)

    return installation_queue


def run_installation(payload, ksdata):
    """Run the complete installation."""
    queue = TaskQueue("Complete installation queue")
    queue.append(_prepare_installation(payload, ksdata))
    queue.append(_prepare_configuration(payload, ksdata))

    # notify progress tracking about the number of steps
    progress_init(queue.task_count)

    # log contents of the main task queue
    log.info(queue.summary)

    # log tasks and queues when they are started
    # - note that we are using generators to add the counter
    queue_counter = util.item_counter(queue.queue_count)
    task_started_counter = util.item_counter(queue.task_count)
    task_completed_counter = util.item_counter(queue.task_count)
    queue.queue_started.connect(
        lambda x: log.info("Queue started: %s (%s)", x.name, next(queue_counter))
    )
    queue.task_started.connect(
        lambda x: log.info("Task started: %s (%s)", x.name, next(task_started_counter))
    )
    queue.task_completed.connect(
        lambda x: log.debug("Task completed: %s (%s) (%1.1f s)", x.name,
                            next(task_completed_counter), x.elapsed_time)
    )

    # start the task queue
    queue.start()

    # done
    progress_complete()
    # this message is automatically detected by QE tools, do not change it lightly
    log.info("All tasks in the installation queue are done. Installation successfully finished.")
