#
# anaconda_log.py: Support for logging to multiple destinations with log
# levels.
#
# Chris Lumens <clumens@redhat.com>
# Matt Wilson <msw@redhat.com>
# Michael Fulbright <msf@redhat.com>
#
# Copyright 2000-2002,2005 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import sys
import logging
from logging.handlers import SysLogHandler, SYSLOG_UDP_PORT

DEFAULT_LEVEL = logging.INFO

logFile = "/tmp/anaconda.log"

logLevelMap = {"debug": logging.DEBUG, "info": logging.INFO,
               "warning": logging.WARNING, "error": logging.ERROR,
               "critical": logging.CRITICAL}

# Base class for logger instances.  This is what will be created any time
# someone calls logging.getLogger("whatever").  We need this class to
# provide the setHandlersLevel function.
class LoggerClass(logging.Logger):
    # Set the level of all handlers attached to a logger, except those
    # with the autoSetLevel=False attribute.
    def setHandlersLevel(self, level):
        map(lambda hdlr: hdlr.setLevel(level),
            filter (lambda hdlr: hasattr(hdlr, "autoSetLevel") and hdlr.autoSetLevel, self.handlers))

    # Specialized addHandler that also adds the autoSetLevel attribute.
    def addHandler(self, hdlr, autoSetLevel=True):
        setattr(hdlr, "autoSetLevel", autoSetLevel)
        logging.Logger.addHandler(self, hdlr)

class AnacondaLog:
    def __init__ (self, minLevel=DEFAULT_LEVEL):
        # Create the base of the logger hierarcy.
        self.logger = logging.getLogger("anaconda")
        self.logger.setLevel(logging.DEBUG)

        # Add a handler for the log file.
        self.addFileHandler (logFile, logging.getLogger("anaconda"),
                             autoSetLevel=False, minLevel=logging.DEBUG)

        # Create a second logger for just the stuff we want to dup on
        # stdout.  Anything written here will also get passed up to the
        # parent loggers for processing and possibly be written to the
        # log.
        self.stdoutLogger = logging.getLogger("anaconda.stdout")
        self.stdoutLogger.setLevel(logging.INFO)

        # Add a handler for the duped stuff.  No fancy formatting, thanks.
        self.addFileHandler (sys.stdout, self.stdoutLogger,
                             fmtStr="%(message)s", minLevel=logging.INFO)

    # Add a simple handler - file or stream, depending on what we're given.
    def addFileHandler (self, file, addToLogger, minLevel=DEFAULT_LEVEL,
                        fmtStr="%(asctime)s %(levelname)-8s: %(message)s",
                        autoSetLevel=True):
        if type (file) == type ("string"):
            logfileHandler = logging.FileHandler(file)
        else:
            logfileHandler = logging.StreamHandler(file)

        logfileHandler.setLevel(minLevel)
        logfileHandler.setFormatter (logging.Formatter (fmtStr, "%H:%M:%S"))
        addToLogger.addHandler(logfileHandler, autoSetLevel=autoSetLevel)

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

# Set base class for logger instances.
logging.setLoggerClass(LoggerClass)
logger = AnacondaLog()
