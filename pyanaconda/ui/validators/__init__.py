# The base validation class.
#
# Copyright (C) 2016  Red Hat, Inc.
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
# Author(s):  Vendula Poncova <vponcova@redhat.com>
#
import logging

from pyanaconda.i18n import _

log = logging.getLogger("anaconda")

__all__ = ["BaseValidator"]


class BaseValidator(object):
    """Base class for a validation of the configuration.

    Subclasses are expected not to print anything. They should use
    logs or the list of errors. They also should not be interactive
    in any way.

    Expected life cycle:
        should_create()
        __init__
        should_validate()
        setup()
        ready()
        validate()
        errors
    """

    # The title of the validator.
    title = ""
    # A list of validators that should be processed before this one.
    depends_on = list()

    @classmethod
    def should_create(cls, config):
        """Should the validator be created?"""
        return True

    def __init__(self, config):
        """Initialize.

        Set the initial state and initialize only what is necessary
        for should_validate. The rest should be in setup.

        The configuration is accessible only here, therefore
        prepare for the access to the parts that are necessary
        the validation, for example:
            self._data = config.data

        :param config: the configuration of the installation
        :type config: an instance of Configuration
        """
        self._errors = list()

    def should_validate(self):
        """Should the validator set up itself and run the validation?"""
        return True

    def setup(self):
        """Set up the validator.

        The configuration can be modified here, set to the default
        values and partially executed if necessary.

        If there are some new threads created, the setup is not done
        until the validator is not ready.
        """
        pass

    def ready(self):
        """Wait till the validator is ready to validate."""
        return True

    def validate(self):
        """Validate the configuration.

        This method should not be overridden. The validation
        logic should be implemented in methods _is_mandatory,
        _is_valid and _get_validation_error.
        """
        # Is the validation mandatory?
        if not self._is_mandatory():
            log.debug("%s is not mandatory.", self.title)
            return True

        # Are there some setup errors?
        if self.errors:
            log.error("%s has some setup errors: %s", self.title, self._errors)
            return False

        # Is the configuration valid?
        if not self._is_valid():
            self._report_error(self._get_validation_error())
            log.error("%s has some validation errors: %s", self.title, self._errors)
            return False

        # Success!
        log.debug("%s is valid.", self.title)
        return True

    def _is_mandatory(self):
        """Is the validation mandatory?."""
        return True

    def _is_valid(self):
        """Is the configuration valid?"""
        return True

    def _report_error(self, error):
        """Append an error to the error list."""
        self._errors.append(error)

    def _get_validation_error(self):
        """Return the validation error message.

        The message is used to report an error
        if there is a validation error detected.
        """
        return _("Validation has failed.")

    @property
    def errors(self):
        """Return all error messages."""
        return self._errors
