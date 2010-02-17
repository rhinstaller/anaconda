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

import os
import signal
import sys
import logging
from logging.handlers import SysLogHandler, SYSLOG_UDP_PORT
import types

import iutil

DEFAULT_TTY_LEVEL = logging.INFO
ENTRY_FORMAT = "%(asctime)s,%(msecs)03d %(levelname)s %(name)s: %(message)s"
TTY_FORMAT = "%(levelname)s %(name)s: %(message)s"
STDOUT_FORMAT = "%(asctime)s %(message)s"
DATE_FORMAT = "%H:%M:%S"

MAIN_LOG_FILE = "/tmp/anaconda.log"
MAIN_LOG_TTY = "/dev/tty3"
PROGRAM_LOG_FILE = "/tmp/program.log"
ANACONDA_SYSLOG_FACILITY = SysLogHandler.LOG_LOCAL1

logLevelMap = {"debug": logging.DEBUG, "info": logging.INFO,
               "warning": logging.WARNING, "error": logging.ERROR,
               "critical": logging.CRITICAL}

# sets autoSetLevel for the given handler
def autoSetLevel(handler, value):
    handler.autoSetLevel = value

# all handlers of given logger with autoSetLevel == True are set to level
def setHandlersLevel(logger, level):
    map(lambda hdlr: hdlr.setLevel(level),
        filter (lambda hdlr: hasattr(hdlr, "autoSetLevel") and hdlr.autoSetLevel, logger.handlers))

class AnacondaSyslogHandler(SysLogHandler):
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

class AnacondaLog:
    def __init__ (self):
        self.tty_loglevel = DEFAULT_TTY_LEVEL
        self.remote_syslog = None
        # Create the base of the logger hierarcy.
        logger = logging.getLogger("anaconda")
        logger.setLevel(logging.DEBUG)
        self.addFileHandler(MAIN_LOG_FILE, logger,
                            minLevel=logging.DEBUG)
        self.forwardToSyslog(logger)
        # Log to tty3.
        if not iutil.isS390() and os.access(MAIN_LOG_TTY, os.W_OK):
            self.addFileHandler(MAIN_LOG_TTY, logger,
                                fmtStr=TTY_FORMAT,
                                autoLevel=True)

        # External program output log
        program_logger = logging.getLogger("program")
        program_logger.setLevel(logging.DEBUG)
        self.addFileHandler(PROGRAM_LOG_FILE, program_logger,
                            minLevel=logging.DEBUG)
        self.forwardToSyslog(program_logger)

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
    def addFileHandler (self, file, addToLogger, minLevel=DEFAULT_TTY_LEVEL,
                        fmtStr=ENTRY_FORMAT,
                        autoLevel=False):
        if isinstance(file, types.StringTypes):
            logfileHandler = logging.FileHandler(file)
        else:
            logfileHandler = logging.StreamHandler(file)

        logfileHandler.setLevel(minLevel)
        logfileHandler.setFormatter(logging.Formatter(fmtStr, DATE_FORMAT))
        autoSetLevel(logfileHandler, autoLevel)
        addToLogger.addHandler(logfileHandler)

    # Add another logger to the hierarchy.  For best results, make sure
    # name falls under anaconda in the tree.
    def addLogger (self, name, minLevel=DEFAULT_TTY_LEVEL):
        newLogger = logging.getLogger(name)
        newLogger.setLevel(minLevel)

    # Add a handler for remote syslogs.
    def addSysLogHandler (self, logger, host, port=SYSLOG_UDP_PORT,
                          minLevel=DEFAULT_TTY_LEVEL):
        fmt = logging.Formatter("%(levelname)-8s %(message)s")
        syslogHandler = SysLogHandler((host, port))
        syslogHandler.setLevel(minLevel)
        syslogHandler.setFormatter(fmt)
        logger.addHandler(syslogHandler)

    def forwardToSyslog(self, logger):
        """Forward everything that goes in the logger to the syslog daemon.
        """
        syslogHandler = AnacondaSyslogHandler(
            '/dev/log', 
            ANACONDA_SYSLOG_FACILITY,
            logger.name)
        syslogHandler.setLevel(logging.DEBUG)
        logger.addHandler(syslogHandler)

    def updateRemote(self, remote_syslog):
        """Updates the location of remote rsyslogd to forward to.

        Requires updating rsyslogd config and sending SIGHUP to the daemon.
        """
        PIDFILE  = "/var/run/syslogd.pid"
        CFGFILE  = "/etc/rsyslog.conf"
        TEMPLATE = "*.* @@%s\n"

        self.remote_syslog = remote_syslog
        with open(CFGFILE, 'a') as cfgfile:
            forward_line = TEMPLATE % remote_syslog
            cfgfile.write(forward_line)
        with open(PIDFILE, 'r') as pidfile:
            pid = int(pidfile.read())
            os.kill(pid, signal.SIGHUP)

logger = AnacondaLog()
