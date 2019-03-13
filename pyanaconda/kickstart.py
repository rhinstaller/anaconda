#
# kickstart.py: kickstart install support
#
# Copyright (C) 1999-2016
# Red Hat, Inc.  All rights reserved.
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

import glob
import os
import os.path
from abc import ABCMeta, abstractmethod

import shlex
import sys
import tempfile
import time
import warnings

import blivet.arch
import blivet.iscsi

from contextlib import contextmanager

from pyanaconda import keyboard, network, nm, ntp, screen_access, timezone
from pyanaconda.core import util
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.kickstart import VERSION, commands as COMMANDS
from pyanaconda.addons import AddonSection, AddonData, AddonRegistry, collect_addon_paths
from pyanaconda.bootloader import get_bootloader
from pyanaconda.bootloader.grub2 import GRUB2
from pyanaconda.core.constants import ADDON_PATHS, IPMI_ABORTED, SELINUX_DEFAULT, \
    SETUP_ON_BOOT_DISABLED, SETUP_ON_BOOT_RECONFIG, \
    BOOTLOADER_LOCATION_PARTITION, FIREWALL_ENABLED, FIREWALL_DISABLED, \
    FIREWALL_USE_SYSTEM_DEFAULTS
from pyanaconda.dbus.structure import apply_structure
from pyanaconda.desktop import Desktop
from pyanaconda.errors import ScriptError, errorHandler
from pyanaconda.flags import flags
from pyanaconda.core.i18n import _
from pyanaconda.modules.common.errors.kickstart import SplitKickstartError
from pyanaconda.modules.common.constants.services import BOSS, TIMEZONE, LOCALIZATION, SECURITY, \
    USERS, SERVICES, STORAGE, NETWORK
from pyanaconda.modules.common.constants.objects import BOOTLOADER, FIREWALL, FCOE
from pyanaconda.modules.common.structures.realm import RealmData
from pyanaconda.modules.common.task import sync_run_task
from pyanaconda.pwpolicy import F22_PwPolicy, F22_PwPolicyData
from pyanaconda.simpleconfig import SimpleConfigFile
from pyanaconda.timezone import NTP_PACKAGE, NTP_SERVICE

from pykickstart.base import BaseHandler, KickstartCommand
from pykickstart.constants import KS_SCRIPT_POST, KS_SCRIPT_PRE, KS_SCRIPT_TRACEBACK, \
    KS_SCRIPT_PREINSTALL, SELINUX_DISABLED, SELINUX_ENFORCING, SELINUX_PERMISSIVE
from pykickstart.errors import KickstartError, KickstartParseError
from pykickstart.parser import KickstartParser
from pykickstart.parser import Script as KSScript
from pykickstart.sections import NullSection, PackageSection, PostScriptSection, PreScriptSection, PreInstallScriptSection, \
                                 OnErrorScriptSection, TracebackScriptSection, Section
from pykickstart.version import returnClassForVersion

from pyanaconda import anaconda_logging
from pyanaconda.anaconda_loggers import get_module_logger, get_stdout_logger, get_blivet_logger,\
    get_anaconda_root_logger

log = get_module_logger(__name__)

stdoutLog = get_stdout_logger()
storage_log = get_blivet_logger()

# kickstart parsing and kickstart script
script_log = log.getChild("script")
parsing_log = log.getChild("parsing")

# command specific loggers
authselect_log = log.getChild("kickstart.authselect")
user_log = log.getChild("kickstart.user")
group_log = log.getChild("kickstart.group")
iscsi_log = log.getChild("kickstart.iscsi")
network_log = log.getChild("kickstart.network")
selinux_log = log.getChild("kickstart.selinux")
timezone_log = log.getChild("kickstart.timezone")
realm_log = log.getChild("kickstart.realm")
firewall_log = log.getChild("kickstart.firewall")

@contextmanager
def check_kickstart_error():
    try:
        yield
    except KickstartError as e:
        # We do not have an interface here yet, so we cannot use our error
        # handling callback.
        print(e)
        util.ipmi_report(IPMI_ABORTED)
        sys.exit(1)

class AnacondaKSScript(KSScript):
    """ Execute a kickstart script

        This will write the script to a file named /tmp/ks-script- before
        execution.
        Output is logged by the program logger, the path specified by --log
        or to /tmp/ks-script-\\*.log
    """
    def run(self, chroot):
        """ Run the kickstart script
            @param chroot directory path to chroot into before execution
        """
        if self.inChroot:
            scriptRoot = chroot
        else:
            scriptRoot = "/"

        (fd, path) = tempfile.mkstemp("", "ks-script-", scriptRoot + "/tmp")

        os.write(fd, self.script.encode("utf-8"))
        os.close(fd)
        os.chmod(path, 0o700)

        # Always log stdout/stderr from scripts.  Using --log just lets you
        # pick where it goes.  The script will also be logged to program.log
        # because of execWithRedirect.
        if self.logfile:
            if self.inChroot:
                messages = "%s/%s" % (scriptRoot, self.logfile)
            else:
                messages = self.logfile

            d = os.path.dirname(messages)
            if not os.path.exists(d):
                os.makedirs(d)
        else:
            # Always log outside the chroot, we copy those logs into the
            # chroot later.
            messages = "/tmp/%s.log" % os.path.basename(path)

        with open(messages, "w") as fp:
            rc = util.execWithRedirect(self.interp, ["/tmp/%s" % os.path.basename(path)],
                                       stdout=fp,
                                       root=scriptRoot)

        if rc != 0:
            script_log.error("Error code %s running the kickstart script at line %s", rc, self.lineno)
            if self.errorOnFail:
                err = ""
                with open(messages, "r") as fp:
                    err = "".join(fp.readlines())

                # Show error dialog even for non-interactive
                flags.ksprompt = True

                errorHandler.cb(ScriptError(self.lineno, err))
                util.ipmi_report(IPMI_ABORTED)
                sys.exit(0)

