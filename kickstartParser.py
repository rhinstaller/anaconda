#
# kickstartParser.py:  Unified kickstart file parser for anaconda and
# s-c-kickstart.
#
# Chris Lumens <clumens@redhat.com>
#
# Copyright 2005 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# general public license.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import sys
import iutil
import string
from optparse import OptionParser, Option
from rhpl.translate import _, N_

import logging
log = logging.getLogger("anaconda")

STATE_COMMANDS = 1
STATE_PACKAGES = 2
STATE_SCRIPT_HDR = 3
STATE_PRE = 4
STATE_POST = 5
STATE_TRACEBACK = 6

KS_MISSING_PROMPT = 0
KS_MISSING_IGNORE = 1

class KickstartError(Exception):
    def __init__(self, val = ""):
        self.value = val

    def __str__ (self):
        return self.value

class KickstartParseError(KickstartError):
    def __init__(self, line = ""):
        self.value = N_("There was a problem reading the following line "
                        "from the kickstart file.  This could be due to "
                        "an error on the line or using a keyword that no "
                        "longer exists.\n\n%s") % line

    def __str__(self):
        return self.value

class KickstartValueError(KickstartError):
    def __init__(self, val = ""):
        self.value = val

    def __str__ (self):
        return self.value

class KSAppendException(KickstartError):
    def __init__(self, s=""):
	self.str = s

    def __str__(self):
	return self.str

class KSOptionParser(OptionParser):
    def exit(self, status=0, msg=None):
        pass

    def error(self, msg):
        raise KickstartParserError, msg

    def __init__(self, map={}):
        self.map = map
        OptionParser.__init__(self, option_class=MappableOption)

# do i belong somewhere else?
class MappableOption(Option):
    ACTIONS = Option.ACTIONS + ("map", "map_extend",)
    STORE_ACTIONS = Option.STORE_ACTIONS + ("map", "map_extend",)
    TYPED_ACTIONS = Option.TYPED_ACTIONS + ("map", "map_extend",)

    def take_action(self, action, dest, opt, value, values, parser):
        if action == "map":
            values.ensure_value(dest, parser.map[opt.lstrip('-')])
        elif action == "map_extend":
            values.ensure_value(dest, []).extend(parser.map[opt.lstrip('-')])
        else:
            Option.take_action(self, action, dest, opt, value, values, parser)

# move run into anaconda specific stuff, subclass, etc.
class Script:
    def __repr__(self):
        str = ("(s: '%s' i: %s c: %d)") %  \
              (self.script, self.interp, self.inChroot)
        return string.replace(str, "\n", "|")

    def __init__(self, script, interp, inChroot, logfile = None,
                 errorOnFail = False):
        self.script = script
        self.interp = interp
        self.inChroot = inChroot
        self.logfile = logfile
        self.errorOnFail = errorOnFail

    def run(self, chroot, serial, intf = None):
        scriptRoot = "/"
        if self.inChroot:
            scriptRoot = chroot

        path = scriptRoot + "/tmp/ks-script"

        f = open(path, "w")
        f.write(self.script)
        f.close()
        os.chmod(path, 0700)

        if self.logfile is not None:
            messages = self.logfile
        elif serial:
            messages = "/tmp/ks-script.log"
        else:
            messages = "/dev/tty3"

        rc = iutil.execWithRedirect(self.interp,
                                    [self.interp,"/tmp/ks-script"],
                                    stdout = messages, stderr = messages,
                                    root = scriptRoot)

        # Always log an error.  Only fail if we have a handle on the
        # windowing system and the kickstart file included --erroronfail.
        if rc != 0:
            log.error("Error code %s encountered running a kickstart %%pre/%%post script", rc)

            if self.errorOnFail:
                if intf != None:
                    intf.messageWindow(_("Scriptlet Failure"),
                                       _("There was an error running the "
                                         "scriptlet.  You may examine the "
                                         "output in %s.  This is a fatal error "
                                         "and your install will be aborted.\n\n"
                                         "Press the OK button to reboot your "
                                         "system.") % (messages,))
                sys.exit(0)

        os.unlink(path)

