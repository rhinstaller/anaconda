# backend_log.py
# Logging infrastructure for Anaconda's backend.
#
# Copyright (C) 2009  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Ales Kozumplik <akozumpl@redhat.com>
#

import logging
import os
import signal

import anaconda_log
import iutil

SYSLOG_PATH           = '/sbin/rsyslogd'
SYSLOG_PIDFILE        = '/var/run/rsyslog_backend.pid'
SYSLOG_CFGFILE        = '/etc/rsyslog_backend.conf'

CFG_TEMPLATE = """
$ModLoad imuxsock
$InputUnixListenSocketHostName sysimage
$AddUnixListenSocket %(socket)s
+sysimage
*.* %(logfile)s;RSYSLOG_TraditionalFileFormat
%(remote_syslog)s
"""

global_log = logging.getLogger("anaconda")
class BackendSyslog:
    def __init__(self):
        pass
    
    def build_cfg(self, root, log):
        socket = "%s/dev/log" % (root, )
        remote_syslog = ''
        if anaconda_log.logger.remote_syslog:
            remote_syslog = "*.* @@%s" % (anaconda_log.logger.remote_syslog, )
        
        cfg = CFG_TEMPLATE % {
            'socket' : socket,
            'logfile' : log,
            'remote_syslog' : remote_syslog
            }
        with open(SYSLOG_CFGFILE, 'w') as cfg_file:
            cfg_file.write(cfg)

    def start(self, root, log):
        """ Start an rsyslogd instance dedicated for the sysimage.

        Other possibility would be to change configuration and SIGHUP the
        existing instance, but it could lose some of its internal queues and
        give us problems with remote logging.
        """
        self.build_cfg(root, log)
        args = ['-c', '4', 
                '-f', SYSLOG_CFGFILE,
                '-i', str(SYSLOG_PIDFILE)]
        status = iutil.execWithRedirect(SYSLOG_PATH, args)
        if status == 0:
            global_log.info("Backend logger started.")
        else:
            global_log.error("Unable to start backend logger")
    
    def stop(self):
        try:
            with open(SYSLOG_PIDFILE, 'r') as pidfile:
                pid = int(pidfile.read())
            os.kill(pid, signal.SIGKILL)
        except:
            return
        global_log.info("Backend logger stopped.")

log = BackendSyslog()