class AnacondaInternalScript(AnacondaKSScript):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._hidden = True

    def __str__(self):
        # Scripts that implement portions of anaconda (copying screenshots and
        # log files, setfilecons, etc.) should not be written to the output
        # kickstart file.
        return ""


###
### SUBCLASSES OF PYKICKSTART COMMAND HANDLERS
###


class RemovedCommand(KickstartCommand, metaclass=ABCMeta):
    """Kickstart command that was moved on DBus.

    This class should simplify the transition to DBus.

    Kickstart command that was moved on DBus should inherit this
    class. Methods parse, setup and execute should be modified to
    access the DBus modules or moved on DBus.
    """

    @abstractmethod
    def __str__(self):
        """Generate this part of a kickstart file from the module.

        This method is required to be overridden, so we don't forget
        to use DBus modules to generate their part of a kickstart file.

        Make sure that each DBus module is used only once.
        """
        return ""

    def parse(self, args):
        """Do not parse anything.

        We can keep this method for the checks if it is possible, but
        it shouldn't parse anything.
        """
        log.warning("Command %s will be parsed in DBus module.", self.currentCmd)


class UselessCommand(RemovedCommand):
    """Kickstart command that was moved on DBus and doesn't do anything.

    Use this class to override the pykickstart command in our command map,
    when we don't want the command to do anything. It is not allowed to
    subclass this class.
    """

    def __init_subclass__(cls, **kwargs):
        raise TypeError("It is not allowed to subclass the UselessCommand class.")

    def __str__(self):
        return ""


class Authselect(RemovedCommand):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.packages = []

    def __str__(self):
        # The kickstart for this command is generated
        # by Security module in the SELinux class.
        return ""

    @property
    def fingerprint_supported(self):
        return (os.path.exists(util.getSysroot() + "/lib64/security/pam_fprintd.so") or
                os.path.exists(util.getSysroot() + "/lib/security/pam_fprintd.so"))

    def setup(self):
        security_proxy = SECURITY.get_proxy()

        if security_proxy.Authselect or not flags.automatedInstall:
            self.packages += ["authselect"]

        if security_proxy.Authconfig:
            self.packages += ["authselect-compat"]

    def execute(self):
        security_proxy = SECURITY.get_proxy()

        # Enable fingerprint option by default (#481273).
        if not flags.automatedInstall and self.fingerprint_supported:
            self._run(
                "/usr/bin/authselect",
                ["select", "sssd", "with-fingerprint", "with-silent-lastlog", "--force"],
                required=False
            )

        # Apply the authselect options from the kickstart file.
        if security_proxy.Authselect:
            self._run(
                "/usr/bin/authselect",
                security_proxy.Authselect + ["--force"]
            )

        # Apply the authconfig options from the kickstart file (deprecated).
        if security_proxy.Authconfig:
            self._run(
                "/usr/sbin/authconfig",
                ["--update", "--nostart"] + security_proxy.Authconfig
            )

    def _run(self, cmd, args, required=True):
        if not os.path.lexists(util.getSysroot() + cmd):
            if required:
                msg = _("%s is missing. Cannot setup authentication.") % cmd
                raise KickstartError(msg)
            else:
                return
        try:
            util.execInSysroot(cmd, args)
        except RuntimeError as msg:
            authselect_log.error("Error running %s %s: %s", cmd, args, msg)


class AutoPart(RemovedCommand):

    def __str__(self):
        return ""


class Bootloader(RemovedCommand):
    def __str__(self):
        return ""

    def parse(self, args):
        """Do not parse anything.

        Only validate the bootloader module.
        """
        super().parse(args)

        # Validate the attributes of the bootloader module.
        bootloader_proxy = STORAGE.get_proxy(BOOTLOADER)

        # Skip the check if the bootloader instance is not GRUB2:
        if not isinstance(get_bootloader(), GRUB2):
            return

        # Check the location support.
        if bootloader_proxy.PreferredLocation == BOOTLOADER_LOCATION_PARTITION:
            raise KickstartParseError(_("GRUB2 does not support installation to a partition."),
                                      lineno=self.lineno)

        # Check the password format.
        if bootloader_proxy.IsPasswordSet \
                and bootloader_proxy.IsPasswordEncrypted \
                and not bootloader_proxy.Password.startswith("grub.pbkdf2."):
            raise KickstartParseError(_("GRUB2 encrypted password must be in grub.pbkdf2 format."),
                                      lineno=self.lineno)


class BTRFS(COMMANDS.BTRFS):
    pass

