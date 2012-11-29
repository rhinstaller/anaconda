# Common classes for user interface
#
# Copyright (C) 2012  Red Hat, Inc.
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
#                    Martin Sivak <msivak@redhat.com>
#

import os
import importlib
import inspect

class UIObject(object):
    """This is the base class from which all other UI classes are derived.  It
       thus contains only attributes and methods that are common to everything
       else.  It should not be directly instantiated.
       """

    def __init__(self, data):
        """Create a new UIObject instance, including loading its uiFile and
           all UI-related objects.

           Instance attributes:

           data     -- An instance of a pykickstart Handler object.  The Hub
                       never directly uses this instance.  Instead, it passes
                       it down into Spokes when they are created and applied.
                       The Hub simply stores this instance so it doesn't need
                       to be passed by the user.
        """
        if self.__class__ is UIObject:
            raise TypeError("UIObject is an abstract class")

        self.skipTo = None
        self._data = data

    def initialize(self):
        """Perform whatever actions are necessary to pre-fill the UI with
           values.  This method is called only once, after the object is
           created.  The difference between this method and __init__ is that
           this method may take a long time (especially for NormalSpokes) and
           thus may be run in its own thread.
        """
        pass

    def refresh(self):
        """Perform whatever actions are necessary to reset the UI immediately
           before it is displayed.  This method is called every time a screen
           is shown, which could potentially be several times in the case of a
           NormalSpoke.  Thus, it's important to not do things like populate
           stores (which could result in the store having duplicate entries) or
           anything that takes a long time (as that will result in a delay
           between the user's action and showing the results).

           For anything potentially long-lived, use the initialize method.
        """
        pass

    @property
    def showable(self):
        """Should this object even be shown?  This method is useful for checking
           some precondition before this screen is shown.  If False is returned,
           the screen will be skipped and the object destroyed.
        """
        return True

    def teardown(self):
        """Perform whatever actions are necessary to clean up after this object
           is done.  It's not necessary for every subclass to have an instance
           of this method.

           NOTE:  It is important for this method to not destroy self.window if
           you are making a Spoke or Hub subclass.  It is assumed that once
           these are instantiated, they live until the program terminates.  This
           is required for various status notifications.
        """
        pass

    @property
    def window(self):
        """Return an object with show_all and hide methods that is to be used
           to display this UI object.
        """
        raise TypeError("UIObject.window has to be overriden")

    @property
    def data(self):
        return self._data

