#
# communication.py: spoke-to-hub communication code
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
#
# Author(s): Chris Lumens <clumens@redhat.com>

import Queue

# A queue to be used for communicating information from a spoke back to its
# hub.  This information includes things like marking spokes as ready and
# updating the status line to tell the user why a spoke is not yet available.
# This queue should have elements of the following format pushed into it:
#
# (HUB_CODE_*, [arguments])
#
# Arguments vary based on the code given, but the first argument must always
# be the name of the class of the spoke to be acted upon.  See below for more
# details.
hubQ = Queue.Queue()

# Arguments:
#
# _READY - [spoke_name, justUpdate]
# _NOT_READY - [spoke_name]
# _MESSAGE - [spoke_name, string]
HUB_CODE_READY = 0
HUB_CODE_NOT_READY = 1
HUB_CODE_MESSAGE = 2

# Convenience methods to put things into the queue without the user having to
# know the details of the queue.
def send_ready(spoke, justUpdate=False):
    """Tell the hub that a spoke given by the name "spoke" has become ready,
       and that it should be made sensitive on the hub.  Some processing may
       also occur after a spoke has become ready.  However, if the justUpdate
       parameter is True, no processing will occur.
    """
    hubQ.put((HUB_CODE_READY, [spoke, justUpdate]))

def send_not_ready(spoke):
    hubQ.put((HUB_CODE_NOT_READY, [spoke]))

def send_message(spoke, msg):
    hubQ.put((HUB_CODE_MESSAGE, [spoke, msg]))