class Realm(RemovedCommand):
    def __init__(self, *args):
        super().__init__(*args)
        self.packages = []
        self.discovered = ""

    def __str__(self):
        # The kickstart for this command is generated
        # by Security module in the SELinux class.
        return ""

    def setup(self):
        security_proxy = SECURITY.get_proxy()
        realm = apply_structure(security_proxy.Realm, RealmData())

        if not realm.name:
            return

        try:
            argv = ["discover", "--verbose"] + realm.discover_options + [realm.name]
            output = util.execWithCapture("realm", argv, filter_stderr=True)
        except OSError:
            # TODO: A lousy way of propagating what will usually be
            # 'no such realm'
            # The error message is logged by util
            return

        # Now parse the output for the required software. First line is the
        # realm name, and following lines are information as "name: value"
        self.packages = ["realmd"]
        self.discovered = ""

        lines = output.split("\n")
        if not lines:
            return
        self.discovered = lines.pop(0).strip()
        realm_log.info("Realm discovered: %s", self.discovered)
        for line in lines:
            parts = line.split(":", 1)
            if len(parts) == 2 and parts[0].strip() == "required-package":
                self.packages.append(parts[1].strip())

        realm_log.info("Realm %s needs packages %s",
                       self.discovered, ", ".join(self.packages))

    def execute(self):
        if not self.discovered:
            return

        security_proxy = SECURITY.get_proxy()
        realm = apply_structure(security_proxy.Realm, RealmData())

        for arg in realm.join_options:
            if arg.startswith("--no-password") or arg.startswith("--one-time-password"):
                pw_args = []
                break
        else:
            # no explicit password arg using implicit --no-password
            pw_args = ["--no-password"]

        argv = ["join", "--install", util.getSysroot(), "--verbose"] + pw_args + realm.join_options
        rc = -1
        try:
            rc = util.execWithRedirect("realm", argv)
        except OSError:
            pass

        if rc == 0:
            realm_log.info("Joined realm %s", realm.name)

class ClearPart(RemovedCommand):
    def __str__(self):
        storage_module_proxy = STORAGE.get_proxy()
        return storage_module_proxy.GenerateTemporaryKickstart()

class Firewall(RemovedCommand):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.packages = []

    def __str__(self):
        # The kickstart for this command is generated by the Firewall sub module
        return ""

    def setup(self):
        firewall_proxy = NETWORK.get_proxy(FIREWALL)
        if firewall_proxy.FirewallKickstarted:
            self.packages = ["firewalld"]

    def execute(self):
        args = []

        firewall_proxy = NETWORK.get_proxy(FIREWALL)
        # If --use-system-defaults was passed then the user wants
        # whatever was provided by the rpms or ostree to be the
        # default, do nothing.
        if firewall_proxy.FirewallMode == FIREWALL_USE_SYSTEM_DEFAULTS:
            firewall_log.info("ks file instructs to use system defaults for "
                              "firewall, skipping configuration.")
            return

        # enabled is None if neither --enable or --disable is passed
        # default to enabled if nothing has been set.
        if firewall_proxy.FirewallMode == FIREWALL_DISABLED:
            args += ["--disabled"]
        else:
            args += ["--enabled"]

        ssh_service_not_enabled = "ssh" not in firewall_proxy.EnabledServices
        ssh_service_not_disabled = "ssh" not in firewall_proxy.DisabledServices
        ssh_port_not_enabled = "22:tcp" not in firewall_proxy.EnabledPorts

        # always enable SSH unless the service is explicitely disabled
        if ssh_service_not_enabled and ssh_service_not_disabled and ssh_port_not_enabled:
            args += ["--service=ssh"]

        for dev in firewall_proxy.Trusts:
            args += ["--trust=%s" % (dev,)]

        for port in firewall_proxy.EnabledPorts:
            args += ["--port=%s" % (port,)]

        for remove_service in firewall_proxy.DisabledServices:
            args += ["--remove-service=%s" % (remove_service,)]

        for service in firewall_proxy.EnabledServices:
            args += ["--service=%s" % (service,)]

        cmd = "/usr/bin/firewall-offline-cmd"
        if not os.path.exists(util.getSysroot() + cmd):
            if firewall_proxy.FirewallMode == FIREWALL_ENABLED:
                msg = _("%s is missing. Cannot setup firewall.") % (cmd,)
                raise KickstartError(msg)
        else:
            util.execInSysroot(cmd, args)

class Firstboot(RemovedCommand):

    def __str__(self):
        # The kickstart for this command is generated
        # by Services module in the Services class.
        return ""

    def execute(self):
        unit_name = "initial-setup.service"
        services_proxy = SERVICES.get_proxy()
        setup_on_boot = services_proxy.SetupOnBoot

        if setup_on_boot == SETUP_ON_BOOT_DISABLED:
            log.debug("The %s service will be disabled.", unit_name)
            util.disable_service(unit_name)
            # Also tell the screen access manager, so that the fact that post installation tools
            # should be disabled propagates to the user interaction config file.
            screen_access.sam.post_install_tools_disabled = True
            return

        if not os.path.exists(os.path.join(util.getSysroot(), "lib/systemd/system/", unit_name)):
            log.debug("The %s service will not be started on first boot, because "
                      "it's unit file is not installed.", unit_name)
            return

        if setup_on_boot == SETUP_ON_BOOT_RECONFIG:
            log.debug("The %s service will run in the reconfiguration mode.", unit_name)
            # write the reconfig trigger file
            f = open(os.path.join(util.getSysroot(), "etc/reconfigSys"), "w+")
            f.close()

        log.debug("The %s service will be enabled.", unit_name)
        util.enable_service(unit_name)

