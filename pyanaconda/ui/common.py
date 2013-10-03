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
import imp
import inspect
import copy
import sys
import types

from pyanaconda.constants import ANACONDA_ENVIRON, FIRSTBOOT_ENVIRON
from pyanaconda.errors import RemovedModuleError
from pykickstart.constants import FIRSTBOOT_RECONFIG

import logging
log = logging.getLogger("anaconda")

class PathDict(dict):
    """Dictionary class supporting + operator"""
    def __add__(self, ext):
        new_dict = copy.copy(self)
        for key, value in ext.iteritems():
            try:
                new_dict[key].extend(value)
            except KeyError:
                new_dict[key] = value[:]

        return new_dict

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

        if environment == ANACONDA_ENVIRON:
            return True
        elif environment == FIRSTBOOT_ENVIRON and data is None:
            # cannot decide, stay in the game and let another call with data
            # available (will come) decide
            return True
        elif environment == FIRSTBOOT_ENVIRON and \
                data and data.firstboot.firstboot == FIRSTBOOT_RECONFIG:
            # generally run spokes in firstboot only if doing reconfig, spokes
            # that should run even if not doing reconfig should override this
            # method
            return True
        else:
            return False


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

        if environment == FIRSTBOOT_ENVIRON:
            # firstboot only spokes should run in firstboot by default, spokes
            # that should run even if not doing reconfig should override this
            # method
            return True
        else:
            return False

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

        self._visitedSinceApplied = True

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
        """
        return False

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
           send_message from pyanaconda.ui.communication with the target
           Spoke's class name and the message to be displayed.

           If the Spoke was not yet ready when send_message was called, the
           message will be overwritten with the value of this status property
           when the Spoke becomes ready.
        """
        raise NotImplementedError

class NormalSpoke(Spoke):
    """A NormalSpoke is a Spoke subclass that is displayed when the user
       selects something on a Hub.  This is what most Spokes in anaconda will
       be based on.

       From a layout perspective, a NormalSpoke takes up the entire screen
       therefore hiding the Hub and its action area.  The NormalSpoke also
       provides some basic navigation information (where you are, what you're
       installing, how to get back to the Hub) at the top of the screen.
    """

    priority = 100

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
           send_not_ready from pyanaconda.ui.communication with the
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

        NormalSpoke.__init__(self, data, storage, payload, instclass)

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

        self.storage = storage
        self.payload = payload
        self.instclass = instclass

        self.paths = {}
        self._spokes = {}

        # spokes for which environments this hub should collect?
        self._environs = [ANACONDA_ENVIRON]

    def set_path(self, path_id, paths):
        """Update the paths attribute with list of tuples in the form (module
           name format string, directory name)"""
        self.paths[path_id] = paths
        
def collect(module_pattern, path, pred):
    """Traverse the directory (given by path), import all files as a module
       module_pattern % filename and find all classes within that match
       the given predicate.  This is then returned as a list of classes.

       It is suggested you use collect_categories or collect_spokes instead of
       this lower-level method.

       :param module_pattern: the full name pattern (pyanaconda.ui.gui.spokes.%s)
                              we want to assign to imported modules
       :type module_pattern: string

       :param path: the directory we are picking up modules from
       :type path: string

       :param pred: function which marks classes as good to import
       :type pred: function with one argument returning True or False
    """

    retval = []
    try:
        contents = os.listdir(path)
    # when the directory "path" does not exist
    except OSError:
        return []
    
    for module_file in contents:
        if (not module_file.endswith(".py")) and \
           (not module_file.endswith(".so")):
            continue

        if module_file == "__init__.py":
            continue

        try:
            mod_name = module_file[:module_file.rindex(".")]
        except ValueError:
            mod_name = module_file

        mod_info = None
        module = None

        try:
            imp.acquire_lock()
            (fo, module_path, module_flags) = imp.find_module(mod_name, [path])
            module = sys.modules.get(module_pattern % mod_name)

            # do not load module if any module with the same name
            # is already imported
            if not module:
                # try importing the module the standard way first
                # uses sys.path and the module's full name!
                try:
                    __import__(module_pattern % mod_name)
                    module = sys.modules[module_pattern % mod_name]

                # if it fails (package-less addon?) try importing single file
                # and filling up the package structure voids
                except ImportError:
                    # prepare dummy modules to prevent RuntimeWarnings
                    module_parts = (module_pattern % mod_name).split(".")

                    # remove the last name as it will be inserted by the import
                    module_parts.pop()

                    # make sure all "parent" modules are in sys.modules
                    for l in range(len(module_parts)):
                        module_part_name = ".".join(module_parts[:l+1])
                        if module_part_name not in sys.modules:
                            module_part = types.ModuleType(module_part_name)
                            module_part.__path__ = [path]
                            sys.modules[module_part_name] = module_part

                    # load the collected module
                    module = imp.load_module(module_pattern % mod_name,
                                             fo, module_path, module_flags)


            # get the filenames without the extensions so we can compare those
            # with the .py[co]? equivalence in mind
            # - we do not have to care about files without extension as the
            #   condition at the beginning of the for loop filters out those
            # - module_flags[0] contains the extension of the module imp found
            candidate_name = module_path[:module_path.rindex(module_flags[0])]
            loaded_name, loaded_ext = module.__file__.rsplit(".", 1)

            # restore the extension dot eaten by split
            loaded_ext = "." + loaded_ext
            
            # do not collect classes when the module is already imported
            # from different path than we are traversing
            # this condition checks the module name without file extension
            if candidate_name != loaded_name:
                continue

            # if the candidate file is .py[co]? and the loaded is not (.so)
            # skip the file as well
            if module_flags[0].startswith(".py") and not loaded_ext.startswith(".py"):
                continue

            # if the candidate file is not .py[co]? and the loaded is
            # skip the file as well
            if not module_flags[0].startswith(".py") and loaded_ext.startswith(".py"):
                continue

        except RemovedModuleError:
            # collected some removed module
            continue

        except ImportError as imperr:
            if "pyanaconda" in module_path:
                # failure when importing our own module:
                raise
            log.error("Failed to import module in collect: %s", imperr)
            continue
        finally:
            imp.release_lock()

            if mod_info and mod_info[0]:
                mod_info[0].close()

        p = lambda obj: inspect.isclass(obj) and pred(obj)

        # if __all__ is defined in the module, use it
        if not hasattr(module, "__all__"):
            members = inspect.getmembers(module, p)
        else:
            members = [(name, getattr(module, name))
                       for name in module.__all__
                       if p(getattr(module, name))]
        
        for (name, val) in members:
            retval.append(val)

    return retval