class KickstartHandlers:
    handlers = { "auth"	        : self.doAuthconfig,
                 "authconfig"   : self.doAuthconfig,
                 "autopart"     : self.doAutoPart,
                 "autostep"     : self.doAutoStep,
                 "bootloader"   : self.doBootloader,
                 "cdrom"        : None,
                 "clearpart"    : self.doClearPart,
                 "cmdline"      : None,
                 "device"       : None,
                 "deviceprobe"  : None,
                 "driverdisk"   : None,
                 "firewall"     : self.doFirewall,
                 "firstboot"    : self.doFirstboot,
                 "graphical"    : None,
                 "halt"         : self.doReboot,
                 "harddrive"    : None,
                 "ignoredisk"   : self.doIgnoreDisk,
                 "install"      : None,
                 "interactive"  : self.doInteractive,
                 "keyboard"     : self.doKeyboard,
                 "lang"         : self.doLang,
                 "langsupport"  : self.doLangSupport,
                 "logvol"       : self.defineLogicalVolume,
                 "mediacheck"   : None,
                 "monitor"      : self.doMonitor,
                 "mouse"        : self.doMouse,
                 "network"      : self.doNetwork,
                 "nfs"          : None,
                 "part"         : self.definePartition,
                 "partition"    : self.definePartition,
                 "poweroff"     : self.doReboot,
                 "raid"         : self.defineRaid,
                 "reboot"       : self.doReboot,
                 "rootpw"       : self.doRootPw,
                 "selinux"      : self.doSELinux,
                 "shutdown"     : self.doReboot,
                 "skipx"        : self.doSkipX,
                 "text"         : None,
                 "timezone"     : self.doTimezone,
                 "url"          : None,
                 "upgrade"      : self.doUpgrade,
                 "vnc"          : None,
                 "volgroup"     : self.defineVolumeGroup,
                 "xconfig"      : self.doXconfig,
                 "xdisplay"     : None,
                 "zerombr"      : self.doZeroMbr,
               }

    def __init__ (self, ksdata):
        self.ksdata = ksdata

    def doAuthconfig(self, id, args):
        self.ksdata.authconfig = string.join(args)

    def doAutoPart(self, id, args):
        pass

    def doAutoStep(self, id, args):
        pass

    def doBootloader(self, id, args):
        pass

    def doClearPart(self, id, args):
        pass

    def doFirewall(self, id, args):
        def firewall_port_cb (option, opt_str, value, parser):
            for p in value.split(","):
                p = p.strip()
                if p.find(":") == -1:
                    p = "%s:tcp" % p
                parser.values.ensure_value(option.dest, []).append(p)

        op = KSOptionParser({"ssh":["22:tcp"], "telnet":["23:tcp"],
                             "smtp":["25:tcp"], "http":["80:tcp", "443:tcp"],
                             "ftp":["21:tcp"]})

        op.add_option("--disable", "--disabled", dest="enabled",
                      action="store_false")
        op.add_option("--enable", "--enabled", dest="enabled",
                      action="store_true", default=True)
        op.add_option("--ssh", "--telnet", "--smtp", "--http", "--ftp",
                      dest="ports", action="map_extend")
        op.add_option("--trust", dest="trusts", action="append")
        op.add_option("--port", dest="ports", action="callback",
                      callback=firewall_port_cb, nargs=1, type="str")

        (opts, extra) = op.parse_args(args=args)

        # FIXME
        for key in opts.keys():
            self.ksdata.firewall{key} = opts{key}

    def doIgnoreDisk(self, id, args):
        pass

    def doInteractive(self, id, args):
        self.ksdata.interactive = True

    def doKeyboard(self, id, args):
        pass

    def doLang(self, id, args):
        pass

    def doLangSupport(self, id, args):
        raise KickstartError, "The langsupport keyword has been removed.  Instead, please alter your kickstart file to include the support package groups for the languages you want instead of using langsupport.  For instance, include the french-support group instead of specifying 'langsupport fr'."

    def defineLogicalVolume(self, id, args):
        pass

    def doMonitor(self, id, args):
        pass

    def doMouse(self, id, args):
        raise KickstartError, "The mouse keyword has not been functional for several releases and has now been removed.  Please modify your kickstart file by removing this keyword."

    def doNetwork(self, id, args):
        pass

    def definePartition(self, id, args):
        pass

    def doReboot(self, id, args):
        pass

    def defineRaid(self, id, args):
        pass

    def doRootPw(self, id, args):
        (args, extra) = isys.getopt(args, '', ["iscrypted"])

        self.ksdata.rootpw{"isCrypted"} = False
        for n in args:
            (str, arg) = n
            if str == "--iscrypted":
                self.ksdata.rootpw{"isCrypted"} = True

        if len(extra) != 1:
            raise KickstartValueError, "A single argument is expected for rootPw"

    def doSELinux(self, id, args):
        (args, extra) = isys.getopt(args, '', ["disabled", "enforcing",
                                               "permissive"])

        for n in args:
            (str, arg) = n
            if str == "--disabled":
                

    def doSkipX(self, id, args):
        pass

    def doTimezone(self, id, args):
        pass

    def doUpgrade(self, id, args):
        pass

    def defineVolumeGroup(self, id, args):
        pass

    def doXConfig(self, id, args):
        pass

    def doZeroMbr(self, id, args):
        pass

