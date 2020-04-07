#
# System purpose library.
#
# Copyright (C) 2020 Red Hat, Inc.
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

import os
import json

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

VALID_FIELDS_FILE_PATH = "/etc/rhsm/syspurpose/valid_fields.json"


def get_valid_fields(valid_fields_file_path=VALID_FIELDS_FILE_PATH):
    """Get valid role, sla and usage fields for system purpose use.

    If no valid fields are provided, the fields file is not found or can not be
    parsed then all three lists will be empty.

    :param str valid_fields_file_path: path to a JSON file holding the valid field listings

    :return: role, sla and usage type lists
    :rtype: [roles], [slas], [usages]
    """
    valid_roles = []
    valid_slas = []
    valid_usage_types = []
    if os.path.exists(valid_fields_file_path):
        try:
            with open(valid_fields_file_path, "rt") as f:
                valid_fields_json = json.load(f)
                valid_roles = valid_fields_json.get("role", [])
                valid_slas = valid_fields_json.get("service_level_agreement", [])
                valid_usage_types = valid_fields_json.get("usage", [])
        except (IOError, json.JSONDecodeError):
            log.exception("parsing of syspurpose valid fields file at %s failed",
                          valid_fields_file_path)
    else:
        log.warning("system purpose valid fields file not found at %s", valid_fields_file_path)
    return valid_roles, valid_slas, valid_usage_types


def _normalize_field(raw_field):
    """Normalize a field for matching.

    Fields specified in free form by users can have different case or trailing white space,
    while still technically being a match on a valid field.

    So convert the field to lower case and strip any trailing white space and return the result.

    :param str raw_field: raw not normalized field
    :return: normalized field suitable for matching
    :rtype: str
    """
    return raw_field.strip().lower()


def _match_field(raw_field, valid_fields):
    """Try to match the field on an item in a list of fields.

    If a match is found return the first matching item from the list.
    If no match is found, return None.

    :param raw_field str: field to match
    :param list valid_fields: list of valid fields to match against
    :return: a matching valid field or None if no match is found
    :rtype: str or None
    """
    matching_valid_field = None
    normalized_field = _normalize_field(raw_field)

    for valid_field in valid_fields:
        if normalized_field == _normalize_field(valid_field):
            # looks like the fields match, no need to search any further
            matching_valid_field = valid_field
            break

    return matching_valid_field


def process_field(syspurpose_value, valid_values, value_name):
    """Process a single system purpose value provided by the user.

    At the moment this value generally comes from kickstart
    as we don't support free form system purpose value entry in the UI.

    We try to match the user provided value to value in a lit of well
    known valid values, so that it can be displayed correct in the UI.

    If the user for example uses "production" for usage, we will match
    it to Production and then display that in the UI.

    If the value does not match any known one, we will just return
    it & display it in its current form.

    :param str syspurpose_value: system purpose value to be processed
    :param valid_values: list of well known valid values for the given
                         type of system purpose value
    :type valid_values: list of str
    :param str value_name: name of the system purpose value to be used
                           in log messages

    :return: matched well known or original value if no match was found
    :rtype: str
    """
    if syspurpose_value:
        value_match = _match_field(syspurpose_value, valid_values)
    else:
        value_match = None

    if value_match:
        log.info("%s system purpose value %s from kickstart matched to known valid field %s",
                 value_name,
                 syspurpose_value,
                 value_match)
        return value_match
    elif syspurpose_value:
        log.info("using custom %s system purpose value from kickstart: %s",
                 value_name,
                 syspurpose_value)
        return syspurpose_value
    else:
        return ""
