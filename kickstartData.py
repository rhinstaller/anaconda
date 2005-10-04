#
# kickstartParser.py:  Unified kickstart file parser for anaconda and
# s-c-kickstart, among others.
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
from constants import *

DISPLAY_MODE_CMDLINE = 0
DISPLAY_MODE_GRAPHICAL = 1
DISPLAY_MODE_TEXT = 2

KS_MISSING_PROMPT = 0
KS_MISSING_IGNORE = 1

class KickstartData:
    def __init__(self):
        # Set by command handlers.
        self.authconfig = ""
        self.autopart = False
        self.autostep = {"autoscreenshot": False}
        self.bootloader = {"appendLine": "", "driveorder": [],
                           "forceLBA": False, "location": "mbr", "md5pass": "",
                           "password": "", "upgrade": False}
        self.clearpart = {"drives": [], "initAll": False,
                          "type": CLEARPART_TYPE_NONE}
        self.device = ""
        self.deviceprobe = ""
        self.displayMode = DISPLAY_MODE_GRAPHICAL
        self.driverdisk = ""
        self.firewall = {"enabled": True, "ports": [], "trusts": []}
        self.firstboot = FIRSTBOOT_SKIP
        self.ignoredisk = []
        self.interactive = False
        self.keyboard = ""
        self.lang = ""
        self.mediacheck = False
        self.method = {"method": ""}
        self.monitor = {"hsync": "", "monitor": "", "vsync": ""}
        self.network = []
        self.platform = ""
        self.reboot = True
        self.rootpw = {"isCrypted": False, "password": ""}
        self.selinux = 2
        self.skipx = False
        self.timezone = {"isUtc": False, "timezone": ""}
        self.upgrade = False
        self.vnc = {"enabled": False, "password": "", "host": "", "port": ""}
        self.xconfig = {"driver": "", "defaultdesktop": "", "depth": 0,
                        "hsync": "", "monitor": "", "probe": True,
                        "resolution": "", "startX": False,
                        "videoRam": "", "vsync": ""}
        self.zerombr = False
        self.zfcp = {"devnum": "", "fcplun": "", "scsiid": "", "scsilun": "",
                     "wwpn": ""}

        self.lvList = []
        self.partitions = []
        self.raidList = []
        self.vgList = []

        # Set by %package header.
        self.excludeDocs = False
        self.addBase = True
        self.handleMissing = KS_MISSING_PROMPT

        # Set by sections.
        self.groupList = []
        self.packageList = []
        self.excludedList = []
        self.preScripts = []
        self.postScripts = []
        self.tracebackScripts = []

class KickstartLogVolData:
    def __init__(self):
        self.bytesPerInode = 0
        self.fsopts = ""
        self.fstype = ""
        self.grow = False
        self.maxSizeMB = 0
        self.name = ""
        self.format = True
        self.percent = 0
        self.recommended = False
        self.size = 0
        self.preexist = False
        self.vgname = ""
        self.mountpoint = ""

class KickstartNetworkData:
    def __init__(self):
        self.bootProto = "dhcp"
        self.dhcpclass = ""
        self.device = ""
        self.essid = ""
        self.ethtool = ""
        self.gateway = ""
        self.hostname = ""
        self.ip = ""
        self.nameserver = ""
        self.netmask = ""
        self.nodns = False
        self.notksdevice = False
        self.onboot = True
        self.wepkey = ""

class KickstartPartData:
    def __init__ (self):
        self.active = False
        self.primOnly = False
        self.bytesPerInode = 0
        self.end = 0
        self.fsopts = ""
        self.fstype = ""
        self.grow = False
        self.label = ""
        self.maxSizeMB = 0
        self.format = True
        self.onbiosdisk = ""
        self.disk = ""
        self.onPart = ""
        self.recommended = False
        self.size = 0
        self.start = 0
        self.mountpoint = ""

class KickstartRaidData:
    def __init__ (self):
        self.device = ""
        self.fsopts = ""
        self.fstype = ""
        self.level = ""
        self.format = True
        self.spares = 0
        self.preexist = False
        self.mountpoint = ""
        self.members = ""

class KickstartVolGroupData:
    def __init__(self):
        self.format = True
        self.pesize = 32768
        self.preexist = False
        self.vgname = ""
        self.physvols = ""
