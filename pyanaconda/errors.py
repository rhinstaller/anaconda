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

from pyanaconda.core.i18n import _, C_
from pyanaconda.flags import flags
from pyanaconda.modules.common.errors.installation import BootloaderInstallationError, \
    StorageInstallationError
from pyanaconda.modules.common.errors.storage import UnusableStorageError

__all__ = ["ERROR_RAISE", "ERROR_CONTINUE", "ERROR_RETRY", "errorHandler", "InvalidImageSizeError",
           "MissingImageError", "ScriptError", "NonInteractiveError", "CmdlineError", "ExitError"]


class InvalidImageSizeError(Exception):
    def __init__(self, message, filename):
        Exception.__init__(self, message)
        self.filename = filename


class MissingImageError(Exception):
    pass


class ScriptError(Exception):
    def __init__(self, lineno, details):
        Exception.__init__(self)
        self.lineno = lineno
        self.details = details


class NonInteractiveError(Exception):
    pass


class CmdlineError(NonInteractiveError):
    pass


class RemovedModuleError(ImportError):
    pass


class PasswordCryptError(Exception):
    def __init__(self, algo):
        Exception.__init__(self)
        self.algo = algo


class ExitError(RuntimeError):
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
# TOP-LEVEL ERROR HANDLING OBJECT
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

    def _storage_install_handler(self, exn):
        message = _("An error occurred while activating your storage configuration.")
        details = str(exn)

        self.ui.showDetailedError(message, details)
        return ERROR_RAISE

    def _storage_reset_handler(self, exn):
        message = (_("There is a problem with your existing storage configuration "
                     "or your initial settings, for example a kickstart file. "
                     "You must resolve this matter before the installation can "
                     "proceed. There is a shell available for use which you "
                     "can access by pressing ctrl-alt-f1 and then ctrl-b 2."
                     "\n\nOnce you have resolved the issue you can retry the "
                     "storage scan. If you do not fix it you will have to exit "
                     "the installer."))
        details = str(exn)
        buttons = (C_("GUI|Storage Detailed Error Dialog", "_Exit Installer"),
                   C_("GUI|Storage Detailed Error Dialog", "_Retry"))
        if self.ui.showDetailedError(message, details, buttons=buttons):
            return ERROR_RETRY
        else:
            return ERROR_RAISE

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

    def _install_specs_handler(self, exn):
        broken_packages = exn.error_pkg_specs
        broken_groups_modules = exn.error_group_specs
        module_depsolv_errors = exn.module_depsolv_errors

        # We use the nice exception string representation
        # provided by DNF as the base of our error message.
        message = "{}\n\n".format(exn)

        # if we have at least one broken package, group or module we will abort the installation
        if broken_packages or broken_groups_modules or module_depsolv_errors:
            message = message + _("Some packages, groups or modules are broken, the installation "
                                  "will be aborted.")
            self.ui.showError(message)
            return ERROR_RAISE
        # "just" missing packages, groups or modules - we give the user an option to continue
        else:
            message = message + _("Would you like to ignore this and continue with installation?")
            if self.ui.showYesNoQuestion(message):
                return ERROR_CONTINUE
            else:
                return ERROR_RAISE

    def _no_module_stream_specified(self, exn):
        message = _("Stream was not specified for a module without a default stream. This is "
                    "a fatal error and installation will be aborted. The details "
                    "of this error are:\n\n%(exception)s") % \
                            {"exception": exn}
        self.ui.showError(message)
        return ERROR_RAISE

    def _multiple_module_streams_specified(self, exn):
        message = _("Multiple streams have been specified for a single module. This is "
                    "a fatal error and installation will be aborted. The details "
                    "of this error are:\n\n%(exception)s") % \
                            {"exception": exn}
        self.ui.showError(message)
        return ERROR_RAISE

    def _scriptErrorHandler(self, exn):
        message = _("There was an error running the kickstart script at line "
                    "%(lineno)s.  This is a fatal error and installation will be "
                    "aborted.  The details of this error are:\n\n%(details)s") % \
                   {"lineno": exn.lineno, "details": exn.details}
        self.ui.showError(message)
        return ERROR_RAISE

    def _payloadInstallHandler(self, exn):
        message = _("The following error occurred while installing.  This is "
                    "a fatal error and installation will be aborted.")
        message += "\n\n" + str(exn)

        self.ui.showError(message)
        return ERROR_RAISE

    def _dependencyErrorHandler(self, exn):
        message = _("The following software marked for installation has errors.\n"
                    "This is likely caused by an error with your installation source.")
        details = str(exn)

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

    def _insightsErrorHandler(self, exn):
        message = _("An error occurred during Red Hat Insights configuration. "
                    "Would you like to ignore this and continue with "
                    "installation?")
        message += "\n\n" + str(exn)

        if self.ui.showYesNoQuestion(message):
            return ERROR_CONTINUE
        else:
            return ERROR_RAISE

    def _kickstartRegistrationErrorHandler(self, exn):
        message = _("An error occurred during registration attempt "
                    "triggered by the rhsm kickstart command. "
                    "This could have happened due to incorrect rhsm command arguments "
                    "or subscription infrastructure issues. "
                    "Would you like to ignore this and continue with "
                    "installation?")
        message += "\n\n" + _("Error detail: ") + str(exn)

        if self.ui.showYesNoQuestion(message):
            return ERROR_CONTINUE
        else:
            return ERROR_RAISE

    def _subscriptionTokenTransferErrorHandler(self, exn):
        message = _("Failed to enable Red Hat subscription on the "
                    "installed system."
                    "\n\n"
                    "Your Red Hat subscription might be invalid "
                    "(such as due to an expired developer subscription)."
                    "\n\n"
                    "Would you like to ignore this and continue with "
                    "installation?")

        if self.ui.showYesNoQuestion(message):
            return ERROR_CONTINUE
        else:
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
            raise exn

        if not flags.ksprompt:
            raise NonInteractiveError("Non interactive installation failed: %s" % exn)

        _map = {
            StorageInstallationError.__name__: self._storage_install_handler,
            UnusableStorageError.__name__: self._storage_reset_handler,
            "InvalidImageSizeError": self._invalidImageSizeHandler,
            "MissingImageError": self._missingImageHandler,
            "NoSuchGroup": self._noSuchGroupHandler,
            "NoStreamSpecifiedException": self._no_module_stream_specified,
            "InstallMoreStreamsException": self._multiple_module_streams_specified,
            "MarkingErrors": self._install_specs_handler,
            "ScriptError": self._scriptErrorHandler,
            "PayloadInstallError": self._payloadInstallHandler,
            "DependencyError": self._dependencyErrorHandler,
            BootloaderInstallationError.__name__: self._bootLoaderErrorHandler,
            "PasswordCryptError": self._passwordCryptErrorHandler,
            "InsightsClientMissingError": self._insightsErrorHandler,
            "InsightsConnectError": self._insightsErrorHandler,
            "KickstartRegistrationError": self._kickstartRegistrationErrorHandler,
            "SubscriptionTokenTransferError": self._subscriptionTokenTransferErrorHandler,
        }

        if exn.__class__.__name__ in _map:
            rc = _map[exn.__class__.__name__](exn)

        return rc


# Create a singleton of the ErrorHandler class.  It is up to the UserInterface
# subclass to set errorHandler.ui before this class is ever used, or there will
# be trouble.
errorHandler = ErrorHandler()
