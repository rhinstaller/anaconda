import os

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.constants import BOOTLOADER_DISABLED
from pyanaconda.core.i18n import _
from pyanaconda.core.path import set_system_root
from pyanaconda.core.util import execProgram
from pyanaconda.modules.common.constants.objects import BOOTLOADER
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.common.errors.installation import PayloadInstallationError
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.payloads.base.utils import get_device_path_for_mount_point

log = get_module_logger(__name__)


def safe_exec_program(cmd, argv, successful_return_codes=(0,), **kwargs):
    """Exec a program and raise on failure."""
    rc, output = execProgram(cmd, argv, **kwargs)
    if rc not in successful_return_codes:
        raise PayloadInstallationError(
            "The command '{}' exited with the code {}:\n{}".format(" ".join([cmd] + argv), rc, output)
        )


def _get_stateroot(data):
    return getattr(data, "stateroot", "")


def _get_ref(data):
    # Bootc uses sourceImgRef
    if hasattr(data, "sourceImgRef"):
        return data.sourceImgRef
    return ""


def _find_first_filename(root, pattern, directory=True, file=True):
    """
    Find the first occurrence of pattern in any directory or subdirectory of root

    This is a top-down depth-first search.

    :arg root: The directory to perform the search from
    :arg pattern: The filename to search for (Note: this is not currently a regex
        or glob pattern)
    :kwarg directory: If set to False, do not return directories with this name
    :kwarg file: If set to False, do not return files with this name
    :returns: The complete path to the filename, including `root`.
    """
    for dirpath, dirs, files in os.walk(root):
        if directory:
            for dirname in dirs:
                if dirname == pattern:
                    return os.path.join(dirpath, dirname)
        if file:
            for filename in files:
                if pattern == filename:
                    return os.path.join(dirpath, pattern)

    raise FileNotFoundError("Could not find {pattern} in directory: {root}".format(
        pattern=pattern,
        root=root
    ))


class DeployBootcTask(Task):
    """Task to deploy Bootc based image."""

    def __init__(self, data, physroot, sysroot):
        super().__init__()
        self._data = data
        self._physroot = physroot
        self._sysroot = sysroot

    @property
    def name(self):
        return "Deploy bootc"

    def run(self):
        bootloader = STORAGE.get_proxy(BOOTLOADER)
        # Bootc will handle bootloader config so disable it
        bootloader.BootloaderMode = BOOTLOADER_DISABLED
        log.debug("Disabled bootloader configuration due to bootc mode")

        stateroot = _get_stateroot(self._data)
        ref = _get_ref(self._data)

        log.debug("Run the bootc based installation")

        self.report_progress(_("Bootc deployment starting: {}" ).format(ref))

        # The main one is SELinux to be presented in the system.
        # It may be disabled but needs to be present.

        # Bootc expects `prepare-root.conf` file to be present in the system
        log.debug("Bootc workaround: add missing configuration file")
        if not os.path.exists("/etc/ostree/prepare-root.conf"):
            with open("/etc/ostree/prepare-root.conf", "w") as f:
                f.write("[ostree]\n")
                f.write("sysroot=/sysroot\n")
        else:
            log.debug("/etc/ostree/prepare-root.conf already presented and will not be modified")

        # After automatic partitioning sysroot and sysimage are mounted,
        # but we need a clear directory structure expected by bootc
        log.debug("Bootc workaround: remove unwanted mounts")
        safe_exec_program("umount", ["-l", self._physroot])

        # Bootc does not need directories created automatically by blivet
        log.debug("Bootc workaround: remove unwanted directories")
        safe_exec_program("rm", ["-rf", self._sysroot + "/root"])
        os.rmdir(self._sysroot + "/dev")
        os.rmdir(self._sysroot + "/proc")
        os.rmdir(self._sysroot + "/run")
        os.rmdir(self._sysroot + "/sys")
        os.rmdir(self._sysroot + "/tmp")
        try:
            os.rmdir(self._sysroot + "/home")
        except FileNotFoundError:
            log.debug("No /home directory to remove")

        # Bootc requires empty `boot` directory to be present
        log.debug("Bootc workaround: create bootc required dirs")
        safe_exec_program("mkdir", ["-p", self._sysroot + "/boot"])
        # Mount /boot partition created by autopart
        boot_partition = get_device_path_for_mount_point("/boot")
        safe_exec_program("mount", [boot_partition, self._sysroot + "/boot"])
        # Make sure the partition is empty
        safe_exec_program("rm", ["-rf", self._sysroot + "/boot/*"])

        log.debug("Executing bootc install command")
        safe_exec_program(
            "bootc",
            [
                "install",
                "to-filesystem",
                "--stateroot=" + stateroot,
                "--source-imgref=" + getattr(self._data, "sourceImgRef", ""),
                "--target-imgref=" + getattr(self._data, "targetImgRef", ""),
                self._sysroot,
            ],
        )

        # After bootc install is completed sysroot is mounted in read only mode
        # and it points to the base of ostree deployment but not the new true sysroot.
        # Final steps expect config dirs like `/etc` in /mnt/sysroot. Fix mounts.

        # Track which partition is sysroot
        sysroot_partition = get_device_path_for_mount_point("/")

        # Remove existing mounts as they are read only
        safe_exec_program("umount", ["-l", "/run/bootc/storage"])
        safe_exec_program("umount", ["-l", self._sysroot])

        # Mount current sysroot as sysimage (unmounted before)
        safe_exec_program("mount", [sysroot_partition, self._physroot])

        # Find the deployment directory: /root/ostree/deploy/<stateroot>/<deploy-id>/home
        # We specifically look in the deploy directory, not the top-level /home
        deploy_base = self._physroot + "/root/ostree/deploy"
        new_home_path = _find_first_filename(deploy_base, "home")
        new_root_path = os.path.dirname(new_home_path)

        set_system_root(new_root_path)

        # Ensure /var/roothome exists for further steps
        if not os.path.exists(self._sysroot + "/var/roothome"):
            safe_exec_program("mkdir", ["-p", self._sysroot + "/var/roothome"])

        # Prepare SELinux hooks needed by chroot operations when SELinux is enabled
        proc_path = "/proc"
        safe_exec_program("mkdir", ["-p", self._sysroot + proc_path])
        safe_exec_program("mount", ["--bind", proc_path, self._sysroot + proc_path])

        selinuxfs_path = "/sys/fs/selinux"
        safe_exec_program("mkdir", ["-p", self._sysroot + selinuxfs_path])
        safe_exec_program("mount", ["--bind", selinuxfs_path, self._sysroot + selinuxfs_path])

        log.info("Bootc deploy complete")
        self.report_progress(_("Bootc deployment complete: {}" ).format(ref))