class Group(COMMANDS.Group):
    def execute(self, storage, ksdata, users):
        for grp in self.groupList:
            kwargs = grp.__dict__
            kwargs.update({"root": util.getSysroot()})
            try:
                users.createGroup(grp.name, **kwargs)
            except ValueError as e:
                group_log.warning(str(e))

class Iscsi(COMMANDS.Iscsi):
    def parse(self, args):
        tg = super().parse(args)

        if tg.iface:
            if not network.wait_for_network_devices([tg.iface]):
                raise KickstartParseError(lineno=self.lineno,
                        msg=_("Network interface \"%(nic)s\" required by iSCSI \"%(iscsiTarget)s\" target is not up.") %
                             {"nic": tg.iface, "iscsiTarget": tg.target})

        mode = blivet.iscsi.iscsi.mode
        if mode == "none":
            if tg.iface:
                network_proxy = NETWORK.get_proxy()
                activated_ifaces = network_proxy.GetActivatedInterfaces()
                blivet.iscsi.iscsi.create_interfaces(activated_ifaces)
        elif ((mode == "bind" and not tg.iface)
              or (mode == "default" and tg.iface)):
            raise KickstartParseError(lineno=self.lineno,
                    msg=_("iscsi --iface must be specified (binding used) either for all targets or for none"))

        try:
            blivet.iscsi.iscsi.add_target(tg.ipaddr, tg.port, tg.user,
                                          tg.password, tg.user_in,
                                          tg.password_in,
                                          target=tg.target,
                                          iface=tg.iface)
            iscsi_log.info("added iscsi target %s at %s via %s", tg.target, tg.ipaddr, tg.iface)
        except (IOError, ValueError) as e:
            raise KickstartParseError(lineno=self.lineno, msg=str(e))

        return tg

class IscsiName(COMMANDS.IscsiName):
    def parse(self, args):
        retval = super().parse(args)

        blivet.iscsi.iscsi.initiator = self.iscsiname
        return retval

class Lang(RemovedCommand):
    def __str__(self):
        localization_proxy = LOCALIZATION.get_proxy()
        return localization_proxy.GenerateKickstart()

    def execute(self):
        localization_proxy = LOCALIZATION.get_proxy()
        task_path = localization_proxy.InstallLanguageWithTask(util.getSysroot())
        task_proxy = LOCALIZATION.get_proxy(task_path)
        sync_run_task(task_proxy)

# no overrides needed here
Eula = COMMANDS.Eula

class LogVol(COMMANDS.LogVol):
    pass

class Logging(COMMANDS.Logging):
    def execute(self):
        if anaconda_logging.logger.loglevel == anaconda_logging.DEFAULT_LEVEL:
            # not set from the command line
            level = anaconda_logging.logLevelMap[self.level]
            anaconda_logging.logger.loglevel = level
            # set log level for the "anaconda" root logger
            anaconda_logging.setHandlersLevel(get_anaconda_root_logger(), level)
            # set log level for the storage logger
            anaconda_logging.setHandlersLevel(storage_log, level)

        if anaconda_logging.logger.remote_syslog is None and len(self.host) > 0:
            # not set from the command line, ok to use kickstart
            remote_server = self.host
            if self.port:
                remote_server = "%s:%s" % (self.host, self.port)
            anaconda_logging.logger.updateRemote(remote_server)

class Mount(RemovedCommand):

    def __str__(self):
        return ""

class Network(COMMANDS.Network):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.packages = []

    def __str__(self):
        network_proxy = NETWORK.get_proxy()
        return network_proxy.GenerateKickstart()

    def parse(self, args):
        nd = super().parse(args)
        setting_only_hostname = nd.hostname and len(args) <= 2
        if not setting_only_hostname:
            if not nd.device:
                ksdevice = flags.cmdline.get('ksdevice')
                if ksdevice:
                    network_log.info('setting %s from ksdevice for missing kickstart --device', ksdevice)
                    nd.device = ksdevice
                else:
                    network_log.info('setting "link" for missing --device specification in kickstart')
                    nd.device = "link"
        return nd

    def setup(self):
        if network.get_team_devices():
            self.packages = ["teamd"]

    def execute(self, payload):
        fcoe_proxy = STORAGE.get_proxy(FCOE)
        fcoe_ifaces = network.get_devices_by_nics(fcoe_proxy.GetNics())
        overwrite = network.can_overwrite_configuration(payload)
        network_proxy = NETWORK.get_proxy()
        task_path = network_proxy.InstallNetworkWithTask(util.getSysroot(),
                                                         fcoe_ifaces,
                                                         overwrite)
        task_proxy = NETWORK.get_proxy(task_path)
        sync_run_task(task_proxy)

        if conf.system.can_change_hostname:
            hostname = network_proxy.Hostname
            if hostname != network.DEFAULT_HOSTNAME:
                network_proxy.SetCurrentHostname(hostname)



class Partition(COMMANDS.Partition):
    pass

class Raid(COMMANDS.Raid):
    pass

