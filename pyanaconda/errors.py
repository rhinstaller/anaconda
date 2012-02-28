#
# errors.py: exception classes used throughout anaconda
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

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

__all__ = ["ERROR_RAISE", "ERROR_CONTINUE", "ERROR_RETRY",
           "ErrorHandler",
           "InvalidImageSizeError", "MissingImageError", "MediaUnmountError",
           "MediaMountError",
           "errorHandler"]

class InvalidImageSizeError(Exception):
    pass

class MissingImageError(Exception):
    pass

class MediaMountError(Exception):
    pass

class MediaUnmountError(Exception):
    pass

import pyanaconda.storage.errors as StorageError

"""These constants are returned by the callback in the ErrorHandler class.
   Each represents a different kind of action the caller can take:

   ERROR_RAISE - This is a fatal error, and anaconda can do nothing but quit
                 or raise an exception.  This then feeds into the exception
                 handling framework.

   ERROR_CONTINUE - anaconda should continue with whatever it was going to do.
                    This result comes from non-fatal errors, asking yes/no
                    questions, and the like.

   ERROR_RETRY - This is a serious problem, but anaconda should attempt to
                 try again.  Continued failures may eventually result in an
                 ERROR_RAISE.
"""
ERROR_RAISE = 0
ERROR_CONTINUE = 1
ERROR_RETRY = 2

###
### TOP-LEVEL ERROR HANDLING OBJECT
###

class ErrorHandler(object):
    """This object makes up one part of anaconda's error handling system.  This
       part is the UI-agnostic error callback.  Throughout anaconda, various
       error conditions can occur in places that need to pop up a dialog, but
       should not know anything about the type or details of the UI.  In order
       to accomplish this, each pyanaconda.ui.UserInterface subclass presents a
       common set of dialog methods.

       The entry point to these methods is through the cb method of this class,
       which acts as a dispatcher to the appropriate handler, which in turn
       pops up the correct kind of dialog.  The result of all this is one of the
       ERROR_* constants defined elsewhere in this module.  The original calling
       code must then interpret this result and take the appropriate action.

       For details on the other parts of the error handling system, see the
       documentation for pyanaconda.ui.UserInterface and pyanaconda.exception.
    """
    def __init__(self, ui=None):
        self.ui = ui

    def _noDisksHandler(self, *args, **kwargs):
        message = _("An error has occurred - no valid devices were found on "
                    "which to create new file systems.  Please check your "
                    "hardware for the cause of this problem.")
        self.ui.showError(message)
        return ERROR_RAISE

    def _dirtyFSHandler(self, *args, **kwargs):
        # FIXME: for rescue it must be possible to continue, but for upgrade
        #        it must be fatal
        devs = kwargs.pop("devices")
        message = _("The following file systems for your Linux system were "
                    "not unmounted cleanly.  Would you like to mount them "
                    "anyway?\n%s") % "\n".join(devices)
        if self.ui.showYesNoQuestion(message):
            return ERROR_CONTINUE
        else:
            return ERROR_RAISE

    def _fstabTypeMismatchHandler(self, *args, **kwargs):
        # FIXME: include the two types in the message instead of including
        #        the raw exception text
        message = _("There is an entry in your /etc/fstab file that contains "
                    "an invalid or incorrect filesystem type:\n\n")
        message += " " + str(kwargs["exception"])
        self.ui.showError(message)

    def _invalidImageSizeHandler(self, *args, **kwargs):
        filename = args[0]
        message = _("The ISO image %s has a size which is not "
                    "a multiple of 2048 bytes.  This may mean "
                    "it was corrupted on transfer to this computer."
                    "\n\n"
                    "It is recommended that you exit and abort your "
                    "installation, but you can choose to continue if "
                    "you think this is in error. Would you like to "
                    "continue using this image?") % filename
        if self.ui.showYesNoQuestion(message):
            return ERROR_CONTINUE
        else:
            return ERROR_RAISE

    def _missingImageHandler(self, *args, **kwargs):
        message = _("The installer has tried to mount the "
                    "installation image, but cannot find it on "
                    "the hard drive.\n\n"
                    "Should I try again to locate the image?")
        if self.ui.showYesNoQuestion(message):
            return ERROR_RETRY
        else:
            return ERROR_RAISE

    def _mediaMountHandler(self, *args, **kwargs):
        device = args[0]
        message = _("An error occurred mounting the source "
                    "device %s. Retry?") % device.name
        if self.ui.showYesNoQuestion(message):
            return ERROR_RETRY
        else:
            return ERROR_RAISE

    def mediaUnmountHandler(self, *args, **kwargs):
        device = args[0]
        message = _("An error occurred unmounting the disc.  "
                    "Please make sure you're not accessing "
                    "%s from the shell on tty2 "
                    "and then click OK to retry.") % device.path
        self.ui.showError(message)

    def cb(self, exn, *args, **kwargs):
        """This method is the callback that all error handling should pass
           through.  The return value is one of the ERROR_* constants defined
           in this module, though the exact constant returned depends on the
           kind of exception being handled.

           Arguments:

           exn      -- An instance of some Exception.
           args     -- A tuple of positional arguments, unused in this code.
           kwargs   -- A dict of keyword arguments.  The arguments expected
                       depends on the exception being handled.
        """
        rc = ERROR_RAISE

        if not self.ui:
            raise exn

        _map = {StorageError.NoDisksError: self._noDisksHandler,
                StorageError.DirtyFSError: self._dirtyFSHandler,
                StorageError.FSTabTypeMismatchError: self._fstabTypeMismatchHandler,
                InvalidImageSizeError: self._invalidImageSizeHandler,
                MissingImageError: self._missingImageHandler,
                MediaMountError: self._mediaMountError,
                MediaUnmountError: self._mediaUnmountError}

        if exn in _map:
            kwargs["exception"] = exn
            rc = _map[exn](*args, **kwargs)

        return rc

# Create a singleton of the ErrorHandler class.  It is up to the UserInterface
# subclass to set errorHandler.ui before this class is ever used, or there will
# be trouble.
errorHandler = ErrorHandler()
