#
# anaconda_log.py: Support for logging to multiple destinations with log
# levels.
#
# Copyright (C) 2000, 2001, 2002, 2005  Red Hat, Inc.  All rights reserved.
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
# Author(s): Chris Lumens <clumens@redhat.com>
#            Matt Wilson <msw@redhat.com>
#            Michael Fulbright <msf@redhat.com>
#

import logging
from logging.handlers import SysLogHandler, SocketHandler, SYSLOG_UDP_PORT
import os
import sys
import types
import warnings

from pyanaconda.flags import flags
from pyanaconda.constants import LOGLVL_LOCK

DEFAULT_LEVEL = logging.INFO
ENTRY_FORMAT = "%(asctime)s,%(msecs)03d %(levelname)s %(name)s: %(message)s"
STDOUT_FORMAT = "%(asctime)s %(message)s"
DATE_FORMAT = "%H:%M:%S"

MAIN_LOG_FILE = "/tmp/anaconda.log"
PROGRAM_LOG_FILE = "/tmp/program.log"
STORAGE_LOG_FILE = "/tmp/storage.log"
PACKAGING_LOG_FILE = "/tmp/packaging.log"
SENSITIVE_INFO_LOG_FILE = "/tmp/sensitive-info.log"
ANACONDA_SYSLOG_FACILITY = SysLogHandler.LOG_LOCAL1

from threading import Lock
program_log_lock = Lock()

logLevelMap = {"lock": LOGLVL_LOCK,
               "debug": logging.DEBUG,
               "info": logging.INFO,
               "warning": logging.WARNING,
               "error": logging.ERROR,
               "critical": logging.CRITICAL}

# sets autoSetLevel for the given handler
def autoSetLevel(handler, value):
    handler.autoSetLevel = value

# all handlers of given logger with autoSetLevel == True are set to level
def setHandlersLevel(logr, level):
    map(lambda hdlr: hdlr.setLevel(level),
        filter (lambda hdlr: hasattr(hdlr, "autoSetLevel") and hdlr.autoSetLevel, logr.handlers))

class AnacondaSyslogHandler(SysLogHandler):
    # syslog doesn't understand these level names
    levelMap = { "ERR": "error",
                 "CRIT": "critical",
                 "LOCK": "debug"}

    def __init__(self,
                 address=('localhost', SYSLOG_UDP_PORT),
                 facility=SysLogHandler.LOG_USER,
                 tag=''):
        self.tag = tag
        SysLogHandler.__init__(self, address, facility)

    def emit(self, record):
        original_msg = record.msg
        record.msg = '%s: %s' %(self.tag, original_msg)
        SysLogHandler.emit(self, record)
        record.msg = original_msg

    def mapPriority(self, level):
        """Map the priority level to a syslog level """
        return self.levelMap.get(level, SysLogHandler.mapPriority(self, level))

class AnacondaSocketHandler(SocketHandler):
    def makePickle(self, record):
        return self.formatter.format(record) + "\n"

