# Abstract base classes for UI classes
#
# Copyright (C) 2013  Red Hat, Inc.
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

# This file contains abstract base classes that provide specific functionality
# that can be added to another class. The idea is sort-of modelled after Java's
# interfaces. An abstract base class cannot be instatiated, and it provides a
# contract for classes that inherit from it: any method or property marked as
# abstract in the base class must be overriden in the inheriting class. This
# allows for cleaner implementation of certain types of mixin-classes: a class
# that adds functionality to another class can explicitly require that methods
# or properties be provided by the inheriting class or another superclass of
# the inheriting class.
#
# In general, classes that inherit from abstract base classes should place the
# abstract base class at the end of the inheritance list. This way any abstract
# methods or properties in the abc will be overridden by the base classes
# that are first in the inheritance list. For example, an abstract base class
# may add a method that reads from Spoke.data:
#
#    class Mixin(object):
#        __metaclass__ = ABCMeta
#
#        @abstractproperty
#        def data(self):
#            pass
#
#        def isHD(self):
#            return self.data.method == "harddrive"
#
# The Mixin class will add the method isHD to any class that inherits from it,
# and classes that inherit from Mixin must provide a data property.
#
#    class MixedObject(UIObject, Mixin):
#        ....
#
# The method resolution order of MixedObject resolves UIObject.data before
# Mixin.data, so UIObject.data satisfies the requirment that Mixin.data be
# overriden.

from abc import ABCMeta, abstractproperty, abstractmethod

from pyanaconda import constants
from pyanaconda.threading import threadMgr, AnacondaThread
from pyanaconda.ui.communication import hubQ
from pyanaconda.i18n import _
from pyanaconda.payload import payloadMgr
from pyanaconda.anaconda_loggers import get_module_logger

import copy

class StorageCheckHandler(object, metaclass=ABCMeta):
    log = get_module_logger(__name__)
    errors = []
    warnings = []

    def __init__(self, mainSpokeClass="StorageSpoke"):
        self._mainSpokeClass = mainSpokeClass
        self._checking = False

    @abstractproperty
    def storage(self):
        pass

    def run(self):
        threadMgr.add(AnacondaThread(name=constants.THREAD_CHECK_STORAGE,
                                     target=self.checkStorage))

    @property
    def checking_storage(self):
        return self._checking

    def checkStorage(self):
        from pyanaconda.storage_utils import storage_checker

        threadMgr.wait(constants.THREAD_EXECUTE_STORAGE)

        hubQ.send_not_ready(self._mainSpokeClass)
        hubQ.send_message(self._mainSpokeClass, _("Checking storage configuration..."))

        self._checking = True
        report = storage_checker.check(self.storage)
        # Storage spoke and custom spoke communicate errors via StorageCheckHandler,
        # so we need to set errors and warnings class attributes here.
        StorageCheckHandler.errors = report.errors
        StorageCheckHandler.warnings = report.warnings
        self._checking = False
        hubQ.send_ready(self._mainSpokeClass, True)
        report.log(self.log)

