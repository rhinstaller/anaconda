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

import sys
import logging
import types
from logging.handlers import SysLogHandler, SYSLOG_UDP_PORT

DEFAULT_LEVEL = logging.INFO
DEFAULT_ENTRY_FORMAT = "%(asctime)s,%(msecs)03d %(levelname)-8s: %(message)s"
DEFAULT_DATE_FORMAT = "%H:%M:%S"

MAIN_LOG_FILE = "/tmp/anaconda.log"
PROGRAM_LOG_FILE = "/tmp/program.log"

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

class AnacondaLog:
    def __init__ (self, minLevel=DEFAULT_LEVEL):
        self.loglevel = logging.DEBUG
        # Create the base of the logger hierarcy.
        self.logger = logging.getLogger("anaconda")
        self.logger.setLevel(logging.DEBUG)
        self.addFileHandler(MAIN_LOG_FILE, self.logger,
                            autoLevel=False, minLevel=logging.DEBUG)

        # External program output log
        program_logger = logging.getLogger("program")
        program_logger.setLevel(logging.DEBUG)
        self.addFileHandler(PROGRAM_LOG_FILE, program_logger,
                            autoLevel=False, minLevel=logging.DEBUG)

        # Create a second logger for just the stuff we want to dup on
        # stdout.  Anything written here will also get passed up to the
        # parent loggers for processing and possibly be written to the
        # log.
        self.stdoutLogger = logging.getLogger("anaconda.stdout")
        self.stdoutLogger.setLevel(logging.INFO)

        # Add a handler for the duped stuff.  No fancy formatting, thanks.
        self.addFileHandler (sys.stdout, self.stdoutLogger,
                             fmtStr="%(asctime)s %(message)s", minLevel=logging.INFO)

    # Add a simple handler - file or stream, depending on what we're given.
    def addFileHandler (self, file, addToLogger, minLevel=DEFAULT_LEVEL,
                        fmtStr=DEFAULT_ENTRY_FORMAT,
                        autoLevel=True):
        if isinstance(file, types.StringTypes):
            logfileHandler = logging.FileHandler(file)
        else:
            logfileHandler = logging.StreamHandler(file)

        logfileHandler.setLevel(minLevel)
        logfileHandler.setFormatter(logging.Formatter(fmtStr, DEFAULT_DATE_FORMAT))
        autoSetLevel(logfileHandler, autoLevel)
        addToLogger.addHandler(logfileHandler)

    # Add another logger to the hierarchy.  For best results, make sure
    # name falls under anaconda in the tree.
    def addLogger (self, name, minLevel=DEFAULT_LEVEL):
        newLogger = logging.getLogger(name)
        newLogger.setLevel(minLevel)

    # Add a handler for remote syslogs.
    def addSysLogHandler (self, logger, host, port=SYSLOG_UDP_PORT,
                          minLevel=DEFAULT_LEVEL):
        fmt = logging.Formatter("%(levelname)-8s %(message)s")
        syslogHandler = SysLogHandler((host, port))
        syslogHandler.setLevel(minLevel)
        syslogHandler.setFormatter(fmt)
        logger.addHandler(syslogHandler)

logger = AnacondaLog()