class RepoData(COMMANDS.RepoData):

    __mount_counter = 0

    def __init__(self, *args, **kwargs):
        """ Add enabled kwarg

            :param enabled: The repo has been enabled
            :type enabled: bool
        """
        self.enabled = kwargs.pop("enabled", True)
        self.repo_id = kwargs.pop("repo_id", None)
        self.treeinfo_origin = kwargs.pop("treeinfo_origin", False)
        self.partition = kwargs.pop("partition", None)
        self.iso_path = kwargs.pop("iso_path", None)

        self.mount_dir_suffix = kwargs.pop("mount_dir_suffix", None)

        super().__init__(*args, **kwargs)

    @classmethod
    def create_copy(cls, other):
        return cls(name=other.name,
                   baseurl=other.baseurl,
                   mirrorlist=other.mirrorlist,
                   metalink=other.metalink,
                   proxy=other.proxy,
                   enabled=other.enabled,
                   treeinfo_origin=other.treeinfo_origin,
                   partition=other.partition,
                   iso_path=other.iso_path,
                   mount_dir_suffix=other.mount_dir_suffix)

    def generate_mount_dir(self):
        """Generate persistent mount directory suffix

        This is valid only for HD repositories
        """
        if self.is_harddrive_based() and self.mount_dir_suffix is None:
            self.mount_dir_suffix = "addition_" + self._generate_mount_dir_suffix()

    @classmethod
    def _generate_mount_dir_suffix(cls):
        suffix = str(cls.__mount_counter)
        cls.__mount_counter += 1
        return suffix

    def __str__(self):
        """Don't output disabled repos"""
        if self.enabled:
            return super().__str__()
        else:
            return ''

    def is_harddrive_based(self):
        return self.partition is not None

class ReqPart(COMMANDS.ReqPart):
    pass

class RootPw(RemovedCommand):

    def __str__(self):
        users_proxy = USERS.get_proxy()
        return users_proxy.GenerateTemporaryKickstart()

    def execute(self, storage, ksdata, users):

        users_proxy = USERS.get_proxy()

        if flags.automatedInstall and not users_proxy.IsRootPasswordSet and not users_proxy.IsRootpwKickstarted:
            # Lock the root password if during an installation with kickstart
            # the root password is empty & not specififed as empty in the kickstart
            # (seen == False) via the rootpw command.
            # Note that kickstart is actually the only way to specify an empty
            # root password - we don't allow that via the UI.
            users_proxy.SetRootAccountLocked(True)
        elif not flags.automatedInstall and not users_proxy.IsRootPasswordSet:
            # Also lock the root password if it was not set during interactive installation.
            users_proxy.SetRootAccountLocked(True)

        users.setRootPassword(users_proxy.RootPassword,
                              users_proxy.IsRootPasswordCrypted,
                              users_proxy.IsRootAccountLocked,
                              None,
                              util.getSysroot())

class SELinux(RemovedCommand):

    SELINUX_STATES = {
        SELINUX_DISABLED: "disabled",
        SELINUX_ENFORCING: "enforcing",
        SELINUX_PERMISSIVE: "permissive"
    }

    def __str__(self):
        security_proxy = SECURITY.get_proxy()
        return security_proxy.GenerateKickstart()

    def execute(self):
        security_proxy = SECURITY.get_proxy()
        selinux = security_proxy.SELinux

        if selinux == SELINUX_DEFAULT:
            selinux_log.debug("Use SELinux default configuration.")
            return

        if selinux not in self.SELINUX_STATES:
            selinux_log.error("Unknown SELinux state for %s.", selinux)
            return

        try:
            selinux_cfg = SimpleConfigFile(util.getSysroot() + "/etc/selinux/config")
            selinux_cfg.read()
            selinux_cfg.set(("SELINUX", self.SELINUX_STATES[selinux]))
            selinux_cfg.write()
        except IOError as msg:
            selinux_log.error("SELinux configuration failed: %s", msg)

class Services(RemovedCommand):

    def __str__(self):
        services_proxy = SERVICES.get_proxy()
        return services_proxy.GenerateKickstart()

    def execute(self):
        services_proxy = SERVICES.get_proxy()

        for svc in services_proxy.DisabledServices:
            log.debug("Disabling the service %s.", svc)
            util.disable_service(svc)

        for svc in services_proxy.EnabledServices:
            log.debug("Enabling the service %s.", svc)
            util.enable_service(svc)

class SshKey(COMMANDS.SshKey):
    def execute(self, storage, ksdata, users):
        for usr in self.sshUserList:
            users.setUserSshKey(usr.username, usr.key)

