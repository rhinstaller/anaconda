#
# progress.py: code for handling the one big progress bar
#
# Copyright (C) 2012  Red Hat, Inc.  All rights reserved.
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

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.i18n import _

log = get_module_logger(__name__)

from pyanaconda.queuefactory import QueueFactory

# A queue to be used for communicating progress information between a subthread
# doing all the hard work and the main thread that does the GTK updates.  This
# queue should have elements of the following format pushed into it:
#
# (PROGRESS_CODE_*, [arguments])
#
# Arguments vary based on the code given.  See below.
progressQ = QueueFactory("progress")

progressQ.addMessage("init", 1)             # num_steps
progressQ.addMessage("step", 0)
progressQ.addMessage("message", 1)          # message
progressQ.addMessage("complete", 0)
progressQ.addMessage("quit", 1)             # exit_code


def progress_message(message):
    progressQ.send_message(_(message))
    log.info(message)


def progress_step(message):
    progressQ.send_step()
    log.info(message)


def progress_init(steps):
    progressQ.send_init(steps)


def progress_complete():
    progressQ.send_complete()
