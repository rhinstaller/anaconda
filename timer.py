#
# timer.py - generic timing object for installation screens
#
# Erik Troan <ewt@redhat.com>
#
# Copyright 2000-2001 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
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