class Timezone(RemovedCommand):

    def __init__(self, *args):
        super().__init__(*args)
        self.packages = []

    def __str__(self):
        timezone_proxy = TIMEZONE.get_proxy()
        return timezone_proxy.GenerateKickstart()

    def setup(self, ksdata):
        timezone_proxy = TIMEZONE.get_proxy()
        services_proxy = SERVICES.get_proxy()

        enabled_services = services_proxy.EnabledServices
        disabled_services = services_proxy.DisabledServices

        # do not install and use NTP package
        if not timezone_proxy.NTPEnabled or NTP_PACKAGE in ksdata.packages.excludedList:
            if util.service_running(NTP_SERVICE) and conf.system.can_set_time_synchronization:
                ret = util.stop_service(NTP_SERVICE)
                if ret != 0:
                    timezone_log.error("Failed to stop NTP service")

            if NTP_SERVICE not in disabled_services:
                disabled_services.append(NTP_SERVICE)
                services_proxy.SetDisabledServices(disabled_services)
        # install and use NTP package
        else:
            if not util.service_running(NTP_SERVICE) and conf.system.can_set_time_synchronization:
                ret = util.start_service(NTP_SERVICE)
                if ret != 0:
                    timezone_log.error("Failed to start NTP service")

            self.packages.append(NTP_PACKAGE)

            if not NTP_SERVICE in enabled_services and \
                    not NTP_SERVICE in disabled_services:
                enabled_services.append(NTP_SERVICE)
                services_proxy.SetEnabledServices(enabled_services)

    def execute(self):
        # get the DBus proxies
        timezone_proxy = TIMEZONE.get_proxy()

        # write out timezone configuration
        kickstart_timezone = timezone_proxy.Timezone

        if not timezone.is_valid_timezone(kickstart_timezone):
            # this should never happen, but for pity's sake
            timezone_log.warning("Timezone %s set in kickstart is not valid, falling "
                                 "back to default (America/New_York).", kickstart_timezone)
            timezone_proxy.SetTimezone("America/New_York")

        timezone.write_timezone_config(timezone_proxy, util.getSysroot())

        # write out NTP configuration (if set) and --nontp is not used
        kickstart_ntp_servers = timezone_proxy.NTPServers

        if timezone_proxy.NTPEnabled and kickstart_ntp_servers:
            chronyd_conf_path = os.path.normpath(util.getSysroot() + ntp.NTP_CONFIG_FILE)
            pools, servers = ntp.internal_to_pools_and_servers(kickstart_ntp_servers)
            if os.path.exists(chronyd_conf_path):
                timezone_log.debug("Modifying installed chrony configuration")
                try:
                    ntp.save_servers_to_config(pools, servers, conf_file_path=chronyd_conf_path)
                except ntp.NTPconfigError as ntperr:
                    timezone_log.warning("Failed to save NTP configuration: %s", ntperr)
            # use chrony conf file from installation environment when
            # chrony is not installed (chrony conf file is missing)
            else:
                timezone_log.debug("Creating chrony configuration based on the "
                                   "configuration from installation environment")
                try:
                    ntp.save_servers_to_config(pools, servers,
                                               conf_file_path=ntp.NTP_CONFIG_FILE,
                                               out_file_path=chronyd_conf_path)
                except ntp.NTPconfigError as ntperr:
                    timezone_log.warning("Failed to save NTP configuration without chrony package: %s", ntperr)

class User(COMMANDS.User):
    def execute(self, storage, ksdata, users):

        for usr in self.userList:
            kwargs = usr.__dict__
            kwargs.update({"root": util.getSysroot()})

            # If the user password came from a kickstart and it is blank we
            # need to make sure the account is locked, not created with an
            # empty password.
            if self.seen and kwargs.get("password", "") == "":
                kwargs["password"] = None
            try:
                users.createUser(usr.name, **kwargs)
            except ValueError as e:
                user_log.warning(str(e))

class VolGroup(COMMANDS.VolGroup):
    pass

class XConfig(RemovedCommand):

    def __str__(self):
        # The kickstart for this command is generated
        # by Services module in the Services class.
        return ""

    def execute(self):
        desktop = Desktop()
        services_proxy = SERVICES.get_proxy()
        default_target = services_proxy.DefaultTarget
        default_desktop = services_proxy.DefaultDesktop

        if default_target:
            log.debug("Using the default target %s.", default_target)
            desktop.default_target = default_target

        if default_desktop:
            log.debug("Using the default desktop %s.", default_desktop)
            desktop.desktop = default_desktop

        desktop.write()


class Snapshot(COMMANDS.Snapshot):
    """The snapshot kickstart command.

    The command will be parsed here and in the Storage module for now.
    The data don't change, so it is ok, to use the Snapshot module
    when we can.
    """

    def __str__(self):
        # Provided by the Storage module.
        return ""

    def get_requests(self, when):
        """Get a list of snapshot requests of the given type.

        :param when: a type of the requests
        :returns: a list of requests
        """
        return [request for request in self.dataList() if request.when == when]

    def verify_requests(self, storage, constraints, report_error, report_warning):
        """Verify the validity of snapshot requests for the given storage.

        This is a callback for the storage checker.

        :param storage: a storage to check
        :param constraints: a dictionary of constraints
        :param report_error: a function for error reporting
        :param report_warning: a function for warning reporting
        """
        # FIXME: This is an ugly temporary workaround for UI.
        from pyanaconda.modules.storage.snapshot import SnapshotModule
        SnapshotModule.verify_requests(self, storage, constraints, report_error, report_warning)


class Keyboard(RemovedCommand):

    def __str__(self):
        # The kickstart for this command is generated
        # by Localization module in the Lang class.
        return ""

    def execute(self):
        localization_proxy = LOCALIZATION.get_proxy()
        keyboard.write_keyboard_config(localization_proxy, util.getSysroot())


###
### %anaconda Section
###
class AnacondaSectionHandler(BaseHandler):
    """A handler for only the anaconda ection's commands."""
    commandMap = {
        "pwpolicy": F22_PwPolicy
    }

    dataMap = {
        "PwPolicyData": F22_PwPolicyData
    }

    def __init__(self):
        super().__init__(mapping=self.commandMap, dataMapping=self.dataMap)

    def __str__(self):
        """Return the %anaconda section"""
        retval = ""
        # This dictionary should only be modified during __init__, so if it
        # changes during iteration something has gone horribly wrong.
        lst = sorted(self._writeOrder.keys())
        for prio in lst:
            for obj in self._writeOrder[prio]:
                retval += str(obj)

        if retval:
            retval = "\n%anaconda\n" + retval + "%end\n"
        return retval

