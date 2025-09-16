#
# Copyright (C) 2019 Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import copy
import os
import shutil

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import util
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import PAYLOAD_TYPE_DNF
from pyanaconda.core.path import join_paths, make_directories
from pyanaconda.modules.common.errors.installation import SecurityInstallationError
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.security.constants import SELinuxMode

log = get_module_logger(__name__)

REALM_TOOL_NAME = "realm"
AUTHSELECT_TOOL_PATH = "/usr/bin/authselect"
AUTHSELECT_ARGS = ["enable-feature", "with-fingerprint"]
PAM_SO_PATH = "/lib/security/pam_fprintd.so"
PAM_SO_64_PATH = "/lib64/security/pam_fprintd.so"


class PreconfigureFIPSTask(Task):
    """Installation task that sets up FIPS for the payload installation."""

    def __init__(self, fips_enabled, payload_type, sysroot):
        """Create a new task.

        :param fips_enabled: True if FIPS is enabled, otherwise False
        :param payload_type: a type of the payload
        :param sysroot: a path to the system root
        """
        super().__init__()
        self._fips_enabled = fips_enabled
        self._payload_type = payload_type
        self._sysroot = sysroot

    @property
    def name(self):
        return "Set up FIPS for the payload installation"

    def run(self):
        """Set up FIPS for the payload installation.

        Copy the crypto policy from the installation environment
        to the target system before package installation. The RPM
        scriptlets need to be executed in the FIPS mode if there
        is fips=1 on the kernel cmdline.
        """
        if not self._fips_enabled:
            log.debug("FIPS is not enabled. Skipping.")
            return

        if self._payload_type != PAYLOAD_TYPE_DNF:
            log.debug("Don't set up FIPS for the %s payload.", self._payload_type)
            return

        if not self._check_fips():
            raise SecurityInstallationError(
                "FIPS is not correctly set up "
                "in the installation environment."
            )

        self._set_up_fips()

    def _check_fips(self):
        """Check FIPS in the installation environment."""
        # Check the config file.
        config_path = "/etc/crypto-policies/config"

        if not os.path.exists(config_path):
            log.error("File '%s' doesn't exist.", config_path)
            return False

        with open(config_path) as f:
            if f.read().strip() != "FIPS":
                log.error("The crypto policy is not set to FIPS.")
                return False

        # Check one of the back-end symlinks.
        symlink_path = "/etc/crypto-policies/back-ends/opensshserver.config"

        if "FIPS" not in os.path.realpath(symlink_path):
            log.error("The back ends are not set to FIPS.")
            return False

        return True

    def _set_up_fips(self):
        """Set up FIPS in the target system."""
        log.debug("Copying the crypto policy.")

        # Create /etc/crypto-policies.
        src = "/etc/crypto-policies/"
        dst = join_paths(self._sysroot, src)
        make_directories(dst)

        # Copy the config file.
        src = "/etc/crypto-policies/config"
        dst = join_paths(self._sysroot, src)
        shutil.copyfile(src, dst)

        # Log the file content on the target system.
        util.execWithRedirect("/bin/cat", [dst])

        # Copy the back-ends.
        src = "/etc/crypto-policies/back-ends/"
        dst = join_paths(self._sysroot, src)
        shutil.copytree(src, dst, symlinks=True)

        # Log the directory content on the target system.
        util.execWithRedirect("/bin/ls", ["-l", dst])


class ConfigureFIPSTask(Task):
    """Installation task that configures FIPS on the installed system."""

    def __init__(self, fips_enabled, sysroot):
        """Create a new task.

        :param fips_enabled: True if FIPS is enabled, otherwise False
        :param sysroot: a path to the system root
        """
        super().__init__()
        self._fips_enabled = fips_enabled
        self._sysroot = sysroot

    @property
    def name(self):
        return "Configure FIPS"

    def run(self):
        """Configure FIPS on the installed system.

        If the installation is running in fips mode then make sure
        fips is also correctly enabled in the installed system.
        """
        if not self._fips_enabled:
            log.debug("FIPS is not enabled. Skipping.")
            return

        if not conf.target.is_hardware:
            log.debug("Don't set up FIPS on %s.", conf.target.type.value)
            return

        # Bootloader is not modified. Anaconda already does everything needed.
        util.execWithRedirect(
            "/usr/libexec/fips-setup-helper",
            ["anaconda"],
            root=self._sysroot
        )


