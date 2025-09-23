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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import os
import copy

from pyanaconda.core import util
from pyanaconda.modules.common.errors.installation import SecurityInstallationError

from pyanaconda.simpleconfig import SimpleConfigFile

from pyanaconda.modules.common.task import Task
from pyanaconda.modules.security.constants import SELinuxMode

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

__all__ = ["ConfigureSELinuxTask", "RealmDiscoverTask", "RealmJoinTask"]

REALM_TOOL_NAME = "realm"
AUTHSELECT_TOOL_PATH = "/usr/bin/authselect"
AUTHSELECT_ARGS = ["select", "sssd", "with-fingerprint", "with-silent-lastlog", "--force"]
AUTHCONFIG_TOOL_PATH = "/usr/sbin/authconfig"
PAM_SO_PATH = "/lib/security/pam_fprintd.so"
PAM_SO_64_PATH = "/lib64/security/pam_fprintd.so"


class ConfigureSELinuxTask(Task):
    """Installation task for Initial Setup configuration."""

    SELINUX_CONFIG_PATH = "etc/selinux/config"

    SELINUX_STATES = {
        SELinuxMode.DISABLED: "disabled",
        SELinuxMode.ENFORCING: "enforcing",
        SELinuxMode.PERMISSIVE: "permissive"
    }

    def __init__(self, sysroot, selinux_mode):
        """Create a new Initial Setup configuration task.

        :param str sysroot: a path to the root of the target system
        :param int selinux_mode: SELinux mode id

        States are defined by the SELinuxMode enum as distinct integers.
        """
        super().__init__()
        self._sysroot = sysroot
        self._selinux_mode = selinux_mode

    @property
    def name(self):
        return "Configure SELinux"

    def run(self):
        if self._selinux_mode == SELinuxMode.DEFAULT:
            log.debug("Use SELinux default configuration.")
            return

        if self._selinux_mode not in self.SELINUX_STATES:
            log.error("Unknown SELinux state for %s.", self._selinux_mode)
            return

        try:
            selinux_cfg = SimpleConfigFile(os.path.join(self._sysroot, self.SELINUX_CONFIG_PATH))
            selinux_cfg.read()
            selinux_cfg.set(("SELINUX", self.SELINUX_STATES[self._selinux_mode]))
            selinux_cfg.write()
        except IOError as msg:
            log.error("SELinux configuration failed: %s", msg)


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

    This generally means either authselect or the legacy authconfig tool.
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
        return (os.path.exists(self._sysroot + PAM_SO_64_PATH) or
                os.path.exists(self._sysroot + PAM_SO_PATH))

    def run(self):
        if not self._fingerprint_auth_enabled:
            return

        if not self._is_fingerprint_configuration_supported():
            log.debug("Fingerprint conifguration is not supported on target system.")
        else:
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
        # Apply the authselect options from the kickstart file.
        if self._authselect_options:
            run_auth_tool(
                AUTHSELECT_TOOL_PATH,
                self._authselect_options + ["--force"],
                self._sysroot
            )


class ConfigureAuthconfigTask(Task):
    """Installation task for Authconfig configuration.

    NOTE: Authconfig is deprecated, this is present temporarily
          as long as we want to provide backward compatibility
          for the authconfig command in kickstart.
    """

    def __init__(self, sysroot, authconfig_options):
        """Create a new Authconfig configuration task.

        :param str sysroot: a path to the root of the target system
        :param list authconfig_options: options for authconfig
        """
        super().__init__()
        self._sysroot = sysroot
        self._authconfig_options = authconfig_options

    @property
    def name(self):
        return "Authconfig configuration"

    def run(self):
        # Apply the authconfig options from the kickstart file (deprecated).
        if self._authconfig_options:
            run_auth_tool(
                AUTHCONFIG_TOOL_PATH,
                ["--update", "--nostart"] + self._authconfig_options,
                self._sysroot
            )
