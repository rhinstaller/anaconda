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
        self.ignoredisk = {}
        self.interactive = False
        self.keyboard = ""
        self.lang = ""
        self.monitor = {"hsync": "", "monitor": "", "vsync": ""}
        self.network = {}
        self.partitions = []
        self.reboot = True
        self.rootpw = {"isCrypted": False, "password": ""}
        self.selinux = 2
        self.skipx = False
        self.timezone = {"isUtc": False, "timezone": ""}
        self.upgrade = False
        self.xconfig = {"card": "", "defaultdesktop": "", "depth": 0,
                        "hsync": "", "monitor": "", "probe": True,
                        "resolution": "", "server": "", "startX": False,
                        "videoRam": "", "vsync": ""}
        self.zerombr = False

        # Set by sections.
        self.groupList = []
        self.packageList = []
        self.excludedList = []
        self.preScripts = []
        self.postScripts = []
        self.tracebackScripts = []