class ConfigureSELinuxTask(Task):
    """Installation task for Initial Setup configuration."""

    SELINUX_CONFIG_PATH = "/etc/selinux/config"

    SELINUX_STATES = {
        SELinuxMode.DISABLED: "disabled",
        SELinuxMode.ENFORCING: "enforcing",
        SELinuxMode.PERMISSIVE: "permissive"
    }

    def __init__(self, sysroot, selinux_mode):
        """Create a new task.

        :param str sysroot: a path to the root of the target system
        :param SELinuxMode selinux_mode: a SELinux mode

        States are defined by the SELinuxMode enum as distinct integers.
        """
        super().__init__()
        self._sysroot = sysroot
        self._selinux_mode = selinux_mode

    @property
    def name(self):
        return "Configure SELinux"

    def run(self):
        """Run the task."""
        if self._selinux_mode == SELinuxMode.DEFAULT:
            log.debug("Use SELinux default configuration.")
            return

        if self._selinux_mode not in self.SELINUX_STATES:
            log.error("Unknown SELinux state for %s.", self._selinux_mode)
            return

        try:
            # Read the SELinux configuration file.
            path = join_paths(self._sysroot, self.SELINUX_CONFIG_PATH)
            log.debug("Modifying the configuration at %s.", path)

            with open(path, "r") as f:
                lines = f.readlines()

            # Modify the SELinux configuration.
            lines = list(map(self._process_line, lines))

            # Write the modified configuration.
            with open(path, "w") as f:
                f.writelines(lines)

        except OSError as msg:
            log.error("SELinux configuration failed: %s", msg)

    @property
    def _selinux_state(self):
        """The string representation of the SELinux mode."""
        return self.SELINUX_STATES[self._selinux_mode]

    def _process_line(self, line):
        """Process a line from the SELinux configuration file."""
        if line.strip().startswith("SELINUX="):
            log.debug("Found '%s'.", line.strip())
            line = "SELINUX={}\n".format(self._selinux_state)
            log.debug("Setting '%s'.", line.strip())
            return line

        return line


class RealmDiscoverTask(Task):
    """Task for discovering information about a realm we intend to join (if any).

    Based on results from this task we might attempt to join the realm via a separate
    task later on.
    """

    def __init__(self, sysroot, realm_data):
        """Create a new realm discovery task.

        :param str sysroot: a path to the root of the target system
        :param realm_data: realm data holder
        """
        super().__init__()
        self._sysroot = sysroot
        self._realm_data = realm_data

    @property
    def name(self):
        return "Discover information about a realm"

    def _parse_realm_data(self, output):
        """Parse data from realm tool output.

        First line is the realm name, and following lines are data
        formatted as a simple key value store:

        "name: value"

        We only care about the keys called "required-package"
        and ignore the rest.

        :param str output: output of the realm tool
        :return: a tuple reporting discovery success and package requirements
        :rtype: (bool, list(str))
        """
        required_packages = ["realmd"]
        discovered_realm_data = None

        lines = output.split("\n")
        if lines:
            discovered_realm_data = lines.pop(0).strip()
            log.info("Realm discovered: %s", discovered_realm_data)
            for line in lines:
                parts = line.split(":", 1)
                if len(parts) == 2 and parts[0].strip() == "required-package":
                    package_spec = parts[1].strip()
                    # "" is not a valid package specification
                    if package_spec:
                        required_packages.append(package_spec)

            log.info("Realm %s needs packages %s",
                     discovered_realm_data, ", ".join(required_packages))
        return bool(discovered_realm_data), required_packages

    def run(self):
        if not self._realm_data.name:
            log.debug("No realm name set, skipping realm discovery.")
            return self._realm_data

        output = ""

        try:
            argv = ["discover", "--verbose"] + self._realm_data.discover_options \
                + [self._realm_data.name]
            output = util.execWithCapture(REALM_TOOL_NAME, argv, filter_stderr=True)
        except OSError:
            # TODO: A lousy way of propagating what will usually be
            # 'no such realm'
            # The error message is logged by util
            return self._realm_data

        realm_discovered, required_packages = self._parse_realm_data(output)

        # set the result in the realm data holder and return it
        self._realm_data.discovered = realm_discovered
        self._realm_data.required_packages = required_packages
        return self._realm_data


