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

from contextlib import contextmanager

from pyanaconda import keyboard, network, ntp, timezone
from pyanaconda.core import util
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.kickstart import VERSION, commands as COMMANDS
from pyanaconda.addons import AddonSection, AddonData, AddonRegistry
from pyanaconda.core.constants import IPMI_ABORTED
from pyanaconda.errors import ScriptError, errorHandler
from pyanaconda.flags import flags
from pyanaconda.core.i18n import _
from pyanaconda.modules.common.errors.kickstart import SplitKickstartError
from pyanaconda.modules.common.constants.services import BOSS, TIMEZONE, LOCALIZATION, SECURITY, \
    USERS, SERVICES, STORAGE, NETWORK
from pyanaconda.modules.common.constants.objects import FCOE
from pyanaconda.modules.common.task import sync_run_task
from pyanaconda.pwpolicy import F22_PwPolicy, F22_PwPolicyData
from pyanaconda.timezone import NTP_PACKAGE, NTP_SERVICE

from pykickstart.base import BaseHandler, KickstartCommand
from pykickstart.constants import KS_SCRIPT_POST, KS_SCRIPT_PRE, KS_SCRIPT_TRACEBACK, KS_SCRIPT_PREINSTALL
from pykickstart.errors import KickstartError
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
        return (os.path.exists(conf.target.system_root + "/lib64/security/pam_fprintd.so") or
                os.path.exists(conf.target.system_root + "/lib/security/pam_fprintd.so"))

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
        if not os.path.lexists(conf.target.system_root + cmd):
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


class BTRFS(COMMANDS.BTRFS):
    pass

class ClearPart(RemovedCommand):
    def __str__(self):
        storage_module_proxy = STORAGE.get_proxy()
        return storage_module_proxy.GenerateKickstart()

class Lang(RemovedCommand):
    def __str__(self):
        localization_proxy = LOCALIZATION.get_proxy()
        return localization_proxy.GenerateKickstart()

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

    def execute(self, payload):
        fcoe_proxy = STORAGE.get_proxy(FCOE)
        fcoe_nics = fcoe_proxy.GetNics()
        fcoe_ifaces = [dev.device_name for dev in network.get_supported_devices()
                       if dev.device_name in fcoe_nics]
        overwrite = network.can_overwrite_configuration(payload)
        network_proxy = NETWORK.get_proxy()

        task_path = network_proxy.ConfigureActivationOnBootWithTask(fcoe_ifaces)
        task_proxy = NETWORK.get_proxy(task_path)
        sync_run_task(task_proxy)

        task_path = network_proxy.InstallNetworkWithTask(overwrite)
        task_proxy = NETWORK.get_proxy(task_path)
        sync_run_task(task_proxy)

        task_path = network_proxy.ConfigureHostnameWithTask(overwrite)
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
        return users_proxy.GenerateKickstart()

class SELinux(RemovedCommand):

    def __str__(self):
        security_proxy = SECURITY.get_proxy()
        return security_proxy.GenerateKickstart()

class Services(RemovedCommand):

    def __str__(self):
        services_proxy = SERVICES.get_proxy()
        return services_proxy.GenerateKickstart()


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

        timezone.write_timezone_config(timezone_proxy, conf.target.system_root)

        # write out NTP configuration (if set) and --nontp is not used
        kickstart_ntp_servers = timezone_proxy.NTPServers

        if timezone_proxy.NTPEnabled and kickstart_ntp_servers:
            chronyd_conf_path = os.path.normpath(conf.target.system_root + ntp.NTP_CONFIG_FILE)
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

class VolGroup(COMMANDS.VolGroup):
    pass

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
        keyboard.write_keyboard_config(localization_proxy, conf.target.system_root)


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
    "bootloader": UselessCommand,
    "clearpart": ClearPart,
    "eula": Eula,
    "fcoe": UselessCommand,
    "firewall": UselessCommand,
    "firstboot": UselessCommand,
    "group" : UselessCommand,
    "ignoredisk": UselessCommand,
    "iscsi": UselessCommand,
    "iscsiname": UselessCommand,
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
    "realm": UselessCommand,
    "reqpart": ReqPart,
    "rootpw": RootPw,
    "selinux": SELinux,
    "services": Services,
    "sshkey" : UselessCommand,
    "skipx": UselessCommand,
    "snapshot": Snapshot,
    "timezone": Timezone,
    "user": UselessCommand,
    "volgroup": VolGroup,
    "xconfig": UselessCommand,
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

def parseKickstart(handler, f, strict_mode=False, pass_to_boss=False):
    # preprocessing the kickstart file has already been handled in initramfs.

    ksparser = AnacondaKSParser(handler)
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
        script.run(conf.target.system_root)
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
