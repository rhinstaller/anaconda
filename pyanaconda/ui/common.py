# Common classes for user interface
#
# Copyright (C) 2012-2014  Red Hat, Inc.
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

from abc import ABCMeta, abstractproperty

from pyanaconda.constants import ANACONDA_ENVIRON, FIRSTBOOT_ENVIRON
from pyanaconda import screen_access
from pyanaconda.flags import flags
from pyanaconda.iutil import collect
from pyanaconda.isignal import Signal
from pyanaconda import lifecycle

from pykickstart.constants import FIRSTBOOT_RECONFIG, DISPLAY_MODE_TEXT

import logging
log = logging.getLogger("anaconda")

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
    def data(self):
        return self._data

class FirstbootSpokeMixIn(object):
    """This MixIn class marks Spokes as usable for Firstboot
       and Anaconda.
    """
    @classmethod
    def should_run(cls, environment, data):
        """This method is responsible for beginning Spoke initialization
           in the firstboot environment (even before __init__).

           It should return True if the spoke is to be shown
           and False if it should be skipped.

           It might be called multiple times, with or without (None)
           the data argument.
        """
        return check_environment_firstboot(data)

class FirstbootOnlySpokeMixIn(object):
    """This MixIn class marks Spokes as usable for Firstboot."""
    @classmethod
    def should_run(cls, environment, data):
        """This method is responsible for beginning Spoke initialization
           in the firstboot environment (even before __init__).

           It should return True if the spoke is to be shown and False
           if it should be skipped.

           It might be called multiple times, with or without (None)
           the data argument.
        """
        return check_environment_firstboot_only(data)

