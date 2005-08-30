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
class KickstartData:
    def __init__(self):
        # Set by command handlers.
        self.authconfig = ""
        self.autostep = {}
        self.bootloader = {}
        self.clearpart = {}
	self.firewall = {"enabled": True, "ports": [], "trusts": []}
        self.firstboot = {}
        self.ignoredisk = {}
        self.interactive = False
        self.keyboard = ""
        self.lang = ""
        self.monitor = {}
        self.network = {}
        self.partitions = []
	self.rootpw = {"isCrypted": False}
        self.selinux = 2
        self.timezone = {}
        self.upgrade = False
        self.xconfig = {}
        self.zerombr = False

        # Set by sections.
        self.groupList = []
        self.packageList = []
        self.excludedList = []
        self.preScripts = []
        self.postScripts = []
        self.tracebackScripts = []