class KickstartParser:
    def __init__ (self, ksdata):
        self.handler = KickstartHandlers(ksdata)
        self.ksdata = ksdata
        self.followIncludes = True

    # Functions to be called when we are at certain points in the
    # kickstart file parsing.  Override these if you need special
    # behavior.
    def addScript (self, state, script):
        s = Script (script["body"], script["interp"], script["chroot"],
                    script["log"], script["errorOnFail"])

        if state == STATE_PRE:
            self.ksdata.preScripts.append(s)
        elif state == STATE_POST:
            self.ksdata.postScripts.append(s)
        elif state == STATE_TRACEBACK:
            self.ksdata.tracebackScripts.append(s)

    def addPackages (self, line):
        if line[0] == '@':
            line = line[1:]
            self.ksdata.groupList.append(line)
        elif line[0] == '-':
            line = line[1:]
            self.ksdata.excludedList.append(line)
        else:
            self.ksdata.packageList.append(line)

    def handleCommand (self, cmd, args):
        try:
            if self.handler.handlers[cmd] != None:
                self.handler.handlers[cmd](args)
        except KeyError:
            raise KickstartError, "Unrecognized kickstart command: %s" % cmd

    def handlePackageHdr (self, line):
        argLst = ["excludedocs", "ignoremissing", "nobase"]
        (args, extra) = isys.getopt(line, '', argLst)