class Spoke(object, metaclass=ABCMeta):
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

    def __init__(self, storage, payload, instclass):
        """Create a new Spoke instance.

           The arguments this base class accepts defines the API that spokes
           have to work with.  A Spoke does not get free reign over everything
           in the anaconda class, as that would be a big mess.  Instead, a
           Spoke may count on the following:

           data         -- An instance of a pykickstart Handler object.  The
                           Spoke uses this to populate its UI with defaults
                           and to pass results back after it has run. The data
                           property must be implemented by classes inherting
                           from Spoke.
           storage      -- An instance of storage.Storage.  This is useful for
                           determining what storage devices are present and how
                           they are configured.
           payload      -- An instance of a payload.Payload subclass.  This
                           is useful for displaying and selecting packages to
                           install, and in carrying out the actual installation.
           instclass    -- An instance of a BaseInstallClass subclass.  This
                           is useful for determining distribution-specific
                           installation information like default package
                           selections and default partitioning.
        """
        self._storage = storage
        self.payload = payload
        self.instclass = instclass
        self.applyOnSkip = False

        self.visitedSinceApplied = True

        # entry and exit signals
        # - get the hub instance as a single argument
        self.entered = Signal()
        self.exited = Signal()

        # connect default callbacks for the signals
        self.entered.connect(self.entry_logger)
        self.entered.connect(self._mark_screen_visited)
        self.exited.connect(self.exit_logger)

    @abstractproperty
    def data(self):
        pass

    @property
    def storage(self):
        return self._storage

    @classmethod
    def should_run(cls, environment, data):
        """This method is responsible for beginning Spoke initialization.

           It should return True if the spoke is to be shown while in
           <environment> and False if it should be skipped.

           It might be called multiple times, with or without (None)
           the data argument.
        """
        return environment == ANACONDA_ENVIRON

    def apply(self):
        """Apply the selections made on this Spoke to the object's preset
           data object.  This method must be provided by every subclass.
        """
        raise NotImplementedError

    @property
    def changed(self):
        """Have the values on the spoke changed since the last time it was
           run?  If not, the apply and execute methods will be skipped.  This
           is to avoid the spoke doing potentially long-lived and destructive
           actions that are completely unnecessary.
        """
        return True

    @property
    def configured(self):
        """This method returns a list of textual ids that should
           be written into the after-install customization status
           file for the firstboot and GIE to know that the spoke was
           configured and what value groups were provided."""
        return ["%s.%s" % (self.__class__.__module__, self.__class__.__name__)]

    @property
    def completed(self):
        """Has this spoke been visited and completed?  If not and the spoke is
           mandatory, a special warning icon will be shown on the Hub beside the
           spoke, and a highlighted message will be shown at the bottom of the
           Hub.  Installation will not be allowed to proceed until all mandatory
           spokes are complete.

           WARNING: This can be called before the spoke is finished initializing
           if the spoke starts a thread. It should make sure it doesn't access
           things until they are completely setup.
        """
        return False

    @property
    def sensitive(self):
        """May the user click on this spoke's selector and be taken to the spoke?
           This is different from the showable property.  A spoke that is not
           sensitive will still be shown on the hub, but the user may not enter it.
           This is also different from the ready property.  A spoke that is not
           ready may not be entered, but the spoke may become ready in the future.
           A spoke that is not sensitive will likely not become so.

           Most spokes will not want to override this method.
        """
        return True

    @property
    def mandatory(self):
        """Mark this spoke as mandatory. Installation will not be allowed
           to proceed until all mandatory spokes are complete.

           Spokes are mandatory unless marked as not being so.
        """
        return True

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

    @property
    def status(self):
        """Given the current status of whatever this Spoke configures, return
           a very brief string.  The purpose of this is to display something
           on the Hub under the Spoke's title so the user can tell at a glance
           how things are configured.

           A spoke's status line on the Hub can also be overloaded to provide
           information about why a Spoke is not yet ready, or if an error has
           occurred when setting it up.  This can be done by calling
           send_message from pyanaconda.ui.communication with the target
           Spoke's class name and the message to be displayed.

           If the Spoke was not yet ready when send_message was called, the
           message will be overwritten with the value of this status property
           when the Spoke becomes ready.
        """
        raise NotImplementedError


    def _mark_screen_visited(self, spoke_instance):
        """Report the spoke screen as visited to the Spoke Access Manager."""
        screen_access.sam.mark_screen_visited(spoke_instance.__class__.__name__)

    def entry_logger(self, spoke_instance):
        """Log immediately before this spoke is about to be displayed on the
           screen.  Subclasses may override this method if they want to log
           more specific information, but an overridden method should finish
           by calling this method so the entry will be logged.
        """
        log.debug("Entered spoke: %s", spoke_instance)

    def exit_logger(self, spoke_instance):
        """Log when a user leaves the spoke.  Subclasses may override this
           method if they want to log more specific information, but an
           overridden method should finish by calling this method so the
           exit will be logged.
        """
        log.debug("Left spoke: %s", spoke_instance)

    def finished(self):
        """Called when exiting the Summary Hub

        This can be used to cleanup the spoke before continuing the
        installation. This method is optional.
        """
        pass

    # Initialization controller related code
    #
    # - initialization_controller
    # -> The controller for this spokes and all others on the given hub.
    # -> The controller has the init_done signal that can be used to trigger
    #    actions that should happen once all spokes on the given Hub have
    #    finished initialization.
    # -> If there is no Hub (standalone spoke) the property is None
    #
    # - initialize_start()
    # -> Should be called when Spoke initialization is started.
    # -> Needs to be called explicitly, if we called it for every spoke by default
    #    then any spoke that does not call initialize_done() would prevent the
    #    controller form ever triggering the init_done signal.
    #
    # - initialize_done()
    # -> Must be called by every spoke that calls initialize_start() or else the init_done
    #    signal will never be emitted.

    @property
    def initialization_controller(self):
        # standalone spokes don't have a category
        if self.category:
            return lifecycle.get_controller_by_category(category_name=self.category.__name__)
        else:
            return None

    def initialize_start(self):
        # get the correct controller for this spoke
        spoke_controller = self.initialization_controller
        # check if there actually is a controller for this spoke, there might not be one
        # if this is a standalone spoke
        if spoke_controller:
            spoke_controller.module_init_start(self)

    def initialize_done(self):
        # get the correct controller for this spoke
        spoke_controller = self.initialization_controller
        # check if there actually is a controller for this spoke, there might not be one
        # if this is a standalone spoke
        if spoke_controller:
            spoke_controller.module_init_done(self)

    def __repr__(self):
        """Return the class name as representation.

        Returning the class name should be enough the uniquely identify a spoke.
        """
        return self.__class__.__name__