class AnacondaSection(Section):
    """A section for anaconda specific commands."""
    sectionOpen = "%anaconda"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cmdno = 0

    def handleLine(self, line):
        if not self.handler:
            return

        self.cmdno += 1
        args = shlex.split(line, comments=True)
        self.handler.currentCmd = args[0]
        self.handler.currentLine = self.cmdno
        return self.handler.dispatcher(args, self.cmdno)

    def handleHeader(self, lineno, args):
        """Process the arguments to the %anaconda header."""
        Section.handleHeader(self, lineno, args)

    def finalize(self):
        """Let %anaconda know no additional data will come."""
        Section.finalize(self)

###
### HANDLERS
###

# This is just the latest entry from pykickstart.handlers.control with all the
# classes we're overriding in place of the defaults.
commandMap = {
    "auth": UselessCommand,
    "authconfig": UselessCommand,
    "authselect": Authselect,
    "autopart": AutoPart,
    "btrfs": BTRFS,
    "bootloader": Bootloader,
    "clearpart": ClearPart,
    "eula": Eula,
    "fcoe": UselessCommand,
    "firewall": Firewall,
    "firstboot": Firstboot,
    "group": Group,
    "ignoredisk": UselessCommand,
    "iscsi": Iscsi,
    "iscsiname": IscsiName,
    "keyboard": Keyboard,
    "lang": Lang,
    "logging": Logging,
    "logvol": LogVol,
    "mount": Mount,
    "network": Network,
    "nvdimm": UselessCommand,
    "part": Partition,
    "partition": Partition,
    "raid": Raid,
    "realm": Realm,
    "reqpart": ReqPart,
    "rootpw": RootPw,
    "selinux": SELinux,
    "services": Services,
    "sshkey": SshKey,
    "skipx": UselessCommand,
    "snapshot": Snapshot,
    "timezone": Timezone,
    "user": User,
    "volgroup": VolGroup,
    "xconfig": XConfig,
    "zerombr": UselessCommand,
    "zfcp": UselessCommand,
}

dataMap = {
    "RepoData": RepoData,
}

superclass = returnClassForVersion(VERSION)

class AnacondaKSHandler(superclass):
    AddonClassType = AddonData

    def __init__(self, addon_paths=None, commandUpdates=None, dataUpdates=None):
        if addon_paths is None:
            addon_paths = []

        if commandUpdates is None:
            commandUpdates = commandMap

        if dataUpdates is None:
            dataUpdates = dataMap

        super().__init__(commandUpdates=commandUpdates, dataUpdates=dataUpdates)
        self.onPart = {}

        # collect all kickstart addons for anaconda to addons dictionary
        # which maps addon_id to it's own data structure based on BaseData
        # with execute method
        addons = {}

        # collect all AddonData subclasses from
        # for p in addon_paths: <p>/<plugin id>/ks/*.(py|so)
        # and register them under <plugin id> name
        for module_name, path in addon_paths:
            addon_id = os.path.basename(os.path.dirname(os.path.abspath(path)))
            if not os.path.isdir(path):
                continue

            classes = util.collect(module_name, path,
                                   lambda cls: issubclass(cls, self.AddonClassType))
            if classes:
                addons[addon_id] = classes[0](name=addon_id)

        # Prepare the final structures for 3rd party addons
        self.addons = AddonRegistry(addons)

        # The %anaconda section uses its own handler for a limited set of commands
        self.anaconda = AnacondaSectionHandler()

    def __str__(self):
        return super().__str__() + "\n" + str(self.addons) + str(self.anaconda)

class AnacondaPreParser(KickstartParser):
    # A subclass of KickstartParser that only looks for %pre scripts and
    # sets them up to be run.  All other scripts and commands are ignored.
    def __init__(self, handler, followIncludes=True, errorsAreFatal=True,
                 missingIncludeIsFatal=True):
        super().__init__(handler, missingIncludeIsFatal=False)

    def handleCommand(self, lineno, args):
        pass

    def setupSections(self):
        self.registerSection(PreScriptSection(self.handler, dataObj=AnacondaKSScript))
        self.registerSection(NullSection(self.handler, sectionOpen="%pre-install"))
        self.registerSection(NullSection(self.handler, sectionOpen="%post"))
        self.registerSection(NullSection(self.handler, sectionOpen="%onerror"))
        self.registerSection(NullSection(self.handler, sectionOpen="%traceback"))
        self.registerSection(NullSection(self.handler, sectionOpen="%packages"))
        self.registerSection(NullSection(self.handler, sectionOpen="%addon"))
        self.registerSection(NullSection(self.handler.anaconda, sectionOpen="%anaconda"))


class AnacondaKSParser(KickstartParser):
    def __init__(self, handler, followIncludes=True, errorsAreFatal=True,
                 missingIncludeIsFatal=True, scriptClass=AnacondaKSScript):
        self.scriptClass = scriptClass
        super().__init__(handler)

    def handleCommand(self, lineno, args):
        if not self.handler:
            return

        return KickstartParser.handleCommand(self, lineno, args)

    def setupSections(self):
        self.registerSection(PreScriptSection(self.handler, dataObj=self.scriptClass))
        self.registerSection(PreInstallScriptSection(self.handler, dataObj=self.scriptClass))
        self.registerSection(PostScriptSection(self.handler, dataObj=self.scriptClass))
        self.registerSection(TracebackScriptSection(self.handler, dataObj=self.scriptClass))
        self.registerSection(OnErrorScriptSection(self.handler, dataObj=self.scriptClass))
        self.registerSection(PackageSection(self.handler))
        self.registerSection(AddonSection(self.handler))
        self.registerSection(AnacondaSection(self.handler.anaconda))

