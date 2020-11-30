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

from pyanaconda.queuefactory import QueueFactory

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
hubQ = QueueFactory("hub")

hubQ.addMessage("ready", 1)             # spoke_name
hubQ.addMessage("not_ready", 1)         # spoke_name
hubQ.addMessage("message", 2)           # spoke_name, string
hubQ.addMessage("exception", 1)         # exception
