# The class for software validation.
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

from pyanaconda.constants import THREAD_PAYLOAD,THREAD_CHECK_SOFTWARE,THREAD_SOFTWARE_WATCHER
from pyanaconda.flags import flags
from pyanaconda.i18n import N_, _
from pyanaconda.packaging import DependencyError, PackagePayload, payloadMgr, NoSuchGroup
from pyanaconda.threads import threadMgr, AnacondaThread
from pyanaconda.ui.validators import BaseValidator
from pyanaconda.ui.validators.source import SourceValidator

log = logging.getLogger("anaconda")

__all__ = ["SoftwareValidator"]


class SoftwareValidator(BaseValidator):
    """A class to check the software."""

    title = N_("Software validation")
    depends_on = [SourceValidator]

    def __init__(self, config):
        super(SoftwareValidator, self).__init__(config)
        self._data = config.data
        self._payload = config.payload

        # dnf tx id
        self._tx_id = None

        # Are we taking values (package list) from a ks file?
        self._kickstarted = flags.automatedInstall and self._data.packages.seen

        # error flags
        self._payload_error = False
        self._check_error = False

    def should_validate(self):
        return isinstance(self._payload, PackagePayload)

    def setup(self):
        """Set up the validator."""
        # Register event listeners to update our status on payload events.
        payloadMgr.addListener(payloadMgr.STATE_ERROR, self._payload_error_occurred)

        # Start a thread to wait for the payload and run the first, automatic
        # dependency check.
        threadMgr.add(AnacondaThread(name=THREAD_SOFTWARE_WATCHER,
                                     target=self._software_initialize))

    def ready(self):
        """Are we ready to validate?"""
        return (not threadMgr.get(THREAD_PAYLOAD) and
                not threadMgr.get(THREAD_CHECK_SOFTWARE) and
                not threadMgr.get(THREAD_SOFTWARE_WATCHER))

    def _is_valid(self):
        """Is the configuration valid?

        Make sure our threads are done running and vars are set.

        WARNING: This can be called before the spoke is finished initializing
        if the spoke starts a thread. It should make sure it doesn't access
        things until they are completely setup.
        """
        # is the processing done?
        if self.ready() and not self.errors and self._is_txid_valid():

            # is the environment selected automatically?
            if flags.automatedInstall or self._kickstarted:
                return self._payload.baseRepo and self._data.packages.seen
            else:
                return self._payload.baseRepo and self._data.packages.environment is not None

        return False

    def _get_validation_error(self):
        """Return the validation error message."""
        if self._payload_error:
            return _("Error setting up software source.")

        elif not self._payload.baseRepo:
            return _("The installation source is not set up.")

        elif not self._is_txid_valid():
            return _("The installation source has changed.")

        elif self._check_error:
            return _("Software selection check has failed.")

        else:
            return _("No software was selected.")

    def _payload_error_occurred(self):
        """Process the payloadMgr.STATE_ERROR event."""
        self._payload_error = True
        self._report_error(payloadMgr.error)

    def _software_initialize(self):
        """Software initialize."""
        threadMgr.wait(THREAD_PAYLOAD)

        # Select the default environment and addons.
        if not self._kickstarted:
            environment, addons = self._get_default_software()

            # Set the software.
            if environment:
                self._set_software(environment, addons)
            # Skip the check.
            else:
                return

        # Check the software selection.
        threadMgr.add(AnacondaThread(name=THREAD_CHECK_SOFTWARE,
                                     target=self._check_software_selection))

    def _get_default_software(self):
        """Returns the default software.

        :return: the environment, set of addons
        """
        # Initialize.
        environment = None
        addons = set()

        # Select the environment and addons.
        # If an environment was specified in the instclass, use that.
        # Otherwise, select the first environment.
        if self._payload.environments:

            environments = self._payload.environments
            instclass = self._payload.instclass

            # Select the default environment.
            if instclass and instclass.defaultPackageEnvironment and \
                            instclass.defaultPackageEnvironment in environments:
                environment = instclass.defaultPackageEnvironment

            # Or select the first one.
            elif len(environments) > 0:
                environment = environments[0]

        return environment, addons

    def _set_software(self, environment, addons):
        """Set the selected software.

        :param environment: the selected environment
        :param addons: the set of  selected addons
        """
        # init packages
        self._payload.data.packages.packageList = []
        self._data.packages.groupList = []

        # select the environment
        self._payload.selectEnvironment(environment)

        # select the addons
        environment_id = self._get_environment_id(environment)
        available_addons = self._get_available_addons(environment_id)

        for addon_id in available_addons:
            if addon_id in addons:
                self._payload.selectGroup(addon_id)

    def _get_environment_id(self, environment):
        """Return the id of the selected environment or None."""
        if environment is None:
            return None
        try:
            return self._payload.environmentId(environment)
        except NoSuchGroup:
            return None

    def _get_available_addons(self, environment_id):
        """Return all add-ons of the specific environment."""
        addons = []

        if environment_id in self._payload.environmentAddons:
            for addons_list in self._payload.environmentAddons[environment_id]:
                addons.extend(addons_list)

        return addons

    def _get_selected_addons(self):
        """Return selected add-ons."""
        return {group.name for group in self._payload.data.packages.groupList}

    def _check_software_selection(self):
        """Depsolving."""
        try:
            self._payload.checkSoftwareSelection()
        except DependencyError as e:
            self._tx_id = None
            self._check_error = True
            self._report_error(str(e))
        else:
            self._tx_id = self._payload.txID

    def _is_txid_valid(self):
        """Whether we have a valid dnf tx id."""
        return self._tx_id == self._payload.txID