def preScriptPass(f):
    # The first pass through kickstart file processing - look for %pre scripts
    # and run them.  This must come in a separate pass in case a script
    # generates an included file that has commands for later.
    ksparser = AnacondaPreParser(AnacondaKSHandler())

    with check_kickstart_error():
        ksparser.readKickstart(f)

    # run %pre scripts
    runPreScripts(ksparser.handler.scripts)

def parseKickstart(f, strict_mode=False, pass_to_boss=False):
    # preprocessing the kickstart file has already been handled in initramfs.

    addon_paths = collect_addon_paths(ADDON_PATHS)
    handler = AnacondaKSHandler(addon_paths["ks"])
    ksparser = AnacondaKSParser(handler)

    # So that drives onlined by these can be used in the ks file
    blivet.iscsi.iscsi.startup()
    # Note we do NOT call dasd.startup() here, that does not online drives, but
    # only checks if they need formatting, which requires zerombr to be known

    kswarnings = []
    ksmodule = "pykickstart"
    kscategories = (UserWarning, SyntaxWarning, DeprecationWarning)
    showwarning = warnings.showwarning

    def ksshowwarning(message, category, filename, lineno, file=None, line=None):
        # Print the warning with default function.
        showwarning(message, category, filename, lineno, file, line)
        # Collect pykickstart warnings.
        if ksmodule in filename and issubclass(category, kscategories):
            kswarnings.append(message)

    try:
        # Process warnings differently in this part.
        with warnings.catch_warnings():

            # Set up the warnings module.
            warnings.showwarning = ksshowwarning

            for category in kscategories:
                warnings.filterwarnings(action="always", module=ksmodule, category=category)

            # Parse the kickstart file in DBus modules.
            if pass_to_boss:
                boss = BOSS.get_proxy()

                boss.SplitKickstart(f)
                errors = boss.DistributeKickstart()

                if errors:
                    message = "\n\n".join("{error_message}".format_map(e) for e in errors)
                    raise KickstartError(message)

            # Parse the kickstart file in anaconda.
            ksparser.readKickstart(f)

            # Process pykickstart warnings in the strict mode:
            if strict_mode and kswarnings:
                raise KickstartError("Please modify your kickstart file to fix the warnings "
                                     "or remove the `ksstrict` option.")

    except (KickstartError, SplitKickstartError) as e:
        # We do not have an interface here yet, so we cannot use our error
        # handling callback.
        parsing_log.error(e)

        # Print kickstart warnings in the strict mode.
        if strict_mode and kswarnings:
            print(_("\nSome warnings occurred during reading the kickstart file:"))
            for w in kswarnings:
                print(str(w).strip())

        # Print an error and terminate.
        print(_("\nAn error occurred during reading the kickstart file:"
                "\n%s\n\nThe installer will now terminate.") % str(e).strip())

        util.ipmi_report(IPMI_ABORTED)
        time.sleep(10)
        sys.exit(1)

    return handler

def appendPostScripts(ksdata):
    scripts = ""

    # Read in all the post script snippets to a single big string.
    for fn in glob.glob("/usr/share/anaconda/post-scripts/*ks"):
        f = open(fn, "r")
        scripts += f.read()
        f.close()

    # Then parse the snippets against the existing ksdata.  We can do this
    # because pykickstart allows multiple parses to save their data into a
    # single data object.  Errors parsing the scripts are a bug in anaconda,
    # so just raise an exception.
    ksparser = AnacondaKSParser(ksdata, scriptClass=AnacondaInternalScript)
    ksparser.readKickstartFromString(scripts, reset=False)

def runPostScripts(scripts):
    postScripts = [s for s in scripts if s.type == KS_SCRIPT_POST]

    if len(postScripts) == 0:
        return

    script_log.info("Running kickstart %%post script(s)")
    for script in postScripts:
        script.run(util.getSysroot())
    script_log.info("All kickstart %%post script(s) have been run")

def runPreScripts(scripts):
    preScripts = [s for s in scripts if s.type == KS_SCRIPT_PRE]

    if len(preScripts) == 0:
        return

    script_log.info("Running kickstart %%pre script(s)")
    stdoutLog.info(_("Running pre-installation scripts"))

    for script in preScripts:
        script.run("/")

    script_log.info("All kickstart %%pre script(s) have been run")

def runPreInstallScripts(scripts):
    preInstallScripts = [s for s in scripts if s.type == KS_SCRIPT_PREINSTALL]

    if len(preInstallScripts) == 0:
        return

    script_log.info("Running kickstart %%pre-install script(s)")

    for script in preInstallScripts:
        script.run("/")

    script_log.info("All kickstart %%pre-install script(s) have been run")

def runTracebackScripts(scripts):
    script_log.info("Running kickstart %%traceback script(s)")
    for script in filter(lambda s: s.type == KS_SCRIPT_TRACEBACK, scripts):
        script.run("/")
    script_log.info("All kickstart %%traceback script(s) have been run")
