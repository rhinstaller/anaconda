#
# timer.py - generic timing object for installation screens
#
# Copyright (C) 2000, 2001  Red Hat, Inc.  All rights reserved.
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
# Author(s): Erik Troan <ewt@redhat.com>
#

import time

class Timer:

    def stop(self):
	if self.startedAt > -1:
	    self.total = self.total + (time.time() - self.startedAt)
	    self.startedAt = -1

    def start(self):
	if self.startedAt == -1:
	    self.startedAt = time.time()

    def elapsed(self):
	if self.startedAt == -1:
	    return self.total
	else:
	    return self.total + (time.time() - self.startedAt)

    def reset(self, start = 1):
        self.total = 0
        self.startedAt = -1
        if start:
            self.start()

    def __init__(self, start = 1):
        self.reset(start)
