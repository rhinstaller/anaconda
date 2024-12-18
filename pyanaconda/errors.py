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
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.i18n import C_, _
from pyanaconda.flags import flags
from pyanaconda.modules.common.errors.installation import (
    BootloaderInstallationError,
    InsightsClientMissingError,
    InsightsConnectError,
    NonCriticalInstallationError,
    PayloadInstallationError,
    StorageInstallationError,
)
from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.common.errors.storage import UnusableStorageError
from pyanaconda.modules.common.errors.subscription import SatelliteProvisioningError

log = get_module_logger(__name__)

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

class ErrorHandler:
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
        self.map = self._get_default_mapping()

    def _get_default_mapping(self):
        return {
            # Anaconda errors
            ScriptError.__name__: self._script_error_handler,

            # Storage errors
            UnusableStorageError.__name__: self._storage_reset_handler,
            StorageInstallationError.__name__: self._storage_install_handler,
            BootloaderInstallationError.__name__: self._bootloader_error_handler,

            # Payload DBus errors
            SourceSetupError.__name__: self._payload_setup_handler,
            PayloadInstallationError.__name__: self._payload_install_handler,

            # Subscription related errors
            InsightsClientMissingError.__name__: self._insightsErrorHandler,
            InsightsConnectError.__name__: self._insightsErrorHandler,
            "KickstartRegistrationError": self._kickstartRegistrationErrorHandler,
            "SubscriptionTokenTransferError": self._subscriptionTokenTransferErrorHandler,

            # Satellite
            SatelliteProvisioningError.__name__: self._target_satellite_provisioning_error_handler,

            # General installation errors.
            NonCriticalInstallationError.__name__: self._non_critical_error_handler,
        }

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

    def _script_error_handler(self, exn):
        message = _("There was an error running the kickstart script at line "
                    "%(lineno)s.  This is a fatal error and installation will be "
                    "aborted.  The details of this error are:\n\n%(details)s") % \
                   {"lineno": exn.lineno, "details": exn.details}
        self.ui.showError(message)
        return ERROR_RAISE

    def _payload_setup_handler(self, exn):
        message = _("The following error occurred while setting up the payload. "
                    "This is a fatal error and installation will be aborted.")
        message += "\n\n" + str(exn)

        self.ui.showError(message)
        return ERROR_RAISE

    def _payload_install_handler(self, exn):
        message = _("The following error occurred while installing the payload. "
                    "This is a fatal error and installation will be aborted.")
        message += "\n\n" + str(exn)

        self.ui.showError(message)
        return ERROR_RAISE

    def _bootloader_error_handler(self, exn):
        message = _("The following error occurred while installing the boot loader. "
                    "The system will not be bootable. "
                    "Would you like to ignore this and continue with "
                    "installation?")
        message += "\n\n" + str(exn)

        if self.ui.showYesNoQuestion(message):
            return ERROR_CONTINUE
        else:
            return ERROR_RAISE

    def _target_satellite_provisioning_error_handler(self, exn):
        message = _("Failed to provision the target system for Satellite.")
        details = str(exn)

        self.ui.showDetailedError(message, details)
        return ERROR_RAISE

    def _non_critical_error_handler(self, exn):
        message = _("The following error occurred during the installation:"
                    "\n\n{details}\n\nWould you like to ignore this and "
                    "continue with installation?").format(details=str(exn))

        if self.ui.showYesNoQuestion(message):
            return ERROR_CONTINUE
        else:
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

        if exn.__class__.__name__ in self.map:
            rc = self.map[exn.__class__.__name__](exn)

        return rc


# Create a singleton of the ErrorHandler class.  It is up to the UserInterface
# subclass to set errorHandler.ui before this class is ever used, or there will
# be trouble.
errorHandler = ErrorHandler()