class SourceSwitchHandler(object, metaclass=ABCMeta):
    """ A class that can be used as a mixin handling
    installation source switching.
    It will correctly switch to the new method
    and cleanup any previous method set.
    """

    @abstractproperty
    def data(self):
        pass

    @abstractproperty
    def storage(self):
        pass

    def __init__(self):
        self._device = None
        self._current_iso_path = None

    def unset_source(self):
        """Unset an already selected source method.

        Unset the source in kickstart and notify the payload so that it can correctly
        release all related resources (unmount iso files, drop caches, etc.).
        """
        self._clean_hdd_iso()
        self.data.method.method = None
        payloadMgr.restartThread(self.storage, self.data, self.payload, self.instclass, checkmount=False)   # pylint: disable=no-member
        threadMgr.wait(constants.THREAD_PAYLOAD_RESTART)
        threadMgr.wait(constants.THREAD_PAYLOAD)

    def _clean_hdd_iso(self):
        """ Clean HDD ISO usage
        This means unmounting the partition and unprotecting it,
        so it can be used for the installation.
        """
        if self.data.method.method == "harddrive" and self.data.method.partition:
            part = self.data.method.partition
            dev = self.storage.devicetree.get_device_by_name(part)
            if dev:
                dev.protected = False
            # the hdd iso cleanup function might be run multiple times,
            # so make sure the partition still is in the list of protected devices
            if part in self.storage.config.protected_dev_specs:
                self.storage.config.protected_dev_specs.remove(part)

    def set_source_hdd_iso(self, device, iso_path):
        """ Switch to the HDD ISO install source
        :param partition: name of the partition hosting the ISO
        :type partition: string
        :param iso_path: full path to the source ISO file
        :type iso_path: string
        """
        partition = device.name
        # the GUI source spoke also does the copy
        old_source = copy.copy(self.data.method)

        # if a different partition was used previously, unprotect it
        if old_source.method == "harddrive" and old_source.partition != partition:
            self._clean_hdd_iso()

        # protect current device
        if device:
            device.protected = True
            self.storage.config.protected_dev_specs.append(device.name)

        self.data.method.method = "harddrive"
        self.data.method.partition = partition
        # the / gets stripped off by payload.ISOImage
        self.data.method.dir = "/" + iso_path

        # as we already made the device protected when
        # switching to it, we don't need to protect it here

    def set_source_url(self, url=None):
        """ Switch to install source specified by URL """
        # clean any old HDD ISO sources
        self._clean_hdd_iso()

        self.data.method.method = "url"
        if url is not None:
            self.data.method.url = url

    def set_source_nfs(self, opts=None):
        """ Switch to NFS install source """
        # clean any old HDD ISO sources
        self._clean_hdd_iso()

        self.data.method.method = "nfs"
        if opts is not None:
            self.data.method.opts = opts
        if self.data.method.server is None:
            self.data.method.server = ""
        if self.data.method.dir is None:
            self.data.method.dir = ""

    def set_source_cdrom(self):
        """ Switch to cdrom install source """
        # clean any old HDD ISO sources
        self._clean_hdd_iso()

        self.data.method.method = "cdrom"

    def set_source_closest_mirror(self):
        """ Switch to the closest mirror install source """
        # clean any old HDD ISO sources
        self._clean_hdd_iso()

        self.data.method.method = None

class InputCheck(object):
    """Handle an input validation check.

       This class is used by classes that implement InputCheckHandler to
       manage and manipulate input validation check instances.
    """

    # Use as a return value to indicate a passed check
    CHECK_OK = None

    # Treat the check as failed but don't display anything
    # This can be used, for example, to reject empty input without setting
    # a big loud error message.
    CHECK_SILENT = ""

    # Read-only properties
    input_obj = property(lambda s: s._input_obj,
                     doc="The input to check.")
    run_check = property(lambda s: s._run_check,
                         doc="A function to call to perform the input check.")
    data = property(lambda s: s._data,
                    doc="Optional data associated with the input check.")
    check_status = property(lambda s: s._check_status,
                            doc="The current status of the check")

    def __init__(self, parent, input_obj, run_check, data=None):
        """Create a new input validation check.

           :param InputCheckHandler parent: The InputCheckHandler object to which this
                                            check is being added.

           :param function input_obj: An object representing the input to check.

           :param function run_check: A function to call to perform the input check. This
                                      function is called with the InputCheck object as a
                                      parameter.  The return value an object representing
                                      the error state, or CHECK_OK if the check succeeds.

           :param data: Optional data associated with the input check
        """
        self._parent = parent
        self._input_obj = input_obj
        self._run_check = run_check
        self._data = data
        self._check_status = None
        self._enabled = True

    def update_check_status(self):
        """Run an input validation check."""
        if not self.enabled:
            return

        self._check_status = self._run_check(self)
        self._parent.set_status(self)

    @property
    def enabled(self):
        """Whether the check is enabled or not.

           Disabling a check indicates that the status will not change if
           the input changes. The value of check_status will be the result of
           the last time the InputCheck was run when enabled. Disabled checks
           will not be included in InputCheckHandler.failed_checks.
        """
        return self._enabled

    @enabled.setter
    def enabled(self, value):
        self._enabled = value