class RealmJoinTask(Task):
    """Task for joining a realm we have discovered (if any)."""

    def __init__(self, sysroot, realm_data):
        """Create a new realm discovery task.

        :param str sysroot: a path to the root of the target system
        :param realm_data: realm data holder
        """
        super().__init__()
        self._sysroot = sysroot
        # We do a deep copy of the realm data holder to avoid
        # changes to the data in the Task from changing the backing
        # data structure in the module, without triggering the changed signal.
        # This also works the other way around, preventing changes
        # to the data structure in the module influencing the task after
        # it has been instantiated.
        self._realm_data = copy.deepcopy(realm_data)

    @property
    def name(self):
        return "Join a realm"

    def set_realm_data(self, realm_data):
        """Set a new version of realm data to the task."""
        log.debug("Setting new realm data for realm join task: %s", realm_data)
        self._realm_data = realm_data

    def run(self):
        if not self._realm_data.discovered:
            log.debug("No realm has been discovered, so not joining any realm.")
            return

        for arg in self._realm_data.join_options:
            if arg.startswith("--no-password") or arg.startswith("--one-time-password"):
                pw_args = []
                break
        else:
            # no explicit password argument, using implicit --no-password
            pw_args = ["--no-password"]

        argv = ["join", "--install", self._sysroot, "--verbose"] \
            + pw_args + self._realm_data.join_options
        rc = -1
        try:
            rc = util.execWithRedirect(REALM_TOOL_NAME, argv)
        except OSError:
            log.exception("Realm %s join failed with exception.", self._realm_data.name)
            pass

        if rc == 0:
            log.info("Joined realm %s", self._realm_data.name)
        else:
            log.info("Joining realm %s failed", self._realm_data.name)


def run_auth_tool(cmd, args, root, required=True):
    """Run an authentication related tool.

    This generally means authselect.
    :param str cmd: path to the tool to be run
    :param list(str) args: list of arguments passed to the tool
    :param str root: a path to the root in which the tool should be run
    :param bool required: require the tool to be present and run
                          (False makes the function pass if the tool is not available)
    :raises: SecurityInstallationError if the tool which is required is not found
    :raises: RuntimeError if the run of the tool fails
    """
    if not os.path.lexists(root + cmd):
        msg = "{} is missing. Cannot setup authentication.".format(cmd)
        if required:
            raise SecurityInstallationError(msg)
        else:
            log.error(msg)
            return
    try:
        log.debug("Configuring authentication: %s %s", cmd, args)
        util.execWithRedirect(cmd, args, root=root)
    except RuntimeError as msg:
        log.error("Error running %s %s: %s", cmd, args, msg)


class ConfigureFingerprintAuthTask(Task):
    """Installation task for fingerprint authentication setup."""

    def __init__(self, sysroot, fingerprint_auth_enabled):
        """Create a new Authselect configuration task.

        :param str sysroot: a path to the root of the target system
        :param bool fingerprint_auth_enabled: True if fingerprint authentication
                                              should be enabled if possible,
                                              False otherwise
        """
        super().__init__()
        self._sysroot = sysroot
        self._fingerprint_auth_enabled = fingerprint_auth_enabled

    @property
    def name(self):
        return "Configure fingerprint authentication"

    def _is_fingerprint_configuration_supported(self):
        """Is the fingerprint configuration supported?"""
        return (os.path.exists(self._sysroot + PAM_SO_64_PATH) or
                os.path.exists(self._sysroot + PAM_SO_PATH))

    def run(self):
        """Run the task."""
        if not self._fingerprint_auth_enabled:
            log.debug("Fingerprint configuration is not enabled. Skipping.")
            return

        if not self._is_fingerprint_configuration_supported():
            log.debug("Fingerprint configuration is not supported on target system. Skipping.")
            return

        log.debug("Enabling fingerprint authentication.")
        run_auth_tool(
            AUTHSELECT_TOOL_PATH,
            AUTHSELECT_ARGS,
            self._sysroot,
            required=False
        )


class ConfigureAuthselectTask(Task):
    """Installation task for Authselect configuration."""

    def __init__(self, sysroot, authselect_options):
        """Create a new Authselect configuration task.

        :param str sysroot: a path to the root of the target system
        :param list authselect_options: options for authselect
        """
        super().__init__()
        self._sysroot = sysroot
        self._authselect_options = authselect_options

    @property
    def name(self):
        return "Authselect configuration"

    def run(self):
        """Run the task."""
        if not self._authselect_options:
            log.debug("Authselect is not configured. Skipping.")
            return

        run_auth_tool(
            AUTHSELECT_TOOL_PATH,
            self._authselect_options + ["--force"],
            self._sysroot
        )
