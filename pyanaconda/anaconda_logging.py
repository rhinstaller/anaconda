#
# anaconda_logging.py: Support for logging to multiple destinations with log
#                      levels - basically an extension to the Python logging
#                      module with Anaconda specififc enhancements.
#
# Copyright (C) 2000, 2001, 2002, 2005, 2017  Red Hat, Inc.  All rights reserved.
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

import logging
from logging.handlers import SysLogHandler, SocketHandler
from systemd.journal import JournalHandler
import os
import sys
import warnings

from pyanaconda.core import constants
from pyanaconda.core.path import set_mode

ENTRY_FORMAT = "%(asctime)s,%(msecs)03d %(levelname)s %(name)s: %(message)s"
STDOUT_FORMAT = "%(asctime)s %(message)s"
DATE_FORMAT = "%H:%M:%S"

# the Anaconda log uses structured logging
ANACONDA_ENTRY_FORMAT = "%(asctime)s,%(msecs)03d %(levelname)s %(log_prefix)s: %(message)s"
ANACONDA_SYSLOG_FORMAT = "anaconda: %(log_prefix)s: %(message)s"

MAIN_LOG_FILE = "/tmp/anaconda.log"
PROGRAM_LOG_FILE = "/tmp/program.log"
ANACONDA_SYSLOG_FACILITY = SysLogHandler.LOG_LOCAL1
ANACONDA_SYSLOG_IDENTIFIER = "anaconda"

from threading import Lock
program_log_lock = Lock()


class _AnacondaLogFixer(object):
    """ A mixin for logging.StreamHandler that does not lock during format.

        Add this mixin before the Handler type in the inheritance order.
    """

    # filter, emit, lock, and acquire need to be implemented in a subclass

    def handle(self, record):
        # copied from logging.Handler, minus the lock acquisition
        rv = self.filter(record)    # pylint: disable=no-member
        if rv:
            self.emit(record)       # pylint: disable=no-member
        return rv

    @property
    def stream(self):
        return self._stream

    @stream.setter
    def stream(self, stream):
        handler = self

        # Wrap the stream write in a lock acquisition
        # Use an object proxy in order to work with types that may not allow
        # the write property to be set.
        class WriteProxy(object):

            def write(self, *args, **kwargs):
                handler.acquire()  # pylint: disable=no-member
                try:
                    stream.write(*args, **kwargs)
                finally:
                    handler.release()  # pylint: disable=no-member

            def __getattr__(self, name):
                return getattr(stream, name)

            def __setattr__(self, name, value):
                return setattr(stream, name, value)

        # Live with this attribute being defined outside of init to avoid the
        # hassle of having an init. If _stream is not set, then stream was
        # never set on the StreamHandler object, so accessing it in that case
        # is supposed to be an error.
        self._stream = WriteProxy()  # pylint: disable=attribute-defined-outside-init


class AnacondaJournalHandler(_AnacondaLogFixer, JournalHandler):
    def __init__(self, tag='', facility=ANACONDA_SYSLOG_FACILITY,
                 identifier=ANACONDA_SYSLOG_IDENTIFIER):
        self.tag = tag
        JournalHandler.__init__(self,
                                SYSLOG_FACILITY=facility,
                                SYSLOG_IDENTIFIER=identifier)

    def emit(self, record):
        if self.tag:
            original_msg = record.msg
            record.msg = '%s: %s' % (self.tag, original_msg)
            JournalHandler.emit(self, record)
            record.msg = original_msg
        else:
            JournalHandler.emit(self, record)


class AnacondaSocketHandler(_AnacondaLogFixer, SocketHandler):
    def makePickle(self, record):
        return bytes(self.formatter.format(record) + "\n", "utf-8")


class AnacondaFileHandler(_AnacondaLogFixer, logging.FileHandler):
    def __init__(self, file_dest):
        logging.FileHandler.__init__(self, file_dest)

        set_mode(file_dest)

class AnacondaStreamHandler(_AnacondaLogFixer, logging.StreamHandler):
    pass


class AnacondaPrefixFilter(logging.Filter):
    """Add a log_prefix field, which is based on the name property,
    but without the "anaconda." prefix.

    Also if name is equal to "anaconda", generally meaning some sort of
    general (or miss-directed) log message, set the log_prefix to "misc".
    """

    def filter(self, record):
        record.log_prefix = ""
        if record.name:
            # messages going to the generic "anaconda" logger get the log prefix "misc"
            if record.name == "anaconda":
                record.log_prefix = "misc"
            elif record.name.startswith("anaconda."):
                # drop "anaconda." from the log prefix
                record.log_prefix = record.name[9:]
        return True


