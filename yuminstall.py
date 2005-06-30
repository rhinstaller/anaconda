#
# Copyright (c) 2005 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

from flags import flags

import yum
import yum.repos
from yum.config import yumconf

class AnacondaYumConf(yumconf):
    """Dynamic yum configuration"""

    def __init__( self, configfile = None, root = '/'):
        self.configdata = {
                'debuglevel': 2,
                'errorlevel': 2,
                'retries': 10,
                'recent': 7, 
                'cachedir': '/var/cache/yum', 
                'logfile': '/tmp/anaconda-yum.log', 
                'reposdir': [],
                'syslog_ident': None,
                'syslog_facility': 'LOG_USER',
                'distroverpkg': 'fedora-release',
                'installroot': root,
                'commands': [],
                'exclude': [],
                'failovermethod': 'roundrobin',
                'yumversion': 'unversioned',
                'proxy': None,
                'proxy_username': None,
                'proxy_password': None,
                'pluginpath': '/usr/lib/yum-plugins',
                'installonlypkgs': [],
                'kernelpkgnames': ['kernel','kernel-smp',
                                             'kernel-enterprise', 'kernel-bigmem',
                                             'kernel-BOOT']),
                'exactarchlist': ['kernel', 'kernel-smp', 'glibc',
                                            'kernel-hugemem', 'kernel-enterprise',
                                            'kernel-bigmem']),
                'tsflags': [],
                'assumeyes': False,
                'alwaysprompt': True,
                'exactarch': True,
                'tolerant': True,
                'diskspacecheck': True,
                'overwrite_groups': False,
                'keepalive': True,
                'gpgcheck': False,
                'obsoletes': False,
                'showdupesfromrepos': False,
                'enabled': True,
                'plugins': False,
                'enablegroups': True,
                'uid': 0,
                'cache': 0,
                'progress_obj': None,
                'timeout', 30.0,
                }


class AnacondaYum(yum.YumBase):
    
    def __init__(self, method, id, intf, instPath):
        self.updates = []
        self.localPackages = []

    def doConfigSetup(self, fn=None, root='/'):
        self.conf = AnacondaYumConf()
        repo = yum.repos.Repository()
        repo.set('baseurl','file:///mnt/source')
        self.repos.add(repo)

    def errorlog(self, value, msg):
        pass

    def filelog(self, value, msg):
        pass

    def log(self, value, msg):
        pass

def doYumInstall(method, id, intf, instPath):
    if flags.test:
        return

# XXX: Only operate on nfs trees for now
    if not id.methodstr.startswith('nfs:/'):
        from packages import doInstall
            return doInstall(method, id, intf, instPath)
    
    