#        self.skipSteps.append("package-selection")

        for n in args:
            (str, arg) = n
            if str == "--excludedocs":
                self.excludeDocs = 1
            elif str == "--ignoremissing":
                self.handleMissing = KS_MISSING_IGNORE
            elif str == "--nobase":
                self.addBase = 0

    def handleScriptHdr (self, args, script):
        argLst = ["interpreter=", "log=", "logfile=", "erroronfail"]

        if args[0] == "%pre" or args[0] == "%traceback":
            script["chroot"] = 0
        elif args[0] == "%post":
            script["chroot"] = 1
            argLst.append("nochroot")

        (args, extra) = isys.getopt(args, '', argLst)
        for n in args:
            (str, arg) = n
            if str == "--nochroot":
                script["chroot"] = 0
            elif str == "--interpreter":
                script["interp"] = arg
            elif str == "log" or str == "--logfile":
                script["log"] = arg
            elif str == "--erroronfail":
                script["errorOnFail"] = True

    # Kickstart file parser.  Only does moving between states and calling
    # functions to do the heavy lifting.
    def readKickstart (self, file, state=STATE_COMMANDS):
        packages = []
        groups = []
        excludedPackages = []

        fh = open(file)
        needLine = True

        while True:
            if needLine:
                line = fh.readline()
                if line == "":
                    if state in [STATE_PRE, STATE_POST, STATE_TRACEBACK]:
                        self.addScript (state, script)
                    break

                needLine = False

            # Don't eliminate whitespace or comments from scripts.
            if line.isspace() or line[0] == '#':
                if state in [STATE_PRE, STATE_POST, STATE_TRACEBACK]:
                    script["body"] = script["body"] + line

                needLine = True
                continue

            line = line.strip()
            args = isys.parseArgv(line)

            if args[0] == "%include" and self.followIncludes:
                if not args[1]:
                    raise KickstartParseError, line
                else:
                    self.readKickstart (args[1], state=state)

            if state == STATE_COMMANDS:
                if args[0] in ["%pre", "%post", "%traceback"]:
                    state = STATE_SCRIPT_HDR
                elif args[0] == "%packages":
                    state = STATE_PACKAGES
                elif args[0][0] == '%':
                    raise KickstartParseError, line
                else:
                    needLine = True
                    self.handleCommand(args[0], args[1:])

            elif state == STATE_PACKAGES:
                if args[0] in ["%pre", "%post", "%traceback"]:
                    state = STATE_SCRIPT_HDR
                elif args[0] == "%packages":
                    needLine = True
                    self.handlePackageHdr (args)
                elif args[0][0] == '%':
                    raise KickstartParseError, line
                else:
                    needLine = True
                    self.addPackages (line)

            elif state == STATE_SCRIPT_HDR:
                needLine = True
                script = {"body": "", "interp": "/bin/sh", "log": None,
                          "errorOnFail": False}

                if args[0] == "%pre":
                    state = STATE_PRE
                elif args[0] == "%post":
                    state = STATE_POST
                elif args[0] == "%traceback":
                    state = STATE_TRACEBACK
                elif args[0][0] == '%':
                    raise KickstartParseError, line

                self.handleScriptHdr (args, script)

            elif state in [STATE_PRE, STATE_POST, STATE_TRACEBACK]:
                # If this is part of a script, append to it.
                if args[0] not in ["%pre", "%post", "%traceback", "%packages"]:
                    script["body"] = script["body"] + line
                    needLine = True
                else:
                    # Otherwise, figure out what kind of a script we just
                    # finished reading, add it to the list, and switch to
                    # the initial state.
                    self.addScript(state, script)
                    state = STATE_COMMANDS

class KickstartPreParser(KickstartParser):
    def __init__ (self, ksdata):
        KickstartParser.__init__(self, ksdata)
        self.followIncludes = False

    def addScript (self, state, script):
        if state == STATE_PRE:
            s = Script (script["body"], script["interp"], script["chroot"],
                        script["log"], script["errorOnFail"])
            self.ksdata.preScripts.append(s)

    def addPackages (self, line):
        pass

    def handleCommand (self, cmd, args):
        pass

    def handlePackageHdr (self, line):
        pass

    def handleScriptHdr (self, args, script):
        if not args[0] == "%pre":
            return

        argLst = ["interpreter=", "log=", "logfile=", "erroronfail"]
        script["chroot"] = 0

        (args, extra) = isys.getopt(args, '', argLst)
        for n in args:
            (str, arg) = n
            if str == "--nochroot":
                script["chroot"] = 0
            elif str == "--interpreter":
                script["interp"] = arg
            elif str == "log" or str == "--logfile":
                script["log"] = arg
            elif str == "--erroronfail":
                script["errorOnFail"] = True
