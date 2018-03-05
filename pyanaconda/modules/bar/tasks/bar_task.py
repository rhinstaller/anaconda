# DBus Task for Bar example modules.
#
# Example of Task Facade implementation.
#
# Copyright (C) 2017 Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

import time

from pyanaconda.modules.common.task import Task


class BarTask(Task):

    @property
    def name(self):
        return "Lazy task"

    @property
    def description(self):
        return "Bar task"

    @property
    def progress_steps_count(self):
        return 5

    def runnable(self):
        self.progress_changed(1, "preparing for the hard work")

        # hard working...
        time.sleep(1)

        if self.check_cancel():
            return

        self.progress_changed(2, "working so HARD!!")
        # pretending hard work while sleeping...
        time.sleep(1)

        if self.check_cancel():
            return

        self.progress_changed(3, "It is almost done")
        # practising memory by trying to remember actual step count
        time.sleep(1)

        self.progress_changed(5, "Done")
