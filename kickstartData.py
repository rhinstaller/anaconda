#
# kickstartParser.py:  Unified kickstart data store for anaconda and
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
from constants import *

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
        self.firewall = {"enabled": True, "ports": [], "trusts": []}
        self.firstboot = FIRSTBOOT_SKIP
        self.graphical = True
        self.ignoredisk = []
        self.interactive = False
        self.keyboard = ""
        self.lang = ""
        self.monitor = {"hsync": "", "monitor": "", "vsync": ""}
        self.network = []
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

        # Set by sections.
        self.groupList = []
        self.packageList = []
        self.excludedList = []
        self.preScripts = []
        self.postScripts = []
        self.tracebackScripts = []

    def __str__ (self):
        str = "authconfig = \"%s\"\n" % self.authconfig
        str = str + "autopart = %s\n" % self.autopart
        str = str + "autostep = %s\n" % self.autostep
        str = str + "bootloader = %s\n" % self.bootloader
        str = str + "clearpart = %s\n" % self.clearpart
        str = str + "firewall = %s\n" % self.firewall
        str = str + "firstboot = %s\n" % self.firstboot
        str = str + "ignoredisk = %s\n" % self.ignoredisk
        str = str + "interactive = %s\n" % self.interactive
        str = str + "keyboard = \"%s\"\n" % self.keyboard
        str = str + "lang = \"%s\"\n" % self.lang
        str = str + "monitor = %s\n" % self.monitor
        str = str + "network = %s\n" % self.network
        str = str + "reboot = %s\n" % self.reboot
        str = str + "rootpw = %s\n" % self.rootpw
        str = str + "selinux = %s\n" % self.selinux
        str = str + "skipx = %s\n" % self.skipx
        str = str + "timezone = %s\n" % self.timezone
        str = str + "upgrade = %s\n" % self.upgrade
        str = str + "vnc = %s\n" % self.vnc
        str = str + "xconfig = %s\n" % self.xconfig
        str = str + "zerombr = %s\n" % self.zerombr
        str = str + "zfcp = %s\n" % self.zfcp

        str = str + "lvList = %s\n" % self.lvList
        str = str + "partitions = %s\n" % self.partitions
        str = str + "raidList = %s\n" % self.raidList
        str = str + "vgList = %s\n" % self.vgList

        str = str + "groupList = %s\n" % self.groupList
        str = str + "packageList = %s\n" % self.packageList
        str = str + "excludedList = %s\n" % self.excludedList

        str = str + "preScripts = %s\n" % self.preScripts
        str = str + "postScripts = %s\n" % self.postScripts
        str = str + "tracebackScripts = %s\n" % self.tracebackScripts

        return str
