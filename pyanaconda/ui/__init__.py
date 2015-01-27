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

import copy
from pyanaconda.ui.common import collect

class PathDict(dict):
    """Dictionary class supporting + operator"""
    def __add__(self, ext):
        new_dict = copy.copy(self)
        for key, value in ext.items():
            try:
                new_dict[key].extend(value)
            except KeyError:
                new_dict[key] = value[:]

        return new_dict

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

    paths = PathDict({})

    @property
    def tty_num(self):
        """Returns the number of tty the UserInterface is running on."""
        raise NotImplementedError

    @classmethod
    def update_paths(cls, pathdict):
        """Receives pathdict and appends it's contents to the current
           class defined search path dictionary."""
        for k,v in pathdict.items():
            cls.paths.setdefault(k, [])
            cls.paths[k].extend(v)

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

    @property
    def meh_interface(self):
        """
        Returns an interface for exception handling (defined by python-meh's
        AbstractIntf class).

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

    def _collectActionClasses(self, module_pattern_w_path, standalone_class):
        """Collect all the Hub and Spoke classes which should be enqueued for
           processing.

           :param module_pattern_w_path: the full name patterns (pyanaconda.ui.gui.spokes.%s)
                                         and directory paths to modules we are about to import
           :type module_pattern_w_path: list of (string, string)

           :param standalone_class: the parent type of Spokes we want to pick up
           :type standalone_class: common.StandaloneSpoke based types

           :return: list of Spoke classes with standalone_class as a parent
           :rtype: list of Spoke classes

        """
        standalones = []

        for module_pattern, path in module_pattern_w_path:
            standalones.extend(collect(module_pattern, path, lambda obj: issubclass(obj, standalone_class) and \
                                       getattr(obj, "preForHub", False) or getattr(obj, "postForHub", False)))

        return standalones

    def _orderActionClasses(self, spokes, hubs):
        """Order all the Hub and Spoke classes which should be enqueued for
           processing according to their pre/post dependencies.

           :param spokes: the classes we are to about order according
                          to the hub dependencies
           :type spokes: list of Spoke instances

           :param hubs: the list of Hub classes we check to be in pre/postForHub
                        attribute of Spokes to pick up
           :type hubs: common.Hub based types
        """

        actionClasses = []
        for hub in hubs:
            actionClasses.extend(sorted(filter(lambda obj, h=hub: getattr(obj, "preForHub", None) == h, spokes),
                                        key=lambda obj: obj.priority))
            actionClasses.append(hub)
            actionClasses.extend(sorted(filter(lambda obj, h=hub: getattr(obj, "postForHub", None) == h, spokes),
                                        key=lambda obj: obj.priority))

        return actionClasses
