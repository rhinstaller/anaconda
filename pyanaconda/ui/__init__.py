# Base classes for all user interfaces.
#
# Copyright (C) 2011-2012  Red Hat, Inc.
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
# Red Hat Author(s): Chris Lumens <clumens@redhat.com>
#

__all__ = ["UserInterface"]

import os
from common import collect

class UserInterface(object):
    """This is the base class for all kinds of install UIs.  It primarily
       defines what kinds of dialogs and entry widgets every interface must
       provide that the rest of anaconda may rely upon.
    """
    def __init__(self, storage, payload, instclass):
        """Create a new UserInterface instance.

           The arguments this base class accepts defines the API that interfaces
           have to work with.  A UserInterface does not get free reign over
           everything in the anaconda class, as that would be a big mess.
           Instead, a UserInterface may count on the following:

           storage      -- An instance of storage.Storage.  This is useful for
                           determining what storage devices are present and how
                           they are configured.
           payload      -- An instance of a packaging.Payload subclass.  This
                           is useful for displaying and selecting packages to
                           install, and in carrying out the actual installation.
           instclass    -- An instance of a BaseInstallClass subclass.  This
                           is useful for determining distribution-specific
                           installation information like default package
                           selections and default partitioning.
        """
        if self.__class__ is UserInterface:
            raise TypeError("UserInterface is an abstract class.")

        self.storage = storage
        self.payload = payload
        self.instclass = instclass

        # Register this interface with the top-level ErrorHandler.
        from pyanaconda.errors import errorHandler
        errorHandler.ui = self

    def setup(self, data):
        """Construct all the objects required to implement this interface.
           This method must be provided by all subclasses.
        """
        raise NotImplementedError

    def run(self):
        """Run the interface.  This should do little more than just pass
           through to something else's run method, but is provided here in
           case more is needed.  This method must be provided by all subclasses.
        """
        raise NotImplementedError

    ###
    ### MESSAGE HANDLING METHODS
    ###
    def showError(self, message):
        """Display an error dialog with the given message. There is no return
           value. This method must be implemented by all UserInterface
           subclasses.

           In the code, this method should be used sparingly and only for
           critical errors that anaconda cannot figure out how to recover from.
        """
        raise NotImplementedError

    def showYesNoQuestion(self, message):
        """Display a dialog with the given message that presents the user a yes
           or no choice.  This method returns True if the yes choice is selected,
           and False if the no choice is selected.  From here, anaconda can
           figure out what to do next.  This method must be implemented by all
           UserInterface subclasses.

           In the code, this method should be used sparingly and only for those
           times where anaconda cannot make a reasonable decision.  We don't
           want to overwhelm the user with choices.
        """
        raise NotImplementedError

    def getActionClasses(self, module_pattern, path, hubs, standalone_class):
        """Collect all the Hub and Spoke classes which should be enqueued for
           processing and order them according to their pre/post dependencies.

           :param module_pattern: the full name pattern (pyanaconda.ui.gui.spokes.%s)
                                  of modules we about to import from path
           :type module_pattern: string

           :param path: the directory we are picking up modules from
           :type path: string

           :param hubs: the list of Hub classes we check to be in pre/postForHub
                        attribute of Spokes to pick up
           :type hubs: common.Hub based types

           :param standalone_class: the parent type of Spokes we want to pick up
           :type standalone_class: common.StandaloneSpoke based types
        """


        standalones = collect(module_pattern, path, lambda obj: issubclass(obj, standalone_class) and \
                              getattr(obj, "preForHub", False) or getattr(obj, "postForHub", False))

        actionClasses = []
        for hub in hubs:
            actionClasses.extend(sorted(filter(lambda obj: getattr(obj, "preForHub", None) == hub, standalones),
                                        key=lambda obj: obj.priority))
            actionClasses.append(hub)
            actionClasses.extend(sorted(filter(lambda obj: getattr(obj, "postForHub", None) == hub, standalones),
                                        key=lambda obj: obj.priority))

        return actionClasses

    def mainExceptionWindow(self, text, exn_file):
        """Return window with the exception and buttons for debugging, bug
           reporting and exitting the installer.

           This method will be called only when unhandled exception appears.
        """
        raise NotImplementedError

    def saveExceptionWindow(self, account_manager, signature):
        """Show a window that provides a way to report a bug."""
        raise NotImplementedError
