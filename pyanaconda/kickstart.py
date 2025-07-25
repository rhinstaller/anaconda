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
import sys
import time
import warnings
from contextlib import contextmanager

from pykickstart.base import KickstartCommand, RemovedCommand
from pykickstart.constants import KS_SCRIPT_PRE
from pykickstart.errors import KickstartError, KickstartParseWarning
from pykickstart.ko import KickstartObject
from pykickstart.parser import KickstartParser
from pykickstart.parser import Script as KSScript
from pykickstart.sections import (
    NullSection,
    OnErrorScriptSection,
    PostScriptSection,
    PreInstallScriptSection,
    PreScriptSection,
    Section,
    TracebackScriptSection,
)
from pykickstart.version import returnClassForVersion

from pyanaconda.anaconda_loggers import get_module_logger, get_stdout_logger
from pyanaconda.core import util
from pyanaconda.core.constants import IPMI_ABORTED
from pyanaconda.core.i18n import _
from pyanaconda.core.kickstart import VERSION
from pyanaconda.core.kickstart.scripts import run_script
from pyanaconda.core.kickstart.specification import KickstartSpecification
from pyanaconda.errors import ScriptError, errorHandler
from pyanaconda.flags import flags
from pyanaconda.modules.common.constants.services import BOSS
from pyanaconda.modules.common.structures.kickstart import KickstartReport

log = get_module_logger(__name__)
stdoutLog = get_stdout_logger()

# kickstart parsing and kickstart script
script_log = log.getChild("script")
parsing_log = log.getChild("parsing")


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
    def run(self, chroot):
        rc, log_file = run_script(self, chroot)
        if self.errorOnFail and rc != 0:
            err = ""
            with open(log_file, "r") as fp:
                err = "".join(fp.readlines())

            if self.type == KS_SCRIPT_PRE:
                # Show error dialog even for non-interactive
                flags.ksprompt = True

                errorHandler.cb(ScriptError(self.lineno, err))
                util.ipmi_report(IPMI_ABORTED)
                sys.exit(0)
            else:
                return self.lineno, err


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

class UselessSection(Section):
    """Kickstart section that was moved on DBus and doesn't do anything."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sectionOpen = kwargs.get("sectionOpen")


class UselessCommand(KickstartCommand):
    """Kickstart command that was moved on DBus and doesn't do anything.

    Use this class to override the pykickstart command in our command map,
    when we don't want the command to do anything.
    """

    def __str__(self):
        """Generate this part of a kickstart file from the DBus module."""
        return ""

    def parse(self, args):
        """Do not parse anything.

        We can keep this method for the checks if it is possible, but
        it shouldn't parse anything.
        """
        log.warning("Command %s will be parsed in DBus module.", self.currentCmd)


class UselessObject(KickstartObject):
    """Kickstart object that was moved on DBus and doesn't do anything."""

    def __str__(self):
        """Generate this part of a kickstart file from the DBus module."""
        return ""

###
### HANDLERS
###

# This is just the latest entry from pykickstart.handlers.control with all the
# classes we're overriding in place of the defaults.
class AnacondaKickstartSpecification(KickstartSpecification):
    """The kickstart specification of the main process."""

    commands = {
    }

    @classmethod
    def generate_command_map(cls, handler):
        """Generate a command map.

        :param handler: a kickstart handler
        :return: a map of command overrides
        """
        command_map = dict(cls.commands)

        for name, command in handler.commandMap.items():
            # Ignore removed commands.
            if issubclass(command, RemovedCommand):
                continue

            # Mark unspecified commands as useless.
            if name not in command_map:
                command_map[name] = UselessCommand

        return command_map

    @classmethod
    def generate_data_map(cls, handler):
        """Generate a data map.

        :param handler: a kickstart handler
        :return: a map of data overrides
        """
        return dict(cls.commands_data)


# Get the kickstart handler for the specified version.
superclass = returnClassForVersion(VERSION)

# Generate the command and data overrides.
specification = AnacondaKickstartSpecification
commandMap = specification.generate_command_map(superclass)
dataMap = specification.generate_data_map(superclass)


