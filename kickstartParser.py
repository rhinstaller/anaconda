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

import shlex
import sys
import string
from optparse import OptionParser, Option
from rhpl.translate import _, N_

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

    def keys(self):
        retval = []

        for opt in self.option_list:
            if opt not in retval:
                retval.append(opt.dest)

        return retval

    def __init__(self, map={}):
        self.map = map
        OptionParser.__init__(self, option_class=MappableOption,
                              add_help_option=False)

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

class KSScript:
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

class KickstartHandlers:
    def __init__ (self, ksdata):
        self.ksdata = ksdata

        self.handlers = { "auth"    : self.doAuthconfig,
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
                     "xconfig"      : self.doXConfig,
                     "xdisplay"     : None,
                     "zerombr"      : self.doZeroMbr,
                   }

    def doAuthconfig(self, args):
        self.ksdata.authconfig = string.join(args)

    def doAutoPart(self, args):
        self.ksdata.autopart = True

    def doAutoStep(self, args):
        op = KSOptionParser()
        op.add_option("--autoscreenshot", dest="autoscreenshot",
                      action="store_true", default=False)

        (opts, extra) = op.parse_args(args=args)
        self.ksdata.autostep["autoscreenshot"] = opts.autoscreenshot

    def doBootloader(self, args):
        def driveorder_cb (option, opt_str, value, parser):
            for d in value.split(','):
                parser.values.ensure_value(option.dest, []).append(d)
            
        op = KSOptionParser()
        op.add_option("--append", dest="appendLine", action="store", type="str",
                      nargs=1)
        op.add_option("--location", dest="location", action="store",
                      type="choice", nargs=1, default="mbr",
                      choices=["mbr", "partition", "none", "boot"])
        op.add_option("--lba32", dest="forceLBA", action="store_true",
                      default=False)
        op.add_option("--password", dest="password", action="store",
                      type="str", nargs=1, default="")
        op.add_option("--md5pass", dest="md5pass", action="store", type="str",
                      nargs=1, default="")
        op.add_option("--upgrade", dest="upgrade", action="store_true",
                      default=False)
        op.add_option("--driveorder", dest="driveorder", action="callback",
                      callback=driveorder_cb, nargs=1, type="str")

        (opts, extra) = op.parse_args(args=args)

        for key in op.keys():
            self.ksdata.bootloader[key] = getattr(opts, key)

    def doClearPart(self, args):
        def drive_cb (option, opt_str, value, parser):
            for d in value.split(','):
                parser.values.ensure_value(option.dest, []).append(d)
            
        op = KSOptionParser()
        op.add_option("--all", dest="type", action="store_const",
                      const=CLEARPART_TYPE_ALL)
        op.add_option("--drives", dest="drives", action=callback,
                      callback=drive_cb, nargs=1, type="str")
        op.add_option("--initlabel", dest="initAll", action="store_true",
                      default=False)
        op.add_option("--linux", dest="type", action="store_const",
                      const=CLEARPART_TYPE_LINUX)
        op.add_option("--none", dest="type", action="store_const",
                      const=CLEARPART_TYPE_NONE)

        (opts, extra) = op.parse_args(args=args)

        for key in op.keys():
            self.ksdata.clearpart[key] = getattr(opts, key)

    def doFirewall(self, args):
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
        op.add_option("--ftp", "--http", "--smtp", "--ssh", "--telnet",
                      dest="ports", action="map_extend")
        op.add_option("--port", dest="ports", action="callback",
                      callback=firewall_port_cb, nargs=1, type="str")
        op.add_option("--trust", dest="trusts", action="append")

        (opts, extra) = op.parse_args(args=args)

        for key in op.keys():
            self.ksdata.firewall[key] = getattr(opts, key)

    def doFirstboot(self, args):
        op = KSOptionParser()
        op.add_option("--disable", "--disabled", dest="firstboot",
                      action="store_const", const=FIRSTBOOT_SKIP)
        op.add_option("--enable", "--enabled", dest="firstboot",
                      action="store_const", const=FIRSTBOOT_DEFAULT)
        op.add_option("--reconfig", dest="firstboot", action="store_const",
                      const=FIRSTBOOT_RECONFIG)

        (opts, extra) = op.parse_args(args=args)
        self.ksdata.firstboot = opts.firstboot

    def doIgnoreDisk(self, args):
        pass

    def doInteractive(self, args):
        self.ksdata.interactive = True

    def doKeyboard(self, args):
        self.ksdata.keyboard = args[0]

    def doLang(self, args):
        self.ksdata.lang = args[0]

    def doLangSupport(self, args):
        raise KickstartError, "The langsupport keyword has been removed.  Instead, please alter your kickstart file to include the support package groups for the languages you want instead of using langsupport.  For instance, include the french-support group instead of specifying 'langsupport fr'."

    def defineLogicalVolume(self, args):
        pass

    def doMonitor(self, args):
        op = KSOptionParser()
        op.add_option("--hsync", dest="hsync", action="store", type="str",
                      nargs=1)
        op.add_option("--monitor", dest="monitor", action="store", type="str",
                      nargs=1)
        op.add_option("--vsync", dest="vsync", action="store", type="str",
                      nargs=1)

        (opts, extra) = op.parse_args(args=args)

        if extra:
            raise KickstartValueError, "Unexpected arguments to monitor"

        for key in op.keys():
            self.ksdata.monitor[key] = getattr(opts, key)

    def doMouse(self, args):
        raise KickstartError, "The mouse keyword has not been functional for several releases and has now been removed.  Please modify your kickstart file by removing this keyword."

    def doNetwork(self, args):
        op = KSOptionParser({"no": 0, "yes": 1})
        op.add_option("--bootproto", dest="bootProto", action="store",
                      type="str", nargs=1, default="dhcp")
        op.add_option("--class", dest="dhcpclass", action="store", type="str",
                      nargs=1)
        op.add_option("--device", dest="device", action="store", type="str",
                      nargs=1)
        op.add_option("--essid", dest="essid", action="store", type="str",
                      nargs=1)
        op.add_option("--ethtool", dest="ethtool", action="store", type="str",
                      nargs=1)
        op.add_option("--gateway", dest="gateway", action="store", type="str",
                      nargs=1)
        op.add_option("--hostname", dest="hostname", action="store", type="str",
                      nargs=1)
        op.add_option("--ip", dest="ip", action="store", type="str", nargs=1)
        op.add_option("--nameserver", dest="nameserver", action="store",
                      type="str", nargs=1)
        op.add_option("--netmask", dest="netmask", action="store", type="str",
                      nargs=1)
        op.add_option("--nodns", dest="nodns", action="store_true",
                      default=False)
        op.add_option("--notksdevice", dest="notksdevice", action="store_true",
                      default=False)
        op.add_option("--onboot", dest="onboot", action="map")
        op.add_option("--wepkey", dest="wepkey", action="store", type="str",
                      nargs=1)

        (opts, extra) = op.parse_args(args=args)

        for key in op.keys():
            self.ksdata.network[key] = getattr(opts, key)

    def definePartition(self, args):
        pass

    def doReboot(self, args):
        self.ksdata.reboot = True

    def defineRaid(self, args):
        pass

    def doRootPw(self, args):
        op = KSOptionParser()
        op.add_option("--iscrypted", dest="isCrypted", action="store_true",
                      default=False)

        (opts, extra) = op.parse_args(args=args)
        self.ksdata.rootpw["isCrypted"] = opts.isCrypted

        if len(extra) != 1:
            raise KickstartValueError, "A single argument is expected for rootPw"

        self.ksdata.rootpw["password"] = extra[0]

    def doSELinux(self, args):
        op = KSOptionParser()
        op.add_option("--disabled", dest="sel", action="store_const", const=0)
        op.add_option("--enforcing", dest="sel", action="store_const", const=1)
        op.add_option("--permissive", dest="sel", action="store_const", const=2)

        (opts, extra) = op.parse_args(args=args)
        self.ksdata.selinux = opts.sel

    def doSkipX(self, args):
        self.ksdata.skipx = True

    def doTimezone(self, args):
        op = KSOptionParser()
        op.add_option("--utc", dest="isUtc", action="store_true", default=False)

        (opts, extra) = op.parse_args(args=args)
        self.ksdata.timezone["isUtc"] = opts.isUtc

        if len(extra) != 1:
            raise KickstartValueError, "A single argument is expected for timezone"

        self.ksdata.timezone["timezone"] = extra[0]

    def doUpgrade(self, args):
        self.ksdata.upgrade = True

    def defineVolumeGroup(self, args):
        pass

    def doXConfig(self, args):
        op = KSOptionParser()
        op.add_option("--card", dest="card", action="store", type="str",
                      nargs=1)
        op.add_option("--defaultdesktop", dest="defaultdesktop", action="store",
                      type="str", nargs=1)
        op.add_option("--depth", dest="depth", action="store", type="int",
                      nargs=1)
        op.add_option("--hsync", dest="hsync", action="store", type="str",
                      nargs=1)
        op.add_option("--monitor", dest="monitor", action="store", type="str",
                      nargs=1)
        op.add_option("--noprobe", dest="probe", action="store_false",
                      default=True)
        op.add_option("--resolution", dest="resolution", action="store",
                      type="str", nargs=1)
        op.add_option("--server", dest="server", action="store", type="str",
                      nargs=1)
        op.add_option("--startxonboot", dest="startX", action="store_true",
                      default=False)
        op.add_option("--videoram", dest="videoRam", action="store", type="str",
                      nargs=1)
        op.add_option("--vsync", dest="vsync", action="store", type="str",
                      nargs=1)

        (opts, extra) = op.parse_args(args=args)
        if extra:
            raise KickstartValueError, "Unexpected arguments to xconfig"

        for key in op.keys():
            self.ksdata.xconfig[key] = getattr(opts, key)

    def doZeroMbr(self, args):
        self.ksdata.zerombr = True