class AnacondaLog(object):
    SYSLOG_CFGFILE = "/etc/rsyslog.conf"

    def __init__(self, write_to_journal=False):
        self.remote_syslog = None
        self.write_to_journal = write_to_journal
        # Rename the loglevels so they are the same as in syslog.
        logging.addLevelName(logging.CRITICAL, "CRT")
        logging.addLevelName(logging.ERROR, "ERR")
        logging.addLevelName(logging.WARNING, "WRN")
        logging.addLevelName(logging.INFO, "INF")
        logging.addLevelName(logging.DEBUG, "DBG")

        # Create the base of the logger hierarchy.
        # Disable propagation to the parent logger, since the root logger is
        # handled by a FileHandler(/dev/null), which can deadlock.
        self.anaconda_logger = logging.getLogger("anaconda")
        self.anaconda_logger.propagate = False
        self.anaconda_logger.setLevel(logging.DEBUG)
        warnings.showwarning = self.showwarning
        self.addFileHandler(MAIN_LOG_FILE, self.anaconda_logger,
                            fmtStr=ANACONDA_ENTRY_FORMAT,
                            log_filter=AnacondaPrefixFilter())
        self.forwardToJournal(self.anaconda_logger,
                              log_filter=AnacondaPrefixFilter(),
                              log_formatter=logging.Formatter(ANACONDA_SYSLOG_FORMAT))

        # External program output log
        program_logger = logging.getLogger(constants.LOGGER_PROGRAM)
        program_logger.propagate = False
        program_logger.setLevel(logging.DEBUG)
        self.addFileHandler(PROGRAM_LOG_FILE, program_logger)
        self.forwardToJournal(program_logger)

        # Create the simpleline logger and link it to anaconda
        simpleline_logger = logging.getLogger(constants.LOGGER_SIMPLELINE)
        simpleline_logger.setLevel(logging.DEBUG)
        self.addFileHandler(MAIN_LOG_FILE, simpleline_logger)
        self.forwardToJournal(simpleline_logger)

        # Create a second logger for just the stuff we want to dup on
        # stdout.  Anything written here will also get passed up to the
        # parent loggers for processing and possibly be written to the
        # log.
        stdout_logger = logging.getLogger(constants.LOGGER_STDOUT)
        stdout_logger.setLevel(logging.INFO)
        # Add a handler for the duped stuff.  No fancy formatting, thanks.
        self.addFileHandler(sys.stdout, stdout_logger, fmtStr=STDOUT_FORMAT)

    # Add a simple handler - file or stream, depending on what we're given.
    def addFileHandler(self, dest, addToLogger, fmtStr=ENTRY_FORMAT, log_filter=None):
        try:
            if isinstance(dest, str):
                logfile_handler = AnacondaFileHandler(dest)
            else:
                logfile_handler = AnacondaStreamHandler(dest)

            if log_filter:
                logfile_handler.addFilter(log_filter)

            logfile_handler.setFormatter(logging.Formatter(fmtStr, DATE_FORMAT))
            addToLogger.addHandler(logfile_handler)
        except OSError:
            pass

    def forwardToJournal(self, logr, log_formatter=None, log_filter=None):
        """Forward everything that goes in the logger to the journal daemon."""
        # Don't add syslog tag if custom formatter is in use.
        # This also means that custom formatters need to make sure they
        # add the tag correctly themselves.
        if not self.write_to_journal:
            return

        if log_formatter:
            tag = None
        else:
            tag = logr.name
        journal_handler = AnacondaJournalHandler(tag=tag)
        journal_handler.setLevel(logging.DEBUG)
        if log_filter:
            journal_handler.addFilter(log_filter)
        if log_formatter:
            journal_handler.setFormatter(log_formatter)
        logr.addHandler(journal_handler)

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
        from pyanaconda.core.service import restart_service
        restart_service("rsyslog")

    def updateRemote(self, remote_syslog):
        """Updates the location of remote rsyslogd to forward to.

        Requires updating rsyslogd config and restarting rsyslog
        """

        template = "*.* @@%s\n"

        self.remote_syslog = remote_syslog
        with open(self.SYSLOG_CFGFILE, 'a') as cfgfile:
            forward_line = template % remote_syslog
            cfgfile.write(forward_line)
        self.restartSyslog()

    def setupVirtio(self, vport):
        """Setup virtio rsyslog logging.
        """
        template = "*.* %s;anaconda_syslog\n"

        if not os.access(vport, os.W_OK):
            return

        with open(self.SYSLOG_CFGFILE, 'a') as cfgfile:
            cfgfile.write(template % (vport,))
        self.restartSyslog()


def init(write_to_journal=False):
    global logger
    logger = AnacondaLog(write_to_journal=write_to_journal)


logger = None
