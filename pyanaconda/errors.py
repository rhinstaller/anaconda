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

from pyanaconda.i18n import _

__all__ = ["ERROR_RAISE", "ERROR_CONTINUE", "ERROR_RETRY",
           "ErrorHandler",
           "InvalidImageSizeError", "MissingImageError", "MediaUnmountError",
           "MediaMountError", "ScriptError",
           "errorHandler"]

class InvalidImageSizeError(Exception):
    pass

class MissingImageError(Exception):
    pass

class MediaMountError(Exception):
    pass

class MediaUnmountError(Exception):
    pass

class ScriptError(Exception):
    pass

class RemovedModuleError(ImportError):
    pass

# These constants are returned by the callback in the ErrorHandler class.
# Each represents a different kind of action the caller can take:
#
# ERROR_RAISE - This is a fatal error, and anaconda can do nothing but quit
#               or raise an exception.  This then feeds into the exception
#               handling framework.
#
# ERROR_CONTINUE - anaconda should continue with whatever it was going to do.
#                  This result comes from non-fatal errors, asking yes/no
#                  questions, and the like.
#
# ERROR_RETRY - This is a serious problem, but anaconda should attempt to
#               try again.  Continued failures may eventually result in an
#               ERROR_RAISE.
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

    def _kickstartErrorHandler(self, *args, **kwargs):
        message = _("The following error was found while parsing the kickstart "
                    "configuration file:\n\n%s") % args[0]
        self.ui.showError(message)
        return ERROR_RAISE

    def _partitionErrorHandler(self, *args, **kwargs):
        message = _("The following errors occurred with your partitioning:\n\n%(errortxt)s\n\n"
                    "The installation will now terminate.") % {"errortxt": str(kwargs["exception"])}
        self.ui.showError(message)
        return ERROR_RAISE

    def _fsResizeHandler(self, *args, **kwargs):
        message = _("An error occurred while resizing the device %s.") % args[0]

        if "details" in kwargs:
            message += "\n\n%s" % kwargs["details"]

        self.ui.showError(message)
        return ERROR_RAISE

    def _noDisksHandler(self, *args, **kwargs):
        message = _("An error has occurred - no valid devices were found on "
                    "which to create new file systems.  Please check your "
                    "hardware for the cause of this problem.")
        self.ui.showError(message)
        return ERROR_RAISE

    def _dirtyFSHandler(self, *args, **kwargs):
        devs = kwargs.pop("devices")
        message = _("The following file systems for your Linux system were "
                    "not unmounted cleanly.  Would you like to mount them "
                    "anyway?\n%s") % "\n".join(devs)
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

    def _mediaUnmountHandler(self, *args, **kwargs):
        device = args[0]
        message = _("An error occurred unmounting the disc.  "
                    "Please make sure you're not accessing "
                    "%s from the shell on tty2 "
                    "and then click OK to retry.") % device.path
        self.ui.showError(message)

    def _noSuchGroupHandler(self, *args, **kwargs):
        group = args[0]
        message = _("You have specified that the group '%s' should be "
                    "installed.  This group does not exist.  Would you like "
                    "to skip this group and continue with "
                    "installation?") % group
        if self.ui.showYesNoQuestion(message):
            return ERROR_CONTINUE
        else:
            return ERROR_RAISE

    def _noSuchPackageHandler(self, *args, **kwargs):
        package = args[0]
        message = _("You have specified that the package '%s' should be "
                    "installed.  This package does not exist.  Would you "
                    "like to skip this package and continue with "
                    "installation?") % package
        if self.ui.showYesNoQuestion(message):
            return ERROR_CONTINUE
        else:
            return ERROR_RAISE

    def _scriptErrorHandler(self, *args, **kwargs):
        lineno = args[0]
        details = args[1]
        message = _("There was an error running the kickstart script at line "
                    "%s.  This is a fatal error and installation will be "
                    "aborted.  The details of this error are:\n\n%s") % \
                   (lineno, details)
        self.ui.showError(message)
        return ERROR_RAISE

    def _payloadInstallHandler(self, *args, **kwargs):
        package = kwargs.pop("package", None)
        if package:
            message = _("There was an error installing the %s package.  This is "
                        "a fatal error and installation will be aborted.") % \
                       package
        else:
            message = _("The following error occurred while installing.  This is "
                        "a fatal error and installation will be aborted.")
        message += "\n\n" + str(kwargs["exception"])

        self.ui.showError(message)
        return ERROR_RAISE

    def _dependencyErrorHandler(self, *args, **kwargs):
        message = _("The following software marked for installation has errors.  "
                    "This is likely caused by an error with\nyour installation source.")
        details = "\n".join(sorted(kwargs["exception"].message))

        self.ui.showDetailedError(message, details)
        return ERROR_RAISE

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
            raise

        _map = {"KickstartError": self._kickstartErrorHandler,
                "PartitioningError": self._partitionErrorHandler,
                "FSResizeError": self._fsResizeHandler,
                "NoDisksError": self._noDisksHandler,
                "DirtyFSError": self._dirtyFSHandler,
                "FSTabTypeMismatchError": self._fstabTypeMismatchHandler,
                "InvalidImageSizeError": self._invalidImageSizeHandler,
                "MissingImageError": self._missingImageHandler,
                "MediaMountError": self._mediaMountHandler,
                "MediaUnmountError": self._mediaUnmountHandler,
                "NoSuchGroup": self._noSuchGroupHandler,
                "NoSuchPackage": self._noSuchPackageHandler,
                "ScriptError": self._scriptErrorHandler,
                "PayloadInstallError": self._payloadInstallHandler,
                "DependencyError": self._dependencyErrorHandler}

        if exn.__class__.__name__ in _map:
            kwargs["exception"] = exn
            rc = _map[exn.__class__.__name__](*args, **kwargs)

        return rc

# Create a singleton of the ErrorHandler class.  It is up to the UserInterface
# subclass to set errorHandler.ui before this class is ever used, or there will
# be trouble.
errorHandler = ErrorHandler()