class AnacondaKSHandler(superclass):

    def __init__(self, commandUpdates=None, dataUpdates=None):
        if commandUpdates is None:
            commandUpdates = commandMap

        if dataUpdates is None:
            dataUpdates = dataMap

        super().__init__(commandUpdates=commandUpdates, dataUpdates=dataUpdates)
        self.onPart = {}

        # The %packages section is handled by the DBus module.
        self.packages = UselessObject()

    def __str__(self):
        proxy = BOSS.get_proxy()
        modules = proxy.GenerateKickstart().strip()
        return super().__str__() + "\n" + modules


class AnacondaPreParser(KickstartParser):
    # A subclass of KickstartParser that only looks for %pre scripts and
    # sets them up to be run.  All other scripts and commands are ignored.
    def __init__(self, handler):
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
        self.registerSection(NullSection(self.handler, sectionOpen="%certificate"))


class AnacondaKSParser(KickstartParser):
    def __init__(self, handler, scriptClass=AnacondaKSScript):
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
        self.registerSection(UselessSection(self.handler, sectionOpen="%packages"))
        self.registerSection(UselessSection(self.handler, sectionOpen="%addon"))
        self.registerSection(UselessSection(self.handler, sectionOpen="%certificate"))


def preScriptPass(f):
    # The first pass through kickstart file processing - look for %pre scripts
    # and run them.  This must come in a separate pass in case a script
    # generates an included file that has commands for later.
    ksparser = AnacondaPreParser(AnacondaKSHandler())

    with check_kickstart_error():
        ksparser.readKickstart(f)

    # run %pre scripts
    runPreScripts(ksparser.handler.scripts)


def parseKickstart(handler, f, strict_mode=False):
    # preprocessing the kickstart file has already been handled in initramfs.

    ksparser = AnacondaKSParser(handler)
    kswarnings = []
    showwarning = warnings.showwarning

    def ksshowwarning(message, category, filename, lineno, file=None, line=None):
        # Print the warning with default function.
        showwarning(message, category, filename, lineno, file, line)
        # Collect pykickstart warnings.
        if issubclass(category, KickstartParseWarning):
            kswarnings.append(message)

    try:
        # Process warnings differently in this part.
        with warnings.catch_warnings():

            # Set up the warnings module.
            warnings.showwarning = ksshowwarning
            warnings.simplefilter("always", category=KickstartParseWarning)

            # Parse the kickstart file in DBus modules.
            boss = BOSS.get_proxy()
            report = KickstartReport.from_structure(
                boss.ReadKickstartFile(f)
            )
            for warn in report.warning_messages:
                warnings.warn(warn.message, KickstartParseWarning)
            if not report.is_valid():
                message = "\n\n".join(map(str, report.error_messages))
                raise KickstartError(message)

            # Parse the kickstart file in anaconda.
            ksparser.readKickstart(f)

            # Print kickstart warnings and error out if in strict mode
            if kswarnings:
                print(_("\nSome warnings occurred during reading the kickstart file:"))
                for w in kswarnings:
                    print(str(w).strip())
                if strict_mode:
                    raise KickstartError("Please modify your kickstart file to fix the warnings "
                                         "or remove the `ksstrict` option.")

    except KickstartError as e:
        # We do not have an interface here yet, so we cannot use our error
        # handling callback.
        parsing_log.error(e)

        # Print an error and terminate.
        print(_("\nAn error occurred during reading the kickstart file:"
                "\n%s\n\nThe installer will now terminate.") % str(e).strip())

        util.ipmi_report(IPMI_ABORTED)
        time.sleep(10)
        sys.exit(1)


def appendPostScripts(ksdata):
    scripts = ""

    # Read in all the post script snippets to a single big string.
    for fn in sorted(glob.glob("/usr/share/anaconda/post-scripts/*ks")):
        f = open(fn, "r")
        scripts += f.read()
        f.close()

    # Then parse the snippets against the existing ksdata.  We can do this
    # because pykickstart allows multiple parses to save their data into a
    # single data object.  Errors parsing the scripts are a bug in anaconda,
    # so just raise an exception.
    ksparser = AnacondaKSParser(ksdata, scriptClass=AnacondaInternalScript)
    ksparser.readKickstartFromString(scripts, reset=False)

def runPreScripts(scripts):
    preScripts = [s for s in scripts if s.type == KS_SCRIPT_PRE]

    if len(preScripts) == 0:
        return

    script_log.info("Running kickstart %%pre script(s)")
    stdoutLog.info(_("Running pre-installation scripts"))

    for script in preScripts:
        script.run("/")

    script_log.info("All kickstart %%pre script(s) have been run")
