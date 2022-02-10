#
# Utility functions for network module
#
# Copyright (C) 2022 Red Hat, Inc.
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

import json

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


def detect_sca_from_registration_data(registration_data_json):
    """Detect SCA/entitlement mode from registration data.

    This function checks JSON data describing registration state as returned
    by the the Register() or RegisterWithActivationKeys() RHSM DBus methods.
    Based on the value of the "contentAccessMode" key present in a dictionary available
    under the "owner" top level key.

    :param str registration_data_json: registration data in JSON format
    :return: True if data inicates SCA enabled, False otherwise
    """
    # we can't try to detect SCA mode if we don't have any registration data
    if not registration_data_json:
        log.warning("no registraton data provided, skipping SCA mode detection attempt")
        return False
    registration_data = json.loads(registration_data_json)
    owner_data = registration_data.get("owner")

    if owner_data:
        content_access_mode = owner_data.get("contentAccessMode")
        if content_access_mode == "org_environment":
            # SCA explicitely noted as enabled
            return True
        elif content_access_mode == "entitlement":
            # SCA explicitely not enabled
            return False
        else:
            log.warning("contentAccessMode mode not set to known value:")
            log.warning(content_access_mode)
            # unknown mode or missing data -> not SCA
            return False
    else:
        # we have no data indicating SCA is enabled
        return False