# Inherit abstract methods from Spoke
# pylint: disable=abstract-method
class NormalSpoke(Spoke):
    """A NormalSpoke is a Spoke subclass that is displayed when the user
       selects something on a Hub.  This is what most Spokes in anaconda will
       be based on.

       From a layout perspective, a NormalSpoke takes up the entire screen
       therefore hiding the Hub and its action area.  The NormalSpoke also
       provides some basic navigation information (where you are, what you're
       installing, how to get back to the Hub) at the top of the screen.
    """

    def __init__(self, storage, payload, instclass):
        """Create a NormalSpoke instance."""
        Spoke.__init__(self, storage, payload, instclass)
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
           send_not_ready from pyanaconda.ui.communication with the
           target Spoke's class name.

           While a Spoke is not ready, a progress message may be shown to
           give the user some feedback.  See the status property for details.
        """
        return True

# Inherit abstract methods from NormalSpoke
# pylint: disable=abstract-method
class StandaloneSpoke(Spoke):
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

    def __init__(self, storage, payload, instclass):
        """Create a StandaloneSpoke instance."""
        if self.preForHub and self.postForHub:
            raise AttributeError("StandaloneSpoke instance %s may not have both preForHub and postForHub set" % self)

        Spoke.__init__(self, storage, payload, instclass)

    # Standalone spokes are not part of a hub, and thus have no status.
    # Provide a concrete implementation of status here so that subclasses
    # don't need one.
    @property
    def status(self):
        return None

class Hub(object, metaclass=ABCMeta):
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

    def __init__(self, storage, payload, instclass):
        """Create a new Hub instance.

           The arguments this base class accepts defines the API that Hubs
           have to work with.  A Hub does not get free reign over everything
           in the anaconda class, as that would be a big mess.  Instead, a
           Hub may count on the following:

           data         -- An instance of a pykickstart Handler object.  The
                           Hub uses this to populate its UI with defaults
                           and to pass results back after it has run. The data
                           property must be implemented by classes inheriting
                           from Hub.
           storage      -- An instance of storage.Storage.  This is useful for
                           determining what storage devices are present and how
                           they are configured.
           payload      -- An instance of a payload.Payload subclass.  This
                           is useful for displaying and selecting packages to
                           install, and in carrying out the actual installation.
           instclass    -- An instance of a BaseInstallClass subclass.  This
                           is useful for determining distribution-specific
                           installation information like default package
                           selections and default partitioning.
        """
        self._storage = storage
        self.payload = payload
        self.instclass = instclass

        self.paths = {}
        self._spokes = {}

        # entry and exit signals
        # - get the hub instance as a single argument
        self.entered = Signal()
        self.exited = Signal()

        # connect the default callbacks
        self.entered.connect(self.entry_logger)
        self.exited.connect(self.exit_logger)

    @abstractproperty
    def data(self):
        pass

    @property
    def storage(self):
        return self._storage

    def set_path(self, path_id, paths):
        """Update the paths attribute with list of tuples in the form (module
           name format string, directory name)"""
        self.paths[path_id] = paths

    def entry_logger(self, hub_instance):
        """Log immediately before this hub is about to be displayed on the
           screen.  Subclasses may override this method if they want to log
           more specific information, but an overridden method should finish
           by calling this method so the entry will be logged.

           Note that due to how the GUI flows, hubs are only entered once -
           when they are initially displayed.  Going to a spoke from a hub
           and then coming back to the hub does not count as exiting and
           entering.
        """
        log.debug("Entered hub: %s", hub_instance)

    def _collectCategoriesAndSpokes(self):
        """This method is provided so that is can be overridden in a subclass
           by a custom collect method.
           One example of such usage is the Initial Setup application.
        """
        return collectCategoriesAndSpokes(self.paths, self.__class__, self.data.displaymode.displayMode)

    def exit_logger(self, hub_instance):
        """Log when a user leaves the hub.  Subclasses may override this
           method if they want to log more specific information, but an
           overridden method should finish by calling this method so the
           exit will be logged.

           Note that due to how the GUI flows, hubs are not exited when the
           user selects a spoke from the hub.  They are only exited when the
           continue or quit button is clicked on the hub.
        """
        log.debug("Left hub: %s", hub_instance)

    def __repr__(self):
        """Return the class name as representation.

        Returning the class name should be enough the uniquely identify a hub.
        """
        return self.__class__.__name__

def collect_spokes(mask_paths, category):
    """Return a list of all spoke subclasses that should appear for a given
       category. Look for them in files imported as module_path % basename(f)

       :param mask_paths: list of mask, path tuples to search for classes
       :type mask_paths: list of (mask, path)

       :return: list of Spoke classes belonging to category
       :rtype: list of Spoke classes

    """
    spokes = []
    for mask, path in mask_paths:
        candidate_spokes = (collect(mask, path,
                            lambda obj: hasattr(obj, "category") and obj.category is not None and obj.category.__name__ == category))
        # filter out any spokes from the candidates that have already been visited by the user before
        # (eq. before Anaconda or Initial Setup started) and should not be visible again
        visible_spokes = []
        for candidate in candidate_spokes:
            if screen_access.sam.get_screen_visited(candidate.__name__):
                log.info("Spoke %s will not be displayed because it has already been visited before.",
                         candidate.__name__)
            else:
                visible_spokes.append(candidate)
        spokes.extend(visible_spokes)

    return spokes

def collect_categories(mask_paths, displaymode):
    """Return a list of all category subclasses. Look for them in modules
       imported as module_mask % basename(f) where f is name of all files in path.
    """
    categories = []
    if displaymode == DISPLAY_MODE_TEXT:
        for mask, path in mask_paths:
            categories.extend(collect(mask, path, lambda obj: getattr(obj, "displayOnHubTUI", None) is not None))
    else:
        for mask, path in mask_paths:
            categories.extend(collect(mask, path, lambda obj: getattr(obj, "displayOnHubGUI", None) is not None))

    return categories

def collectCategoriesAndSpokes(paths, klass, displaymode):
    """Collects categories and spokes to be displayed on this Hub

       :param paths: dictionary mapping categories, spokes, and hubs to their
                     their respective search path(s)
       :return: dictionary mapping category class to list of spoke classes
       :rtype: dictionary[category class] -> [ list of spoke classes ]
    """

    ret = {}
    # Collect all the categories this hub displays, then collect all the
    # spokes belonging to all those categories.
    if displaymode == DISPLAY_MODE_TEXT:
        categories = sorted(filter(lambda c: c.displayOnHubTUI == klass.__name__, collect_categories(paths["categories"], displaymode)),
                            key=lambda c: c.sortOrder)
    else:
        categories = sorted(filter(lambda c: c.displayOnHubGUI == klass.__name__, collect_categories(paths["categories"], displaymode)),
                            key=lambda c: c.sortOrder)
    for c in categories:
        ret[c] = collect_spokes(paths["spokes"], c.__name__)

    # As we now have a list of all categories this hub holds we can now register it's controller.
    # We need the list of categories so that spokes can find out which controller they should use
    # based on their category.
    category_names = set()
    for c in categories:
        category_names.add(c.__name__)

    # We have gathered all known category names and more are not expected to be added,
    # so we can now add an initialization controller, which needs the final list
    # of categories for the given hub.
    lifecycle.add_controller(klass.__name__, category_names)

    return ret

def check_environment_firstboot(data, anaconda_check=True, firstboot_check=True, firstboot_data_check=True):
    """Returns true if it is the expected environment."""

    if ANACONDA_ENVIRON in flags.environs and anaconda_check:
        return True
    elif FIRSTBOOT_ENVIRON in flags.environs and firstboot_check:
        if data is None:
            # cannot decide, stay in the game and let another call with data
            # available (will come) decide
            return True
        elif data.firstboot.firstboot == FIRSTBOOT_RECONFIG and firstboot_data_check:
            # generally run spokes in firstboot only if doing reconfig, spokes
            # that should run even if not doing reconfig should override this
            # method
            return True

        return False

def check_environment_firstboot_only(data, firstboot_check=True):
    """Returns true if it is the expected environment."""

    if FIRSTBOOT_ENVIRON in flags.environs and firstboot_check:
        # firstboot only spokes should run in firstboot by default, spokes
        # that should run even if not doing reconfig should override this
        # method
        return True
    else:
        return False