class KickstartParser:
    def __init__ (self, ksdata):
        self.handler = KickstartHandlers(ksdata)
        self.ksdata = ksdata
        self.followIncludes = True

    # Functions to be called when we are at certain points in the
    # kickstart file parsing.  Override these if you need special
    # behavior.
    def addScript (self, state, script):
        if script["body"].strip() == "":
            return

        s = KSScript (script["body"], script["interp"], script["chroot"],
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
            self.ksdata.groupList.append(line.lstrip())
        elif line[0] == '-':
            line = line[1:]
            self.ksdata.excludedList.append(line.lstrip())
        else:
            self.ksdata.packageList.append(line.lstrip())

    def handleCommand (self, cmd, args):
        try:
            if self.handler.handlers[cmd] != None:
                self.handler.handlers[cmd](args)
        except KeyError:
            raise KickstartError, "Unrecognized kickstart command: %s" % cmd

    def handlePackageHdr (self, args):
        op = KSOptionParser()
        op.add_option("--excludedocs", dest="excludedocs", action="store_true",
                      default=False)
        op.add_option("--ignoremissing", dest="ignoremissing",
                      action="store_true", default=False)
        op.add_option("--nobase", dest="nobase", action="store_true",
                      default=False)

        (opts, extra) = op.parse_args(args=args[1:])

        self.excludeDocs = opts.excludedocs
        self.addBase = not opts.nobase
        if opts.ignoremissing:
            self.handleMissing = KS_MISSING_IGNORE
        else:
            self.handleMissing = KS_MISSING_PROMPT

    def handleScriptHdr (self, args, script):
        op = KSOptionParser()
        op.add_option("--erroronfail", dest="errorOnFail", action="store_true",
                      default=False)
        op.add_option("--interpreter", dest="interpreter", action="store",
                      nargs=1, type="str", default="/bin/sh")
        op.add_option("--log", "--logfile", dest="log", action="store",
                      nargs=1, type="str")

        if args[0] == "%pre" or args[0] == "%traceback":
            script["chroot"] = 0
        elif args[0] == "%post":
            script["chroot"] = 1
            op.add_option("--nochroot", dest="nochroot", action="store_true",
                          default=False)

        (opts, extra) = op.parse_args(args=args[1:])

        script["interp"] = opts.interpreter
        script["log"] = opts.log
        script["errorOnFail"] = opts.errorOnFail
        if opts.nochroot:
            script["chroot"] = opts.nochroot

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
            args = shlex.split(line)

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
            s = KSScript (script["body"], script["interp"], script["chroot"],
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

        op = KSOptionParser()
        op.add_option("--erroronfail", dest="errorOnFail", action="store_true",
                      default=False)
        op.add_option("--interpreter", dest="interpreter", action="store",
                      nargs=1, type="str", default="/bin/sh")
        op.add_option("--log", "--logfile", dest="log", action="store",
                      nargs=1, type="str")

        (opts, extra) = op.parse_args(args=args[1:])

        script["interp"] = opts.interpreter
        script["log"] = opts.log
        script["errorOnFail"] = opts.errorOnFail
        script["chroot"] = 0