class InputCheckHandler(object, metaclass=ABCMeta):
    """Provide a framework for adding input validation checks to a screen.

       This helper class provides a mean of defining and associating input
       validation checks with an input screen. Running the checks and acting
       upon the results is left up to the subclasses. Classes implementing
       InputCheckHandler should ensure that the checks are run at the
       appropriate times (e.g., calling InputCheck.update_check_status when
       input is changed), and that input for the screen is not accepted if
       self.failed_checks is not empty.

       See GUIInputCheckHandler and GUISpokeInputCheckHandler for additional
       functionality.
    """

    def __init__(self):
        self._check_list = []

    def _check_re(self, inputcheck):
        """Perform an input validation check against a regular expression."""
        if inputcheck.data['regex'].match(self.get_input(inputcheck.input_obj)):
            return inputcheck.CHECK_OK
        else:
            return inputcheck.data['message']

    @abstractmethod
    def get_input(self, input_obj):
        """Return the input string from an input object.

           :param input_obj: The input object

           :returns: An input string
           :rtype: str
        """
        pass

    @abstractmethod
    def set_status(self, inputcheck):
        """Update the status of the window from the input validation results.

           This function could, for example, set or clear an error on the window,
           or display a message near an input area with invalid data.

           :param InputCheck inputcheck: The InputCheck object whose status last changed.
        """
        pass

    def add_check(self, input_obj, run_check, data=None):

        """Add an input validation check to this object.

           :param input_obj: An object representing the input to check.

           :param function run_check: A function to call to perform the input check. This
                                      function is called with the InputCheck object as a
                                      parameter.  The return value an object representing
                                      the error state, or CHECK_OK if the check succeeds.

           :param data: Optional data associated with the input check

           :returns: The InputCheck object created.
           :rtype: InputCheck
        """
        checkRef = InputCheck(self, input_obj, run_check, data)
        self._check_list.append(checkRef)
        return checkRef

    def add_re_check(self, input_obj, regex, message):
        """Add a check using a regular expression.

           :param function input_obj: An object representing the input to check.

           :param re.RegexObject regex: The regular expression to check input against.

           :param str message: A message to return for failed checks

           :returns: The InputCheck object created.
           :rtype: InputCheck
        """
        return self.add_check(input_obj=input_obj, run_check=self._check_re,
                data={'regex': regex, 'message': message})

    def remove_check(self, inputcheck):
        """Remove an input check.

           If the check being removed is not in the OK status, the status will
           be set to CHECK_OK and set_status will be called.

           :param inputcheck InputCheck: the InputCheck object to remove
           :raise ValueError: if the inputcheck does not exist for this InputCheckHandler
        """
        self._check_list.remove(inputcheck)
        if inputcheck.check_status != InputCheck.CHECK_OK:
            inputcheck._check_status = InputCheck.CHECK_OK
            self.set_status(inputcheck)

    @property
    def failed_checks(self):
        """A generator of all failed input checks"""
        return (c for c in self._check_list \
                if c.enabled and c.check_status != InputCheck.CHECK_OK)

    @property
    def failed_checks_with_message(self):
        """A generator of all failed input checks with an error message"""
        return (c for c in self._check_list \
                if c.enabled and c.check_status not in (InputCheck.CHECK_OK, InputCheck.CHECK_SILENT))

    @property
    def checks(self):
        """An iterator over all input checks"""
        return self._check_list.__iter__()
