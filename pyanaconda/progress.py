#
# progress.py: one big progress bar class
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

class ProgressReporter(object):
    """In the new UI, we have one large progress bar displayed on the second
       hub that handles progress for both storage creation and package
       installation.  In order to do this in a UI-agnostic way (graphical,
       text, etc.) we must have an API that can be called from anywhere without
       knowledge of the UI details.

       The use of this class is very simple:  Instantiate, call setSteps once,
       call update in a loop, and finally call complete.
    """
    def __init__(self):
        self._initCB = None
        self._updateProgressCB = None
        self._updateMessageCB = None
        self._completeCB = None

    def register(self, initCB, updateProgressCB, updateMessageCB, completeCB):
        self._initCB = initCB
        self._updateProgressCB = updateProgressCB
        self._updateMessageCB = updateMessageCB
        self._completeCB = completeCB

    def setSteps(self, steps):
        """In order for the progress bar to know how big each step needs to be,
           this method must first be called to specify the total number of
           steps.
        """
        if not self._initCB:
            return

        self._initCB(steps)

    def updateMessage(self, message):
        """This method should be called when a task begins, so the progress
           bar reflects what is happening and taking up time.  This method does
           not cause the progress bar itself to be filled in any more.
        """
        if not self._updateMessageCB:
            return

        self._updateMessageCB(message)

    def updateProgress(self):
        """This method should be called when a task finishes.  It will cause
           the progress bar to be filled in a little more.
        """
        if not self._updateProgressCB:
            return

        self._updateProgressCB()

    def complete(self):
        """When the process is complete, call this method to display a
           completion method on the screen and make sure the progress bar is
           100% full.
        """
        if not self._completeCB:
            return

        self._completeCB()

# Create a singleton of the ProgressReporter class.  The required callbacks
# must be registered before the class needs to be used, or nothing will
# happen.
progress = ProgressReporter()
