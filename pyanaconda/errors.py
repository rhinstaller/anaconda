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
           "InvalidImageSizeError", "MissingImageError", "MediaUnmountError",
           "MediaMountError", "ScriptError", "CmdlineError",
           "errorHandler"]

class InvalidImageSizeError(Exception):
    def __init__(self, message, filename):
        Exception.__init__(self, message)
        self.filename = filename

class MissingImageError(Exception):
    pass

class MediaMountError(Exception):
    def __init__(self, device):
        Exception.__init__(self)
        self.device = device

class MediaUnmountError(Exception):
    def __init__(self, device):
        Exception.__init__(self)
        self.device = device

class ScriptError(Exception):
    def __init__(self, lineno, details):
        Exception.__init__(self)
        self.lineno = lineno
        self.details = details

class CmdlineError(Exception):
    pass

class RemovedModuleError(ImportError):
    pass

class PasswordCryptError(Exception):
    def __init__(self, algo):
        Exception.__init__(self)
        self.algo = algo

class ZIPLError(Exception):
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

    def _partitionErrorHandler(self, exn):
        message = _("The following errors occurred with your partitioning:\n\n%(errortxt)s\n\n"
                    "The installation will now terminate.") % {"errortxt": exn}
        self.ui.showError(message)
        return ERROR_RAISE

    def _fsResizeHandler(self, exn):
        message = _("An error occurred while resizing the device %s.") % exn

        if exn.details:
            message += "\n\n%s" % exn.details

        self.ui.showError(message)
        return ERROR_RAISE

    def _noDisksHandler(self, exn):
        message = _("An error has occurred - no valid devices were found on "
                    "which to create new file systems.  Please check your "
                    "hardware for the cause of this problem.")
        self.ui.showError(message)
        return ERROR_RAISE

    def _fstabTypeMismatchHandler(self, exn):
        # FIXME: include the two types in the message instead of including
        #        the raw exception text
        message = _("There is an entry in your /etc/fstab file that contains "
                    "an invalid or incorrect file system type:\n\n")
        message += " " + str(exn)
        self.ui.showError(message)

    def _invalidImageSizeHandler(self, exn):
        message = _("The ISO image %s has a size which is not "
                    "a multiple of 2048 bytes.  This may mean "
                    "it was corrupted on transfer to this computer."
                    "\n\n"
                    "It is recommended that you exit and abort your "
                    "installation, but you can choose to continue if "
                    "you think this is in error. Would you like to "
                    "continue using this image?") % exn.filename
        if self.ui.showYesNoQuestion(message):
            return ERROR_CONTINUE
        else:
            return ERROR_RAISE

    def _missingImageHandler(self, exn):
        message = _("The installer has tried to mount the "
                    "installation image, but cannot find it on "
                    "the hard drive.\n\n"
                    "Should I try again to locate the image?")
        if self.ui.showYesNoQuestion(message):
            return ERROR_RETRY
        else:
            return ERROR_RAISE

    def _mediaMountHandler(self, exn):
        message = _("An error occurred mounting the source "
                    "device %s. Retry?") % exn.device.name
        if self.ui.showYesNoQuestion(message):
            return ERROR_RETRY
        else:
            return ERROR_RAISE

    def _mediaUnmountHandler(self, exn):
        message = _("An error occurred unmounting the disc.  "
                    "Please make sure you're not accessing "
                    "%s from the shell on tty2 "
                    "and then click OK to retry.") % exn.device.path
        self.ui.showError(message)

    def _noSuchGroupHandler(self, exn):
        if exn.required:
            message = _("The group '%s' is required for this installation. "
                        "This group does not exist. This is a fatal error and "
                        "installation will be aborted.") % exn.group
            self.ui.showError(message)
            return ERROR_RAISE
        elif exn.adding:
            message = _("You have specified that the group '%s' should be "
                        "installed.  This group does not exist.  Would you like "
                        "to ignore this group and continue with "
                        "installation?") % exn.group
        else:
            message = _("You have specified that the group '%s' should be "
                        "excluded from installation.  This group does not exist.  "
                        "Would you like to ignore this group and continue with "
                        "installation?") % exn.group

        if self.ui.showYesNoQuestion(message):
            return ERROR_CONTINUE
        else:
            return ERROR_RAISE

    def _noSuchPackageHandler(self, exn):
        if exn.required:
            message = _("The package '%s' is required for this installation. "
                        "This package does not exist. This is a fatal error and "
                        "installation will be aborted.") % exn.package
            self.ui.showError(message)
            return ERROR_RAISE

        else:
            message = _("You have specified that the package '%s' should be "
                        "installed.  This package does not exist.  Would you "
                        "like to ignore this package and continue with "
                        "installation?") % exn.package

            if self.ui.showYesNoQuestion(message):
                return ERROR_CONTINUE
            else:
                return ERROR_RAISE

    def _scriptErrorHandler(self, exn):
        message = _("There was an error running the kickstart script at line "
                    "%(lineno)s.  This is a fatal error and installation will be "
                    "aborted.  The details of this error are:\n\n%(details)s") % \
                   {"lineno": exn.lineno, "details" : exn.details}
        self.ui.showError(message)
        return ERROR_RAISE

    def _payloadInstallHandler(self, exn):
        message = _("The following error occurred while installing.  This is "
                    "a fatal error and installation will be aborted.")
        message += "\n\n" + str(exn)

        self.ui.showError(message)
        return ERROR_RAISE

    def _dependencyErrorHandler(self, exn):
        message = _("The following software marked for installation has errors.  "
                    "This is likely caused by an error with\nyour installation source.")
        details = "\n".join(sorted(exn.message))

        self.ui.showDetailedError(message, details)
        return ERROR_RAISE

    def _bootLoaderErrorHandler(self, exn):
        message = _("The following error occurred while installing the boot loader. "
                    "The system will not be bootable. "
                    "Would you like to ignore this and continue with "
                    "installation?")
        message += "\n\n" + str(exn)

        if self.ui.showYesNoQuestion(message):
            return ERROR_CONTINUE
        else:
            return ERROR_RAISE

    def _passwordCryptErrorHandler(self, exn):
        message = _("Unable to encrypt password: unsupported algorithm %s") % exn.algo

        self.ui.showError(message)
        return ERROR_RAISE

    def _ziplErrorHandler(self, *args, **kwargs):
        details = kwargs["exception"]
        message = _("Installation was stopped due to an error installing the "
                    "boot loader. The exact error message is:\n\n%s\n\n"
                    "The installer will now terminate.") % details

        self.ui.showError(message)
        return ERROR_RAISE

    def cb(self, exn):
        """This method is the callback that all error handling should pass
           through.  The return value is one of the ERROR_* constants defined
           in this module, though the exact constant returned depends on the
           kind of exception being handled.

           Arguments:

           exn      -- An instance of some Exception.
        """
        rc = ERROR_RAISE

        if not self.ui:
            raise

        _map = {"PartitioningError": self._partitionErrorHandler,
                "FSResizeError": self._fsResizeHandler,
                "NoDisksError": self._noDisksHandler,
                "FSTabTypeMismatchError": self._fstabTypeMismatchHandler,
                "InvalidImageSizeError": self._invalidImageSizeHandler,
                "MissingImageError": self._missingImageHandler,
                "MediaMountError": self._mediaMountHandler,
                "MediaUnmountError": self._mediaUnmountHandler,
                "NoSuchGroup": self._noSuchGroupHandler,
                "NoSuchPackage": self._noSuchPackageHandler,
                "ScriptError": self._scriptErrorHandler,
                "PayloadInstallError": self._payloadInstallHandler,
                "DependencyError": self._dependencyErrorHandler,
                "BootLoaderError": self._bootLoaderErrorHandler,
                "PasswordCryptError": self._passwordCryptErrorHandler,
                "ZIPLError": self._ziplErrorHandler}

        if exn.__class__.__name__ in _map:
            rc = _map[exn.__class__.__name__](exn)

        return rc

# Create a singleton of the ErrorHandler class.  It is up to the UserInterface
# subclass to set errorHandler.ui before this class is ever used, or there will
# be trouble.
errorHandler = ErrorHandler()