class AnacondaLog:
    SYSLOG_CFGFILE  = "/etc/rsyslog.conf"
    VIRTIO_PORT = "/dev/virtio-ports/org.fedoraproject.anaconda.log.0"

    def __init__ (self):
        self.loglevel = DEFAULT_LEVEL
        self.remote_syslog = None
        # Rename the loglevels so they are the same as in syslog.
        logging.addLevelName(logging.WARNING, "WARN")
        logging.addLevelName(logging.ERROR, "ERR")
        logging.addLevelName(logging.CRITICAL, "CRIT")
        logging.addLevelName(LOGLVL_LOCK, "LOCK")

        # Create the base of the logger hierarchy.
        self.anaconda_logger = logging.getLogger("anaconda")
        self.addFileHandler(MAIN_LOG_FILE, self.anaconda_logger,
                            minLevel=logging.DEBUG)
        warnings.showwarning = self.showwarning

        # Create the storage logger.
        storage_logger = logging.getLogger("blivet")
        self.addFileHandler(STORAGE_LOG_FILE, storage_logger,
                            minLevel=logging.DEBUG)

        # Set the common parameters for anaconda and storage loggers.
        for logr in [self.anaconda_logger, storage_logger]:
            logr.setLevel(logging.DEBUG)
            self.forwardToSyslog(logr)

        # External program output log
        program_logger = logging.getLogger("program")
        program_logger.setLevel(logging.DEBUG)
        self.addFileHandler(PROGRAM_LOG_FILE, program_logger,
                            minLevel=logging.DEBUG)
        self.forwardToSyslog(program_logger)

        # Create the packaging logger.
        packaging_logger = logging.getLogger("packaging")
        packaging_logger.setLevel(LOGLVL_LOCK)
        self.addFileHandler(PACKAGING_LOG_FILE, packaging_logger,
                            minLevel=logging.INFO,
                            autoLevel=True)
        self.forwardToSyslog(packaging_logger)

        # Create the yum logger and link it to packaging
        yum_logger = logging.getLogger("yum")
        yum_logger.setLevel(logging.DEBUG)
        self.addFileHandler(PACKAGING_LOG_FILE, yum_logger,
                            minLevel=logging.DEBUG)
        self.forwardToSyslog(yum_logger)

        # Create the sensitive information logger
        # * the sensitive-info.log file is not copied to the installed
        # system, as it might contain sensitive information that
        # should not be persistently stored by default
        sensitive_logger = logging.getLogger("sensitive-info")
        self.addFileHandler(SENSITIVE_INFO_LOG_FILE, sensitive_logger,
                            minLevel=logging.DEBUG)

        # Create a second logger for just the stuff we want to dup on
        # stdout.  Anything written here will also get passed up to the
        # parent loggers for processing and possibly be written to the
        # log.
        stdoutLogger = logging.getLogger("anaconda.stdout")
        stdoutLogger.setLevel(logging.INFO)
        # Add a handler for the duped stuff.  No fancy formatting, thanks.
        self.addFileHandler(sys.stdout, stdoutLogger,
                            fmtStr=STDOUT_FORMAT, minLevel=logging.INFO)

        # Stderr logger
        stderrLogger = logging.getLogger("anaconda.stderr")
        stderrLogger.setLevel(logging.INFO)
        self.addFileHandler(sys.stderr, stderrLogger,
                            fmtStr=STDOUT_FORMAT, minLevel=logging.INFO)

    # Add a simple handler - file or stream, depending on what we're given.
    def addFileHandler (self, dest, addToLogger, minLevel=DEFAULT_LEVEL,
                        fmtStr=ENTRY_FORMAT,
                        autoLevel=False):
        try:
            if isinstance(dest, types.StringTypes):
                logfileHandler = logging.FileHandler(dest)
            else:
                logfileHandler = logging.StreamHandler(dest)

            logfileHandler.setLevel(minLevel)
            logfileHandler.setFormatter(logging.Formatter(fmtStr, DATE_FORMAT))
            autoSetLevel(logfileHandler, autoLevel)
            addToLogger.addHandler(logfileHandler)
        except IOError:
            pass

    def forwardToSyslog(self, logr):
        """Forward everything that goes in the logger to the syslog daemon.
        """
        if flags.imageInstall or flags.dirInstall:
            # don't clutter up the system logs when doing an image install
            return

        syslogHandler = AnacondaSyslogHandler(
            '/dev/log',
            ANACONDA_SYSLOG_FACILITY,
            logr.name)
        syslogHandler.setLevel(logging.DEBUG)
        logr.addHandler(syslogHandler)

    # pylint: disable=redefined-builtin
    def showwarning(self, message, category, filename, lineno,
                      file=sys.stderr, line=None):
        """ Make sure messages sent through python's warnings module get logged.

            The warnings mechanism is used by some libraries we use,
            notably pykickstart.
        """
        self.anaconda_logger.warning("%s", warnings.formatwarning(
                message, category, filename, lineno, line))

    def setup_remotelog(self, host, port):
        remotelog = AnacondaSocketHandler(host, port)
        remotelog.setFormatter(logging.Formatter(ENTRY_FORMAT, DATE_FORMAT))
        remotelog.setLevel(logging.DEBUG)
        logging.getLogger().addHandler(remotelog)

    def restartSyslog(self):
        # Import here instead of at the module level to avoid an import loop
        from pyanaconda.iutil import execWithRedirect
        execWithRedirect("systemctl", ["restart", "rsyslog.service"])

    def updateRemote(self, remote_syslog):
        """Updates the location of remote rsyslogd to forward to.

        Requires updating rsyslogd config and restarting rsyslog
        """
        TEMPLATE = "*.* @@%s\n"

        self.remote_syslog = remote_syslog
        with open(self.SYSLOG_CFGFILE, 'a') as cfgfile:
            forward_line = TEMPLATE % remote_syslog
            cfgfile.write(forward_line)
        self.restartSyslog()

    def setupVirtio(self):
        """Setup virtio rsyslog logging.
        """
        TEMPLATE = "*.* %s;anaconda_syslog\n"

        vport = flags.cmdline.get('virtiolog', self.VIRTIO_PORT)

        if not os.access(vport, os.W_OK):
            return

        with open(self.SYSLOG_CFGFILE, 'a') as cfgfile:
            cfgfile.write(TEMPLATE % (vport,))
        self.restartSyslog()


logger = None
def init():
    global logger
    logger = AnacondaLog()
