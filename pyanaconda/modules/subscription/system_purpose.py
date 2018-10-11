#
# System purpose module.
#
# Copyright (C) 2018 Red Hat, Inc.
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

from pyanaconda.core import util
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
            log.exception("parsing of syspurpose valid fields file at %s failed", valid_fields_file_path)
    else:
        log.warning("system purpose valid fields file not found at %s", valid_fields_file_path)
    return valid_roles, valid_slas, valid_usage_types


def normalize_field(raw_field):
    """Normalize a field for matching.

    Fields specified in free form by users can have different case or trailing white space,
    while still technically being a match on a valid field.

    So convert the field to lower case and strip any trailing white space and return the result.

    :param str raw_field: raw not normalized field
    :return: normalized field suitable for matching
    :rtype: str
    """
    return raw_field.strip().lower()


def match_field(raw_field, valid_fields):
    """Try to match the field on an item in a list of fields.

    If a match is found return the first matching item from the list.

    :param raw_field str: field to match
    :param list valid_fields: list of valid fields to match against
    """
    matching_valid_field = None
    normalized_field = normalize_field(raw_field)

    for valid_field in valid_fields:
        if normalized_field == normalize_field(valid_field):
            # looks like the fields match, no need to search
            # any further
            matching_valid_field = valid_field
            break

    return matching_valid_field

def give_the_system_purpose(sysroot, role, sla, usage, addons):
    """Set system purpose for the installed system by calling the syspurpose tool.

    The tool is called in the installed system chroot, so this method can be only
    called once the system rootfs content is in place.

    :param role: role of the system
    :type role: str or None
    :param sla: Service Level Agreement for the system
    :type sla: str or None
    :param usage: intended usage of the system
    :type usage: str or None
    :param list addons: any additional layered products or features
    """
    if role or sla or usage or addons:
        syspurpose_sysroot_path = os.path.join(sysroot, "usr/sbin/syspurpose")
        if os.path.exists(syspurpose_sysroot_path):
            # The syspurpose utility can only set one value at a time,
            # so we might need to call it multiple times to set all the
            # requested values.
            #
            # Also as the values can contain white space ween need to make sure the
            # values passed to arguments are all properly quoted.
            if role:
                args = ["set-role", '{}'.format(role)]
                util.execInSysroot("syspurpose", args)

            if sla:
                args = ["set-sla", '{}'.format(sla)]
                util.execInSysroot("syspurpose", args)

            if usage:
                args = ["set-usage", '{}'.format(usage)]
                util.execInSysroot("syspurpose", args)

            if addons:
                args = ["add", 'addons']
                for addon in addons:
                    args.append('{}'.format(addon))
                util.execInSysroot("syspurpose", args)
        else:
            log.error("the syspurpose tool is missing, cannot set system purpose")
    else:
        log.warning("not calling syspurpose as no fields have been provided")