class Spoke(UIObject):
    """A Spoke is a single configuration screen.  There are several different
       places where a Spoke can be displayed, each of which will have its own
       unique class.  A Spoke is typically used when an element in the Hub is
       selected but can also be displayed before a Hub or between multiple
       Hubs.

       What amount of the UI layout a Spoke provides depends upon where it is
       to be shown.  Regardless, the UI of a Spoke should be given by an
       interface description file like glade as often as possible, though this
       is not a strict requirement.

       Class attributes:

       category   -- Under which SpokeCategory shall this Spoke be displayed
                     in the Hub?  This is a reference to a Hub subclass (not an
                     object, but the class itself).  If no category is given,
                     this Spoke will not be displayed.  Note that category is
                     not required for any Spokes appearing before or after a
                     Hub.
       icon       -- The name of the icon to be displayed in the SpokeSelector
                     widget corresponding to this Spoke instance.  If no icon
                     is given, the default from SpokeSelector will be used.
       title      -- The title to be displayed in the SpokeSelector widget
                     corresponding to this Spoke instance.  If no title is
                     given, the default from SpokeSelector will be used.
    """
    category = None
    icon = None
    title = None

    def __init__(self, data, storage, payload, instclass):
        """Create a new Spoke instance.

           The arguments this base class accepts defines the API that spokes
           have to work with.  A Spoke does not get free reign over everything
           in the anaconda class, as that would be a big mess.  Instead, a
           Spoke may count on the following:

           data         -- An instance of a pykickstart Handler object.  The
                           Spoke uses this to populate its UI with defaults
                           and to pass results back after it has run.
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
        if self.__class__ is Spoke:
            raise TypeError("Spoke is an abstract class")

        UIObject.__init__(self, data)
        self.storage = storage
        self.payload = payload
        self.instclass = instclass
        self.applyOnSkip = False

    def apply(self):
        """Apply the selections made on this Spoke to the object's preset
           data object.  This method must be provided by every subclass.
        """
        raise NotImplementedError

    @property
    def completed(self):
        """Has this spoke been visited and completed?  If not, a special warning
           icon will be shown on the Hub beside the spoke, and a highlighted
           message will be shown at the bottom of the Hub.  Installation will not
           be allowed to proceed until all spokes are complete.
        """
        return False

    def execute(self):
        """Cause the data object to take effect on the target system.  This will
           usually be as simple as calling one or more of the execute methods on
           the data object.  This method does not need to be provided by all
           subclasses.

           This method will be called in two different places:  (1) Immediately
           after initialize on kickstart installs.  (2) Immediately after apply
           in all cases.
        """
        pass

    def initialize(self):
        UIObject.initialize(self)

    @property
    def status(self):
        """Given the current status of whatever this Spoke configures, return
           a very brief string.  The purpose of this is to display something
           on the Hub under the Spoke's title so the user can tell at a glance
           how things are configured.

           A spoke's status line on the Hub can also be overloaded to provide
           information about why a Spoke is not yet ready, or if an error has
           occurred when setting it up.  This can be done by calling
           send_message from pyanaconda.ui.gui.communication with the target
           Spoke's class name and the message to be displayed.

           If the Spoke was not yet ready when send_message was called, the
           message will be overwritten with the value of this status property
           when the Spoke becomes ready.
        """
        raise NotImplementedError

class NormalSpoke(Spoke):
    priority = 100

    """A NormalSpoke is a Spoke subclass that is displayed when the user
       selects something on a Hub.  This is what most Spokes in anaconda will
       be based on.

       From a layout perspective, a NormalSpoke takes up the entire screen
       therefore hiding the Hub and its action area.  The NormalSpoke also
       provides some basic navigation information (where you are, what you're
       installing, how to get back to the Hub) at the top of the screen.
    """
    def __init__(self, data, storage, payload, instclass):
        """Create a NormalSpoke instance."""
        if self.__class__ is NormalSpoke:
            raise TypeError("NormalSpoke is an abstract class")

        Spoke.__init__(self, data, storage, payload, instclass)
        self.selector = None

    @property
    def indirect(self):
        """If this property returns True, then this spoke is considered indirect.
           An indirect spoke is one that can only be reached through another spoke
           instead of directly through the hub.  One example of this is the
           custom partitioning spoke, which may only be accessed through the
           install destination spoke.

           Indirect spokes do not need to provide a completed or status property.

           For most spokes, overriding this property is unnecessary.
        """
        return False

    @property
    def ready(self):
        """Returns True if the Spoke has all the information required to be
           displayed.  Almost all spokes should keep the default value here.
           Only override this method if the Spoke requires some potentially
           long-lived process (like storage probing) before it's ready.

           A Spoke may be marked as ready or not by calling send_ready or
           send_not_ready from pyanaconda.ui.gui.communication with the
           target Spoke's class name.

           While a Spoke is not ready, a progress message may be shown to
           give the user some feedback.  See the status property for details.
        """
        return True

class StandaloneSpoke(NormalSpoke):
    """A StandaloneSpoke is a Spoke subclass that is displayed apart from any
       Hub.  It is suitable to be used as a Welcome screen.

       From a layout perspective, a StandaloneSpoke provides a full screen
       interface.  However, it also provides navigation information at the top
       and bottom of the screen that makes it look like the StandaloneSpoke
       fits into some other UI element.

       Class attributes:

       preForHub/postForHub   -- A reference to a Hub subclass this Spoke is
                                 either a pre or post action for.  Only one of
                                 these may be set at a time.  Note that all
                                 post actions will be run for one hub before
                                 any pre actions for the next.
       priority               -- This value is used to sort pre and post
                                 actions.  The lower a value, the earlier it
                                 will be run.  So a value of 0 for a post action
                                 ensures it will run immediately after a Hub,
                                 while a value of 0 for a pre actions means
                                 it will run as the first thing.
    """
    preForHub = None
    postForHub = None

    def __init__(self, data, storage, payload, instclass):
        """Create a StandaloneSpoke instance."""
        if self.__class__ is StandaloneSpoke:
            raise TypeError("StandaloneSpoke is an abstract class")

        if self.preForHub and self.postForHub:
            raise AttributeError("StandaloneSpoke instance %s may not have both preForHub and postForHub set" % self)

        Spoke.__init__(self, data, storage, payload, instclass)



class PersonalizationSpoke(Spoke):
    """A PersonalizationSpoke is a Spoke subclass that is displayed when the
       user selects something on the Hub during package installation.

       From a layout perspective, a PersonalizationSpoke takes up the middle
       of the screen therefore hiding the Hub but leaving its action area
       displayed.  This allows the user to continue seeing package installation
       progress being made.  The PersonalizationSpoke also provides the same
       basic navigation information at the top of the screen as a NormalSpoke.
    """
    def __init__(self, data, storage, payload, instclass):
        """Create a PersonalizationSpoke instance."""
        if self.__class__ is PersonalizationSpoke:
            raise TypeError("PersonalizationSpoke is an abstract class")

        Spoke.__init__(self, data, storage, payload, instclass)

class Hub(UIObject):
    """A Hub is an overview UI screen.  A Hub consists of one or more grids of
       configuration options that the user may choose from.  Each grid is
       provided by a SpokeCategory, and each option is provided by a Spoke.
       When the user dives down into a Spoke and is finished interacting with
       it, they are returned to the Hub.

       Some Spokes are required.  The user must interact with all required
       Spokes before they are allowed to proceed to the next stage of
       installation.

       From a layout perspective, a Hub is the entirety of the screen, though
       the screen itself can be roughly divided into thirds.  The top third is
       some basic navigation information (where you are, what you're
       installing).  The middle third is the grid of Spokes.  The bottom third
       is an action area providing additional buttons (quit, continue) or
       progress information (during package installation).

       Installation may consist of multiple chained Hubs, or Hubs with
       additional standalone screens either before or after them.
    """

    def __init__(self, data, storage, payload, instclass):
        """Create a new Hub instance.

           The arguments this base class accepts defines the API that Hubs
           have to work with.  A Hub does not get free reign over everything
           in the anaconda class, as that would be a big mess.  Instead, a
           Hub may count on the following:

           data         -- An instance of a pykickstart Handler object.  The
                           Hub uses this to populate its UI with defaults
                           and to pass results back after it has run.
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
        UIObject.__init__(self, data)

        self._spokes = {}
        self.storage = storage
        self.payload = payload
        self.instclass = instclass

def collect(module_pattern, path, pred):
    """Traverse the directory (given by path), import all files as a module
       module_pattern % filename and find all classes withing that match
       the given predicate.  This is then returned as a list of classes.

       It is suggested you use collect_categories or collect_spokes instead of
       this lower-level method.

       :param module_pattern: the full name pattern (pyanaconda.ui.gui.spokes.%s)
                              of modules we about to import from path
       :type module_pattern: string

       :param path: the directory we are picking up modules from
       :type path: string


       :param pred: function which marks classes as good to import
       :type pred: function with one argument returning True or False
    """

    retval = []
    for module_file in os.listdir(path):
        if not module_file.endswith(".py") or module_file == "__init__.py":
            continue

        mod_name = module_file[:-3]
        module = importlib.import_module(module_pattern % mod_name)

        p = lambda obj: inspect.isclass(obj) and pred(obj)

        for (name, val) in inspect.getmembers(module, p):
            retval.append(val)

    return retval
